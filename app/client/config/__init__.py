from dotenv import load_dotenv
import os
from typing import Iterable, Optional


PLACEHOLDER_VALUES = {
    "your_telegram_bot_token",
    "your_sandbox_token",
    "your_telegram_chat_id",
    "your_token",
}


class ConfigError(ValueError):
    """Raised when required local startup configuration is missing or invalid."""


def _normalized(value: Optional[str]) -> str:
    return "" if value is None else value.strip().strip('"').strip("'")


def is_placeholder_value(value: Optional[str], placeholders: Iterable[str] = PLACEHOLDER_VALUES) -> bool:
    normalized = _normalized(value).lower()
    return normalized == "" or normalized in placeholders or normalized.startswith("your_")


def require_env(name: str, *, placeholder_values: Iterable[str] = PLACEHOLDER_VALUES) -> str:
    load_dotenv()
    value = os.getenv(name)
    if is_placeholder_value(value, placeholder_values):
        raise ConfigError(
            f"Environment variable {name} is required. "
            "Create .env from .env.example and replace the placeholder value."
        )
    return _normalized(value)


def get_app_mode() -> str:
    load_dotenv()
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
    load_dotenv()
    return os.getenv("ALLOW_PROD_TRADING", "false").strip().lower() in {"1", "true", "yes", "on"}


def background_schedulers_enabled() -> bool:
    load_dotenv()
    return os.getenv("ENABLE_BACKGROUND_SCHEDULERS", "false").strip().lower() in {"1", "true", "yes", "on"}


def investor_reminders_enabled() -> bool:
    load_dotenv()
    return os.getenv("ENABLE_INVESTOR_REMINDERS", "false").strip().lower() in {"1", "true", "yes", "on"}


def investment_plans_enabled() -> bool:
    load_dotenv()
    return os.getenv("ENABLE_INVESTMENT_PLANS", "false").strip().lower() in {"1", "true", "yes", "on"}


def allow_auto_investing() -> bool:
    load_dotenv()
    return os.getenv("ALLOW_AUTO_INVESTING", "false").strip().lower() in {"1", "true", "yes", "on"}


def get_money_limit(name: str) -> float:
    load_dotenv()
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
    load_dotenv()
    return _normalized(os.getenv("INVESTOR_REMINDER_TIME") or "09:00") or "09:00"


def get_tokens() -> dict:
    load_dotenv()
    return {
        "token": os.getenv("TOKEN"),
        "sandbox_token": os.getenv("SANDBOX_TOKEN"),
    }


def get_active_invest_token() -> Optional[str]:
    tokens = get_tokens()
    return tokens["sandbox_token"] if is_sandbox_mode() else tokens["token"]


def get_api_base_url() -> str:
    load_dotenv()
    return os.getenv("API_BASE_URL", "http://localhost:8000").strip() or "http://localhost:8000"


def validate_startup_config() -> None:
    require_env("BOT_TOKEN")
    require_env("CHAT_ID")
    broker_fee = require_env("BROKER_FEE", placeholder_values=set())

    try:
        float(broker_fee)
    except ValueError as exc:
        raise ConfigError("Environment variable BROKER_FEE must be a number, for example 0.3.") from exc

    if is_sandbox_mode():
        require_env("SANDBOX_TOKEN")
    else:
        require_env("TOKEN")
