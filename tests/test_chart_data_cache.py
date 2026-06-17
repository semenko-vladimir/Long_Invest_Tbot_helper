from datetime import datetime, timedelta
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.backend.models.database import Base
from app.data_sources.schemas import DATA_SOURCE_MOEX_ISS, DATA_SOURCE_T_INVEST
from app.charts.adapters import FallbackChartDataAdapter
from app.charts.repository import PriceCandleRepository
from app.charts.schemas import ChartAdapterResult, ChartDataGap, PriceCandle
from app.charts.services import ChartHistoryService
from app.charts.snapshots import ChartDataRefreshService, ChartSnapshotService


def candle(day: int, close: float) -> PriceCandle:
    return PriceCandle(
        time=datetime(2026, 5, 1, 10, 0) + timedelta(days=day - 1),
        open=close - 1,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=day * 100,
    )


class FakeIncrementalAdapter:
    source_name = "fake-market-data"

    def __init__(self):
        self.fetch_calls = []
        self.since_calls = []
        self.full_candles = [candle(1, 100.0), candle(2, 102.0)]
        self.incremental_candles = [candle(2, 103.0), candle(3, 104.0)]

    def fetch_candles(self, ticker, range_name):
        self.fetch_calls.append((ticker, range_name))
        return ChartAdapterResult(
            source_name=self.source_name,
            ticker=ticker,
            figi=f"FIGI-{ticker}",
            fetched_at=datetime(2026, 5, 3, 10, 0),
            as_of_date="2026-05-02",
            freshness="current_or_latest",
            delay_status="broker_api",
            candles=list(self.full_candles),
            interval="day",
        )

    def fetch_candles_since(self, ticker, range_name, since):
        self.since_calls.append((ticker, range_name, since))
        return ChartAdapterResult(
            source_name=self.source_name,
            ticker=ticker,
            figi=f"FIGI-{ticker}",
            fetched_at=datetime(2026, 5, 3, 10, 1),
            as_of_date="2026-05-03",
            freshness="current_or_latest",
            delay_status="broker_api",
            candles=list(self.incremental_candles),
            interval="day",
        )


class StaticChartAdapter:
    def __init__(self, result):
        self.source_name = result.source_name
        self.result = result
        self.calls = []

    def fetch_candles(self, ticker, range_name):
        self.calls.append((ticker, range_name))
        return self.result


class FailingChartAdapter:
    source_name = "failing-market-data"

    def fetch_candles(self, ticker, range_name):
        raise RuntimeError("market data unavailable")


class ChartDataCacheTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_repository_upserts_candles_by_ticker_interval_and_time(self):
        repository = PriceCandleRepository(self.SessionLocal)
        repository.upsert_candles(
            ticker="sber",
            interval="day",
            candles=[candle(1, 100.0)],
            source="unit-source",
            figi="FIGI-SBER",
            fetched_at=datetime(2026, 5, 2, 10, 0),
        )
        repository.upsert_candles(
            ticker="SBER",
            interval="day",
            candles=[candle(1, 105.0)],
            source="unit-source",
            figi="FIGI-SBER",
            fetched_at=datetime(2026, 5, 2, 10, 1),
        )

        candles = repository.list_candles(ticker="SBER", interval="day")

        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].close, 105.0)
        metadata = repository.metadata(ticker="SBER", interval="day")
        self.assertEqual(metadata.candle_count, 1)
        self.assertEqual(metadata.source, "unit-source")

    def test_refresh_uses_incremental_fetch_after_cache_has_latest_candle(self):
        adapter = FakeIncrementalAdapter()
        repository = PriceCandleRepository(self.SessionLocal)
        history_service = ChartHistoryService(
            adapter=adapter,
            now_provider=lambda: datetime(2026, 5, 3, 10, 0),
        )
        refresh_service = ChartDataRefreshService(
            history_service=history_service,
            repository=repository,
            now_provider=lambda: datetime(2026, 5, 3, 10, 1),
        )

        refresh_service.refresh_ticker("SBER", "month")
        refresh_service.refresh_ticker("SBER", "month")

        self.assertEqual(adapter.fetch_calls, [("SBER", "month")])
        self.assertEqual(len(adapter.since_calls), 1)
        self.assertEqual(adapter.since_calls[0][2], candle(2, 102.0).time)
        candles = repository.list_candles(ticker="SBER", interval="day")
        self.assertEqual([item.close for item in candles], [100.0, 103.0, 104.0])

    def test_snapshot_reads_cached_candles_and_returns_analytics(self):
        adapter = FakeIncrementalAdapter()
        repository = PriceCandleRepository(self.SessionLocal)
        history_service = ChartHistoryService(
            adapter=adapter,
            now_provider=lambda: datetime(2026, 5, 3, 10, 0),
        )
        refresh_service = ChartDataRefreshService(
            history_service=history_service,
            repository=repository,
            now_provider=lambda: datetime(2026, 5, 3, 10, 1),
        )
        snapshot_service = ChartSnapshotService(
            history_service=history_service,
            repository=repository,
            refresh_service=refresh_service,
            now_provider=lambda: datetime(2026, 5, 3, 10, 2),
        )

        snapshot = snapshot_service.get_snapshot("sber", "month")

        self.assertTrue(snapshot.ok)
        self.assertTrue(snapshot.refreshed)
        self.assertEqual(snapshot.history.ticker, "SBER")
        self.assertEqual(snapshot.interval, "day")
        self.assertEqual(len(snapshot.history.candles), 2)
        self.assertAlmostEqual(snapshot.analytics.range_return_pct, 2.0)
        self.assertEqual(snapshot.data_status.source, "fake-market-data")
        self.assertEqual(snapshot.data_status.freshness, "current")
        self.assertEqual(snapshot.data_status.delay_status, "broker_api")
        self.assertTrue(snapshot.educational_only)
        self.assertTrue(snapshot.cache.used)
        self.assertTrue(snapshot.cache.refreshed)
        self.assertTrue(snapshot.refresh_status.attempted)

    def test_snapshot_uses_moex_status_when_tinvest_falls_back_to_moex(self):
        primary = StaticChartAdapter(
            ChartAdapterResult(
                source_name=DATA_SOURCE_T_INVEST,
                ticker="SBER",
                data_gaps=[ChartDataGap("authentication", "No T-Invest token.", "high")],
                errors=["No T-Invest token is configured."],
            )
        )
        fallback = StaticChartAdapter(
            ChartAdapterResult(
                source_name=DATA_SOURCE_MOEX_ISS,
                ticker="SBER",
                fetched_at=datetime(2026, 5, 3, 10, 0),
                as_of_date="2026-05-02",
                freshness="delayed_public_data",
                delay_status="delayed_public_iss",
                candles=[candle(1, 100.0), candle(2, 102.0)],
                interval="day",
            )
        )
        history_service = ChartHistoryService(
            adapter=FallbackChartDataAdapter(primary=primary, fallback=fallback),
            now_provider=lambda: datetime(2026, 5, 3, 10, 1),
        )
        snapshot_service = ChartSnapshotService(
            history_service=history_service,
            now_provider=lambda: datetime(2026, 5, 3, 10, 2),
        )

        snapshot = snapshot_service.get_snapshot("sber", "month", refresh=False)

        self.assertTrue(snapshot.ok)
        self.assertEqual(snapshot.data_status.source, "MOEX ISS")
        self.assertEqual(snapshot.data_status.delay_status, "moex_delayed")
        self.assertIn(snapshot.data_status.freshness, {"current", "latest_available"})
        self.assertTrue(any(gap.category == "source_fallback" for gap in snapshot.history.data_gaps))

    def test_snapshot_uses_stale_local_cache_when_live_refresh_fails(self):
        repository = PriceCandleRepository(self.SessionLocal)
        repository.upsert_candles(
            ticker="SBER",
            interval="day",
            candles=[candle(1, 100.0), candle(2, 102.0)],
            source="fake-market-data",
            fetched_at=datetime(2026, 5, 2, 10, 0),
            as_of_date="2026-05-02",
            freshness="current",
            delay_status="broker_api",
        )
        history_service = ChartHistoryService(
            adapter=FailingChartAdapter(),
            now_provider=lambda: datetime(2026, 5, 3, 10, 0),
        )
        refresh_service = ChartDataRefreshService(
            history_service=history_service,
            repository=repository,
            now_provider=lambda: datetime(2026, 5, 3, 10, 1),
        )
        snapshot_service = ChartSnapshotService(
            history_service=history_service,
            repository=repository,
            refresh_service=refresh_service,
            now_provider=lambda: datetime(2026, 5, 3, 10, 2),
        )

        snapshot = snapshot_service.get_snapshot("SBER", "month")

        self.assertTrue(snapshot.ok)
        self.assertEqual(snapshot.history.errors, [])
        self.assertEqual(snapshot.data_status.source, "local cache")
        self.assertEqual(snapshot.data_status.freshness, "stale")
        self.assertEqual(snapshot.data_status.delay_status, "cached")
        self.assertTrue(any(gap.category == "local_cache" for gap in snapshot.history.data_gaps))
        self.assertTrue(snapshot.refresh_status.errors)

    def test_snapshot_marks_no_refresh_cache_as_cached_delay(self):
        repository = PriceCandleRepository(self.SessionLocal)
        repository.upsert_candles(
            ticker="SBER",
            interval="day",
            candles=[candle(1, 100.0), candle(2, 102.0)],
            source="fake-market-data",
            fetched_at=datetime(2026, 5, 3, 10, 0),
            as_of_date="2026-05-02",
            freshness="current",
            delay_status="broker_api",
        )
        history_service = ChartHistoryService(
            adapter=FailingChartAdapter(),
            now_provider=lambda: datetime(2026, 5, 3, 10, 0),
        )
        snapshot_service = ChartSnapshotService(
            history_service=history_service,
            repository=repository,
            now_provider=lambda: datetime(2026, 5, 3, 10, 2),
        )

        snapshot = snapshot_service.get_snapshot("SBER", "month", refresh=False)

        self.assertTrue(snapshot.ok)
        self.assertEqual(snapshot.data_status.source, "local cache")
        self.assertEqual(snapshot.data_status.delay_status, "cached")
        self.assertEqual(snapshot.data_status.freshness, "current")
        self.assertFalse(snapshot.refresh_status.attempted)

    def test_snapshot_without_live_data_or_cache_returns_clear_error(self):
        repository = PriceCandleRepository(self.SessionLocal)
        history_service = ChartHistoryService(
            adapter=FailingChartAdapter(),
            now_provider=lambda: datetime(2026, 5, 3, 10, 0),
        )
        refresh_service = ChartDataRefreshService(
            history_service=history_service,
            repository=repository,
            now_provider=lambda: datetime(2026, 5, 3, 10, 1),
        )
        snapshot_service = ChartSnapshotService(
            history_service=history_service,
            repository=repository,
            refresh_service=refresh_service,
            now_provider=lambda: datetime(2026, 5, 3, 10, 2),
        )

        snapshot = snapshot_service.get_snapshot("SBER", "month")

        self.assertFalse(snapshot.ok)
        self.assertEqual(snapshot.data_status.freshness, "stale")
        self.assertTrue(any("No chart data available" in error for error in snapshot.history.errors))
        self.assertTrue(any(gap.category == "price_history" for gap in snapshot.history.data_gaps))

    def test_snapshot_marks_usable_invalid_candle_result_as_partial(self):
        adapter = StaticChartAdapter(
            ChartAdapterResult(
                source_name="fake-market-data",
                ticker="SBER",
                fetched_at=datetime(2026, 5, 3, 10, 0),
                as_of_date="2026-05-02",
                candles=[candle(1, 100.0), candle(2, 102.0)],
                data_gaps=[ChartDataGap("price_history", "Skipped 1 candle with invalid OHLC data.", "medium")],
                errors=["Partial candle payload contained invalid rows."],
                interval="day",
            )
        )
        history_service = ChartHistoryService(
            adapter=adapter,
            now_provider=lambda: datetime(2026, 5, 3, 10, 1),
        )
        snapshot_service = ChartSnapshotService(
            history_service=history_service,
            now_provider=lambda: datetime(2026, 5, 3, 10, 2),
        )

        snapshot = snapshot_service.get_snapshot("SBER", "month", refresh=False)

        self.assertTrue(snapshot.ok)
        self.assertEqual(snapshot.data_status.freshness, "partial")
        self.assertEqual(snapshot.data_status.errors, ["Partial candle payload contained invalid rows."])
        self.assertEqual(len(snapshot.history.candles), 2)


if __name__ == "__main__":
    unittest.main()
