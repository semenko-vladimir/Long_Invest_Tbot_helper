from dotenv import load_dotenv
import os
from ipaddress import ip_address
from typing import Iterable, Optional


PLACEHOLDER_VALUES = {
    "your_telegram_bot_token",
    "your_sandbox_token",
    "your_telegram_chat_id",
    "your_token",
}
TRUE_VALUES = {"1", "true", "yes", "on"}


class ConfigError(ValueError):
    """Raised when required local startup configuration is missing or invalid."""


def load_local_env() -> None:
    """Load local .env values so the edited project config wins in local runs."""
    load_dotenv(override=True)


def _normalized(value: Optional[str]) -> str:
    return "" if value is None else value.strip().strip('"').strip("'")


def _env_bool(name: str, default: str = "false") -> bool:
    load_local_env()
    return _normalized(os.getenv(name) or default).lower() in TRUE_VALUES


def is_placeholder_value(value: Optional[str], placeholders: Iterable[str] = PLACEHOLDER_VALUES) -> bool:
    normalized = _normalized(value).lower()
    return normalized == "" or normalized in placeholders or normalized.startswith("your_")


def require_env(name: str, *, placeholder_values: Iterable[str] = PLACEHOLDER_VALUES) -> str:
    load_local_env()
    value = os.getenv(name)
    if is_placeholder_value(value, placeholder_values):
        raise ConfigError(
            f"Environment variable {name} is required. "
            "Create .env from .env.example and replace the placeholder value."
        )
    return _normalized(value)


def get_app_mode() -> str:
    load_local_env()
    mode = _normalized(os.getenv("APP_MODE") or os.getenv("INVEST_MODE") or "sandbox").lower()

    if mode in {"prod", "production", "real"}:
        return "prod"

    if mode in {"sandbox", "sand", "test"}:
        return "sandbox"

    raise ConfigError("Environment variable APP_MODE must be either 'sandbox' or 'prod'.")


def get_invest_mode() -> str:
    return get_app_mode()


def is_sandbox_mode() -> bool:
    return get_invest_mode() != "prod"


def allow_prod_trading() -> bool:
    return _env_bool("ALLOW_PROD_TRADING")


def background_schedulers_enabled() -> bool:
    return _env_bool("ENABLE_BACKGROUND_SCHEDULERS")


def investor_reminders_enabled() -> bool:
    return _env_bool("ENABLE_INVESTOR_REMINDERS")


def investment_plans_enabled() -> bool:
    return _env_bool("ENABLE_INVESTMENT_PLANS")


def anti_greedy_policy_enabled() -> bool:
    return _env_bool("ENABLE_ANTI_GREEDY_POLICY")


def chart_data_refresh_enabled() -> bool:
    return _env_bool("ENABLE_CHART_DATA_REFRESH")


def get_chart_data_refresh_interval_seconds() -> int:
    load_local_env()
    value = _normalized(os.getenv("CHART_DATA_REFRESH_SECONDS") or "60")
    try:
        seconds = int(value)
    except ValueError as exc:
        raise ConfigError("Environment variable CHART_DATA_REFRESH_SECONDS must be a positive integer.") from exc
    if seconds <= 0:
        raise ConfigError("Environment variable CHART_DATA_REFRESH_SECONDS must be a positive integer.")
    return seconds


def get_chart_data_refresh_ranges() -> tuple[str, ...]:
    load_local_env()
    value = _normalized(os.getenv("CHART_DATA_REFRESH_RANGES") or "day,month")
    ranges = tuple(part.strip().lower().replace("-", "_") for part in value.split(",") if part.strip())
    return ranges or ("day", "month")


def allow_auto_investing() -> bool:
    return _env_bool("ALLOW_AUTO_INVESTING")


def get_money_limit(name: str) -> float:
    load_local_env()
    value = _normalized(os.getenv(name) or "0")
    try:
        return max(float(value), 0.0)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be a non-negative number.") from exc


def get_max_order_rub() -> float:
    return get_money_limit("MAX_ORDER_RUB")


def get_max_daily_invest_rub() -> float:
    return get_money_limit("MAX_DAILY_INVEST_RUB")


def get_investor_reminder_time() -> str:
    load_local_env()
    return _normalized(os.getenv("INVESTOR_REMINDER_TIME") or "09:00") or "09:00"


def get_anti_greedy_profit_pct() -> float:
    load_local_env()
    value = _normalized(os.getenv("ANTI_GREEDY_PROFIT_PCT") or "20")
    try:
        threshold = float(value)
    except ValueError as exc:
        raise ConfigError("Environment variable ANTI_GREEDY_PROFIT_PCT must be a positive number.") from exc

    if threshold <= 0:
        raise ConfigError("Environment variable ANTI_GREEDY_PROFIT_PCT must be a positive number.")
    return threshold


def get_anti_greedy_check_time() -> str:
    load_local_env()
    return _normalized(os.getenv("ANTI_GREEDY_CHECK_TIME") or "18:30") or "18:30"


def get_tokens() -> dict:
    load_local_env()
    from app.client.config.users import get_default_web_user_config, users_config_is_configured

    if users_config_is_configured(load_env=False):
        return get_default_web_user_config().tokens

    return {
        "token": os.getenv("TOKEN"),
        "sandbox_token": os.getenv("SANDBOX_TOKEN"),
    }


def get_active_invest_token() -> Optional[str]:
    tokens = get_tokens()
    return tokens["sandbox_token"] if is_sandbox_mode() else tokens["token"]


def get_broker_fee() -> float:
    load_local_env()
    from app.client.config.users import get_default_web_user_config, users_config_is_configured

    if users_config_is_configured(load_env=False):
        return get_default_web_user_config().broker_fee

    broker_fee = require_env("BROKER_FEE", placeholder_values=set())
    try:
        return float(broker_fee)
    except ValueError as exc:
        raise ConfigError("Environment variable BROKER_FEE must be a number, for example 0.3.") from exc


def get_api_base_url() -> str:
    load_local_env()
    return os.getenv("API_BASE_URL", "http://localhost:8000").strip() or "http://localhost:8000"


def get_api_host() -> str:
    load_local_env()
    return _normalized(os.getenv("API_HOST") or "127.0.0.1") or "127.0.0.1"


def api_host_is_localhost(host: Optional[str] = None) -> bool:
    normalized = _normalized(host if host is not None else get_api_host()).lower()
    normalized = normalized.strip("[]")

    if normalized == "localhost":
        return True

    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


def web_auth_enabled() -> bool:
    return _env_bool("WEB_AUTH_ENABLED")


def get_web_auth_token() -> Optional[str]:
    load_local_env()
    token = _normalized(os.getenv("WEB_AUTH_TOKEN"))
    return token or None


def validate_web_auth_config() -> None:
    auth_enabled = web_auth_enabled()
    token_configured = get_web_auth_token() is not None

    if auth_enabled and not token_configured:
        raise ConfigError("WEB_AUTH_TOKEN is required when WEB_AUTH_ENABLED=true.")

    api_host = get_api_host()
    if not api_host_is_localhost(api_host) and (not auth_enabled or not token_configured):
        raise ConfigError(
            "WEB_AUTH_ENABLED=true and WEB_AUTH_TOKEN are required when API_HOST is not localhost."
        )


def validate_startup_config() -> None:
    validate_web_auth_config()
    require_env("BOT_TOKEN")
    from app.client.config.users import users_config_is_configured, validate_users_config_for_mode

    if users_config_is_configured(load_env=False):
        validate_users_config_for_mode(get_invest_mode())
        return

    require_env("CHAT_ID")
    get_broker_fee()

    if is_sandbox_mode():
        require_env("SANDBOX_TOKEN")
    else:
        require_env("TOKEN")
