"""Independent read-only price polling, hourly intake and daily market drafts."""

import json
from datetime import datetime, timezone
from itertools import count
from zoneinfo import ZoneInfo

from app.client.log.logger import setup_logger

logger = setup_logger(__name__)
monitoring_scheduler = None
MOSCOW = ZoneInfo("Europe/Moscow")


def configure_monitoring_scheduler():
    global monitoring_scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from app.client.bot.bot import bot
    from app.client.config.users import load_runtime_users_config
    from app.client.handlers.monitoring_handler import send_cached_chart, send_digest_album
    from app.backend.models.monitoring import MarketReport
    from app.services.article_news_analysis import OllamaArticleAnalyzer, RuleArticleAnalyzer, DirectNewsPrefilter
    from app.services.market_news_queue import MarketNewsQueue
    from app.services.market_dividends import MarketDividendContext
    from app.services.market_screening import MarketDataRefreshRunner, MarketScreeningService, MarketCandidate, OllamaMarketSelector
    from app.services.monitoring import MonitoringRunner
    from app.services.news_article_text import fetch_article_text
    from app.services.news_llm_config import NewsLLMConfig
    from app.services.news_queue import NewsQueue
    from app.services.ollama_news_analysis import OllamaNewsAnalyzer
    from app.services.user_context import UserContext

    if monitoring_scheduler is not None:
        monitoring_scheduler.shutdown(wait=False)
    scheduler = BackgroundScheduler(timezone="Europe/Moscow")
    llm_config = NewsLLMConfig.from_env()
    runtimes = []
    for config in load_runtime_users_config().enabled_users:
        user = UserContext.from_config(config)
        runner = MonitoringRunner(user,
            send_text=lambda chat_id, message: bot.send_message(chat_id, message, disable_web_page_preview=True),
            send_chart=send_cached_chart, send_album=send_digest_album)
        account_queue = None
        if llm_config.enabled:
            account_queue = NewsQueue(runner.session_factory, user, prefilter=DirectNewsPrefilter(),
                analyzer=OllamaNewsAnalyzer(llm_config, runner.session_factory, user),
                analyzer_version=llm_config.analyzer_version, article_fetcher=fetch_article_text, publish_events=False)
        analyzer = OllamaArticleAnalyzer(llm_config) if llm_config.enabled else RuleArticleAnalyzer()
        queue = MarketNewsQueue(runner.session_factory, user, analyzer=analyzer, account_queue=account_queue)
        refresh = MarketDataRefreshRunner(runner.session_factory, user)
        screening = MarketScreeningService(runner.session_factory, corporate_context=MarketDividendContext(runner.session_factory, user))
        selector = OllamaMarketSelector(llm_config) if llm_config.enabled else None

        def intake(runner=runner, queue=queue):
            settings = runner.settings_service.get()
            if not (settings.alerts_enabled or settings.digest_enabled):
                return
            try:
                interests, names, accounts = runner._interests()
            except Exception:
                interests, names, accounts = {}, {}, ()
                logger.warning("Hourly intake account context unavailable user_id=%s", runner.user.user_id)
            queue.intake(names=names, accounts_by_ticker=interests, accounts=accounts)

        def prepare(runner=runner, screening=screening, selector=selector):
            if not runner.settings_service.get().digest_enabled:
                return
            now = datetime.now(timezone.utc)
            try:
                interests, _, _ = runner._interests()
            except Exception:
                from app.services.daily_digest import owned_interest
                interests = owned_interest(runner.session_factory, now)[0]
            day = now.astimezone(MOSCOW).date()
            candidates = screening.prepare(day, owned_tickers=interests, now=now)
            if selector and candidates:
                with runner.session_factory() as db:
                    db.get(MarketReport, day.isoformat()).selection_status = "pending_model"
                    db.commit()

        def bootstrap(refresh=refresh, prepare=prepare):
            refresh.run()
            prepare()

        def digest(runner=runner):
            settings = runner.settings_service.get()
            if settings.digest_enabled:
                runner._send_digest_if_due(settings, (), datetime.now(timezone.utc), ())

        scheduler.add_job(lambda runner=runner: runner.run(include_news=False), "interval", minutes=5,
            id=f"monitoring_{user.user_id}", replace_existing=True, max_instances=1, coalesce=True)
        scheduler.add_job(digest, "cron", minute="*", second=0, id=f"digest_delivery_{user.user_id}",
            replace_existing=True, max_instances=1, coalesce=True, misfire_grace_time=60)
        scheduler.add_job(intake, "cron", minute=0, id=f"news_intake_{user.user_id}",
            replace_existing=True, max_instances=1, coalesce=True, misfire_grace_time=3600)
        scheduler.add_job(intake, "date", run_date=datetime.now(timezone.utc), id=f"news_startup_{user.user_id}")
        scheduler.add_job(refresh.run, "cron", hour=2, minute=0, id=f"market_history_{user.user_id}",
            replace_existing=True, max_instances=1, coalesce=True, misfire_grace_time=21600)
        scheduler.add_job(prepare, "cron", hour=8, minute=0, id=f"market_prepare_{user.user_id}",
            replace_existing=True, max_instances=1, coalesce=True, misfire_grace_time=3600)
        scheduler.add_job(bootstrap, "date", run_date=datetime.now(timezone.utc), id=f"market_startup_{user.user_id}")
        runtimes.append((runner, queue, selector))

    if runtimes:
        turns = count()

        def process_next():
            runner, queue, selector = runtimes[next(turns) % len(runtimes)]
            day = datetime.now(timezone.utc).astimezone(MOSCOW).date().isoformat()
            with runner.session_factory() as db:
                report = db.get(MarketReport, day)
                candidates = [MarketCandidate(**value) for value in json.loads(report.candidates_json)] if report and report.selection_status == "pending_model" else []
            news = queue.cached_assessments(datetime.now(timezone.utc)) if candidates else []
            if candidates and selector and runner.settings_service.get().digest_enabled:
                status, selected = "model", None
                try:
                    selected = selector.select(candidates, news)
                except Exception:
                    status = "unavailable"
                    logger.warning("Market selection unavailable user_id=%s; keeping algorithmic draft", runner.user.user_id)
                with runner.session_factory() as db:
                    report = db.get(MarketReport, day)
                    if selected:
                        from dataclasses import asdict
                        report.selected_json = json.dumps([asdict(value) for value in selected], ensure_ascii=False)
                    report.selection_status = status
                    db.commit()
                return
            if not queue.process_account_pending():
                queue.process_pending(limit=1 if llm_config.enabled else 10)

        scheduler.add_job(process_next, "interval", seconds=30, id="news_worker",
            replace_existing=True, max_instances=1, coalesce=True)
    scheduler.start()
    monitoring_scheduler = scheduler
    logger.info("Read-only monitoring scheduler started for %d users", len(runtimes))
