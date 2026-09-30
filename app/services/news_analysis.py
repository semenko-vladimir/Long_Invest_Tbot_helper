"""Replaceable analysis boundary; deterministic rules are the initial implementation."""

import re
from dataclasses import dataclass
from typing import Protocol

from app.services.accounts import InvestmentAccountContext
from app.services.news_sources import NewsItem


@dataclass(frozen=True)
class NewsAssessment:
    important: bool
    ticker: str | None
    reason: str
    analysis: "ModelNewsAnalysis | None" = None


@dataclass(frozen=True)
class ModelNewsAnalysis:
    investment_account_id: int
    model: str
    impact: str
    facts: tuple[str, ...]
    uncertainty: str
    insufficient_data: bool
    source_url: str
    evidence_scope: str
    limitations: tuple[str, ...] = ()


class NewsAnalyzer(Protocol):
    def assess(
        self,
        item: NewsItem,
        ticker_names: dict[str, str],
        accounts: tuple[InvestmentAccountContext, ...],
    ) -> NewsAssessment: ...


class RuleNewsAnalyzer:
    MARKET_TERMS = ("ключев", "ставк", "дивиденд", "листинг", "приостанов", "торг", "индекс", "санкц")

    def assess(self, item, ticker_names, accounts) -> NewsAssessment:
        title = item.title.casefold()
        for ticker, name in ticker_names.items():
            if re.search(rf"(?<![\w]){re.escape(ticker.casefold())}(?![\w])", title):
                return NewsAssessment(True, ticker, "Упоминание тикера")
            if name and len(name) >= 8 and name.casefold() in title:
                return NewsAssessment(True, ticker, "Упоминание эмитента")
        important = item.source in {"moex_main", "moex_listing"} or any(word in title for word in self.MARKET_TERMS)
        return NewsAssessment(important, None, "Общерыночная новость" if important else "Нет признаков значимости")


class ModelNewsPrefilter:
    """Bound expensive model work to account names and material market themes."""

    MARKET_TERMS = ("ключев", "ставк", "инфляц", "капитал", "кредитн", "макропруденц",
                    "валют", "дивиденд", "дефолт", "санкц", "ликвидност")
    MOEX_TERMS = ("дивиденд", "дефолт", "санкц", "индекс", "делистинг",
                  "приостановке всех торгов", "приостановке торгов на всем рынке",
                  "возобновлении всех торгов")
    MOEX_SECURITY_TERMS = ("приостановке торгов ценными бумагами",
                           "возобновлении торгов ценными бумагами",
                           "исключении ценных бумаг из списка")

    def __init__(self):
        self.rules = RuleNewsAnalyzer()

    def assess(self, item, ticker_names, accounts) -> NewsAssessment:
        if not accounts:
            return self.rules.assess(item, ticker_names, accounts)
        title = item.title.casefold()
        text = title + " " + item.summary.casefold()[:1500]
        for ticker, name in ticker_names.items():
            if re.search(rf"(?<![\w]){re.escape(ticker.casefold())}(?![\w])", text):
                return NewsAssessment(True, ticker, "Упоминание тикера счёта или списка наблюдения")
            if name and len(name) >= 8 and name.casefold() in text:
                return NewsAssessment(True, ticker, "Упоминание эмитента счёта или списка наблюдения")
        terms = self.MOEX_TERMS if item.source in {"moex_main", "moex_listing"} else self.MARKET_TERMS
        important = any(word in title for word in terms) or self.needs_security_match(item)
        return NewsAssessment(important, None, "Важная рыночная тема" if important else "Не прошла быстрый отбор")

    @classmethod
    def needs_security_match(cls, item: NewsItem) -> bool:
        return item.source in {"moex_main", "moex_listing"} and any(
            term in item.title.casefold() for term in cls.MOEX_SECURITY_TERMS
        )
