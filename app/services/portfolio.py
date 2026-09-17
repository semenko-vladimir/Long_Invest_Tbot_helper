import logging
from dataclasses import dataclass
from typing import Callable, List, Optional

from app.backend.models.accounts import PortfolioSnapshot, PositionSnapshot, utc_now
from app.client.config import get_active_invest_token
from app.integrations.broker import BrokerAdapter
from app.integrations.tinvest import TInvestBroker
from app.services.accounts import AccountRegistryService, InvestmentAccountContext
from app.services.mode import ModeContext, ModeService
from app.services.user_database import SessionFactory


logger = logging.getLogger(__name__)


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
    figi: str = ""
    instrument_uid: str = ""
    market_value: float = 0.0
    investment_account_id: int | None = None
    account_name: str | None = None


@dataclass(frozen=True)
class PortfolioView:
    """Compatibility aggregate used by existing read-only chart/watchlist services."""

    mode: ModeContext
    total_value: float
    total_value_display: str
    positions: List[PortfolioPosition]
    empty: bool
    error: Optional[str] = None
    partial: bool = False
    account_count: int = 0


@dataclass(frozen=True)
class AccountPortfolioView:
    mode: ModeContext
    account: InvestmentAccountContext
    total_value: float
    total_value_display: str
    positions: tuple[PortfolioPosition, ...]
    empty: bool
    error: Optional[str] = None


@dataclass(frozen=True)
class AggregatePortfolioView:
    mode: ModeContext
    total_value: float
    total_value_display: str
    accounts: tuple[AccountPortfolioView, ...]
    empty: bool
    partial: bool
    error: Optional[str] = None

    @property
    def positions(self) -> tuple[PortfolioPosition, ...]:
        return tuple(position for account in self.accounts for position in account.positions)


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
        broker: Optional[BrokerAdapter] = None,
        mode_service: Optional[ModeService] = None,
        token_provider: Optional[Callable[[], Optional[str]]] = None,
        *,
        account_registry: Optional[AccountRegistryService] = None,
        session_factory: Optional[SessionFactory] = None,
    ):
        self.broker = broker or TInvestBroker()
        self.mode_service = mode_service or ModeService()
        self.token_provider = token_provider or get_active_invest_token
        self.account_registry = account_registry
        self.session_factory = session_factory

    def get_account_portfolio(self, account_context: InvestmentAccountContext) -> AccountPortfolioView:
        mode = self.mode_service.current()
        if self.account_registry is not None:
            try:
                account_context = self.account_registry.validate_account_context(account_context)
            except Exception as exc:
                return self._account_error(mode, account_context, str(exc))
        token = self.token_provider()
        if not token:
            return self._account_error(
                mode,
                account_context,
                "No broker token is configured for the current mode.",
            )
        if account_context.broker_provider != self.broker.provider_key:
            return self._account_error(mode, account_context, "The selected broker connection is unsupported.")

        try:
            raw_portfolio = self.broker.get_portfolio(
                token,
                account_id=account_context.external_account_id,
                sandbox=mode.is_sandbox,
            )
            positions = tuple(
                self._build_position(token, position, account_context)
                for position in raw_portfolio.get("positions", [])
            )
            total_value = as_float(raw_portfolio.get("total_amount_portfolio"))
            self._save_snapshot(account_context, raw_portfolio, positions, total_value)
            return AccountPortfolioView(
                mode=mode,
                account=account_context,
                total_value=total_value,
                total_value_display=money(total_value),
                positions=positions,
                empty=len(positions) == 0,
            )
        except Exception as exc:
            logger.exception(
                "Portfolio data is unavailable for investment_account_id=%s",
                account_context.investment_account_id,
            )
            return self._account_error(mode, account_context, portfolio_error_message(exc))

    def get_aggregate_portfolio(self, *, sync_accounts: bool = True) -> AggregatePortfolioView:
        mode = self.mode_service.current()
        if self.account_registry is None:
            return AggregatePortfolioView(
                mode=mode,
                total_value=0.0,
                total_value_display=money(0.0),
                accounts=(),
                empty=True,
                partial=False,
                error="Account registry is not configured.",
            )

        try:
            if sync_accounts:
                account_contexts = self.account_registry.sync_accounts().accounts
            else:
                account_contexts = self.account_registry.list_enabled_accounts()
        except Exception as exc:
            logger.exception("Broker account discovery is unavailable")
            return AggregatePortfolioView(
                mode=mode,
                total_value=0.0,
                total_value_display=money(0.0),
                accounts=(),
                empty=True,
                partial=False,
                error=account_discovery_error_message(exc),
            )

        account_views = tuple(self.get_account_portfolio(context) for context in account_contexts)
        successful = tuple(view for view in account_views if view.error is None)
        failed = tuple(view for view in account_views if view.error is not None)
        total_value = sum(view.total_value for view in successful)
        error = None
        if not account_views:
            error = "No enabled broker accounts were discovered."
        elif not successful:
            error = "Portfolio data is unavailable for every enabled account."
        return AggregatePortfolioView(
            mode=mode,
            total_value=total_value,
            total_value_display=money(total_value),
            accounts=account_views,
            empty=not any(view.positions for view in successful),
            partial=bool(successful and failed),
            error=error,
        )

    def get_portfolio_view(self) -> PortfolioView:
        aggregate = self.get_aggregate_portfolio()
        return PortfolioView(
            mode=aggregate.mode,
            total_value=aggregate.total_value,
            total_value_display=aggregate.total_value_display,
            positions=list(aggregate.positions),
            empty=aggregate.empty,
            error=aggregate.error,
            partial=aggregate.partial,
            account_count=len(aggregate.accounts),
        )

    def _build_position(
        self,
        token: str,
        raw_position: dict,
        account_context: InvestmentAccountContext,
    ) -> PortfolioPosition:
        ticker = str(raw_position.get("ticker") or "-")
        figi = str(raw_position.get("figi") or "")
        name = str(raw_position.get("name") or "")
        if not name:
            name = self.broker.get_instrument_name(token, figi) or ticker
        quantity = as_float(raw_position.get("quantity"))
        average_price = as_float(raw_position.get("average_position_price"))
        market_value = as_float(raw_position.get("current_price"))
        current_price = as_float(raw_position.get("current_price_one"))
        cost_basis = average_price * quantity
        pnl = market_value - cost_basis if cost_basis else as_float(raw_position.get("expected_yield"))
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
            figi=figi,
            instrument_uid=str(raw_position.get("instrument_uid") or ""),
            market_value=market_value,
            investment_account_id=account_context.investment_account_id,
            account_name=account_context.account_name,
        )

    def _save_snapshot(
        self,
        account_context: InvestmentAccountContext,
        raw_portfolio: dict,
        positions: tuple[PortfolioPosition, ...],
        total_value: float,
    ) -> None:
        if self.session_factory is None:
            return
        db = self.session_factory()
        try:
            snapshot = PortfolioSnapshot(
                investment_account_id=account_context.investment_account_id,
                captured_at=utc_now(),
                total_value=total_value,
                currency="RUB",
                source=account_context.broker_provider,
                freshness="live",
            )
            db.add(snapshot)
            db.flush()
            raw_by_key = {
                (str(item.get("figi") or ""), str(item.get("ticker") or "")): item
                for item in raw_portfolio.get("positions", [])
            }
            for position in positions:
                raw = raw_by_key.get((position.figi, position.ticker), {})
                db.add(
                    PositionSnapshot(
                        portfolio_snapshot_id=snapshot.id,
                        investment_account_id=account_context.investment_account_id,
                        instrument_uid=position.instrument_uid or None,
                        figi=position.figi or None,
                        ticker=position.ticker,
                        quantity=position.quantity,
                        average_price=position.average_price,
                        current_price=position.current_price,
                        market_value=position.market_value,
                        expected_yield=as_float(raw.get("expected_yield")),
                        currency=position.currency,
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "Portfolio snapshot could not be persisted for investment_account_id=%s",
                account_context.investment_account_id,
            )
        finally:
            db.close()

    @staticmethod
    def _account_error(
        mode: ModeContext,
        account_context: InvestmentAccountContext,
        error: str,
    ) -> AccountPortfolioView:
        return AccountPortfolioView(
            mode=mode,
            account=account_context,
            total_value=0.0,
            total_value_display=money(0.0),
            positions=(),
            empty=True,
            error=error,
        )


def portfolio_error_message(exc: Exception) -> str:
    details = str(exc).strip()
    if not details:
        return "Portfolio data is unavailable right now. Check the broker token and try again."
    if len(details) > 300:
        details = f"{details[:300]}..."
    return f"Portfolio data is unavailable right now: {details}"


def account_discovery_error_message(exc: Exception) -> str:
    details = str(exc).strip()
    if not details:
        return "Broker accounts could not be discovered right now."
    if len(details) > 300:
        details = f"{details[:300]}..."
    return f"Broker accounts could not be discovered right now: {details}"
