import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app.backend.main_api import app
from app.charts.analytics import ChartAnalyticsService
from app.charts.schemas import ChartHistory, PriceCandle
from app.services.mode import ModeContext


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-chart"


class FakeChartImageService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def render_png(self, ticker, range_name, include_analytics=True, mode="price"):
        self.calls.append((ticker, range_name, include_analytics, mode))
        return self.result


class RaisingChartImageService:
    def render_png(self, ticker, range_name, include_analytics=True, mode="price"):
        raise RuntimeError(f"render failed for {ticker} {range_name}")


class FakeChartSnapshotService:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def get_snapshot(self, ticker, range_name, interval_name="auto", refresh=True):
        self.calls.append((ticker, range_name, interval_name, refresh))
        if self.result is not None:
            return self.result

        candles = [
            PriceCandle(
                time=datetime(2026, 5, 1, 10, 0),
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=1000,
            ),
            PriceCandle(
                time=datetime(2026, 5, 2, 10, 0),
                open=101.0,
                high=104.0,
                low=100.0,
                close=103.0,
                volume=1200,
            ),
        ]
        history = ChartHistory(
            ticker=ticker,
            figi=f"FIGI-{ticker}",
            range=range_name,
            interval="day",
            candles=candles,
            generated_at=datetime(2026, 5, 2, 10, 1),
            source="fake-market-data",
            fetched_at=datetime(2026, 5, 2, 10, 0),
            as_of_date="2026-05-02",
            freshness="current_or_latest",
            delay_status="broker_api",
            data_gaps=[],
            errors=[],
        )
        return SimpleNamespace(
            ok=True,
            history=history,
            analytics=ChartAnalyticsService().calculate(candles),
            interval="day",
            cache_candle_count=2,
            refreshed=True,
        )


def chart_result(**overrides):
    values = {
        "ok": True,
        "png_bytes": PNG_BYTES,
        "content_type": "image/png",
        "errors": [],
        "data_gaps": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class WebChartsTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def mode(self):
        return ModeContext(
            mode="sandbox",
            is_sandbox=True,
            prod_trading_allowed=False,
            trading_available=True,
            banner_title="Mode: sandbox",
            banner_message="Sandbox mode.",
        )

    def portfolio_view(self, positions=None):
        return SimpleNamespace(
            positions=list(
                positions
                if positions is not None
                else [
                    SimpleNamespace(
                        ticker="SBER",
                        name="Sber",
                        quantity=10.0,
                        quantity_display="10.00",
                    )
                ]
            ),
            empty=False,
            error=None,
        )

    def services(self, chart_image_service=None, portfolio_view=None, chart_snapshot_service=None):
        return SimpleNamespace(
            user=SimpleNamespace(display_name="Test User", user_id="test", db_path=":memory:"),
            mode_service=SimpleNamespace(current=self.mode),
            chart_image_service=chart_image_service or FakeChartImageService(chart_result()),
            chart_snapshot_service=chart_snapshot_service or FakeChartSnapshotService(),
            portfolio_service=SimpleNamespace(get_portfolio_view=lambda: portfolio_view or self.portfolio_view()),
        )

    def test_charts_page_returns_html_with_mode_range_and_portfolio_ticker_controls(self):
        with mock.patch("app.backend.web.chart_routes.get_web_services", return_value=self.services()):
            response = self.client.get("/charts")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('name="ticker"', response.text)
        self.assertIn('list="portfolio-ticker-options"', response.text)
        self.assertIn('<option value="SBER">Sber - 10.00</option>', response.text)
        self.assertIn('name="mode"', response.text)
        self.assertIn('value="price"', response.text)
        self.assertIn('value="position_value"', response.text)
        self.assertIn("Price chart", response.text)
        self.assertIn("Current quantity value chart", response.text)
        self.assertIn('name="range"', response.text)
        self.assertIn('name="analytics"', response.text)
        self.assertIn('value="0"', response.text)
        self.assertIn('value="1"', response.text)
        self.assertIn("Hindsight-only analytics", response.text)
        self.assertIn('value="day"', response.text)
        self.assertIn('value="six_months"', response.text)
        self.assertIn('value="all"', response.text)
        self.assertIn("Read-only educational chart", response.text)
        self.assertIn("Not a trading signal", response.text)

    def test_charts_page_with_ticker_includes_png_image_url(self):
        with mock.patch("app.backend.web.chart_routes.get_web_services", return_value=self.services()):
            response = self.client.get("/charts?ticker=sber&range=month")

        self.assertEqual(response.status_code, 200)
        self.assertIn('/charts/SBER.png?range=month&amp;mode=price&amp;analytics=1', response.text)
        self.assertIn('/charts/SBER.json?range=month&amp;interval=auto&amp;analytics=1', response.text)
        self.assertIn("data-chart-data-status", response.text)
        self.assertIn("Hindsight-only analytics are educational diagnostics", response.text)

    def test_charts_page_with_analytics_disabled_preserves_png_image_url_flag(self):
        with mock.patch("app.backend.web.chart_routes.get_web_services", return_value=self.services()):
            response = self.client.get("/charts?ticker=sber&range=month&analytics=0")

        self.assertEqual(response.status_code, 200)
        self.assertIn('/charts/SBER.png?range=month&amp;mode=price&amp;analytics=0', response.text)
        self.assertNotIn('id="chart-analytics" type="checkbox" name="analytics" value="1" checked', response.text)

    def test_charts_page_position_value_mode_includes_limitation_notice(self):
        with mock.patch("app.backend.web.chart_routes.get_web_services", return_value=self.services()):
            response = self.client.get("/charts?ticker=sber&range=month&mode=position_value")

        self.assertEqual(response.status_code, 200)
        self.assertIn('/charts/SBER.png?range=month&amp;mode=position_value&amp;analytics=0', response.text)
        self.assertIn("current position quantity valued at historical close prices", response.text)
        self.assertIn("not historical holdings", response.text)

    def test_chart_png_returns_image_bytes(self):
        fake_chart_service = FakeChartImageService(chart_result())
        with mock.patch(
            "app.backend.web.chart_routes.get_web_services",
            return_value=self.services(fake_chart_service),
        ):
            response = self.client.get("/charts/SBER.png?range=month")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.content, PNG_BYTES)
        self.assertEqual(fake_chart_service.calls, [("SBER", "month", True, "price")])

    def test_chart_json_returns_candles_metrics_and_metadata(self):
        snapshot_service = FakeChartSnapshotService()
        with mock.patch(
            "app.backend.web.chart_routes.get_web_services",
            return_value=self.services(chart_snapshot_service=snapshot_service),
        ):
            response = self.client.get("/charts/SBER.json?range=month")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["ticker"], "SBER")
        self.assertEqual(payload["interval"], "day")
        self.assertEqual(payload["cache"]["candle_count"], 2)
        self.assertIn("data_status", payload)
        self.assertEqual(payload["data_status"]["source"], "fake-market-data")
        self.assertEqual(payload["data_status"]["delay_status"], "broker_api")
        self.assertIn("refresh", payload)
        self.assertTrue(payload["educational_only"])
        self.assertTrue(payload["analytics"]["educational_only"])
        self.assertEqual(len(payload["candles"]), 2)
        metric_keys = {metric["key"] for metric in payload["analytics"]["metrics"]}
        self.assertIn("range_return_pct", metric_keys)
        self.assertIn("max_drawdown_pct", metric_keys)
        self.assertEqual(snapshot_service.calls, [("SBER", "month", "day", True)])

    def test_chart_json_forwards_disabled_refresh_and_analytics_flags(self):
        snapshot_service = FakeChartSnapshotService()
        with mock.patch(
            "app.backend.web.chart_routes.get_web_services",
            return_value=self.services(chart_snapshot_service=snapshot_service),
        ):
            response = self.client.get("/charts/SBER.json?range=month&analytics=0&refresh=0")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["analytics"]["metrics"][0]["display"], "n/a")
        self.assertEqual(snapshot_service.calls, [("SBER", "month", "day", False)])

    def test_chart_png_forwards_disabled_analytics_flag(self):
        fake_chart_service = FakeChartImageService(chart_result())
        with mock.patch(
            "app.backend.web.chart_routes.get_web_services",
            return_value=self.services(fake_chart_service),
        ):
            response = self.client.get("/charts/SBER.png?range=month&analytics=0")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_chart_service.calls, [("SBER", "month", False, "price")])

    def test_chart_png_forwards_position_value_mode_without_analytics(self):
        fake_chart_service = FakeChartImageService(chart_result())
        with mock.patch(
            "app.backend.web.chart_routes.get_web_services",
            return_value=self.services(fake_chart_service),
        ):
            response = self.client.get("/charts/SBER.png?range=month&mode=position_value&analytics=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_chart_service.calls, [("SBER", "month", False, "position_value")])

    def test_position_value_png_non_portfolio_ticker_returns_clear_400(self):
        fake_chart_service = FakeChartImageService(
            chart_result(
                ok=False,
                png_bytes=None,
                errors=[
                    "Ticker SBER is not in the current portfolio; current quantity value chart requires an open position."
                ],
            )
        )
        with mock.patch(
            "app.backend.web.chart_routes.get_web_services",
            return_value=self.services(fake_chart_service),
        ):
            response = self.client.get("/charts/SBER.png?range=month&mode=position_value")

        self.assertEqual(response.status_code, 400)
        self.assertIn("not in the current portfolio", response.text)
        self.assertIn("current position quantity valued at historical close prices", response.text)
        self.assertIn("no broker orders were created", response.text)

    def test_chart_png_invalid_range_returns_plain_text_400(self):
        response = self.client.get("/charts/SBER.png?range=intraday")

        self.assertEqual(response.status_code, 400)
        self.assertIn("text/plain", response.headers["content-type"])
        self.assertIn("Unsupported chart range", response.text)
        self.assertIn("Read-only educational chart", response.text)
        self.assertIn("Hindsight-only analytics", response.text)
        self.assertIn("Not a trading signal", response.text)
        self.assertIn("No broker orders were created", response.text)

    def test_chart_png_invalid_analytics_returns_plain_text_400(self):
        response = self.client.get("/charts/SBER.png?range=month&analytics=maybe")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported analytics option", response.text)
        self.assertIn("Use analytics=1 or analytics=0", response.text)
        self.assertIn("No broker orders were created", response.text)

    def test_chart_png_service_error_returns_plain_text_400(self):
        fake_chart_service = FakeChartImageService(
            chart_result(ok=False, png_bytes=None, errors=["No candles are available for chart rendering."])
        )
        with mock.patch(
            "app.backend.web.chart_routes.get_web_services",
            return_value=self.services(fake_chart_service),
        ):
            response = self.client.get("/charts/SBER.png?range=month")

        self.assertEqual(response.status_code, 400)
        self.assertIn("No candles are available", response.text)
        self.assertIn("Not investment advice", response.text)

    def test_chart_png_generation_exception_returns_plain_text_400(self):
        with mock.patch(
            "app.backend.web.chart_routes.get_web_services",
            return_value=self.services(RaisingChartImageService()),
        ):
            response = self.client.get("/charts/SBER.png?range=month")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Chart could not be generated", response.text)
        self.assertIn("render failed", response.text)
        self.assertIn("No broker orders were created", response.text)

    def test_chart_web_routes_import_no_order_signal_or_rating_modules(self):
        forbidden_prefixes = (
            "app.services.orders",
            "app.client.handlers.orders",
            "app.client.handlers.signals",
            "app.client.signals",
            "app.client.strategy",
        )
        forbidden_names = {"OrderService", "place_order", "post_order", "BUY", "SELL", "HOLD", "WATCH", "AVOID"}
        route_path = Path(__file__).resolve().parents[1] / "app" / "backend" / "web" / "chart_routes.py"
        tree = ast.parse(route_path.read_text(encoding="utf-8"))

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
