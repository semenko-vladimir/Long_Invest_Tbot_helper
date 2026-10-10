"""Small, bounded runtime settings for read-only news and market digests."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MonitoringLimits:
    news_per_hour: int = 10
    account_analyses_per_hour: int = 2
    pending_jobs: int = 100
    news_alerts_per_hour: int = 3
    news_alerts_per_day: int = 6
    urgent_importance: int = 80
    liquidity_rub: float = 10_000_000
    section_pages: int = 5

    @classmethod
    def from_env(cls):
        fields = {
            "news_per_hour": ("NEWS_ANALYSES_PER_HOUR", 10, 1, 100),
            "account_analyses_per_hour": ("NEWS_ACCOUNT_ANALYSES_PER_HOUR", 2, 1, 20),
            "pending_jobs": ("NEWS_MAX_PENDING_JOBS", 100, 1, 1000),
            "news_alerts_per_hour": ("NEWS_ALERTS_PER_HOUR", 3, 1, 20),
            "news_alerts_per_day": ("NEWS_ALERTS_PER_DAY", 6, 1, 100),
            "urgent_importance": ("NEWS_URGENT_IMPORTANCE", 80, 1, 100),
            "section_pages": ("NEWS_SECTION_MAX_PAGES", 5, 1, 5),
        }
        values = {}
        for field, (env, default, lower, upper) in fields.items():
            try:
                value = int(os.getenv(env, str(default)))
            except ValueError as exc:
                raise ValueError(f"{env} must be a whole number.") from exc
            if not lower <= value <= upper:
                raise ValueError(f"{env} must be between {lower} and {upper}.")
            values[field] = value
        liquidity = float(os.getenv("MARKET_DIGEST_MIN_TURNOVER_RUB", "10000000"))
        if not 0 < liquidity <= 1_000_000_000:
            raise ValueError("MARKET_DIGEST_MIN_TURNOVER_RUB is outside its allowed range.")
        return cls(**values, liquidity_rub=liquidity)
