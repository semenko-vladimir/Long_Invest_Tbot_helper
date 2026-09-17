from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.charts.services import normalize_chart_range
from app.client.log.logger import setup_logger


logger = setup_logger(__name__)


@dataclass
class ChartDataRefreshRunner:
    watchlist_service: object
    portfolio_service: object
    refresh_service: object
    ranges: tuple[str, ...] = ("day", "month")

    def run(self) -> None:
        tickers = self._selected_tickers()
        if not tickers:
            logger.info("Chart data refresh skipped: no selected tickers.")
            return

        ranges = tuple(range_name for range_name in self.ranges if normalize_chart_range(range_name))
        for ticker in tickers:
            for range_name in ranges:
                try:
                    result = self.refresh_service.refresh_ticker(ticker, range_name)
                    if result.ok:
                        logger.info(
                            "Chart data refreshed: ticker=%s range=%s candles=%d",
                            ticker,
                            range_name,
                            result.changed_count,
                        )
                    else:
                        logger.warning(
                            "Chart data refresh returned gaps/errors: ticker=%s range=%s errors=%s",
                            ticker,
                            range_name,
                            "; ".join(result.history.errors),
                        )
                except Exception as exc:
                    logger.warning(
                        "Chart data refresh failed: ticker=%s range=%s error=%s",
                        ticker,
                        range_name,
                        str(exc),
                    )

    def _selected_tickers(self) -> tuple[str, ...]:
        tickers: set[str] = set()
        tickers.update(self._watchlist_tickers())
        tickers.update(self._portfolio_tickers())
        return tuple(sorted(tickers))

    def _watchlist_tickers(self) -> Iterable[str]:
        try:
            watchlist = self.watchlist_service.list_items()
        except Exception:
            return ()
        return tuple(
            ticker
            for ticker in (
                self._normalize_ticker(getattr(item, "ticker", ""))
                for item in getattr(watchlist, "items", []) or []
            )
            if ticker
        )

    def _portfolio_tickers(self) -> Iterable[str]:
        try:
            portfolio = self.portfolio_service.get_portfolio_view()
        except Exception:
            return ()
        return tuple(
            ticker
            for ticker in (
                self._normalize_ticker(getattr(position, "ticker", ""))
                for position in getattr(portfolio, "positions", []) or []
            )
            if ticker
        )

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""
