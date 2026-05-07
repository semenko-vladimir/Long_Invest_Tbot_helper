from dataclasses import dataclass
from typing import Callable, List, Optional

from app.client.config import get_active_invest_token
from app.integrations.tinvest import TInvestBroker
from app.services.mode import ModeContext, ModeService


@dataclass(frozen=True)
class PortfolioPosition:
    ticker: str
    name: str
    quantity: float
    quantity_display: str
    average_price: float
    average_price_display: str
    current_price: float
    current_price_display: str
    pnl: float
    return_percent: Optional[float]
    currency: str
    pnl_class: str
    pnl_display: str
    return_display: str


@dataclass(frozen=True)
class PortfolioView:
    mode: ModeContext
    total_value: float
    total_value_display: str
    positions: List[PortfolioPosition]
    empty: bool
    error: Optional[str] = None


def money(value: float, currency: str = "RUB") -> str:
    return f"{value:,.2f} {currency}".replace(",", " ")


def signed_money(value: float, currency: str = "RUB") -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{money(value, currency)}"


def percent(value: Optional[float]) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def format_quantity(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


def as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class PortfolioService:
    def __init__(
        self,
        broker: Optional[TInvestBroker] = None,
        mode_service: Optional[ModeService] = None,
        token_provider: Optional[Callable[[], Optional[str]]] = None,
    ):
        self.broker = broker or TInvestBroker()
        self.mode_service = mode_service or ModeService()
        self.token_provider = token_provider or get_active_invest_token

    def get_portfolio_view(self) -> PortfolioView:
        mode = self.mode_service.current()
        token = self.token_provider()

        if not token:
            return PortfolioView(
                mode=mode,
                total_value=0.0,
                total_value_display=money(0.0),
                positions=[],
                empty=True,
                error="No broker token is configured for the current mode.",
            )

        try:
            raw_portfolio = self.broker.get_portfolio(token, sandbox=mode.is_sandbox)
            positions = [
                self._build_position(token, position)
                for position in raw_portfolio.get("positions", [])
            ]
            total_value = as_float(raw_portfolio.get("total_amount_portfolio"))

            return PortfolioView(
                mode=mode,
                total_value=total_value,
                total_value_display=money(total_value),
                positions=positions,
                empty=len(positions) == 0,
            )
        except Exception:
            return PortfolioView(
                mode=mode,
                total_value=0.0,
                total_value_display=money(0.0),
                positions=[],
                empty=True,
                error="Portfolio data is unavailable right now. Check the broker token and try again.",
            )

    def _build_position(self, token: str, raw_position: dict) -> PortfolioPosition:
        ticker = str(raw_position.get("ticker") or "-")
        figi = str(raw_position.get("figi") or "")
        name = self.broker.get_instrument_name(token, figi) or ticker
        quantity = as_float(raw_position.get("quantity"))
        average_price = as_float(raw_position.get("average_position_price"))
        current_total = as_float(raw_position.get("current_price"))
        current_price = as_float(raw_position.get("current_price_one"))
        cost_basis = average_price * quantity
        pnl = current_total - cost_basis if cost_basis else as_float(raw_position.get("expected_yield"))
        return_percent = (pnl / cost_basis * 100) if cost_basis else None
        pnl_class = "positive" if pnl > 0 else "negative" if pnl < 0 else "neutral"

        return PortfolioPosition(
            ticker=ticker,
            name=name,
            quantity=quantity,
            quantity_display=format_quantity(quantity),
            average_price=average_price,
            average_price_display=money(average_price),
            current_price=current_price,
            current_price_display=money(current_price),
            pnl=pnl,
            return_percent=return_percent,
            currency="RUB",
            pnl_class=pnl_class,
            pnl_display=signed_money(pnl),
            return_display=percent(return_percent),
        )
