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
