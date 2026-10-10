import json
import unittest
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.backend.models.database import Base
from app.backend.models.accounts import BrokerConnection, InvestmentAccount, PortfolioSnapshot, PositionSnapshot
from app.backend.models.trading import Instrument
from app.backend.models.monitoring import (
    ArticleAnalysisJob, DigestDelivery, MarketRefreshState, MarketReport, MonitoringEvent,
    NewsAnalysisJob, NewsArticle, NewsSourceState,
)
from app.charts.images import ChartImageService
from app.charts.repository import PriceCandleRepository
from app.charts.schemas import PriceCandle
from app.services.article_news_analysis import ArticleAssessment, DirectNewsPrefilter, OllamaArticleAnalyzer, market_catalog, matched_tickers
from app.services.daily_digest import DigestChart, DigestDraft, DigestDeliveryService, DigestService, owned_interest
from app.services.local_inference import NewsAnalysisUnavailable
from app.services.market_news_queue import MarketNewsQueue
from app.services.market_screening import MarketScreeningService, OllamaMarketSelector, rank_candidate
from app.services.market_screening import fetch_equity_universe
from app.services.market_dividends import dividend_note
from app.integrations.moex_iss import MOEXISSClient
from app.services.media_news_sources import NewsFetchResult, fetch_news_source
from app.services.monitoring import MonitoringRunner
from app.services.monitoring_config import MonitoringLimits
from app.services.monitoring_settings import MonitoringSettingsService
from app.services.news_analysis import NewsAssessment
from app.services.news_article_text import ArticleDocument, fetch_article_document
from app.services.news_llm_config import NewsLLMConfig
from app.services.news_queue import NewsQueue
from app.services.news_sources import NewsItem
from app.services.news_urls import canonical_news_url, fetch_public_html
from app.services.user_context import UserContext


NOW = datetime(2026, 10, 3, 6, tzinfo=timezone.utc)


def history(change=1.5, volume=3000, turnover=20_000_000):
    bars = []
    for i in range(31):
        close = 100 if i < 30 else 100 * (1 + change / 100)
        width = 1 if i < 20 else 0.1 if i < 30 else 1
        bars.append(PriceCandle(datetime(2026, 9, 2) + timedelta(days=i), close, close + width, close - width,
                               close, 1000 if i < 30 else volume, turnover))
    return bars


class Response:
    def __init__(self, value=None, *, body=b"", status=200, headers=None):
        self.value, self.body, self.status_code = value, body, status
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.encoding, self.closed = "utf-8", False
    def raise_for_status(self):
        if self.status_code >= 400:
            raise ValueError("HTTP error")
    def json(self):
        return self.value
    def iter_content(self, size):
        yield self.body
    def close(self):
        self.closed = True


class Session:
    def __init__(self, response):
        self.response, self.calls, self.trust_env = response, [], True
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class MediaAdapterTests(unittest.TestCase):
    def test_invalid_structured_date_cannot_make_news_fresh_or_coverage_complete(self):
        html = '<script type="application/ld+json">' + json.dumps({"@type": "NewsArticle",
            "url": "https://www.interfax.ru/business/1", "headline": "Банк России изменил ставку",
            "datePublished": "unknown"}) + '</script>'
        result = fetch_news_source("interfax", feed_fetcher=lambda _: [], page_fetcher=lambda *_: html, since=NOW, now=NOW)
        self.assertFalse(result.coverage_complete)
        self.assertFalse(result.items[0].publication_time_known)

    def test_interfax_time_is_moscow_and_lazy_pagination_is_reported(self):
        html = '<time datetime="2026-10-03T08:00">08:00</time><a href="/business/1">Банк России сообщил об инфляции</a>'
        html += '<div onclick="getMoreTimeline()">Загрузить еще</div>'
        result = fetch_news_source("interfax", feed_fetcher=lambda _: [], page_fetcher=lambda *_: html, now=NOW)
        self.assertTrue(result.items[0].publication_time_known)
        self.assertEqual(result.items[0].published_at.hour, 5)
        self.assertFalse(result.coverage_complete)

    def test_rbc_public_cards_include_short_news_and_publication_time(self):
        html = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps({"props": {"pageProps": {"materials": {
            "moreExists": True, "items": [{"url": "https://www.rbc.ru/rbcfreenews/abcdef", "title": "Газпром сообщил о запасах газа",
            "publishDate": "Sat, 03 Oct 2026 08:00:00 +0300", "rubric": {"nick": "economics"}}]}}}}) + '</script>'
        result = fetch_news_source("rbc", feed_fetcher=lambda _: [], page_fetcher=lambda *_: html, since=NOW, now=NOW)
        self.assertEqual(len(result.items), 1)
        self.assertTrue(result.items[0].publication_time_known)
        self.assertEqual(result.items[0].published_at.hour, 5)
        self.assertIn("economics", result.items[0].categories)

    def test_kommersant_dated_card_does_not_adopt_sidebar_links(self):
        html = '<article data-article-url="https://www.kommersant.ru/doc/1" data-article-title="Банк России снизил ставку" data-article-rubric-ids="3">'
        html += '<p>03.10.2026, 08:00</p><a href="/doc/1">Банк России снизил ставку</a></article><a href="/doc/2">Спортивная новость со страницы</a>'
        result = fetch_news_source("kommersant", feed_fetcher=lambda _: [], page_fetcher=lambda *_: html, now=NOW)
        self.assertEqual(len(result.items), 1)
        self.assertTrue(result.items[0].publication_time_known)
        self.assertEqual(result.items[0].published_at.hour, 5)

    def test_section_budget_is_total_per_source(self):
        calls = []
        def page(url, _):
            calls.append(url)
            return '<link rel="next" href="?page=' + str(len(calls)) + '"><a href="/economics/03/10/2026/abcdef">Экономическая новость</a>'
        result = fetch_news_source("rbc", feed_fetcher=lambda _: [], page_fetcher=page, max_pages=5, now=NOW)
        self.assertEqual(len(calls), 5)
        self.assertFalse(result.coverage_complete)

    def test_section_finds_article_missing_from_short_feed_and_follows_next(self):
        visited = []
        def page(url, hosts):
            visited.append(url)
            number = "10" if "pg=" not in url else "11"
            next_page = '<link rel="next" href="?pg=1">' if number == "10" else ""
            return next_page + '<script type="application/ld+json">' + json.dumps({
                "@type": "NewsArticle", "url": "https://www.interfax.ru/business/" + number,
                "headline": "Ставка и экономика России", "datePublished": "2026-10-03T08:00:00+03:00"}) + '</script>'
        result = fetch_news_source("interfax", feed_fetcher=lambda _: [], page_fetcher=page, now=NOW)
        self.assertEqual({item.url for item in result.items}, {"https://www.interfax.ru/business/10", "https://www.interfax.ru/business/11"})
        self.assertEqual(len(visited), 2)

    def test_undated_section_does_not_claim_complete_coverage(self):
        result = fetch_news_source("interfax", feed_fetcher=lambda _: [], now=NOW,
            page_fetcher=lambda *_: '<a href="/business/12">Ключевая ставка изменена</a>')
        self.assertFalse(result.coverage_complete)
        self.assertFalse(result.items[0].publication_time_known)

    def test_rss_survives_a_section_failure(self):
        item = NewsItem("interfax", "Ключевая ставка", "https://www.interfax.ru/business/1", NOW)
        result = fetch_news_source("interfax", feed_fetcher=lambda _: [item], now=NOW,
            page_fetcher=Mock(side_effect=TimeoutError()))
        self.assertEqual(result.items, (item,))
        self.assertFalse(result.coverage_complete)
        self.assertTrue(result.errors)

    @patch("app.services.news_urls._public_host", return_value=True)
    def test_three_article_formats_strip_navigation_and_extract_date(self, _):
        cases = (
            ("rbc", "https://www.rbc.ru/economics/03/10/2026/abcdef", '<meta itemprop="articleBody" content="Инфляция снизилась.">'),
            ("interfax", "https://www.interfax.ru/business/1", '<article itemprop="articleBody"><p>Инфляция снизилась.</p><aside>Реклама</aside></article>'),
            ("kommersant", "https://www.kommersant.ru/doc/1", '<div class="article_text_wrapper"><p class="doc__text">Инфляция снизилась.</p><script>Реклама</script></div>'),
        )
        for source, url, body in cases:
            with self.subTest(source=source):
                html = '<nav>Меню</nav><meta property="article:published_time" content="2026-10-03T08:00:00+03:00">' + body
                doc = fetch_article_document(NewsItem(source, "Заголовок", url, NOW), session=Session(Response(body=html.encode())))
                self.assertEqual(doc.text, "Инфляция снизилась.")
                self.assertEqual(doc.published_at.hour, 5)

    @patch("app.services.news_urls._public_host", return_value=True)
    def test_redirect_cannot_escape_site_allowlist(self, _):
        session = Session(Response(status=302, headers={"Location": "https://evil.test/page"}))
        with self.assertRaises(ValueError):
            fetch_public_html("https://www.interfax.ru/business/", {"www.interfax.ru"}, session=session)
        self.assertEqual(len(session.calls), 1)
        self.assertFalse(session.calls[0][1]["allow_redirects"])

    def test_url_identity_preserves_meaningful_parameters(self):
        self.assertEqual(canonical_news_url("https://www.rbc.ru/x?from=newsfeed&utm_source=t#top"), "https://www.rbc.ru/x")
        self.assertIn("file=report.htm", canonical_news_url("https://www.cbr.ru/press/PR/?file=report.htm&utm_source=t"))


class ModelValidationTests(unittest.TestCase):
    def test_exchange_listing_boilerplate_is_not_a_direct_moex_position_match(self):
        catalog = {"MOEX": "Московская Биржа", "SBER": "Сбербанк"}
        item = NewsItem("moex_listing", "О регистрации облигаций", "https://www.moex.com/n1", NOW,
            "В соответствии с Правилами листинга ПАО Московская Биржа зарегистрированы облигации Сбербанка.")
        self.assertEqual(matched_tickers(item, catalog), ("SBER",))
        self.assertEqual(matched_tickers(replace(item, title="Московская биржа опубликовала отчётность"), catalog), ("MOEX", "SBER"))

    def test_full_issuer_name_excludes_short_parent_brand_and_keeps_share_classes(self):
        catalog = market_catalog({
            "FEES": {"name": '"ФСК - Россети" ПАО', "short_name": "Россети"},
            "MRKZ": {"name": "ПАО Россети Северо-Запад ао", "short_name": "РСетиСЗ ао"},
            "SBER": {"name": "Сбербанк России ПАО ао", "short_name": "Сбербанк"},
            "SBERP": {"name": "Сбербанк России ПАО ап", "short_name": "Сбербанк-п"},
        }, {"SBER": ""})
        item = NewsItem("moex_listing", "Россети Северо-Запад: дивиденды", "https://www.moex.com/n1", NOW)
        self.assertEqual(matched_tickers(item, catalog), ("MRKZ",))
        self.assertEqual(matched_tickers(replace(item, title="Сбербанк России объявил дивиденды"), catalog), ("SBER", "SBERP"))
        self.assertEqual(matched_tickers(replace(item, title="FEES и Россети Северо-Запад"), catalog), ("FEES", "MRKZ"))

    def test_confidence_json_is_not_a_prose_limitation(self):
        analyzer, item, _ = self.model({"uncertainty": '{"confidence": "high", "scope": "article"}'})
        with self.assertRaises(NewsAnalysisUnavailable):
            analyzer.assess_article(item, {"SBER": "Сбербанк"})

    def test_issuer_homonyms_do_not_match_an_aircraft_or_a_generic_system(self):
        catalog = {"SMLT": "Самолет ао", "AFKS": "Система ао"}
        item = NewsItem("rbc", "Самолет Boeing и система управления", "https://www.rbc.ru/x", NOW)
        self.assertEqual(matched_tickers(item, catalog), ())
        self.assertEqual(matched_tickers(replace(item, title='Группа «Самолет» опубликовала отчётность'), catalog), ("SMLT",))

    def test_numbers_written_as_russian_words_are_equivalent(self):
        analyzer, item, _ = self.model({"summary": "Прибыль Сбербанка выросла в 4 раза."})
        result = analyzer.assess_article(replace(item, summary="Прибыль Сбербанка выросла в четыре раза."), {"SBER": "Сбербанк"})
        self.assertEqual(result.importance, 85)

    def test_cited_numbers_do_not_borrow_from_other_evidence(self):
        analyzer, item, _ = self.model({"evidence_ids": ["headline"]})
        with self.assertRaises(NewsAnalysisUnavailable):
            analyzer.assess_article(item, {"SBER": "Сбербанк"})

    def model(self, overrides=None):
        value = {"relevant": True, "importance": 85, "summary": "Прибыль Сбербанка выросла на 10%.",
            "topic": "company", "tickers": ["SBER"], "reason": "Существенное изменение прибыли эмитента.",
            "evidence_ids": ["summary"], "uncertainty": "Влияние на рыночную цену не установлено."}
        value.update(overrides or {})
        session = Session(Response({"done": True, "message": {"content": json.dumps(value)}}))
        analyzer = OllamaArticleAnalyzer(NewsLLMConfig(enabled=True), http_session=session)
        item = NewsItem("rbc", "Прибыль Сбербанка", "https://www.rbc.ru/x", NOW, "Прибыль Сбербанка выросла на 10%.")
        return analyzer, item, session

    def test_source_grounded_assessment_has_no_account_profile(self):
        analyzer, item, session = self.model()
        result = analyzer.assess_article(item, {"SBER": "Сбербанк"})
        self.assertEqual(result.importance, 85)
        request = session.calls[0][1]["json"]
        payload = json.loads(request["messages"][1]["content"])
        self.assertNotIn("investment_account", payload)
        self.assertEqual(request["options"]["num_predict"], 768)
        self.assertFalse(session.trust_env)
        self.assertEqual(request["format"]["properties"]["tickers"]["items"]["enum"], ["SBER"])
        self.assertIn("summary", request["format"]["properties"]["evidence_ids"]["items"]["enum"])

    def test_rejects_unknown_facts_instruments_numbers_and_directives(self):
        for change in ({"evidence_ids": ["invented"]}, {"tickers": ["GAZP"]},
                       {"summary": "Прибыль выросла на 99%."}, {"reason": "true"},
                       {"reason": "Купите акции Сбербанка."}, {"reason": "Рекомендую покупать акции."}):
            with self.subTest(change=change):
                analyzer, item, _ = self.model(change)
                with self.assertRaises(NewsAnalysisUnavailable):
                    analyzer.assess_article(item, {"SBER": "Сбербанк"})

    def test_headline_cannot_trigger_urgent_assessment(self):
        analyzer, item, _ = self.model()
        with self.assertRaises(NewsAnalysisUnavailable):
            analyzer.assess_article(replace(item, summary=""), {"SBER": "Сбербанк"})


class DatabaseCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.user = UserContext("u", "User", 123, 0.3, "unused")
        MonitoringSettingsService(self.factory, self.user).update(alerts_enabled=True, digest_enabled=True)
    def tearDown(self):
        self.engine.dispose()
    def seed_accounts(self):
        with self.factory() as db:
            connection = BrokerConnection(provider_key="t-invest", connection_key="default", display_name="T-Invest")
            db.add(connection)
            db.flush()
            for number in (1, 2):
                account = InvestmentAccount(broker_connection_id=connection.id, external_account_id=str(number),
                    display_name=f"Счёт {number}", status="open", enabled=True)
                db.add(account)
                db.flush()
                snapshot = PortfolioSnapshot(investment_account_id=account.id, captured_at=NOW.replace(tzinfo=None), total_value=1000, source="test")
                db.add(snapshot)
                db.flush()
                db.add(PositionSnapshot(investment_account_id=account.id, portfolio_snapshot_id=snapshot.id, ticker="SBER", quantity=10))
            db.commit()
        with self.factory() as db:
            queue = NewsQueue(self.factory, self.user)
            return tuple(queue._account_context(db, row.id) for row in db.query(InvestmentAccount).order_by(InvestmentAccount.id))


class MarketQueueTests(DatabaseCase):
    def test_removed_source_is_not_analyzed_by_account_worker(self):
        self.seed_accounts()
        analyzer = Mock()
        account_queue = NewsQueue(self.factory, self.user, analyzer=analyzer)
        queue = self.queue(account_queue=account_queue)
        queue.enqueue(self.item(), NOW)
        queue.process_pending(NOW)
        MonitoringSettingsService(self.factory, self.user).update(sources=("moex_main",))
        self.assertEqual(queue.process_account_pending(NOW), 0)
        analyzer.assess.assert_not_called()
        with self.factory() as db:
            self.assertEqual(db.query(NewsAnalysisJob).filter_by(status="pending").count(), 0)

    def test_existing_account_followup_gets_capacity_before_new_shared_work(self):
        self.seed_accounts()
        queue = self.queue(limits=replace(MonitoringLimits(), pending_jobs=1))
        queue.enqueue(self.item(), NOW)
        queue.enqueue(replace(self.item(), url="https://www.rbc.ru/deferred"), NOW)
        queue.process_pending(NOW)
        queue.account_queue = NewsQueue(self.factory, self.user)
        queue.process_pending(NOW, limit=0)
        with self.factory() as db:
            self.assertEqual(db.query(NewsAnalysisJob).filter_by(status="pending").count(), 1)
            self.assertEqual(db.query(ArticleAnalysisJob).filter_by(status="pending").count(), 0)

    def test_deferred_owned_news_has_priority_over_more_recent_general_news(self):
        self.seed_accounts()
        queue = self.queue(limits=replace(MonitoringLimits(), pending_jobs=1))
        general = replace(self.item(), title="ВВП России увеличился", summary="Экономика выросла.", url="https://www.rbc.ru/first")
        owned = replace(self.item(), url="https://www.rbc.ru/owned")
        recent = replace(general, url="https://www.rbc.ru/recent", published_at=NOW + timedelta(minutes=5))
        for item in (general, owned, recent):
            queue.enqueue(item, NOW)
        queue.process_pending(NOW)
        queue.process_pending(NOW, limit=0)
        with self.factory() as db:
            pending = db.query(ArticleAnalysisJob).filter_by(status="pending").one()
            self.assertEqual(db.get(NewsArticle, pending.article_id).url, owned.url)

    def test_changed_article_removes_unconfirmed_urgent_event_until_reanalysis(self):
        queue = self.queue()
        item = self.item()
        queue.enqueue(item, NOW)
        queue.process_pending(NOW)
        with self.factory() as db:
            self.assertEqual(db.query(MonitoringEvent).count(), 1)
        queue.enqueue(replace(item, summary="Прибыль выросла на 11%."), NOW)
        with self.factory() as db:
            self.assertEqual(db.query(MonitoringEvent).count(), 0)
        self.assertEqual(queue.cached_assessments(NOW), [])

    def test_selection_news_requires_current_content_source_and_recent_publication(self):
        queue = self.queue()
        queue.enqueue(self.item(), NOW)
        queue.process_pending(NOW)
        self.assertEqual(len(queue.cached_assessments(NOW)), 1)
        self.assertEqual(queue.cached_assessments(NOW + timedelta(days=3)), [])
        MonitoringSettingsService(self.factory, self.user).update(sources=("moex_main",))
        self.assertEqual(queue.cached_assessments(NOW), [])

    def test_pending_old_analyzer_does_not_block_new_version_at_capacity(self):
        queue = self.queue(limits=replace(MonitoringLimits(), pending_jobs=1))
        queue.enqueue(self.item(), NOW)
        with self.factory() as db:
            db.query(ArticleAnalysisJob).one().analyzer_version = "retired-model"
            db.commit()
        queue.process_pending(NOW, limit=0)
        with self.factory() as db:
            self.assertEqual(db.query(ArticleAnalysisJob).filter_by(analyzer_version="retired-model").one().status, "superseded")
            self.assertEqual(db.query(ArticleAnalysisJob).filter_by(analyzer_version=queue.analyzer.version).one().status, "pending")

    def test_removed_source_releases_capacity_and_can_resume_when_added(self):
        queue = self.queue()
        item = self.item()
        queue.enqueue(item, NOW)
        MonitoringSettingsService(self.factory, self.user).update(sources=("moex_main",))
        queue.process_pending(NOW, limit=0)
        with self.factory() as db:
            self.assertEqual(db.query(ArticleAnalysisJob).one().status, "superseded")
        MonitoringSettingsService(self.factory, self.user).update(sources=(item.source,))
        queue.enqueue(item, NOW)
        self.assertEqual(queue.process_pending(NOW), 1)

    def test_pre_upgrade_url_variant_preserves_article_and_old_delivery(self):
        import hashlib
        url = "https://www.moex.com/n101?nt=100"
        with self.factory() as db:
            db.add(NewsArticle(article_key=hashlib.sha256(url.encode()).hexdigest(), source="moex_main", url=url,
                title="Прибыль Сбербанка", summary="Прибыль выросла на 10%.", published_at=NOW.replace(tzinfo=None)))
            db.add(MonitoringEvent(event_key="old-delivered", kind="news", title="Прибыль Сбербанка", source="moex_main", url=url,
                published_at=NOW.replace(tzinfo=None), observed_at=NOW.replace(tzinfo=None), delivered_at=NOW.replace(tzinfo=None)))
            db.commit()
        queue = self.queue()
        queue.enqueue(replace(self.item(), source="moex_listing", url="https://www.moex.com/n101?nt=104"), NOW)
        queue.process_pending(NOW)
        with self.factory() as db:
            self.assertEqual(db.query(NewsArticle).count(), 1)
            self.assertEqual(db.query(MonitoringEvent).filter(MonitoringEvent.delivered_at.is_(None)).count(), 0)
            self.assertEqual(db.query(NewsArticle).one().source, "moex_listing")

    def test_interrupted_lease_recovers_after_restart(self):
        queue = self.queue()
        queue.enqueue(self.item(), NOW)
        with self.factory() as db:
            job = db.query(ArticleAnalysisJob).one()
            job.status, job.started_at, job.attempts = "running", (NOW - timedelta(minutes=11)).replace(tzinfo=None), 1
            db.commit()
        self.assertEqual(self.queue().process_pending(NOW), 1)

    def test_changed_article_during_model_call_does_not_publish_stale_output(self):
        queue = self.queue()
        queue.enqueue(self.item(), NOW)
        original = queue.analyzer.assess_article
        def update(item, catalog):
            queue.enqueue(replace(item, summary="Прибыль выросла на 11%."), NOW)
            return original(item, catalog)
        queue.analyzer.assess_article = update
        self.assertEqual(queue.process_pending(NOW), 0)
        with self.factory() as db:
            self.assertEqual(db.query(MonitoringEvent).count(), 0)
            self.assertEqual(db.query(ArticleAnalysisJob).one().status, "pending")

    def test_account_capacity_defers_and_recovers_followups_without_reassessing_article(self):
        self.seed_accounts()
        account_queue = NewsQueue(self.factory, self.user, prefilter=DirectNewsPrefilter(), publish_events=False)
        queue = self.queue(limits=MonitoringLimits(pending_jobs=1), account_queue=account_queue)
        queue.enqueue(self.item(), NOW)
        queue.process_pending(NOW)
        with self.factory() as db:
            self.assertEqual(db.query(NewsAnalysisJob).count(), 1)
            db.query(NewsAnalysisJob).update({NewsAnalysisJob.status: "done"})
            db.commit()
        queue.process_pending(NOW)
        with self.factory() as db:
            self.assertEqual(db.query(NewsAnalysisJob).count(), 2)
        self.assertEqual(queue.analyzer.calls, 1)

    def test_body_change_invalidates_account_assessment_hash(self):
        self.seed_accounts()
        account_queue = NewsQueue(self.factory, self.user, prefilter=DirectNewsPrefilter(), publish_events=False)
        queue = self.queue(account_queue=account_queue)
        queue.document_fetcher = lambda _: ArticleDocument("Первоначальная прибыль Сбербанка.")
        queue.enqueue(self.item(), NOW)
        queue.process_pending(NOW)
        with self.factory() as db:
            original_hash = db.query(NewsAnalysisJob).first().content_hash
            db.query(NewsAnalysisJob).update({NewsAnalysisJob.status: "done"})
            db.commit()
        queue.document_fetcher = lambda _: ArticleDocument("Обновлённая прибыль Сбербанка.")
        queue.enqueue(self.item(), NOW + timedelta(hours=1))
        queue.process_pending(NOW + timedelta(hours=1))
        with self.factory() as db:
            self.assertNotEqual(db.query(NewsAnalysisJob).first().content_hash, original_hash)
            self.assertEqual(db.query(NewsAnalysisJob).first().status, "pending")

    def queue(self, *, limits=None, assessment=None, account_queue=None):
        class Analyzer:
            version = "article-test"
            calls = 0
            def assess_article(self, item, catalog):
                self.calls += 1
                return assessment or ArticleAssessment(True, 85, item.summary, "company", ("SBER",), "Важная отчётность.",
                    ("summary",), "Реакция цены неизвестна.", "summary", "local")
        queue = MarketNewsQueue(self.factory, self.user, analyzer=Analyzer(), limits=limits,
            account_queue=account_queue, document_fetcher=lambda item: ArticleDocument(item.full_text))
        queue.names = {"SBER": "Сбербанк"}
        return queue
    def item(self, number=1):
        return NewsItem("rbc", "Прибыль Сбербанка", f"https://www.rbc.ru/economics/03/10/2026/abcdef{number}", NOW, "Прибыль выросла на 10%.")

    def test_one_general_assessment_and_explicit_account_jobs(self):
        accounts = self.seed_accounts()
        account_queue = NewsQueue(self.factory, self.user, prefilter=DirectNewsPrefilter(), publish_events=False)
        queue = self.queue(account_queue=account_queue)
        queue.accounts_by_ticker = {"SBER": accounts}
        queue.enqueue(self.item(), NOW)
        queue.enqueue(replace(self.item(), url=self.item().url + "?from=newsfeed"), NOW)
        self.assertEqual(queue.process_pending(NOW), 1)
        self.assertEqual(queue.process_pending(NOW), 0)
        with self.factory() as db:
            self.assertEqual(db.query(NewsArticle).count(), 1)
            self.assertEqual(db.query(ArticleAnalysisJob).count(), 1)
            self.assertEqual(db.query(NewsAnalysisJob).count(), 2)
            self.assertEqual(db.query(MonitoringEvent).count(), 1)
        self.assertEqual(queue.analyzer.calls, 1)

    def test_capacity_never_drops_article_and_deferred_work_recovers(self):
        queue = self.queue(limits=MonitoringLimits(pending_jobs=1))
        queue.enqueue(self.item(1), NOW)
        queue.enqueue(self.item(2), NOW)
        with self.factory() as db:
            self.assertEqual(db.query(NewsArticle).count(), 2)
            self.assertEqual(db.query(ArticleAnalysisJob).count(), 1)
        queue.process_pending(NOW)
        queue.process_pending(NOW)
        with self.factory() as db:
            self.assertEqual(db.query(ArticleAnalysisJob).filter_by(status="done").count(), 2)

    def test_hourly_limit_is_persistent_and_does_not_block_intake(self):
        queue = self.queue(limits=MonitoringLimits(news_per_hour=1))
        for number in (1, 2):
            queue.enqueue(self.item(number), NOW)
        queue.process_pending(NOW)
        queue.process_pending(NOW)
        self.assertEqual(queue.analyzer.calls, 1)
        queue.process_pending(NOW + timedelta(hours=1))
        self.assertEqual(queue.analyzer.calls, 2)

    def test_body_revision_is_reassessed_without_duplicate_event(self):
        queue = self.queue()
        queue.document_fetcher = lambda _: ArticleDocument("Первоначальный текст о прибыли.")
        queue.enqueue(self.item(), NOW)
        queue.process_pending(NOW)
        queue.enqueue(self.item(), NOW + timedelta(hours=1))
        queue.process_pending(NOW + timedelta(hours=1))
        self.assertEqual(queue.analyzer.calls, 1)
        queue.document_fetcher = lambda _: ArticleDocument("Обновлённый текст о прибыли.")
        queue.enqueue(self.item(), NOW + timedelta(hours=2))
        queue.process_pending(NOW + timedelta(hours=2))
        self.assertEqual(queue.analyzer.calls, 2)
        with self.factory() as db:
            self.assertEqual(db.query(MonitoringEvent).count(), 1)

    def test_model_failure_retries_then_preserves_rule_fallback(self):
        queue = self.queue()
        queue.analyzer.assess_article = Mock(side_effect=TimeoutError())
        queue.enqueue(self.item(), NOW)
        for minutes in (0, 2, 5):
            queue.process_pending(NOW + timedelta(minutes=minutes))
        with self.factory() as db:
            job = db.query(ArticleAnalysisJob).one()
            self.assertEqual((job.status, job.attempts), ("failed", 3))
            self.assertEqual(json.loads(job.result_json)["model"], "rules")

    def test_disabled_subscriptions_do_no_network_work(self):
        MonitoringSettingsService(self.factory, self.user).update(alerts_enabled=False, digest_enabled=False)
        queue = self.queue()
        queue.source_fetcher = Mock()
        self.assertEqual(queue.intake(NOW), 0)
        queue.source_fetcher.assert_not_called()

    def test_failed_source_does_not_prevent_other_source_intake(self):
        MonitoringSettingsService(self.factory, self.user).update(sources=("rbc", "interfax"))
        queue = self.queue()
        def fetch(source, **kwargs):
            if source == "rbc":
                raise TimeoutError()
            return NewsFetchResult((replace(self.item(), source="interfax"),), True)
        queue.source_fetcher = fetch
        self.assertEqual(queue.intake(NOW, names=queue.names), 1)
        with self.factory() as db:
            self.assertEqual(db.get(NewsSourceState, "rbc").status, "error")
            self.assertEqual(db.get(NewsSourceState, "interfax").status, "ok")

    def test_hour_old_model_news_reaches_alert_and_lists_both_accounts_once(self):
        accounts = self.seed_accounts()
        queue = self.queue()
        queue.accounts_by_ticker = {"SBER": accounts}
        queue.enqueue(replace(self.item(), published_at=NOW - timedelta(hours=1)), NOW)
        queue.process_pending(NOW)
        sent = []
        with patch("app.services.monitoring.session_factory_for_user", return_value=self.factory):
            runner = MonitoringRunner(self.user, send_text=lambda chat, text: sent.append(text))
        runner._send_alerts(runner.settings_service.get(), {"SBER": accounts}, accounts, NOW)
        self.assertEqual(len(sent), 1)
        self.assertIn("Счёт 1, Счёт 2", sent[0])

    def test_news_alert_cap_does_not_limit_price_alerts(self):
        queue = self.queue()
        for number in range(4):
            queue.enqueue(self.item(number), NOW)
        queue.process_pending(NOW, limit=4)
        with self.factory() as db:
            db.add(MonitoringEvent(event_key="price:test", kind="price", ticker="SBER", title="SBER +6%", source="MOEX ISS",
                published_at=NOW.replace(tzinfo=None), observed_at=NOW.replace(tzinfo=None)))
            db.commit()
        sent = []
        with patch("app.services.monitoring.session_factory_for_user", return_value=self.factory):
            runner = MonitoringRunner(self.user, send_text=lambda chat, text: sent.append(text))
        runner._send_alerts(runner.settings_service.get(), {"SBER": []}, (), NOW)
        self.assertEqual(len(sent), 4)
        self.assertEqual(sum("Движение цены" in text for text in sent), 1)


class ScreeningTests(unittest.TestCase):
    def test_selector_uses_compact_ranked_news_and_existing_reason_indexes(self):
        candidates = [rank_candidate(ticker, ticker, history()) for ticker in ("AAA", "BBB", "CCC")]
        choices = [{"ticker": ticker, "reason_ids": [0]} for ticker in ("AAA", "BBB", "CCC")]
        session = Session(Response({"done": True, "message": {"content": json.dumps({"selected": choices})}}))
        news = [{"summary": "Событие " * 100, "importance": value, "topic": "macro", "tickers": [],
                 "uncertainty": "Большое объяснение " * 100} for value in range(10)]
        selected = OllamaMarketSelector(NewsLLMConfig(enabled=True), http_session=session).select(candidates, news)
        request = session.calls[0][1]["json"]
        payload = json.loads(request["messages"][1]["content"])
        self.assertEqual([value["importance"] for value in payload["news"]], [9, 8, 7, 6, 5])
        self.assertTrue(all(len(value["summary"]) <= 240 for value in payload["news"]))
        self.assertNotIn("uncertainty", payload["news"][0])
        self.assertEqual(request["options"]["num_predict"], 256)
        self.assertEqual(selected[0].selection_reason, candidates[0].reasons[0])

    def test_board_catalog_that_ignores_pagination_stops_and_excludes_funds(self):
        rows = [["STOCK" + str(i), "Акция", "1"] for i in range(100)] + [["ETF", "Фонд", "J"]]
        client = SimpleNamespace(_get_json=Mock(return_value={"securities": {"columns": ["SECID", "SHORTNAME", "SECTYPE"], "data": rows}}))
        result = fetch_equity_universe(client)
        self.assertEqual(len(result), 100)
        self.assertEqual(client._get_json.call_count, 2)
        self.assertNotIn("ETF", result)

    def test_real_equity_candle_path_has_no_json_before_candles(self):
        client = MOEXISSClient()
        client._get_json = Mock(return_value={"candles": {"columns": [], "data": []}})
        client.get_daily_candles_result("SBER")
        self.assertEqual(client._get_json.call_args.args[0], "/engines/stock/markets/shares/boards/TQBR/securities/SBER/candles.json")

    def test_dividend_context_marks_only_window_after_last_buy_date(self):
        event = SimpleNamespace(last_buy_date=datetime(2026, 10, 1), record_date=datetime(2026, 10, 3))
        self.assertIsNone(dividend_note(date(2026, 10, 1), [event]))
        self.assertIn("Причина движения цены не установлена", dividend_note(date(2026, 10, 2), [event]))
        self.assertIsNone(dividend_note(date(2026, 10, 6), [event]))

    def test_last_volume_is_excluded_from_baseline(self):
        result = rank_candidate("AAA", "Компания", history(volume=100000))
        self.assertEqual(result.volume_ratio, 100)

    def test_sub_five_percent_awakening_volume_breakout_and_relative_move(self):
        result = rank_candidate("AAA", "Компания", history(), index_return=-1)
        self.assertLess(result.change_pct, 5)
        self.assertTrue(result.quiet_expansion)
        self.assertEqual(result.breakout, "up")
        self.assertEqual(result.volume_ratio, 3)
        self.assertGreater(result.score, 80)

    def test_low_liquidity_short_history_and_invalid_data_are_excluded(self):
        self.assertIsNone(rank_candidate("AAA", "Компания", history(turnover=2_000_000)))
        self.assertIsNone(rank_candidate("AAA", "Компания", history()[:30]))
        bars = history()
        bars[-1] = replace(bars[-1], close=float("nan"))
        self.assertIsNone(rank_candidate("AAA", "Компания", bars))

    def test_zero_historical_bases_and_missing_volume_do_not_divide_by_zero(self):
        bars = [replace(bar, volume=None, high=bar.close, low=bar.close) for bar in history(change=0)]
        result = rank_candidate("AAA", "Компания", bars)
        self.assertEqual(result.price_ratio, 0)
        self.assertIsNone(result.volume_ratio)

    def test_model_can_only_select_distinct_candidates_and_existing_reasons(self):
        candidates = [rank_candidate(ticker, ticker, history()) for ticker in ("AAA", "BBB", "CCC")]
        for selected in ([{"ticker": "UNKNOWN", "reason_ids": [0]}] * 3,
                         [{"ticker": "AAA", "reason_ids": [0]}] * 3,
                         [{"ticker": ticker, "reason_ids": [99]} for ticker in ("AAA", "BBB", "CCC")]):
            with self.subTest(selected=selected):
                session = Session(Response({"done": True, "message": {"content": json.dumps({"selected": selected})}}))
                with self.assertRaises(NewsAnalysisUnavailable):
                    OllamaMarketSelector(NewsLLMConfig(enabled=True), http_session=session).select(candidates)

    def test_cached_renderer_returns_real_png_without_network(self):
        result = ChartImageService(None).render_cached_history_png("AAA", history(), name="Компания",
            reason="Оживление после затишья", range_bounds=(99, 101))
        self.assertTrue(result.startswith(b"\x89PNG\r\n\x1a\n"))


class DailyDigestTests(DatabaseCase):
    def test_watchlist_priority_does_not_claim_ownership_and_zero_positions_are_ignored(self):
        self.seed_accounts()
        with self.factory() as db:
            db.query(PositionSnapshot).update({PositionSnapshot.quantity: 0})
            db.add(Instrument(ticker="AAA", figi="watchlist-AAA"))
            db.commit()
        tickers, _, account_links = owned_interest(self.factory, NOW)
        self.assertEqual(tickers, {"AAA"})
        self.assertEqual(account_links, {})
        self.seed_market()
        with self.factory() as db:
            db.query(MarketReport).delete()
            db.commit()
        renderer = SimpleNamespace(render_cached_history_png=lambda *_args, **_kwargs: b"png")
        draft = DigestService(self.factory, self.user, renderer=renderer).build(now=NOW)
        self.assertEqual(draft.charts[0].ticker, "AAA")
        self.assertNotIn("В твоём портфеле", draft.text)

    def test_album_is_not_sent_while_text_claim_is_unconfirmed(self):
        text, album = Mock(side_effect=TimeoutError()), Mock()
        draft = DigestDraft("2026-10-03", "Обзор", (DigestChart("AAA", b"png", "График"),))
        delivery = DigestDeliveryService(self.factory, self.user, send_text=text, send_album=album)
        delivery.deliver(draft, NOW)
        delivery.deliver(draft, NOW + timedelta(minutes=1))
        album.assert_not_called()

    def seed_market(self):
        repository = PriceCandleRepository(self.factory)
        for ticker in ("AAA", "BBB", "CCC", "IMOEX"):
            repository.upsert_candles(ticker=ticker, interval="day", candles=history(change=1.5), source="moex_iss", fetched_at=NOW)
        with self.factory() as db:
            db.add(MarketRefreshState(id=1, universe_json=json.dumps({ticker: {"name": ticker} for ticker in ("AAA", "BBB", "CCC")}),
                refreshed_at=NOW.replace(tzinfo=None), status="ok"))
            db.commit()
        MarketScreeningService(self.factory).prepare(NOW.date(), now=NOW)

    def test_quiet_day_always_has_three_cached_charts_and_nonempty_overview(self):
        self.seed_market()
        renderer = SimpleNamespace(render_cached_history_png=lambda *_args, **_kwargs: b"png")
        draft = DigestService(self.factory, self.user, renderer=renderer).build(now=NOW)
        self.assertEqual(len(draft.charts), 3)
        self.assertEqual(len({chart.ticker for chart in draft.charts}), 3)
        self.assertIn("IMOEX", draft.text)
        self.assertNotIn("Значительных движений не найдено", draft.text)
        self.assertLessEqual(len(draft.text), 3900)

    def test_preview_does_not_create_delivery_checkpoint(self):
        self.seed_market()
        renderer = SimpleNamespace(render_cached_history_png=lambda *_args, **_kwargs: b"png")
        DigestService(self.factory, self.user, renderer=renderer).build(now=NOW)
        with self.factory() as db:
            self.assertEqual(db.query(DigestDelivery).count(), 0)

    def test_future_unfinished_candles_are_not_used(self):
        self.seed_market()
        repository = PriceCandleRepository(self.factory)
        repository.upsert_candles(ticker="AAA", interval="day", source="moex_iss", candles=[
            PriceCandle(NOW.replace(tzinfo=None), 100, 1000, 100, 900, 999999, 999999999)])
        candidates = MarketScreeningService(self.factory).scan(NOW.date())
        self.assertLess(next(candidate.change_pct for candidate in candidates if candidate.ticker == "AAA"), 5)

    def test_album_failure_only_retries_album_and_acknowledged_parts_survive_restart(self):
        texts, albums = [], []
        def album(chat, charts):
            albums.append(charts)
            if len(albums) == 1:
                raise ValueError("Telegram rejected request")
        draft = DigestDraft("2026-10-03", "Обзор", (DigestChart("AAA", b"png", "График"),))
        delivery = DigestDeliveryService(self.factory, self.user, send_text=lambda *_: texts.append(True), send_album=album)
        self.assertFalse(delivery.deliver(draft, NOW))
        restarted = DigestDeliveryService(self.factory, self.user, send_text=lambda *_: texts.append(True), send_album=album)
        self.assertTrue(restarted.deliver(draft, NOW + timedelta(minutes=5)))
        self.assertTrue(restarted.deliver(draft, NOW + timedelta(minutes=10)))
        self.assertEqual((len(texts), len(albums)), (1, 2))

    def test_ambiguous_timeout_is_recorded_and_not_retried_immediately(self):
        sender = Mock(side_effect=TimeoutError())
        draft = DigestDraft("2026-10-03", "Обзор", ())
        delivery = DigestDeliveryService(self.factory, self.user, send_text=sender)
        self.assertFalse(delivery.deliver(draft, NOW))
        self.assertFalse(delivery.deliver(draft, NOW + timedelta(minutes=1)))
        self.assertEqual(sender.call_count, 1)
        with self.factory() as db:
            self.assertTrue(db.get(DigestDelivery, draft.report_date).ambiguous)

    def test_unavailable_sources_are_not_reported_as_no_news(self):
        with self.factory() as db:
            db.add(NewsSourceState(source="rbc", status="error", item_count=0, coverage_complete=False))
            db.commit()
        draft = DigestService(self.factory, self.user).build(now=NOW)
        self.assertIn("rbc: источник недоступен", draft.text)
        self.assertIn("доступных источниках", draft.text)


class MonitoringScheduleTests(DatabaseCase):
    def test_independent_jobs_and_disabled_startup_do_no_network(self):
        from app.client.config import monitoring_scheduler as module
        MonitoringSettingsService(self.factory, self.user).update(alerts_enabled=False, digest_enabled=False)
        scheduler = Mock()
        with patch.object(module, "monitoring_scheduler", None), \
             patch("apscheduler.schedulers.background.BackgroundScheduler", return_value=scheduler), \
             patch("app.client.config.users.load_runtime_users_config", return_value=SimpleNamespace(enabled_users=[object()])), \
             patch("app.services.user_context.UserContext.from_config", return_value=self.user), \
             patch("app.services.monitoring.session_factory_for_user", return_value=self.factory), \
             patch("app.services.news_llm_config.NewsLLMConfig.from_env", return_value=NewsLLMConfig(enabled=False)), \
             patch("app.services.monitoring.MonitoringRunner._interests") as interests, \
             patch("app.integrations.moex_iss.MOEXISSClient._get_json") as network:
            module.configure_monitoring_scheduler()
            jobs = {call.kwargs["id"]: call for call in scheduler.add_job.call_args_list}
            self.assertEqual(jobs["news_intake_u"].args[1], "cron")
            self.assertEqual(jobs["news_intake_u"].kwargs["minute"], 0)
            self.assertEqual(jobs["market_history_u"].kwargs["hour"], 2)
            self.assertEqual(jobs["market_prepare_u"].kwargs["hour"], 8)
            self.assertEqual(jobs["news_worker"].kwargs["seconds"], 30)
            self.assertEqual(jobs["digest_delivery_u"].kwargs["minute"], "*")
            for identifier in ("news_startup_u", "market_startup_u", "monitoring_u", "news_worker"):
                jobs[identifier].args[0]()
            interests.assert_not_called()
            network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
