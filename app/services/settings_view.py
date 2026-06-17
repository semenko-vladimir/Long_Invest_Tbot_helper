from dataclasses import dataclass

from app.client.config import (
    allow_prod_trading,
    anti_greedy_policy_enabled,
    background_schedulers_enabled,
    chart_data_refresh_enabled,
    get_anti_greedy_check_time,
    get_anti_greedy_profit_pct,
    get_api_base_url,
    get_chart_data_refresh_interval_seconds,
    get_chart_data_refresh_ranges,
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
class ChartDataSettingsView:
    refresh_enabled: bool = False
    ranges: tuple[str, ...] = ("day", "month")
    interval_seconds: int = 60
    tracked_ticker_count: int = 0
    cache_candle_count: int = 0
    oldest_candle_at: object = None
    latest_candle_at: object = None
    latest_fetched_at: object = None
    last_refresh_status: str = "not available"
    last_refresh_errors: tuple[str, ...] = ()
    source_priority: str = "T-Invest -> MOEX ISS -> local cache"


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
    chart_data_refresh_enabled: bool = False
    anti_greedy_policy_enabled: bool = False
    anti_greedy_profit_pct: float = 20.0
    anti_greedy_check_time: str = "18:30"
    web_auth_enabled: bool = False
    web_auth_token_configured: bool = False
    chart_data: ChartDataSettingsView = ChartDataSettingsView()
    change_note: str = "To change settings, edit .env and restart the app."


class SettingsViewService:
    def __init__(
        self,
        *,
        mode_service: ModeService | None = None,
        chart_candle_repository=None,
    ):
        self.mode_service = mode_service or ModeService()
        self.chart_candle_repository = chart_candle_repository

    def current(self) -> SettingsView:
        mode = self.mode_service.current()
        tokens = get_tokens()
        chart_refresh_enabled = chart_data_refresh_enabled()

        return SettingsView(
            mode=mode,
            active_mode=mode.mode,
            active_mode_meaning=mode.banner_message,
            sandbox_token_configured=not is_placeholder_value(tokens.get("sandbox_token")),
            token_configured=not is_placeholder_value(tokens.get("token")),
            allow_prod_trading=allow_prod_trading(),
            background_schedulers_enabled=background_schedulers_enabled(),
            chart_data_refresh_enabled=chart_refresh_enabled,
            investment_plans_enabled=investment_plans_enabled(),
            api_base_url=get_api_base_url(),
            investor_reminders_enabled=investor_reminders_enabled(),
            investor_reminder_time=get_investor_reminder_time(),
            anti_greedy_policy_enabled=anti_greedy_policy_enabled(),
            anti_greedy_profit_pct=get_anti_greedy_profit_pct(),
            anti_greedy_check_time=get_anti_greedy_check_time(),
            web_auth_enabled=web_auth_enabled(),
            web_auth_token_configured=get_web_auth_token() is not None,
            chart_data=self._chart_data_settings(chart_refresh_enabled),
        )

    def _chart_data_settings(self, refresh_enabled: bool) -> ChartDataSettingsView:
        try:
            ranges = get_chart_data_refresh_ranges()
        except Exception:
            ranges = ("day", "month")

        try:
            interval_seconds = get_chart_data_refresh_interval_seconds()
        except Exception:
            interval_seconds = 60

        summary = None
        if self.chart_candle_repository is not None:
            try:
                summary = self.chart_candle_repository.summary()
            except Exception:
                summary = None

        return ChartDataSettingsView(
            refresh_enabled=refresh_enabled,
            ranges=tuple(ranges),
            interval_seconds=interval_seconds,
            tracked_ticker_count=int(getattr(summary, "ticker_count", 0) or 0),
            cache_candle_count=int(getattr(summary, "candle_count", 0) or 0),
            oldest_candle_at=getattr(summary, "oldest_candle_at", None),
            latest_candle_at=getattr(summary, "latest_candle_at", None),
            latest_fetched_at=getattr(summary, "latest_fetched_at", None),
        )
