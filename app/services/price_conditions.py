from dataclasses import dataclass
from typing import Callable, Optional

from app.integrations.tinvest import TInvestBroker


@dataclass(frozen=True)
class PriceConditionResult:
    allowed: bool
    reason: str
    current_price: float
    limit_price: Optional[float] = None


class PriceConditionService:
    """Checks whether a plan's price condition allows execution."""

    def __init__(self, *, token_provider: Callable[[], Optional[str]], broker=None):
        self._token_provider = token_provider
        self._broker = broker or TInvestBroker()

    def check(self, *, plan, current_price: float) -> PriceConditionResult:
        rule = str(getattr(plan, "price_rule", "") or "").strip().lower()

        if rule in ("any", "current_market"):
            return PriceConditionResult(
                allowed=True,
                reason="Условие по цене не задано.",
                current_price=current_price,
            )

        if rule == "max_price":
            return self._check_max_price(plan, current_price)

        if rule == "pct_from_avg":
            return self._check_pct_from_avg(plan, current_price)

        if rule == "previous_day_average_discount":
            return self._check_previous_day_average_discount(plan, current_price)

        return PriceConditionResult(
            allowed=False,
            reason=f"Неизвестное условие цены: {rule}.",
            current_price=current_price,
        )

    def _check_max_price(self, plan, current_price: float) -> PriceConditionResult:
        limit = getattr(plan, "price_limit", None)
        if limit is None:
            return PriceConditionResult(
                allowed=False,
                reason="price_limit не задан для правила max_price.",
                current_price=current_price,
            )

        operation = str(getattr(plan, "operation", "buy") or "buy").strip().lower()
        if operation == "buy":
            allowed = current_price <= limit
            reason = (
                f"Цена {current_price:.2f}₽ ≤ лимит {limit:.2f}₽ — условие выполнено."
                if allowed
                else f"Цена {current_price:.2f}₽ > лимит {limit:.2f}₽ — пропускаем."
            )
        else:
            allowed = current_price >= limit
            reason = (
                f"Цена {current_price:.2f}₽ ≥ лимит {limit:.2f}₽ — условие выполнено."
                if allowed
                else f"Цена {current_price:.2f}₽ < лимит {limit:.2f}₽ — пропускаем."
            )

        return PriceConditionResult(
            allowed=allowed,
            reason=reason,
            current_price=current_price,
            limit_price=limit,
        )

    def _check_pct_from_avg(self, plan, current_price: float) -> PriceConditionResult:
        period_days = getattr(plan, "avg_period_days", None) or 30
        avg = self._get_moving_average(getattr(plan, "ticker", ""), period_days)
        if avg is None:
            return PriceConditionResult(
                allowed=False,
                reason="Не удалось получить историческую среднюю цену.",
                current_price=current_price,
            )

        threshold_pct = getattr(plan, "pct_threshold", None) or 5.0
        operation = str(getattr(plan, "operation", "buy") or "buy").strip().lower()
        if operation == "buy":
            limit = avg * (1 + threshold_pct / 100)
            allowed = current_price <= limit
        else:
            limit = avg * (1 - threshold_pct / 100)
            allowed = current_price >= limit

        direction = "≤" if operation == "buy" else "≥"
        reason = (
            f"Цена {current_price:.2f}₽ {direction} {threshold_pct}% от {period_days}д-ср "
            f"({avg:.2f}₽ → лимит {limit:.2f}₽) — "
            + ("условие выполнено." if allowed else "пропускаем.")
        )

        return PriceConditionResult(
            allowed=allowed,
            reason=reason,
            current_price=current_price,
            limit_price=limit,
        )

    def _get_moving_average(self, ticker: str, days: int) -> Optional[float]:
        try:
            token = self._token_provider()
            if not token:
                return None
            prices = self._broker.get_closing_prices(token, ticker, days)
            if not prices:
                return None
            return sum(prices) / len(prices)
        except Exception:
            return None

    def _check_previous_day_average_discount(self, plan, current_price: float) -> PriceConditionResult:
        avg = self._get_previous_day_average(getattr(plan, "ticker", ""))
        if avg is None:
            return PriceConditionResult(
                allowed=False,
                reason="Не удалось получить вчерашнюю среднерыночную цену.",
                current_price=current_price,
            )

        threshold_pct = getattr(plan, "pct_threshold", None)
        threshold_pct = 0.5 if threshold_pct is None else float(threshold_pct)
        limit = avg * (1 - threshold_pct / 100)
        allowed = current_price <= limit
        reason = (
            f"Цена {current_price:.2f}₽ ≤ вчерашняя средняя - {threshold_pct:g}% "
            f"({avg:.2f}₽ → лимит {limit:.2f}₽) — "
            + ("условие выполнено." if allowed else "пропускаем.")
        )
        return PriceConditionResult(
            allowed=allowed,
            reason=reason,
            current_price=current_price,
            limit_price=limit,
        )

    def _get_previous_day_average(self, ticker: str) -> Optional[float]:
        try:
            token = self._token_provider()
            if not token:
                return None
            return self._broker.get_previous_day_average_price(token, ticker)
        except Exception:
            return None
