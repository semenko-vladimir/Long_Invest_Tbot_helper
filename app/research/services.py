from datetime import datetime
from typing import Any, Callable, Optional, Sequence

from app.research.adapters import DataSourceAdapter
from app.research.schemas import (
    AdapterResult,
    DataGap,
    ResearchReport,
    SourceFreshness,
)


RESEARCH_DISCLAIMER = (
    "Educational long-term research only. This is not personal investment advice "
    "and must not trigger broker orders."
)


class TickerResearchService:
    def __init__(
        self,
        adapters: Sequence[DataSourceAdapter],
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.adapters = list(adapters)
        self.now_provider = now_provider or datetime.utcnow

    def collect(self, ticker: str) -> list[AdapterResult]:
        normalized_ticker = self._normalize_ticker(ticker)
        if not normalized_ticker:
            fetched_at = self.now_provider()
            return [
                AdapterResult(
                    source_name="ticker-research",
                    data={"ticker": ""},
                    freshness=SourceFreshness(
                        source_name="ticker-research",
                        fetched_at=fetched_at,
                        as_of_date=fetched_at.date().isoformat(),
                    ),
                    gaps=[DataGap("ticker", "Ticker is required and must use letters, numbers, or hyphen.", "high")],
                    errors=["Ticker is required and must use letters, numbers, or hyphen."],
                )
            ]

        results: list[AdapterResult] = []
        for adapter in self.adapters:
            source_name = self._adapter_source_name(adapter)
            try:
                results.append(adapter.fetch(normalized_ticker))
            except Exception as exc:
                fetched_at = self.now_provider()
                results.append(
                    AdapterResult(
                        source_name=source_name,
                        data={"ticker": normalized_ticker},
                        freshness=SourceFreshness(
                            source_name=source_name,
                            fetched_at=fetched_at,
                            as_of_date=fetched_at.date().isoformat(),
                            notes="Adapter failed before returning a complete result.",
                        ),
                        gaps=[DataGap("adapter", f"{source_name} failed before returning data.", "medium")],
                        errors=[f"{source_name} adapter failed: {str(exc)}"],
                    )
                )
        return results

    def _adapter_source_name(self, adapter: DataSourceAdapter) -> str:
        return str(getattr(adapter, "source_name", adapter.__class__.__name__) or adapter.__class__.__name__)

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""


class ResearchReportService:
    def __init__(
        self,
        now_provider: Optional[Callable[[], datetime]] = None,
        disclaimer: str = RESEARCH_DISCLAIMER,
    ):
        self.now_provider = now_provider or datetime.utcnow
        self.disclaimer = disclaimer

    def build_report(self, ticker: str, adapter_results: Sequence[AdapterResult]) -> ResearchReport:
        normalized_ticker = self._normalize_ticker(ticker)
        sources: list[str] = []
        freshness: list[SourceFreshness] = []
        data_gaps: list[DataGap] = []
        errors: list[str] = []
        risks: list[str] = []
        fields: dict[str, Any] = {}

        for result in adapter_results:
            sources.append(result.source_name)
            if result.freshness is not None:
                freshness.append(result.freshness)
            data_gaps.extend(result.gaps)
            errors.extend(result.errors)
            self._merge_result_data(result.data, fields, risks)

        if not normalized_ticker:
            data_gaps.append(DataGap("ticker", "Ticker is missing or invalid.", "high"))
            errors.append("Ticker is missing or invalid.")

        if errors and not any(gap.category == "source_errors" for gap in data_gaps):
            data_gaps.append(DataGap("source_errors", "One or more data sources returned errors.", "medium"))

        return ResearchReport(
            ticker=normalized_ticker,
            generated_at=self.now_provider(),
            instrument_identity=fields.get("instrument_identity"),
            sources=sources,
            freshness=freshness,
            market_snapshot=fields.get("market_snapshot"),
            company_profile=fields.get("company_profile"),
            financials=fields.get("financials"),
            dividends=fields.get("dividends"),
            sector_industry=fields.get("sector_industry"),
            competitors=fields.get("competitors"),
            market_context=fields.get("market_context"),
            macro_context=fields.get("macro_context"),
            news_osint=fields.get("news_osint"),
            risks=risks,
            data_gaps=data_gaps,
            errors=errors,
            disclaimer=self.disclaimer,
            educational_rating=None,
        )

    def _merge_result_data(self, data: dict[str, Any], fields: dict[str, Any], risks: list[str]) -> None:
        for key in (
            "instrument_identity",
            "market_snapshot",
            "company_profile",
            "financials",
            "dividends",
            "sector_industry",
            "competitors",
            "market_context",
            "macro_context",
            "news_osint",
        ):
            if key not in fields and data.get(key) is not None:
                fields[key] = data[key]

        raw_risks = data.get("risks", [])
        if isinstance(raw_risks, str):
            raw_risks = [raw_risks]
        if isinstance(raw_risks, list):
            risks.extend(str(risk) for risk in raw_risks if str(risk).strip())

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""
