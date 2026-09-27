"""Per-user monitoring settings. Explicit users.json fields override Telegram edits."""

import json
import math
from dataclasses import dataclass, replace
from datetime import time
from urllib.parse import urlsplit

from app.backend.models.monitoring import MonitoringPreference
from app.services.user_context import UserContext
from app.services.user_database import SessionFactory


DEFAULT_SOURCES = (
    "moex_main",
    "moex_listing",
    "cbr_events",
    "cbr_press",
)
SOURCE_URLS = {
    "moex_main": "https://www.moex.com/export/news.aspx?cat=101",
    "moex_listing": "https://www.moex.com/export/news.aspx?cat=104",
    "cbr_events": "https://www.cbr.ru/rss/eventrss",
    "cbr_press": "https://www.cbr.ru/rss/RssPress",
}


@dataclass(frozen=True)
class MonitoringSettings:
    alerts_enabled: bool = False
    digest_enabled: bool = False
    scope: str = "owned"
    threshold_pct: float = 5.0
    digest_time: str = "09:00"
    sources: tuple[str, ...] = DEFAULT_SOURCES


def validate_source(value: str) -> str:
    value = str(value).strip()
    if value in SOURCE_URLS:
        return value
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or len(value) > 500:
        raise ValueError("Источник должен быть HTTPS RSS/Atom URL без учетных данных.")
    if parts.port not in (None, 443):
        raise ValueError("Для RSS/Atom разрешен только стандартный порт HTTPS.")
    return value


def validate_settings(settings: MonitoringSettings) -> MonitoringSettings:
    if not isinstance(settings.alerts_enabled, bool) or not isinstance(settings.digest_enabled, bool):
        raise ValueError("Переключатели мониторинга должны быть true или false.")
    if settings.scope not in {"owned", "market"}:
        raise ValueError("Охват должен быть owned или market.")
    if isinstance(settings.threshold_pct, bool) or not isinstance(settings.threshold_pct, (int, float)) or not math.isfinite(settings.threshold_pct) or not 0 < settings.threshold_pct <= 100:
        raise ValueError("Порог должен быть больше 0 и не больше 100%.")
    if not isinstance(settings.digest_time, str):
        raise ValueError("Время дайджеста должно быть HH:MM.")
    try:
        time.fromisoformat(settings.digest_time)
        if len(settings.digest_time) != 5 or settings.digest_time[2] != ":":
            raise ValueError
    except ValueError as exc:
        raise ValueError("Время дайджеста должно быть HH:MM.") from exc
    if not isinstance(settings.sources, (tuple, list)) or len(settings.sources) > 20:
        raise ValueError("Можно выбрать не более 20 источников.")
    return replace(settings, sources=tuple(dict.fromkeys(validate_source(s) for s in settings.sources)))


class MonitoringSettingsService:
    FIELDS = {"alerts_enabled", "digest_enabled", "scope", "threshold_pct", "digest_time", "sources"}

    def __init__(self, session_factory: SessionFactory, user: UserContext):
        self.session_factory = session_factory
        self.user = user

    def get(self) -> MonitoringSettings:
        db = self.session_factory()
        try:
            row = db.get(MonitoringPreference, 1)
            saved = {} if row is None else {
                "alerts_enabled": row.alerts_enabled,
                "digest_enabled": row.digest_enabled,
                "scope": row.scope,
                "threshold_pct": row.threshold_pct,
                "digest_time": row.digest_time,
                "sources": json.loads(row.sources_json) if row.sources_json is not None else None,
            }
        finally:
            db.close()
        values = {key: value for key, value in saved.items() if value is not None}
        overrides = self.user.monitoring or {}
        unknown = set(overrides) - self.FIELDS
        if unknown:
            raise ValueError(f"Unknown monitoring setting: {', '.join(sorted(unknown))}")
        values.update(overrides)
        if "sources" in values and not isinstance(values["sources"], (list, tuple)):
            raise ValueError("Источники должны быть списком.")
        if "sources" in values:
            values["sources"] = tuple(values["sources"])
        return validate_settings(MonitoringSettings(**values))

    def update(self, **changes) -> MonitoringSettings:
        if set(changes) - self.FIELDS:
            raise ValueError("Unknown monitoring setting.")
        current = self.get()
        proposed = validate_settings(replace(current, **changes))
        db = self.session_factory()
        try:
            row = db.get(MonitoringPreference, 1)
            if row is None:
                row = MonitoringPreference(id=1)
                db.add(row)
            for key, value in changes.items():
                if key == "sources":
                    row.sources_json = json.dumps(proposed.sources)
                else:
                    setattr(row, key, getattr(proposed, key))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return self.get()
