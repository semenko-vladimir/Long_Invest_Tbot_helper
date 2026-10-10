import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import requests
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.backend.models import Base
from app.backend.models.accounts import BrokerConnection, InvestmentAccount
from app.backend.models.stocks import StockTracking
from app.charts.schemas import PriceCandle
from app.integrations.stock_market import StockMarketAdapter
from app.services.accounts import UnknownInvestmentAccountError
from app.services.portfolio import PortfolioService
from app.services.statistics import StatisticsService
from app.services.stock_charts import StockChartService
from app.services.stock_market import StockMarketService, naive
from app.services.stock_notes import StockNotesService
from app.services.stock_tracking import StockTrackingService, parse_interval
from app.services.user_context import UserContext
from tests.test_portfolio_service import FakeBroker, FakeModeService, FakeRegistry, account


class Registry(FakeRegistry):
    def __init__(self, accounts):
        super().__init__(accounts)
        self.discovered = self.accounts
        self.fail = False

    def sync_accounts(self):
        if self.fail:
            raise TimeoutError()
        return SimpleNamespace(accounts=self.discovered)

    def get_account_context(self, account_id):
        for context in self.accounts:
            if context.investment_account_id == account_id:
                return context
        raise UnknownInvestmentAccountError("Счёт недоступен.")


class Adapter:
    def __init__(self):
        self.calls, self.candle_calls = [], []
        self.trading, self.fail, self.candle_fail = True, False, False

    def quotes(self, token, keys, *, sandbox):
        self.calls.append((set(keys), sandbox))
        if self.fail:
            raise TimeoutError()
        return {key: {"price": 110, "previous_close": 100, "time": datetime.now(timezone.utc).isoformat(),
                      "trading": self.trading} for key in keys}

    def candles(self, token, key, interval, start, end, *, sandbox):
        self.candle_calls.append((key, interval))
        if self.candle_fail:
            raise TimeoutError()
        step = {"day": timedelta(days=1), "hour": timedelta(hours=1), "5min": timedelta(minutes=5)}[interval]
        return [PriceCandle(end - step * (100 - i), 100 + i, 102 + i, 99 + i, 101 + i, 1000 + i) for i in range(100)]


class StockFeatureTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.clock = datetime.now(timezone.utc).replace(microsecond=0)
        self.time_patch = patch("app.services.portfolio.utc_now", side_effect=lambda: naive(self.clock))
        self.time_patch.start()
        self.user = UserContext("user-1", "Test", 42, 0.3, ":memory:", sandbox_token="test-token")
        self.contexts = [account(1, "a", "Первый"), account(2, "b", "Второй")]
        with self.factory() as db:
            db.add(BrokerConnection(id=1, provider_key="tinvest", connection_key="default", display_name="Test"))
            for context in self.contexts:
                db.add(InvestmentAccount(id=context.investment_account_id, broker_connection_id=1,
                    external_account_id=context.external_account_id, display_name=context.account_name, status="OPEN"))
            db.commit()
        position = {"ticker": "SBER", "figi": "figi-sber", "instrument_uid": "uid-sber", "quantity": 2,
                    "average_position_price": 100, "current_price": 220, "current_price_one": 110, "name": "Сбер"}
        self.broker = FakeBroker(portfolios={"a": {"total_amount_portfolio": 300, "positions": [position]},
                                           "b": {"total_amount_portfolio": 500, "positions": [{**position, "quantity": 3, "current_price": 330}]}})
        self.registry = Registry(self.contexts)
        self.portfolio = PortfolioService(self.broker, FakeModeService(), lambda: "test-token",
            account_registry=self.registry, session_factory=self.factory)
        self.adapter = Adapter()
        self.market = StockMarketService(self.factory, self.user, self.portfolio, self.registry,
            adapter=self.adapter, index_client=Mock(), now_provider=lambda: self.clock)
        self.market.refresh(force=True)
        self.charts = StockChartService(self.market)
        self.text, self.photo = Mock(return_value=SimpleNamespace(message_id=7)), Mock(return_value=SimpleNamespace(message_id=8))
        self.tracking = StockTrackingService(self.market, self.charts, send_text=self.text, send_photo=self.photo)
        self.notes = StockNotesService(self.factory, self.user)

    def tearDown(self):
        self.time_patch.stop()
        self.engine.dispose()

    def advance(self, minutes=5):
        self.clock += timedelta(minutes=minutes)
        self.market.refresh(force=True)

    def test_current_stats_keep_accounts_separate_and_sum_unrealized_profit(self):
        view = StatisticsService(session_factory=self.factory, market_service=self.market).get_current_view(refresh=False)
        self.assertEqual(view.total_value, 800)
        self.assertEqual(view.unrealized_pnl, 50)
        self.assertFalse(view.partial)
        self.assertEqual([p.quantity for a in view.accounts for p in a.positions], [2, 3])

    def test_force_refresh_coalesces_and_quotes_are_batched_once_per_instrument(self):
        self.market.refresh(force=True)
        self.assertEqual(len(self.broker.portfolio_calls), 2)
        self.assertEqual(self.adapter.calls, [({"uid-sber"}, True)])
        self.clock += timedelta(seconds=61)
        self.market.poll()
        self.assertEqual(len(self.broker.portfolio_calls), 2)
        self.clock += timedelta(minutes=5)
        self.market.poll()
        self.assertEqual(len(self.broker.portfolio_calls), 4)

    def test_background_does_not_refresh_portfolio_when_exchange_closed(self):
        self.adapter.trading = False
        self.clock += timedelta(minutes=5)
        self.market.poll()
        self.assertEqual(len(self.broker.portfolio_calls), 2)

    def test_broker_error_keeps_last_snapshot_and_marks_partial(self):
        self.broker.failing_ids.add("a")
        self.advance()
        view = StatisticsService(session_factory=self.factory, market_service=self.market).get_current_view(refresh=False)
        self.assertTrue(view.partial)
        self.assertEqual(view.total_value, 800)
        self.assertEqual(len(view.accounts[0].positions), 1)

    def test_discovery_failure_marks_existing_accounts_stale(self):
        self.registry.fail = True
        self.advance()
        self.assertTrue(all(a.stale for a in self.market.snapshots()))

    def test_accounts_absent_from_successful_discovery_do_not_reappear_from_sqlite(self):
        self.registry.discovered = (self.contexts[1],)
        self.advance()
        self.assertEqual([a.account.investment_account_id for a in self.market.snapshots()], [2])

    def test_shared_notes_survive_position_close_and_enforce_user_ownership(self):
        note = self.notes.add("uid-sber", "SBER", "Мой тезис")
        other = StockNotesService(self.factory, UserContext("other", "Other", 99, 0, ":memory:"))
        self.assertEqual(other.list(), ())
        for action in (lambda: other.edit(note.id, "чужое"), lambda: other.delete(note.id)):
            with self.assertRaises(ValueError): action()
        self.broker.portfolios["a"]["positions"] = []
        self.advance()
        self.assertEqual(self.notes.list("uid-sber")[0].text, "Мой тезис")
        self.notes.edit(note.id, "Новый тезис")
        self.assertEqual(self.notes.get(note.id).text, "Новый тезис")
        self.notes.delete(note.id)
        self.assertEqual(self.notes.list(), ())

    def test_note_length_and_interval_validation(self):
        for text in ("", " " * 10, "x" * 3001):
            with self.assertRaises(ValueError): self.notes.add("uid-sber", "SBER", text)
        for text in ("4", "1441", "5.5", "-10", "oops", "True"):
            with self.assertRaises(ValueError): parse_interval(text)
        self.assertEqual(parse_interval("15 мин"), 15)
        self.assertEqual(parse_interval("1440"), 1440)

    def test_quote_freshness_rejects_stale_future_and_invalid_timestamps(self):
        for stamp in ("invalid", (self.clock - timedelta(minutes=5)).isoformat(), (self.clock + timedelta(minutes=5)).isoformat()):
            self.assertFalse(self.market.quote_is_current({"fetched_at": stamp}, self.clock))
        self.assertTrue(self.market.quote_is_current({"fetched_at": self.clock.isoformat()}, self.clock))

    def test_tracking_is_explicitly_account_scoped(self):
        a = self.tracking.configure(1, "uid-sber", interval_minutes=5)
        b = self.tracking.configure(2, "uid-sber", interval_minutes=30, chart_range="month")
        self.assertNotEqual(a.id, b.id)
        with self.assertRaises(UnknownInvestmentAccountError): self.tracking.configure(999, "uid-sber")
        with self.assertRaises(ValueError): self.tracking.configure(1, "foreign-uid")

    def test_tracking_delivers_graph_once_and_survives_restart(self):
        self.tracking.configure(1, "uid-sber", interval_minutes=5, chart_range="week")
        self.advance()
        self.tracking.run()
        self.assertEqual(self.photo.call_count, 1)
        self.assertEqual(self.photo.call_args.args[0], 42)
        self.assertTrue(self.photo.call_args.args[1].startswith(b"\x89PNG"))
        restarted = StockTrackingService(self.market, self.charts, send_photo=self.photo)
        restarted.run()
        self.assertEqual(self.photo.call_count, 1)
        self.assertEqual(restarted.get(1, "uid-sber").chart_range, "week")

    def test_closed_exchange_suppresses_messages_and_reopening_does_not_backfill(self):
        self.tracking.configure(1, "uid-sber", interval_minutes=5)
        self.adapter.trading = False
        self.advance(60)
        self.tracking.run()
        self.photo.assert_not_called()
        self.adapter.trading = True
        self.advance(10)
        self.tracking.run()
        self.assertEqual(self.photo.call_count, 1)
        self.tracking.run()
        self.assertEqual(self.photo.call_count, 1)

    def test_failed_quote_read_cannot_use_old_trading_status_to_send(self):
        self.tracking.configure(1, "uid-sber", interval_minutes=5)
        self.adapter.fail = True
        self.advance()
        self.tracking.run()
        self.photo.assert_not_called()

    def test_failed_account_read_does_not_pause_tracking(self):
        self.tracking.configure(1, "uid-sber", interval_minutes=5)
        self.broker.failing_ids.add("a")
        self.advance()
        self.tracking.run()
        self.assertEqual(self.tracking.get(1, "uid-sber").status, "active")
        self.text.assert_not_called()
        self.photo.assert_not_called()

    def test_closed_position_pauses_and_notifies_once(self):
        self.tracking.configure(1, "uid-sber", interval_minutes=5)
        self.broker.portfolios["a"]["positions"] = []
        self.advance()
        self.tracking.run()
        self.tracking.run()
        self.assertEqual(self.tracking.get(1, "uid-sber").status, "paused")
        self.assertEqual(self.text.call_count, 1)
        self.photo.assert_not_called()

    def test_pause_disable_and_resume_reset_schedule(self):
        self.tracking.configure(1, "uid-sber", interval_minutes=5)
        self.tracking.set_status(1, "uid-sber", "paused")
        self.advance()
        self.tracking.run()
        self.photo.assert_not_called()
        self.tracking.set_status(1, "uid-sber", "active")
        self.tracking.run()
        self.photo.assert_not_called()
        self.tracking.set_status(1, "uid-sber", "disabled")
        self.assertEqual(self.tracking.get(1, "uid-sber").status, "disabled")

    def test_ambiguous_delivery_is_not_replayed_and_does_not_advance_reference_price(self):
        self.tracking.configure(1, "uid-sber", interval_minutes=5)
        self.photo.side_effect = requests.Timeout()
        self.advance()
        self.tracking.run()
        self.tracking.run()
        self.assertEqual(self.photo.call_count, 1)
        with self.factory() as db:
            row = db.query(StockTracking).one()
            self.assertIsNone(row.last_sent_price)
            self.assertIn("не подтверждена", row.error_text)

    def test_chart_failure_falls_back_to_text(self):
        self.tracking.configure(1, "uid-sber", interval_minutes=5)
        self.adapter.candle_fail = True
        self.advance()
        self.tracking.run()
        self.text.assert_called_once()
        self.assertIn("График сейчас недоступен", self.text.call_args.args[1])

    def test_charts_use_warmed_history_and_distinct_intervals(self):
        position = self.market.position(1, "uid-sber")[1]
        for period, interval in (("day", "5min"), ("week", "hour"), ("month", "day")):
            chart = self.charts.render(position, period)
            self.assertTrue(chart.png_bytes.startswith(b"\x89PNG"))
            self.assertFalse(chart.stale)
            self.assertIn("ATR14", chart.summary)
            self.assertEqual(self.adapter.candle_calls[-1], ("uid-sber", interval))
        self.charts.render(position, "month")
        self.assertEqual(len(self.adapter.candle_calls), 3)

    def test_chart_failure_preserves_marked_cache(self):
        position = self.market.position(1, "uid-sber")[1]
        self.charts.render(position)
        self.adapter.candle_fail = True
        self.clock += timedelta(minutes=6)
        chart = self.charts.render(position)
        self.assertTrue(chart.stale)
        self.assertIn("Устаревший кэш", chart.summary)

    def test_index_compares_last_session_with_preceding_close_on_weekend(self):
        self.market.index_client.get_index_market_data.return_value = SimpleNamespace(errors=[], last=110, close=None,
            trade_date=datetime(2026, 10, 2).date(), as_of_date="2026-10-02")
        self.market.index_client.get_index_daily_candles_result.return_value = SimpleNamespace(candles=[
            SimpleNamespace(begin=datetime(2026, 10, 1), close=100)])
        self.market.refresh_index(now=datetime(2026, 10, 4, tzinfo=timezone.utc))
        kwargs = self.market.index_client.get_index_daily_candles_result.call_args.kwargs
        self.assertEqual(kwargs["till_date"].isoformat(), "2026-10-01")
        view = StatisticsService(session_factory=self.factory, market_service=self.market).get_current_view(refresh=False)
        self.assertAlmostEqual(view.index["change_pct"], 10)

    def test_short_history_is_labelled_and_does_not_invent_indicators(self):
        position = self.market.position(1, "uid-sber")[1]
        original = self.adapter.candles
        self.adapter.candles = lambda *args, **kwargs: original(*args, **kwargs)[-7:]
        chart = self.charts.render(position)
        self.assertIn("недостаточно истории", chart.summary.lower())
        self.assertTrue(chart.png_bytes.startswith(b"\x89PNG"))


class StockTelegramTests(unittest.TestCase):
    def test_scheduler_is_independent_and_coalesces_missed_ticks(self):
        from app.client.config import stock_scheduler as module
        services = SimpleNamespace(stock_market_service=Mock(), stock_tracking_service=Mock(), user=SimpleNamespace(user_id="user"))
        scheduler = Mock()
        config = SimpleNamespace(enabled_users=[SimpleNamespace(user_id="user", telegram_chat_id=42)])
        with patch.object(module, "stock_scheduler", None), \
             patch("apscheduler.schedulers.background.BackgroundScheduler", return_value=scheduler), \
             patch("app.client.config.users.load_runtime_users_config", return_value=config), \
             patch("app.client.handlers.user_context.get_telegram_services", return_value=services), \
             patch.dict("os.environ", {"ENABLE_BACKGROUND_SCHEDULERS": "false"}):
            module.configure_stock_scheduler()
        job = scheduler.add_job.call_args
        self.assertEqual(job.kwargs["minutes"], 1)
        self.assertEqual(job.kwargs["max_instances"], 1)
        self.assertTrue(job.kwargs["coalesce"])
        job.args[0]()
        services.stock_market_service.poll.assert_called_once()
        services.stock_tracking_service.run.assert_called_once()

    def test_unknown_account_callback_cannot_fetch_a_chart(self):
        from app.client.handlers.stocks import stock_handler as handler
        services = SimpleNamespace(account_registry=Mock(), stock_chart_service=Mock())
        services.account_registry.get_account_context.side_effect = UnknownInvestmentAccountError("Счёт недоступен.")
        with patch.object(handler, "get_telegram_services_or_notify", return_value=services), patch.object(handler, "bot"):
            handler.stock_action(SimpleNamespace(id="call", message=SimpleNamespace(chat=SimpleNamespace(id=42)), data="stk:graphs:999:uid"))
        services.stock_chart_service.render.assert_not_called()

    def test_graph_button_opens_month_and_offers_period_selection(self):
        from app.client.handlers.stocks import stock_handler as handler
        services = SimpleNamespace(stock_chart_service=Mock())
        services.stock_chart_service.render.return_value = SimpleNamespace(png_bytes=b"image", summary="summary")
        position = SimpleNamespace(ticker="SBER")
        with patch.object(handler, "bot") as bot:
            handler.send_stock_chart(42, services, position, 1, "uid")
        services.stock_chart_service.render.assert_called_once_with(position, "month")
        data = [row[0].callback_data for row in bot.send_photo.call_args.kwargs["reply_markup"].keyboard]
        self.assertEqual(data[:3], ["stk:g_day:1:uid", "stk:g_week:1:uid", "stk:g_month:1:uid"])

    def test_stock_command_requires_account_choice_for_duplicate_ticker(self):
        from app.client.handlers.stocks import stock_handler as handler
        position = SimpleNamespace(ticker="SBER", quantity=1, instrument_uid="uid", figi="figi")
        services = SimpleNamespace(stock_market_service=Mock())
        services.stock_market_service.snapshots.return_value = [
            SimpleNamespace(account=SimpleNamespace(investment_account_id=i, account_name=f"Счёт {i}"), positions=[position]) for i in (1, 2)]
        with patch.object(handler, "get_telegram_services_or_notify", return_value=services), patch.object(handler, "bot") as bot:
            handler.stock_command(SimpleNamespace(chat=SimpleNamespace(id=42), text="/stock SBER"))
            keyboard = bot.send_message.call_args.kwargs["reply_markup"]
            self.assertEqual([row[0].callback_data for row in keyboard.keyboard], ["stk:card:1:uid", "stk:card:2:uid"])

    def test_delete_note_requires_confirmation(self):
        from app.client.handlers.stocks import stock_handler as handler
        notes = Mock()
        notes.get.return_value = SimpleNamespace(id=7, instrument_key="uid")
        services = SimpleNamespace(stock_notes_service=notes)
        with patch.object(handler, "get_telegram_services_or_notify", return_value=services), patch.object(handler, "bot") as bot:
            handler.note_action(SimpleNamespace(id="call", message=SimpleNamespace(chat=SimpleNamespace(id=42)), data="note:delete:7"))
            notes.delete.assert_not_called()
            self.assertEqual(bot.send_message.call_args.kwargs["reply_markup"].keyboard[0][0].callback_data, "note:confirm:7")

    def test_long_statistics_split_with_keyboard_on_last_message(self):
        from app.client.handlers.stocks import stock_handler as handler
        with patch.object(handler, "bot") as bot:
            handler.send_long_text(42, "hello\n" * 2000, "keyboard")
            self.assertGreater(bot.send_message.call_count, 1)
            self.assertTrue(all(len(c.args[1]) <= 3900 for c in bot.send_message.call_args_list))
            self.assertEqual(bot.send_message.call_args.kwargs["reply_markup"], "keyboard")

    def test_new_background_services_have_no_execution_dependencies(self):
        root = Path(__file__).resolve().parents[1]
        paths = ["app/services/stock_market.py", "app/services/stock_tracking.py", "app/services/stock_charts.py", "app/integrations/stock_market.py"]
        for path in paths:
            tree = ast.parse((root / path).read_text(encoding="utf-8"))
            names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
            self.assertFalse(names & {"post_order", "post_stop_order", "post_sandbox_order", "execute", "confirm"})


class StockAdapterTests(unittest.TestCase):
    def test_same_session_close_is_not_used_as_daily_reference(self):
        now = datetime.now(timezone.utc)
        row = SimpleNamespace(instrument_uid="uid", figi="figi", price=SimpleNamespace(units=110, nano=0),
                              time=now, trading_status=5)
        client = Mock()
        client.market_data.get_last_prices.return_value.last_prices = [row]
        client.market_data.get_trading_statuses.return_value.trading_statuses = [row]
        client.market_data.get_close_prices.return_value.close_prices = [row]
        client.get_all_candles.return_value = [SimpleNamespace(time=now - timedelta(days=1), is_complete=True,
            close=SimpleNamespace(units=100, nano=0))]
        factory = Mock()
        factory.return_value.__enter__ = Mock(return_value=client)
        factory.return_value.__exit__ = Mock(return_value=False)
        adapter = StockMarketAdapter(factory)
        self.assertEqual(adapter.quotes("test", ["uid"], sandbox=True)["uid"]["previous_close"], 100)
        adapter.quotes("test", ["uid"], sandbox=True)
        self.assertEqual(client.get_all_candles.call_count, 1)

    def test_exchange_quotes_use_read_only_batches_and_explicit_sandbox(self):
        row = SimpleNamespace(instrument_uid="uid", figi="figi", price=SimpleNamespace(units=110, nano=0),
                              time=datetime.now(timezone.utc), trading_status=5)
        client = Mock()
        client.market_data.get_last_prices.return_value.last_prices = [row]
        client.market_data.get_trading_statuses.return_value.trading_statuses = [row]
        client.market_data.get_close_prices.return_value.close_prices = [row]
        factory = Mock()
        factory.return_value.__enter__ = Mock(return_value=client)
        factory.return_value.__exit__ = Mock(return_value=False)
        result = StockMarketAdapter(factory).quotes("test-token", ["uid", "uid"], sandbox=True)
        self.assertEqual(result["uid"]["price"], 110)
        self.assertTrue(result["uid"]["trading"])
        factory.assert_called_once_with("test-token", sandbox=True)
        self.assertEqual(client.market_data.get_last_prices.call_args.kwargs["instrument_id"], ["uid"])

    def test_sdk_candles_exclude_incomplete_and_invalid_prices(self):
        price = SimpleNamespace(units=100, nano=0)
        zero = SimpleNamespace(units=0, nano=0)
        row = dict(time=datetime.now(timezone.utc), open=price, high=price, low=price, close=price, volume=10)
        client = Mock()
        client.get_all_candles.return_value = [SimpleNamespace(**row, is_complete=True),
            SimpleNamespace(**row, is_complete=False), SimpleNamespace(**{**row, "low": zero}, is_complete=True)]
        factory = Mock()
        factory.return_value.__enter__ = Mock(return_value=client)
        factory.return_value.__exit__ = Mock(return_value=False)
        candles = StockMarketAdapter(factory).candles("test", "uid", "5min", row["time"] - timedelta(hours=1), row["time"], sandbox=True)
        self.assertEqual(len(candles), 1)


class StockMigrationTests(unittest.TestCase):
    def test_migration_preserves_digest_payload_and_monitoring_preferences(self):
        from alembic import command
        from alembic.config import Config
        with TemporaryDirectory() as directory:
            path = Path(directory) / "database.db"
            config = Config("alembic.ini")
            config.set_main_option("sqlalchemy.url", "sqlite:///" + path.as_posix())
            command.upgrade(config, "e8f1a6b72d40")
            engine = create_engine("sqlite:///" + path.as_posix())
            try:
                with engine.begin() as db:
                    db.execute(text("INSERT INTO monitoring_preferences (id, alerts_enabled, digest_enabled, digest_time) VALUES (1,1,1,'09:30')"))
                    db.execute(text("INSERT INTO digest_deliveries (report_date,payload_json,ambiguous,created_at) VALUES ('2026-10-08','stored-payload',0,'2026-10-08')"))
                command.upgrade(config, "head")
                with engine.connect() as db:
                    self.assertEqual(db.execute(text("SELECT digest_time FROM monitoring_preferences")).scalar_one(), "09:30")
                    self.assertEqual(db.execute(text("SELECT payload_json FROM digest_deliveries")).scalar_one(), "stored-payload")
                    self.assertEqual(db.execute(text("PRAGMA integrity_check")).scalar_one(), "ok")
                    self.assertEqual(db.execute(text("SELECT version_num FROM alembic_version")).scalar_one(), "f9a2b7c83e51")
            finally:
                engine.dispose()
