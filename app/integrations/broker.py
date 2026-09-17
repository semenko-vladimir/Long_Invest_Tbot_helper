from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BrokerAccountInfo:
    external_account_id: str
    name: str
    account_type: str | None = None
    status: str | None = None
    access_level: str | None = None


class BrokerAdapter(Protocol):
    provider_key: str

    def list_accounts(self, token: str, *, sandbox: bool) -> list[BrokerAccountInfo]:
        """Return existing broker accounts without creating or mutating them."""

    def get_portfolio(self, token: str, *, account_id: str, sandbox: bool) -> dict:
        """Return exactly one account's portfolio."""

    def get_instrument_name(self, token: str, figi: str) -> str | None:
        """Resolve a safe display name for an instrument when available."""
