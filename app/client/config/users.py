import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from app.client.config import ConfigError, _normalized, is_placeholder_value


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_USERS_CONFIG = ROOT_DIR / "users.json"
USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class UserConfig:
    user_id: str
    display_name: str
    telegram_chat_id: int
    broker_fee: float
    db_path: str
    sandbox_token: Optional[str] = None
    token: Optional[str] = None
    enabled: bool = True

    @property
    def tokens(self) -> dict:
        return {
            "token": self.token,
            "sandbox_token": self.sandbox_token,
        }

    def active_token(self, mode: str) -> Optional[str]:
        return self.token if mode == "prod" else self.sandbox_token


@dataclass(frozen=True)
class UsersConfig:
    users: list[UserConfig]
    default_web_user_id: Optional[str]
    source_path: Path

    @property
    def enabled_users(self) -> list[UserConfig]:
        return [user for user in self.users if user.enabled]

    def get_user(self, user_id: str) -> UserConfig:
        normalized_id = _normalized(user_id)
        for user in self.users:
            if user.user_id == normalized_id:
                return user
        raise ConfigError(f"User '{normalized_id}' is not configured in {self.source_path}.")

    def get_enabled_user(self, user_id: str) -> UserConfig:
        user = self.get_user(user_id)
        if not user.enabled:
            raise ConfigError(f"User '{user.user_id}' is disabled in {self.source_path}.")
        return user

    def get_user_by_chat_id(self, chat_id: int | str) -> Optional[UserConfig]:
        normalized_chat_id = _parse_chat_id(chat_id, field_name="chat_id")
        for user in self.enabled_users:
            if user.telegram_chat_id == normalized_chat_id:
                return user
        return None

    def default_web_user(self) -> UserConfig:
        configured_default = _normalized(self.default_web_user_id)
        if configured_default:
            return self.get_enabled_user(configured_default)

        enabled = self.enabled_users
        if not enabled:
            raise ConfigError(f"No enabled users are configured in {self.source_path}.")
        return enabled[0]


def users_config_path(path: Optional[str | Path] = None, *, load_env: bool = True) -> Path:
    if load_env:
        load_dotenv()
    if path is not None:
        return _resolve_path(path)

    configured_path = _normalized(os.getenv("USERS_CONFIG_PATH"))
    if configured_path:
        return _resolve_path(configured_path)
    return DEFAULT_USERS_CONFIG


def users_config_is_configured(path: Optional[str | Path] = None, *, load_env: bool = True) -> bool:
    if load_env:
        load_dotenv()
    if path is not None:
        return True
    if _normalized(os.getenv("USERS_CONFIG_PATH")):
        return True
    return DEFAULT_USERS_CONFIG.exists()


def load_users_config(path: Optional[str | Path] = None) -> UsersConfig:
    config_path = users_config_path(path)
    if not config_path.exists():
        raise ConfigError(f"Users config file was not found: {config_path}")

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Users config file is malformed JSON: {config_path}") from exc

    if not isinstance(payload, dict):
        raise ConfigError("Users config must be a JSON object.")

    raw_users = payload.get("users")
    if not isinstance(raw_users, list) or not raw_users:
        raise ConfigError("Users config must contain a non-empty 'users' list.")

    users = [_parse_user(raw_user, config_path) for raw_user in raw_users]
    _validate_unique_users(users, config_path)
    if not any(user.enabled for user in users):
        raise ConfigError(f"Users config must contain at least one enabled user: {config_path}")

    config = UsersConfig(
        users=users,
        default_web_user_id=_normalized(os.getenv("DEFAULT_WEB_USER_ID") or payload.get("default_web_user_id")),
        source_path=config_path,
    )
    config.default_web_user()
    return config


def load_runtime_users_config() -> UsersConfig:
    if users_config_is_configured():
        return load_users_config()
    return load_legacy_env_user_config()


def load_legacy_env_user_config() -> UsersConfig:
    load_dotenv()
    user = UserConfig(
        user_id="legacy",
        display_name="Legacy .env User",
        telegram_chat_id=_parse_chat_id(os.getenv("CHAT_ID"), field_name="CHAT_ID"),
        sandbox_token=_normalize_secret(os.getenv("SANDBOX_TOKEN")),
        token=_normalize_secret(os.getenv("TOKEN")),
        broker_fee=_parse_broker_fee(os.getenv("BROKER_FEE"), "legacy"),
        db_path="database.db",
        enabled=True,
    )
    return UsersConfig(users=[user], default_web_user_id="legacy", source_path=ROOT_DIR / ".env")


def get_default_web_user_config() -> UserConfig:
    return load_runtime_users_config().default_web_user()


def validate_users_config_for_mode(mode: str) -> None:
    config = load_users_config()
    selected_token_name = "TOKEN" if mode == "prod" else "SANDBOX_TOKEN"
    for user in config.enabled_users:
        if is_placeholder_value(user.active_token(mode)):
            raise ConfigError(
                f"User '{user.user_id}' must configure {selected_token_name} "
                f"for APP_MODE='{mode}' in {config.source_path}."
            )


def _parse_user(raw_user: Any, config_path: Path) -> UserConfig:
    if not isinstance(raw_user, dict):
        raise ConfigError(f"Each user entry in {config_path} must be an object.")

    user_id = _normalized(raw_user.get("id"))
    if not user_id or not USER_ID_RE.match(user_id):
        raise ConfigError("Each user must have an id using letters, numbers, '_' or '-'.")

    display_name = _normalized(raw_user.get("name") or raw_user.get("display_name")) or user_id
    telegram_chat_id = _parse_chat_id(
        raw_user.get("telegram_chat_id", raw_user.get("chat_id")),
        field_name=f"{user_id}.telegram_chat_id",
    )
    broker_fee = _parse_broker_fee(raw_user.get("broker_fee"), user_id)
    enabled = _parse_enabled(raw_user.get("enabled", True))
    db_path = _normalized(raw_user.get("db_path")) or f"data/users/{user_id}/database.db"

    return UserConfig(
        user_id=user_id,
        display_name=display_name,
        telegram_chat_id=telegram_chat_id,
        sandbox_token=_normalize_secret(raw_user.get("sandbox_token")),
        token=_normalize_secret(raw_user.get("token")),
        broker_fee=broker_fee,
        db_path=db_path,
        enabled=enabled,
    )


def _validate_unique_users(users: list[UserConfig], config_path: Path) -> None:
    seen_ids = set()
    seen_chat_ids = set()
    for user in users:
        if user.user_id in seen_ids:
            raise ConfigError(f"Duplicate user id '{user.user_id}' in {config_path}.")
        if user.telegram_chat_id in seen_chat_ids:
            raise ConfigError(f"Duplicate telegram_chat_id '{user.telegram_chat_id}' in {config_path}.")
        seen_ids.add(user.user_id)
        seen_chat_ids.add(user.telegram_chat_id)


def _parse_chat_id(value: Any, *, field_name: str) -> int:
    normalized = _normalized(str(value) if value is not None else None)
    if is_placeholder_value(normalized):
        raise ConfigError(f"{field_name} is required.")
    try:
        return int(normalized)
    except ValueError as exc:
        raise ConfigError(f"{field_name} must be an integer Telegram chat id.") from exc


def _parse_broker_fee(value: Any, user_id: str) -> float:
    normalized = _normalized(str(value) if value is not None else None)
    if normalized == "":
        raise ConfigError(f"User '{user_id}' must configure broker_fee.")
    try:
        fee = float(normalized)
    except ValueError as exc:
        raise ConfigError(f"User '{user_id}' broker_fee must be a number.") from exc
    if fee < 0:
        raise ConfigError(f"User '{user_id}' broker_fee must be non-negative.")
    return fee


def _parse_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _normalized(str(value)).lower() in {"1", "true", "yes", "on"}


def _normalize_secret(value: Any) -> Optional[str]:
    normalized = _normalized(str(value) if value is not None else None)
    return normalized or None


def _resolve_path(path: str | Path) -> Path:
    result = Path(path)
    if result.is_absolute():
        return result
    return ROOT_DIR / result
