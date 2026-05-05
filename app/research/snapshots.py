from dataclasses import asdict
from datetime import UTC, date, datetime
import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.backend.models.research import ResearchSnapshot
from app.research.schemas import ResearchReport


DEFAULT_SNAPSHOT_LIMIT = 20
MAX_SNAPSHOT_LIMIT = 100
SENSITIVE_FIELD_PARTS = ("token", "secret", "password", "authorization", "api_key")


class ResearchSnapshotService:
    """Local read-only research snapshot storage.

    This service persists already-built reports only. It does not collect broker
    data, evaluate ratings, or expose order-placement behavior.
    """

    def __init__(self, db: Session, now_provider=None):
        self.db = db
        self.now_provider = now_provider or _utcnow

    def save_report(self, report: ResearchReport) -> ResearchSnapshot:
        report_payload = report_to_jsonable(report)
        snapshot = ResearchSnapshot(
            ticker=self._normalize_ticker(report.ticker),
            generated_at=report.generated_at,
            source_names=json.dumps(report_payload.get("sources", []), ensure_ascii=False),
            report_json=json.dumps(report_payload, ensure_ascii=False, sort_keys=True),
            data_gap_count=len(report.data_gaps),
            error_count=len(report.errors),
            created_at=self.now_provider(),
        )

        self.db.add(snapshot)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(snapshot)
        return snapshot

    def list_recent(self, ticker: Optional[str] = None, limit: int = DEFAULT_SNAPSHOT_LIMIT) -> list[ResearchSnapshot]:
        query = self.db.query(ResearchSnapshot)
        normalized_ticker = self._normalize_ticker(ticker or "")
        if normalized_ticker:
            query = query.filter(ResearchSnapshot.ticker == normalized_ticker)

        return (
            query.order_by(ResearchSnapshot.created_at.desc(), ResearchSnapshot.id.desc())
            .limit(self._normalize_limit(limit))
            .all()
        )

    def get_snapshot(self, snapshot_id: int) -> Optional[ResearchSnapshot]:
        if snapshot_id < 1:
            return None
        return self.db.query(ResearchSnapshot).filter(ResearchSnapshot.id == snapshot_id).first()

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""

    def _normalize_limit(self, limit: int) -> int:
        try:
            parsed = int(limit)
        except (TypeError, ValueError):
            parsed = DEFAULT_SNAPSHOT_LIMIT
        return min(max(parsed, 1), MAX_SNAPSHOT_LIMIT)


def report_to_jsonable(report: ResearchReport) -> dict[str, Any]:
    return _to_jsonable(asdict(report))


def snapshot_to_dict(snapshot: ResearchSnapshot) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "ticker": snapshot.ticker,
        "generated_at": _to_jsonable(snapshot.generated_at),
        "source_names": _loads_json(snapshot.source_names, []),
        "report_json": _loads_json(snapshot.report_json, {}),
        "data_gap_count": snapshot.data_gap_count,
        "error_count": snapshot.error_count,
        "created_at": _to_jsonable(snapshot.created_at),
    }


def _to_jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _to_jsonable(item)
            for key, item in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _loads_json(raw_value: Optional[str], default):
    if not raw_value:
        return default
    try:
        return json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _is_sensitive_key(key: object) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in SENSITIVE_FIELD_PARTS)
