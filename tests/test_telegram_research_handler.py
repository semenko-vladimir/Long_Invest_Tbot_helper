import ast
from datetime import datetime
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


os.environ["BOT_TOKEN"] = "123456:TEST"

from app.client.handlers.research import research_handler
from app.research.schemas import (
    AdapterResult,
    DataGap,
    InstrumentIdentity,
    MarketSnapshot,
    ResearchReport,
    SourceFreshness,
)
from app.research.services import ResearchReportService, TickerResearchService


class FakeMessage:
    def __init__(self, text: str, chat_id: int = 42):
        self.text = text
        self.chat = SimpleNamespace(id=chat_id)


class SuccessfulAdapter:
    source_name = "fake-source"

    def __init__(self):
        self.calls = []

    def fetch(self, ticker: str) -> AdapterResult:
        self.calls.append(("fetch", ticker))
        fetched_at = datetime(2026, 5, 4, 12, 0)
        return AdapterResult(
            source_name=self.source_name,
            data={
                "instrument_identity": InstrumentIdentity(
                    ticker=ticker,
                    figi="FIGI-SBER",
                    name="Sber",
                    currency="RUB",
                ),
                "market_snapshot": MarketSnapshot(
                    current_price=101.5,
                    currency="RUB",
                    captured_at=fetched_at,
                ),
            },
            freshness=SourceFreshness(source_name=self.source_name, fetched_at=fetched_at),
            gaps=[DataGap("financials", "Financial source is not configured.", "medium")],
            errors=["Optional source unavailable."],
        )

    def place_order(self, *args, **kwargs):
        raise AssertionError("Research handler must not place broker orders.")


class TelegramResearchHandlerTests(unittest.TestCase):
    def build_services(self, adapter):
        now = datetime(2026, 5, 4, 12, 30)
        return research_handler.TelegramResearchServices(
            ticker_research=TickerResearchService([adapter], now_provider=lambda: now),
            report_builder=ResearchReportService(now_provider=lambda: now),
        )

    def test_research_command_missing_ticker_shows_usage_without_building_report(self):
        with patch.object(research_handler, "get_telegram_research_services") as get_services:
            with patch.object(
                research_handler.bot,
                "send_message",
                return_value=SimpleNamespace(message_id=100),
            ) as send_message:
                research_handler.research_command_handler(FakeMessage("/research"))

        get_services.assert_not_called()
        text = send_message.call_args.kwargs["text"]
        self.assertIn("/research SBER", text)
        self.assertIn("research SBER", text)
        self.assertIn("not a trading signal", text)
        self.assertIn("never creates or prepares broker orders", text)

    def test_research_command_returns_compact_read_only_summary(self):
        adapter = SuccessfulAdapter()
        services = self.build_services(adapter)

        with patch.object(research_handler, "get_telegram_research_services", return_value=services):
            with patch.object(
                research_handler.bot,
                "send_message",
                return_value=SimpleNamespace(message_id=101),
            ) as send_message:
                research_handler.research_command_handler(FakeMessage("/research sber"))

        self.assertEqual(adapter.calls, [("fetch", "SBER")])
        text = send_message.call_args.kwargs["text"]
        self.assertIn("Read-only research: SBER", text)
        self.assertIn("Ticker: SBER", text)
        self.assertIn("Sources: fake-source", text)
        self.assertIn("Instrument identity:", text)
        self.assertIn("FIGI-SBER", text)
        self.assertIn("Market snapshot:", text)
        self.assertIn("101.5 RUB", text)
        self.assertIn("Data gaps:", text)
        self.assertIn("financials (medium)", text)
        self.assertIn("Errors:", text)
        self.assertIn("Optional source unavailable.", text)
        self.assertIn("not a trading signal", text)
        self.assertIn("must not trigger broker orders", text)
        for forbidden_rating in ("BUY", "HOLD", "SELL", "WATCH", "AVOID"):
            self.assertNotIn(forbidden_rating, text)

    def test_plain_text_research_command_is_supported(self):
        adapter = SuccessfulAdapter()
        services = self.build_services(adapter)

        with patch.object(research_handler, "get_telegram_research_services", return_value=services):
            with patch.object(
                research_handler.bot,
                "send_message",
                return_value=SimpleNamespace(message_id=102),
            ) as send_message:
                research_handler.research_text_command_handler(FakeMessage("research sber"))

        self.assertEqual(adapter.calls, [("fetch", "SBER")])
        self.assertIn("Ticker: SBER", send_message.call_args.kwargs["text"])

    def test_research_command_parsers(self):
        self.assertEqual(research_handler.parse_research_command_argument("/research@LocalBot SBER"), "SBER")
        self.assertEqual(research_handler.parse_research_command_argument("/research"), "")
        self.assertIsNone(research_handler.parse_research_command_argument("/start"))
        self.assertEqual(research_handler.parse_research_text_command("research SBER"), "SBER")
        self.assertEqual(research_handler.parse_research_text_command("research"), "")
        self.assertIsNone(research_handler.parse_research_text_command("buy SBER 1"))

    def test_formatter_includes_no_data_gap_and_error_placeholders(self):
        report = ResearchReport(
            ticker="SBER",
            generated_at=datetime(2026, 5, 4, 12, 30),
            sources=["fake-source"],
        )

        text = research_handler.format_research_report(report)

        self.assertIn("Instrument identity: unavailable.", text)
        self.assertIn("Company profile: unavailable.", text)
        self.assertIn("Sector/industry: unavailable.", text)
        self.assertIn("Financials: unavailable.", text)
        self.assertIn("Market snapshot: unavailable.", text)
        self.assertIn("Data gaps: none reported.", text)
        self.assertIn("Errors: none reported.", text)

    def test_formatter_includes_available_profile_and_sector_fields(self):
        report = ResearchReport(
            ticker="SBER",
            generated_at=datetime(2026, 5, 4, 12, 30),
            sources=["local-fundamentals"],
            company_profile={"name": "Sberbank of Russia PJSC", "country": "Russia"},
            sector_industry={"sector": "Financials", "industry": "Banks"},
            financials={"reporting_currency": "RUB"},
        )

        text = research_handler.format_research_report(report)

        self.assertIn("Company profile:", text)
        self.assertIn("name: Sberbank of Russia PJSC", text)
        self.assertIn("Sector/industry:", text)
        self.assertIn("sector: Financials", text)
        self.assertIn("Financials:", text)
        self.assertIn("reporting currency: RUB", text)
        for forbidden_rating in ("BUY", "HOLD", "SELL", "WATCH", "AVOID"):
            self.assertNotIn(forbidden_rating, text)

    def test_formatter_includes_compact_market_context_without_rating(self):
        report = ResearchReport(
            ticker="SBER",
            generated_at=datetime(2026, 5, 4, 12, 30),
            sources=["market-context"],
            market_context={
                "source": "MOEX ISS",
                "period": "month",
                "indexes": [
                    {
                        "ticker": "IMOEX",
                        "latest_close": 3200.0,
                        "recent_change_pct": 1.5,
                        "as_of_date": "2026-05-03",
                    },
                    {
                        "ticker": "RTSI",
                        "latest_close": None,
                        "recent_change_pct": None,
                    },
                ],
            },
        )

        text = research_handler.format_research_report(report)

        self.assertIn("Market context:", text)
        self.assertIn("IMOEX: close 3200", text)
        self.assertIn("+1.50% over month", text)
        self.assertIn("as of 2026-05-03", text)
        self.assertIn("RTSI: unavailable", text)
        self.assertIn("Source: MOEX ISS", text)
        for forbidden_rating in ("BUY", "HOLD", "SELL", "WATCH", "AVOID"):
            self.assertNotIn(forbidden_rating, text)

    def test_telegram_research_handler_imports_no_order_signal_or_llm_modules(self):
        forbidden_prefixes = (
            "app.services.orders",
            "app.client.orders",
            "app.client.handlers.orders",
            "app.client.handlers.signals",
            "app.client.handlers.mls",
            "app.client.signals",
            "app.client.strategy",
            "app.client.api.signals_client",
            "app.client.api.strategy_client",
            "keras",
            "tensorflow",
            "g4f",
        )
        forbidden_names = {"OrderService", "manual_order_handler", "place_order", "post_order"}
        handler_path = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "client"
            / "handlers"
            / "research"
            / "research_handler.py"
        )
        tree = ast.parse(handler_path.read_text(encoding="utf-8"))

        imported_modules = set()
        imported_names = set()
        attribute_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
                imported_names.update(alias.asname or alias.name.split(".")[-1] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
                imported_names.update(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, ast.Attribute):
                attribute_names.add(node.attr)

        forbidden_imports = sorted(
            module
            for module in imported_modules
            if any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden_prefixes)
        )

        self.assertEqual(forbidden_imports, [])
        self.assertEqual(forbidden_names.intersection(imported_names), set())
        self.assertEqual({"place_order", "post_order"}.intersection(attribute_names), set())


if __name__ == "__main__":
    unittest.main()
