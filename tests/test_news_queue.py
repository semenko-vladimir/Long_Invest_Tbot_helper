import unittest
import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.backend.models.accounts import BrokerConnection, InvestmentAccount, PortfolioSnapshot, PositionSnapshot
from app.backend.models.database import Base
from app.backend.models.monitoring import MonitoringEvent, NewsAnalysisJob, NewsArticle
from app.integrations.moex_market_monitor import StockQuote
from app.services.monitoring import MonitoringRunner
from app.services.monitoring_settings import MonitoringSettingsService
from app.services.news_analysis import ModelNewsAnalysis, ModelNewsPrefilter, NewsAssessment
from app.services.news_queue import NewsQueue
from app.services.news_sources import NewsItem
from app.services.user_context import UserContext


class NewsQueueTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.user = UserContext("u", "User", 123, 0.3, "unused")
        self.now = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
        self.item = NewsItem("moex_main", "Новость о рынке", "https://www.moex.com/news/42", self.now)
        with self.factory() as db:
            connection = BrokerConnection(provider_key="t-invest", connection_key="default", display_name="T-Invest")
            db.add(connection)
            db.flush()
            for number in (1, 2):
                db.add(InvestmentAccount(broker_connection_id=connection.id, external_account_id=str(number),
                                         display_name=f"Счёт {number}", status="open", enabled=True))
            db.commit()
        MonitoringSettingsService(self.factory, self.user).update(alerts_enabled=True)

    def tearDown(self):
        self.engine.dispose()

    def accounts(self):
        with self.factory() as db:
            queue = NewsQueue(self.factory, self.user)
            return tuple(queue._account_context(db, row.id) for row in db.query(InvestmentAccount).order_by(InvestmentAccount.id))

    def test_one_article_creates_one_job_per_account_and_no_repeat(self):
        seen = []

        class Analyzer:
            def assess(self, item, names, accounts):
                seen.append(accounts[0].investment_account_id)
                return NewsAssessment(True, None, f"Для счёта {accounts[0].investment_account_id}")

        accounts = self.accounts()
        queue = NewsQueue(self.factory, self.user, analyzer=Analyzer())
        self.assertTrue(queue.enqueue(self.item, {}, {}, accounts, "market", self.now))
        self.assertFalse(queue.enqueue(self.item, {}, {}, accounts, "market", self.now))
        self.assertEqual(queue.process_pending(self.now), 2)
        self.assertEqual(queue.process_pending(self.now), 0)
        with self.factory() as db:
            self.assertEqual(db.query(NewsArticle).count(), 1)
            self.assertEqual(db.query(NewsAnalysisJob).filter_by(status="done").count(), 2)
            events = db.query(MonitoringEvent).order_by(MonitoringEvent.investment_account_id).all()
            self.assertEqual([event.investment_account_id for event in events],
                             [account.investment_account_id for account in accounts])
            self.assertNotEqual(events[0].event_key, events[1].event_key)
            with patch("app.services.monitoring.session_factory_for_user", return_value=self.factory):
                runner = MonitoringRunner(self.user, send_text=lambda *_: None)
            first_message = runner._format_event(events[0], {}, accounts)
            self.assertIn("Счёт 1", first_message)
            self.assertNotIn("Счёт 2", first_message)
            self.assertIn("Причина отбора:", first_message)
        self.assertEqual(seen, [account.investment_account_id for account in accounts])

    def test_same_url_from_two_moex_feeds_creates_one_analysis(self):
        queue = NewsQueue(self.factory, self.user)
        accounts = self.accounts()
        first = NewsItem("moex_main", "О приостановке торгов", "https://www.moex.com/n104716", self.now)
        second = NewsItem("moex_listing", first.title, first.url, self.now)
        self.assertTrue(queue.enqueue(first, {}, {}, accounts, "market", self.now))
        self.assertFalse(queue.enqueue(second, {}, {}, accounts, "market", self.now))
        with self.factory() as db:
            self.assertEqual(db.query(NewsArticle).count(), 1)
            self.assertEqual(db.query(NewsAnalysisJob).count(), 2)

    def test_failure_retries_then_completes(self):
        calls = []

        class FlakyAnalyzer:
            def assess(self, item, names, accounts):
                calls.append(accounts[0].investment_account_id)
                if len(calls) == 1:
                    raise TimeoutError("temporary timeout")
                return NewsAssessment(True, None, "Важная новость")

        queue = NewsQueue(self.factory, self.user, analyzer=FlakyAnalyzer())
        queue.enqueue(self.item, {}, {}, self.accounts()[:1], "market", self.now)
        self.assertEqual(queue.process_pending(self.now), 0)
        with self.factory() as db:
            job = db.query(NewsAnalysisJob).one()
            self.assertEqual((job.status, job.attempts), ("pending", 1))
        self.assertEqual(queue.process_pending(self.now + timedelta(seconds=30)), 0)
        self.assertEqual(queue.process_pending(self.now + timedelta(minutes=2)), 1)
        self.assertEqual(len(calls), 2)

    def test_stale_running_job_is_recovered(self):
        queue = NewsQueue(self.factory, self.user)
        queue.enqueue(self.item, {}, {}, self.accounts()[:1], "market", self.now)
        with self.factory() as db:
            job = db.query(NewsAnalysisJob).one()
            job.status = "running"
            job.attempts = 1
            job.started_at = self.now.replace(tzinfo=None) - timedelta(minutes=11)
            db.commit()
        self.assertEqual(queue.process_pending(self.now), 1)
        with self.factory() as db:
            self.assertEqual(db.query(NewsAnalysisJob).one().status, "done")

    def test_changed_article_requeues_without_duplicate_notification(self):
        queue = NewsQueue(self.factory, self.user)
        account = self.accounts()[0]
        queue.enqueue(self.item, {}, {}, (account,), "market", self.now)
        self.assertEqual(queue.process_pending(self.now), 1)
        changed = NewsItem(self.item.source, "Новая редакция новости", self.item.url,
                           self.now + timedelta(minutes=1), "Добавлены подробности")
        self.assertTrue(queue.enqueue(changed, {}, {}, (account,), "market", self.now + timedelta(minutes=1)))
        self.assertEqual(queue.process_pending(self.now + timedelta(minutes=1)), 1)
        with self.factory() as db:
            self.assertEqual(db.query(NewsArticle).count(), 1)
            self.assertEqual(db.query(NewsAnalysisJob).one().attempts, 1)
            self.assertEqual(db.query(MonitoringEvent).count(), 1)
            self.assertEqual(db.query(NewsArticle).one().summary, "Добавлены подробности")

    def test_article_update_during_analysis_discards_old_result(self):
        account = self.accounts()[0]
        changed = NewsItem(self.item.source, "Обновлённая новость", self.item.url,
                           self.now + timedelta(minutes=1), "Уточнение")
        queue = NewsQueue(self.factory, self.user)
        now = self.now

        class UpdatingAnalyzer:
            def __init__(self):
                self.calls = 0

            def assess(self, item, names, accounts):
                self.calls += 1
                if self.calls == 1:
                    queue.enqueue(changed, {}, {}, (account,), "market", now + timedelta(minutes=1))
                return NewsAssessment(True, None, item.title)

        analyzer = UpdatingAnalyzer()
        queue.analyzer = analyzer
        queue.enqueue(self.item, {}, {}, (account,), "market", self.now)
        self.assertEqual(queue.process_pending(self.now, limit=1), 0)
        with self.factory() as db:
            self.assertEqual(db.query(NewsAnalysisJob).one().status, "pending")
            self.assertEqual(db.query(MonitoringEvent).count(), 0)
        self.assertEqual(queue.process_pending(self.now + timedelta(minutes=1), limit=1), 1)
        with self.factory() as db:
            result = json.loads(db.query(NewsAnalysisJob).one().result_json)
            self.assertEqual(result["reason"], changed.title)

    def test_new_analyzer_version_can_reassess_existing_article(self):
        account = self.accounts()[0]
        rules = NewsQueue(self.factory, self.user)
        rules.enqueue(self.item, {}, {}, (account,), "market", self.now)
        self.assertEqual(rules.process_pending(self.now), 1)
        newer = NewsQueue(self.factory, self.user, analyzer_version="model-v1")
        self.assertTrue(newer.enqueue(self.item, {}, {}, (account,), "market", self.now))
        self.assertEqual(rules.process_pending(self.now), 0)
        self.assertEqual(newer.process_pending(self.now), 1)
        with self.factory() as db:
            self.assertEqual(db.query(NewsArticle).count(), 1)
            self.assertEqual(db.query(NewsAnalysisJob).count(), 2)
            self.assertEqual(db.query(MonitoringEvent).count(), 2)

    def test_model_result_is_saved_and_displayed_for_its_account(self):
        account = self.accounts()[0]

        class ModelAnalyzer:
            def assess(self, item, names, accounts):
                details = ModelNewsAnalysis(accounts[0].investment_account_id, "local-model", "unknown",
                                            ("Заголовок RSS: " + item.title,), "Полный текст не проверен.",
                                            True, item.url, "title_only", ("Полный текст не проверен.",))
                return NewsAssessment(True, None, "Связано со стратегией", details)

        queue = NewsQueue(self.factory, self.user, analyzer=ModelAnalyzer(), analyzer_version="ollama-test")
        queue.enqueue(self.item, {}, {}, (account,), "market", self.now)
        self.assertEqual(queue.process_pending(self.now, limit=1), 1)
        with self.factory() as db:
            job_result = json.loads(db.query(NewsAnalysisJob).one().result_json)
            event = db.query(MonitoringEvent).one()
            self.assertEqual(job_result["analysis"]["investment_account_id"], account.investment_account_id)
            self.assertEqual(json.loads(event.payload_json)["analysis_status"], "model")
            with patch("app.services.monitoring.session_factory_for_user", return_value=self.factory):
                runner = MonitoringRunner(self.user, send_text=lambda *_: None)
            text = runner._format_event(event, {}, (account,))
            self.assertIn("Разбор Qwen", text)
            self.assertIn("Оценка модели:", text)
            self.assertIn("Ограничение:", text)
            self.assertIn(self.item.url, text)

    def test_model_failure_keeps_job_and_marks_rule_fallback(self):
        class FailingAnalyzer:
            def assess(self, *_):
                raise TimeoutError("model unavailable")

        queue = NewsQueue(self.factory, self.user, analyzer=FailingAnalyzer(), analyzer_version="ollama-test")
        queue.enqueue(self.item, {}, {}, self.accounts()[:1], "market", self.now)
        with patch("app.services.news_queue.logger.exception"):
            self.assertEqual(queue.process_pending(self.now, limit=1), 0)
            self.assertEqual(queue.process_pending(self.now + timedelta(minutes=2), limit=1), 0)
            self.assertEqual(queue.process_pending(self.now + timedelta(minutes=5), limit=1), 0)
        with self.factory() as db:
            job = db.query(NewsAnalysisJob).one()
            event = db.query(MonitoringEvent).one()
            self.assertEqual((job.status, job.attempts), ("failed", 3))
            self.assertEqual(json.loads(event.payload_json)["analysis_status"], "unavailable")

    def test_generic_moex_notice_fetches_once_and_only_analyzes_matching_account(self):
        accounts = self.accounts()
        with self.factory() as db:
            snapshot = PortfolioSnapshot(investment_account_id=accounts[0].investment_account_id,
                                         captured_at=datetime.now(timezone.utc).replace(tzinfo=None), total_value=1000,
                                         currency="RUB", source="test")
            db.add(snapshot)
            db.flush()
            db.add(PositionSnapshot(portfolio_snapshot_id=snapshot.id,
                                    investment_account_id=accounts[0].investment_account_id,
                                    ticker="SBER", quantity=1, currency="RUB"))
            db.commit()
        item = NewsItem("moex_listing", "О приостановке торгов ценными бумагами",
                        "https://www.moex.com/n104716", self.now, "Подробности на сайте биржи")
        fetched = []
        assessed = []

        def fetch(article):
            fetched.append(article.url)
            return "Приостановить торги бумагой SBER. Бумага GAZP не затронута."

        class Analyzer:
            def assess(self, article, names, selected):
                assessed.append((article.full_text, names, selected[0].investment_account_id))
                return NewsAssessment(True, next(iter(names)), "Связано со счётом")

        queue = NewsQueue(self.factory, self.user, prefilter=ModelNewsPrefilter(),
                          analyzer=Analyzer(), analyzer_version="ollama-test", article_fetcher=fetch)
        self.assertTrue(queue.enqueue(item, {}, {}, accounts, "market", self.now))
        self.assertEqual(queue.process_pending(self.now, limit=2), 2)
        self.assertEqual(fetched, [item.url])
        self.assertEqual(len(assessed), 1)
        self.assertEqual(assessed[0][1], {"SBER": ""})
        with self.factory() as db:
            self.assertEqual(db.query(MonitoringEvent).count(), 1)
            self.assertEqual(db.query(NewsAnalysisJob).filter_by(status="done").count(), 2)

    def test_generic_moex_notice_retries_unavailable_article_without_generic_alert(self):
        item = NewsItem("moex_listing", "О приостановке торгов ценными бумагами",
                        "https://www.moex.com/n104716", self.now)

        def unavailable(_):
            raise TimeoutError("article unavailable")

        queue = NewsQueue(self.factory, self.user, prefilter=ModelNewsPrefilter(),
                          analyzer_version="ollama-test", article_fetcher=unavailable)
        queue.enqueue(item, {}, {}, self.accounts()[:1], "market", self.now)
        with patch("app.services.news_queue.logger.exception"), patch("app.services.news_queue.logger.warning"):
            queue.process_pending(self.now, limit=1)
            queue.process_pending(self.now + timedelta(minutes=2), limit=1)
            queue.process_pending(self.now + timedelta(minutes=5), limit=1)
        with self.factory() as db:
            self.assertEqual(db.query(NewsAnalysisJob).one().status, "failed")
            self.assertEqual(db.query(MonitoringEvent).count(), 0)

    def test_price_poll_does_not_execute_news_analyzer(self):
        sent = []
        account = self.accounts()[0]
        quote = StockQuote("SBER", "Сбербанк", 106, 100, date(2026, 10, 1))
        with patch("app.services.monitoring.session_factory_for_user", return_value=self.factory):
            runner = MonitoringRunner(self.user, send_text=lambda _, message: sent.append(message),
                                      quote_fetcher=lambda _: {"SBER": quote}, feed_fetcher=lambda _: [self.item])
        runner._interests = lambda: ({"SBER": [account]}, {"SBER": "Сбербанк"}, (account,))

        class SlowAnalyzer:
            def assess(self, *_):
                raise AssertionError("The news worker must run independently")

        runner.news_queue.analyzer = SlowAnalyzer()
        runner.run(self.now)
        self.assertEqual(len(sent), 1)
        self.assertIn("+6.00%", sent[0])
        with self.factory() as db:
            self.assertEqual(db.query(NewsAnalysisJob).filter_by(status="pending").count(), 1)
            self.assertEqual(db.query(MonitoringEvent).filter_by(kind="price").count(), 1)


if __name__ == "__main__":
    unittest.main()
