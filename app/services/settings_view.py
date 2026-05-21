from dataclasses import dataclass

from app.client.config import (
    allow_prod_trading,
    anti_greedy_policy_enabled,
    background_schedulers_enabled,
    get_anti_greedy_check_time,
    get_anti_greedy_profit_pct,
    get_api_base_url,
    get_investor_reminder_time,
    get_tokens,
    get_web_auth_token,
    investment_plans_enabled,
    investor_reminders_enabled,
    is_placeholder_value,
    web_auth_enabled,
)
from app.services.mode import ModeContext, ModeService


@dataclass(frozen=True)
class SettingsView:
    mode: ModeContext
    active_mode: str
    active_mode_meaning: str
    sandbox_token_configured: bool
    token_configured: bool
    allow_prod_trading: bool
    background_schedulers_enabled: bool
    investment_plans_enabled: bool
    api_base_url: str
    investor_reminders_enabled: bool
    investor_reminder_time: str
    anti_greedy_policy_enabled: bool = False
    anti_greedy_profit_pct: float = 20.0
    anti_greedy_check_time: str = "18:30"
    web_auth_enabled: bool = False
    web_auth_token_configured: bool = False
    change_note: str = "To change settings, edit .env and restart the app."


class SettingsViewService:
    def __init__(
        self,
        *,
        mode_service: ModeService | None = None,
    ):
        self.mode_service = mode_service or ModeService()

    def current(self) -> SettingsView:
        mode = self.mode_service.current()
        tokens = get_tokens()

        return SettingsView(
            mode=mode,
            active_mode=mode.mode,
            active_mode_meaning=mode.banner_message,
            sandbox_token_configured=not is_placeholder_value(tokens.get("sandbox_token")),
            token_configured=not is_placeholder_value(tokens.get("token")),
            allow_prod_trading=allow_prod_trading(),
            background_schedulers_enabled=background_schedulers_enabled(),
            investment_plans_enabled=investment_plans_enabled(),
            api_base_url=get_api_base_url(),
            investor_reminders_enabled=investor_reminders_enabled(),
            investor_reminder_time=get_investor_reminder_time(),
            anti_greedy_policy_enabled=anti_greedy_policy_enabled(),
            anti_greedy_profit_pct=get_anti_greedy_profit_pct(),
            anti_greedy_check_time=get_anti_greedy_check_time(),
            web_auth_enabled=web_auth_enabled(),
            web_auth_token_configured=get_web_auth_token() is not None,
        )
