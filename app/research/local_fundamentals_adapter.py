from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable, Optional

from app.research.schemas import AdapterResult, DataGap, SourceFreshness


DEFAULT_LOCAL_FUNDAMENTALS_PATH = Path(__file__).resolve().parent / "data" / "local_fundamentals.json"
EXPECTED_PROFILE_SECTIONS = ("company_profile", "sector_industry", "financials")
SENSITIVE_FIELD_PARTS = ("token", "secret", "password", "authorization", "api_key")


class LocalFundamentalsAdapter:
    """Read-only adapter for locally configured company and fundamental profile data."""

    source_name = "local-fundamentals"

    def __init__(
        self,
        data_path: Optional[str | Path] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.data_path = Path(data_path) if data_path is not None else DEFAULT_LOCAL_FUNDAMENTALS_PATH
        self.now_provider = now_provider or datetime.utcnow

    def fetch(self, ticker: str) -> AdapterResult:
        fetched_at = self.now_provider()
        normalized_ticker = self._normalize_ticker(ticker)
        data: dict[str, Any] = {"ticker": normalized_ticker}
        gaps: list[DataGap] = []
        errors: list[str] = []

        freshness = SourceFreshness(
            source_name=self.source_name,
            fetched_at=fetched_at,
            as_of_date=fetched_at.date().isoformat(),
            notes="Local JSON fundamentals snapshot.",
        )

        if not normalized_ticker:
            gaps.append(DataGap("ticker", "Ticker is required and must use letters, numbers, or hyphen.", "high"))
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        payload = self._load_payload(gaps, errors)
        if payload is None:
            self._add_missing_data_gaps(normalized_ticker, gaps, "Local fundamentals data is unavailable.")
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        entries = self._extract_ticker_entries(payload, gaps, errors)
        if entries is None:
            self._add_missing_data_gaps(normalized_ticker, gaps, "Local fundamentals data is malformed.")
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        source_metadata = self._extract_source_metadata(payload)
        entry = entries.get(normalized_ticker)
        if entry is None:
            self._add_missing_data_gaps(
                normalized_ticker,
                gaps,
                f"Local fundamentals profile is not configured for {normalized_ticker}.",
            )
            freshness = self._with_payload_metadata(freshness, source_metadata, None)
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        if not isinstance(entry, dict):
            errors.append(f"Local fundamentals entry for {normalized_ticker} is malformed: expected an object.")
            self._add_missing_data_gaps(normalized_ticker, gaps, "Local fundamentals ticker entry is malformed.")
            freshness = self._with_payload_metadata(freshness, source_metadata, None)
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        freshness = self._with_payload_metadata(freshness, source_metadata, entry)
        self._copy_profile_sections(normalized_ticker, entry, data, gaps, errors)
        return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

    def _load_payload(self, gaps: list[DataGap], errors: list[str]) -> Optional[dict[str, Any]]:
        try:
            raw_payload = self.data_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            errors.append(f"Local fundamentals data file is unavailable: {self.data_path}")
            gaps.append(DataGap("local_fundamentals", "Local fundamentals data file is unavailable.", "medium"))
            return None
        except OSError as exc:
            errors.append(f"Local fundamentals data file could not be read: {str(exc)}")
            gaps.append(DataGap("local_fundamentals", "Local fundamentals data file could not be read.", "medium"))
            return None

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            errors.append(f"Local fundamentals data file is malformed JSON: {exc.msg}.")
            gaps.append(DataGap("local_fundamentals", "Local fundamentals data file is malformed JSON.", "medium"))
            return None

        if not isinstance(payload, dict):
            errors.append("Local fundamentals data file is malformed: expected a JSON object.")
            gaps.append(DataGap("local_fundamentals", "Local fundamentals data file is malformed.", "medium"))
            return None
        return payload

    def _extract_ticker_entries(
        self,
        payload: dict[str, Any],
        gaps: list[DataGap],
        errors: list[str],
    ) -> Optional[dict[str, Any]]:
        if "tickers" in payload:
            entries = payload.get("tickers")
            if isinstance(entries, dict):
                return {self._normalize_ticker(key): value for key, value in entries.items() if self._normalize_ticker(key)}

            errors.append("Local fundamentals data file is malformed: tickers must be a JSON object.")
            gaps.append(DataGap("local_fundamentals", "Local fundamentals tickers section is malformed.", "medium"))
            return None

        entries = {
            self._normalize_ticker(key): value
            for key, value in payload.items()
            if key not in {"source", "metadata"} and self._normalize_ticker(key)
        }
        return entries

    def _extract_source_metadata(self, payload: dict[str, Any]) -> dict[str, Any]:
        metadata = payload.get("source") or payload.get("metadata") or {}
        return metadata if isinstance(metadata, dict) else {}

    def _with_payload_metadata(
        self,
        freshness: SourceFreshness,
        source_metadata: dict[str, Any],
        entry: Optional[dict[str, Any]],
    ) -> SourceFreshness:
        as_of_date = self._clean_string(
            (entry or {}).get("as_of_date")
            or (entry or {}).get("updated_at")
            or source_metadata.get("as_of_date")
            or source_metadata.get("updated_at")
            or freshness.as_of_date
        )
        notes = self._clean_string(source_metadata.get("description")) or freshness.notes
        return SourceFreshness(
            source_name=freshness.source_name,
            fetched_at=freshness.fetched_at,
            as_of_date=as_of_date,
            is_stale=freshness.is_stale,
            notes=notes,
        )

    def _copy_profile_sections(
        self,
        ticker: str,
        entry: dict[str, Any],
        data: dict[str, Any],
        gaps: list[DataGap],
        errors: list[str],
    ) -> None:
        for section in EXPECTED_PROFILE_SECTIONS:
            raw_value = entry.get(section)
            if raw_value is None or raw_value == {}:
                gaps.append(DataGap(section, f"Local {section} data is not configured for {ticker}.", "low"))
                continue

            if not isinstance(raw_value, dict):
                errors.append(f"Local {section} data for {ticker} is malformed: expected an object.")
                gaps.append(DataGap(section, f"Local {section} data is malformed for {ticker}.", "medium"))
                continue

            clean_value = self._sanitize_mapping(raw_value)
            if clean_value:
                data[section] = clean_value
            else:
                gaps.append(DataGap(section, f"Local {section} data has no usable fields for {ticker}.", "low"))

    def _add_missing_data_gaps(self, ticker: str, gaps: list[DataGap], description: str) -> None:
        for section in EXPECTED_PROFILE_SECTIONS:
            gaps.append(DataGap(section, f"{description} Missing {section} for {ticker}.", "low"))

    def _sanitize_mapping(self, value: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if self._is_sensitive_key(key):
                continue

            clean_item = self._sanitize_value(item)
            if self._has_value(clean_item):
                clean[str(key)] = clean_item
        return clean

    def _sanitize_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return self._sanitize_mapping(value)
        if isinstance(value, list):
            clean_items = [self._sanitize_value(item) for item in value]
            return [item for item in clean_items if self._has_value(item)]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    def _is_sensitive_key(self, key: object) -> bool:
        lowered = str(key).lower()
        return any(part in lowered for part in SENSITIVE_FIELD_PARTS)

    def _has_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ""
        if isinstance(value, (dict, list)):
            return bool(value)
        return True

    def _clean_string(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    def _normalize_ticker(self, ticker: object) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""
