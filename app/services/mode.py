from dataclasses import dataclass

from app.client.config import allow_prod_trading, get_invest_mode, is_sandbox_mode


@dataclass(frozen=True)
class ModeContext:
    mode: str
    is_sandbox: bool
    prod_trading_allowed: bool
    trading_available: bool
    banner_title: str
    banner_message: str


class ModeService:
    def current(self) -> ModeContext:
        mode = get_invest_mode()
        sandbox = is_sandbox_mode()
        prod_allowed = allow_prod_trading()
        trading_available = sandbox or prod_allowed

        if sandbox:
            return ModeContext(
                mode="sandbox",
                is_sandbox=True,
                prod_trading_allowed=False,
                trading_available=True,
                banner_title="Mode: sandbox",
                banner_message="Sandbox orders are available. Production trading is not active.",
            )

        if prod_allowed:
            return ModeContext(
                mode="prod",
                is_sandbox=False,
                prod_trading_allowed=True,
                trading_available=True,
                banner_title="Mode: prod",
                banner_message="Production trading is enabled. Real orders require explicit confirmation.",
            )

        return ModeContext(
            mode="prod",
            is_sandbox=False,
            prod_trading_allowed=False,
            trading_available=False,
            banner_title="Mode: prod, trading disabled",
            banner_message="Portfolio viewing is available. Trading actions are blocked in read-only mode.",
        )
