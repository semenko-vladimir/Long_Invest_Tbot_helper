from dataclasses import dataclass
from typing import Callable, Optional

from app.client.config.users import UserConfig, UsersConfig, load_runtime_users_config


class UnknownUserError(PermissionError):
    pass


@dataclass(frozen=True)
class UserContext:
    user_id: str
    display_name: str
    telegram_chat_id: int
    broker_fee: float
    db_path: str
    sandbox_token: Optional[str] = None
    token: Optional[str] = None

    @classmethod
    def from_config(cls, user: UserConfig) -> "UserContext":
        return cls(
            user_id=user.user_id,
            display_name=user.display_name,
            telegram_chat_id=user.telegram_chat_id,
            sandbox_token=user.sandbox_token,
            token=user.token,
            broker_fee=user.broker_fee,
            db_path=user.db_path,
        )

    @property
    def tokens(self) -> dict:
        return {
            "token": self.token,
            "sandbox_token": self.sandbox_token,
        }

    def active_token(self, mode: str) -> Optional[str]:
        return self.token if mode == "prod" else self.sandbox_token


class UserContextResolver:
    def __init__(self, *, config_loader: Callable[[], UsersConfig] = load_runtime_users_config):
        self.config_loader = config_loader

    def resolve_telegram_chat(self, chat_id: int | str) -> UserContext:
        config = self.config_loader()
        user = config.get_user_by_chat_id(chat_id)
        if user is None:
            raise UnknownUserError(f"Telegram chat_id '{chat_id}' is not authorized.")
        return UserContext.from_config(user)

    def default_web_user(self) -> UserContext:
        return UserContext.from_config(self.config_loader().default_web_user())

    def enabled_users(self) -> list[UserContext]:
        return [UserContext.from_config(user) for user in self.config_loader().enabled_users]
