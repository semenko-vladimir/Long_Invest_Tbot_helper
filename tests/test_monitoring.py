import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.backend.models.database import Base
from app.backend.models.monitoring import MonitoringEvent
from app.integrations.moex_market_monitor import StockQuote, fetch_monitoring_quotes, fetch_stock_quotes
from app.services.monitoring import MonitoringRunner
from app.services.monitoring_settings import MonitoringSettingsService, validate_source
from app.services.news_sources import NewsItem
from app.services.user_context import UserContext


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.user = UserContext("u", "User", 123, 0.3, "unused")

    def tearDown(self):
        self.engine.dispose()

    def test_opt_in_and_config_precedence(self):
        service = MonitoringSettingsService(self.factory, self.user)
        self.assertFalse(service.get().alerts_enabled)
        self.assertTrue(service.update(alerts_enabled=True).alerts_enabled)
        controlled = UserContext("u", "User", 123, 0.3, "unused", monitoring={"alerts_enabled": False})
        self.assertFalse(MonitoringSettingsService(self.factory, controlled).get().alerts_enabled)
        self.assertFalse(MonitoringSettingsService(self.factory, controlled).update(alerts_enabled=True).alerts_enabled)

    def test_price_deduped_and_scoped(self):
        sent = []
        now = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)
        quote = StockQuote("SBER", "Сбербанк", 106, 100, date(2026, 9, 28))
        with patch("app.services.monitoring.session_factory_for_user", return_value=self.factory):
            runner = MonitoringRunner(self.user, send_text=lambda _, message: sent.append(message),
                                      quote_fetcher=lambda _: {"SBER": quote}, feed_fetcher=lambda _: [])
        runner._interests = lambda: ({"SBER": []}, {"SBER": "Сбербанк"}, ())
        runner.settings_service.update(alerts_enabled=True)
        runner.run(now)
        runner.run(now)
        self.assertEqual(len(sent), 1)
        self.assertIn("+6.00%", sent[0])
        with self.factory() as db:
            self.assertEqual(db.query(MonitoringEvent).count(), 1)

    def test_monitoring_uses_current_broker_accounts_before_local_stale_rows(self):
        current = SimpleNamespace(investment_account_id=2, status="open")
        stale = SimpleNamespace(investment_account_id=1, status="open")
        registry = SimpleNamespace(
            sync_accounts=Mock(return_value=SimpleNamespace(accounts=(current,))),
            list_enabled_accounts=Mock(return_value=(stale, current)),
        )
        services = SimpleNamespace(
            account_registry=registry,
            portfolio_service=SimpleNamespace(get_account_portfolio=lambda _: SimpleNamespace(positions=())),
            watchlist_service=SimpleNamespace(list_items=lambda: SimpleNamespace(items=())),
        )
        with patch("app.services.monitoring.session_factory_for_user", return_value=self.factory), patch(
            "app.client.handlers.user_context.build_telegram_services", return_value=services,
        ):
            runner = MonitoringRunner(self.user, send_text=lambda *_: None)
            _, _, accounts = runner._interests()
            self.assertEqual(accounts, (current,))
            registry.list_enabled_accounts.assert_not_called()

            registry.sync_accounts.side_effect = RuntimeError("broker temporarily unavailable")
            _, _, fallback_accounts = runner._interests()
            self.assertEqual(fallback_accounts, (stale, current))

    def test_news_digested_without_alert_when_old(self):
        sent = []
        now = datetime(2026, 9, 28, 7, 0, tzinfo=timezone.utc)
        item = NewsItem("moex_main", "Важная новость", "https://www.moex.com/news/1", now)
        with patch("app.services.monitoring.session_factory_for_user", return_value=self.factory):
            runner = MonitoringRunner(self.user, send_text=lambda _, message: sent.append(message),
                                      quote_fetcher=lambda _: {}, feed_fetcher=lambda _: [item])
        runner._interests = lambda: ({}, {}, ())
        runner.settings_service.update(digest_enabled=True)
        runner.run(now)
        runner.run(now)
        self.assertEqual(len(sent), 1)
        self.assertIn("Важная новость", sent[0])

    def test_sources_require_https(self):
        with self.assertRaises(ValueError):
            validate_source("http://localhost/feed")
        self.assertEqual(validate_source("moex_main"), "moex_main")

    def test_one_message_lists_each_affected_account(self):
        with patch("app.services.monitoring.session_factory_for_user", return_value=self.factory):
            runner = MonitoringRunner(self.user, send_text=lambda *_: None, quote_fetcher=lambda _: {}, feed_fetcher=lambda _: [])
        event = SimpleNamespace(kind="price", title="SBER: +6%", ticker="SBER", source="MOEX ISS",
                                published_at=datetime(2026, 9, 28), url=None, payload_json=None)
        first = SimpleNamespace(account_name="Брокерский", strategy=SimpleNamespace(title="Рост"))
        second = SimpleNamespace(account_name="ИИС", strategy=SimpleNamespace(title="Дивиденды"))
        text = runner._format_event(event, {"SBER": [first, second]})
        self.assertEqual(text.count("Счёт:"), 2)
        self.assertIn("ИИС · Дивиденды", text)

    def test_bulk_quotes_need_fresh_trade(self):
        class FakeClient:
            def _get_json(self, path, params):
                return {
                    "securities": {"columns": ["SECID", "SHORTNAME", "PREVPRICE"],
                                   "data": [["SBER", "Сбербанк", 100]]},
                    "marketdata": {"columns": ["SECID", "LAST", "VOLTODAY", "LASTTRADEDATE"],
                                   "data": [["SBER", 106, 1000, "2026-09-28"]]},
                }
        self.assertAlmostEqual(fetch_stock_quotes(FakeClient(), date(2026, 9, 28))["SBER"].change_pct, 6)
        self.assertFalse(fetch_stock_quotes(FakeClient(), date(2026, 9, 29)))

    def test_monitoring_quote_fetch_retries_once_with_longer_timeout(self):
        trade_date = date(2026, 9, 28)
        quote = StockQuote("SBER", "Сбербанк", 106, 100, trade_date)
        with patch("app.integrations.moex_market_monitor.MOEXISSClient") as client, patch(
            "app.integrations.moex_market_monitor.fetch_stock_quotes",
            side_effect=[RuntimeError("temporary disconnect"), {"SBER": quote}],
        ) as fetch:
            self.assertEqual(fetch_monitoring_quotes(trade_date)["SBER"], quote)
        client.assert_called_once_with(timeout_seconds=15)
        self.assertEqual(fetch.call_count, 2)

        with patch("app.integrations.moex_market_monitor.fetch_stock_quotes",
                   side_effect=RuntimeError("still unavailable")) as fetch:
            with self.assertRaises(RuntimeError):
                fetch_monitoring_quotes(trade_date)
        self.assertEqual(fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
