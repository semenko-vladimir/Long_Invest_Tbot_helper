from itertools import count

from app.client.log.logger import setup_logger


logger = setup_logger(__name__)
monitoring_scheduler = None


def configure_monitoring_scheduler():
    """Start read-only polling; disabled subscriptions do no network work."""
    global monitoring_scheduler
    from apscheduler.schedulers.background import BackgroundScheduler

    from app.client.bot.bot import bot
    from app.client.config.users import load_runtime_users_config
    from app.services.monitoring import MonitoringRunner
    from app.services.news_analysis import ModelNewsPrefilter
    from app.services.news_article_text import fetch_article_text
    from app.services.news_queue import NewsQueue
    from app.services.news_llm_config import NewsLLMConfig
    from app.services.ollama_news_analysis import OllamaNewsAnalyzer
    from app.services.user_context import UserContext
    from app.client.handlers.monitoring_handler import send_cached_chart

    if monitoring_scheduler is not None:
        monitoring_scheduler.shutdown(wait=False)
    scheduler = BackgroundScheduler(timezone="Europe/Moscow")
    llm_config = NewsLLMConfig.from_env()
    news_workers = []
    for config in load_runtime_users_config().enabled_users:
        user = UserContext.from_config(config)
        runner = MonitoringRunner(
            user,
            send_text=lambda chat_id, message: bot.send_message(chat_id, message, disable_web_page_preview=True),
            send_chart=send_cached_chart,
        )
        scheduler.add_job(runner.run, "interval", minutes=5, id=f"monitoring_{user.user_id}",
                          replace_existing=True, max_instances=1, coalesce=True)
        if llm_config.enabled:
            runner.news_queue = NewsQueue(
                runner.session_factory, user,
                prefilter=ModelNewsPrefilter(),
                analyzer=OllamaNewsAnalyzer(llm_config, runner.session_factory, user),
                analyzer_version=llm_config.analyzer_version,
                article_fetcher=fetch_article_text,
            )
        news_workers.append(runner.news_queue)
    if news_workers:
        turns = count()

        def process_next_news_queue():
            news_workers[next(turns) % len(news_workers)].process_pending(limit=1 if llm_config.enabled else 10)

        scheduler.add_job(process_next_news_queue, "interval", seconds=30, id="news_worker",
                          replace_existing=True, max_instances=1, coalesce=True)
    scheduler.start()
    monitoring_scheduler = scheduler
    logger.info("Read-only monitoring scheduler started for %d users", len(load_runtime_users_config().enabled_users))
