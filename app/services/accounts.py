import json
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy.exc import IntegrityError

from app.backend.models.accounts import BrokerConnection, InvestmentAccount, StrategyProfile, utc_now
from app.integrations.broker import BrokerAdapter, BrokerAccountInfo
from app.services.mode import ModeService
from app.services.user_context import UserContext
from app.services.user_database import SessionFactory


DEFAULT_TINVEST_CONNECTION_KEY = "default"


@dataclass(frozen=True)
class StrategyProfileContext:
    id: int
    title: str | None
    strategy_key: str | None
    thesis: str | None
    settings: dict
    analysis_profile_key: str | None


@dataclass(frozen=True)
class InvestmentAccountContext:
    user_id: str
    investment_account_id: int
    broker_connection_id: int
    broker_provider: str
    broker_connection_key: str
    external_account_id: str
    account_name: str
    account_type: str | None
    status: str | None
    access_level: str | None
    strategy: StrategyProfileContext | None = None


@dataclass(frozen=True)
class AccountRegistryResult:
    accounts: tuple[InvestmentAccountContext, ...]
    created_count: int
    updated_count: int


class UnknownInvestmentAccountError(LookupError):
    pass


class AccountRegistryService:
    def __init__(
        self,
        *,
        broker: BrokerAdapter,
        session_factory: SessionFactory,
        user: UserContext,
        mode_service: Optional[ModeService] = None,
        token_provider: Optional[Callable[[], Optional[str]]] = None,
        connection_key: str = DEFAULT_TINVEST_CONNECTION_KEY,
        connection_name: str = "T-Invest",
    ):
        self.broker = broker
        self.session_factory = session_factory
        self.user = user
        self.mode_service = mode_service or ModeService()
        self.token_provider = token_provider or (lambda: user.active_token(self.mode_service.current().mode))
        self.connection_key = connection_key
        self.connection_name = connection_name

    def sync_accounts(self) -> AccountRegistryResult:
        mode = self.mode_service.current()
        token = self.token_provider()
        if not token:
            raise ValueError("No broker token is configured for the current mode.")

        discovered = self.broker.list_accounts(token, sandbox=mode.is_sandbox)
        self._validate_discovery(discovered)
        db = self.session_factory()
        try:
            connection = self._get_or_create_connection(db)
            existing = {
                row.external_account_id: row
                for row in db.query(InvestmentAccount).filter(
                    InvestmentAccount.broker_connection_id == connection.id
                )
            }
            now = utc_now()
            seen_external_ids = {
                account_info.external_account_id
                for account_info in discovered
            }
            created_count = 0
            updated_count = 0
            for account_info in discovered:
                account = existing.get(account_info.external_account_id)
                if account is None:
                    account = InvestmentAccount(
                        broker_connection_id=connection.id,
                        external_account_id=account_info.external_account_id,
                        display_name=account_info.name or "Broker account",
                        account_type=account_info.account_type,
                        status=account_info.status,
                        access_level=account_info.access_level,
                        enabled=True,
                        discovered_at=now,
                        last_seen_at=now,
                    )
                    db.add(account)
                    existing[account_info.external_account_id] = account
                    created_count += 1
                else:
                    account.display_name = account_info.name or account.display_name
                    account.account_type = account_info.account_type
                    account.status = account_info.status
                    account.access_level = account_info.access_level
                    account.last_seen_at = now
                    account.updated_at = now
                    updated_count += 1

            connection.updated_at = now
            db.commit()
            rows = self._current_account_rows(db, connection.id, seen_external_ids)
            return AccountRegistryResult(
                accounts=tuple(self._to_context(row, connection) for row in rows),
                created_count=created_count,
                updated_count=updated_count,
            )
        except IntegrityError:
            db.rollback()
            raise
        finally:
            db.close()

    def list_enabled_accounts(self) -> tuple[InvestmentAccountContext, ...]:
        db = self.session_factory()
        try:
            connection = self._find_connection(db)
            if connection is None or not connection.enabled:
                return ()
            return tuple(
                self._to_context(row, connection)
                for row in self._enabled_account_rows(db, connection.id)
            )
        finally:
            db.close()

    def get_account_context(self, investment_account_id: int) -> InvestmentAccountContext:
        db = self.session_factory()
        try:
            connection = self._find_connection(db)
            if connection is None or not connection.enabled:
                raise UnknownInvestmentAccountError("Investment account is unavailable or no longer enabled.")
            account = db.query(InvestmentAccount).filter(
                InvestmentAccount.id == investment_account_id,
                InvestmentAccount.broker_connection_id == connection.id,
                InvestmentAccount.enabled.is_(True),
            ).first()
            if account is None:
                raise UnknownInvestmentAccountError("Investment account is unavailable or no longer enabled.")
            return self._to_context(account, connection)
        finally:
            db.close()

    def validate_account_context(
        self,
        account_context: InvestmentAccountContext,
    ) -> InvestmentAccountContext:
        if account_context.user_id != self.user.user_id:
            raise UnknownInvestmentAccountError("Investment account does not belong to the current user.")
        canonical = self.get_account_context(account_context.investment_account_id)
        if (
            canonical.broker_connection_id != account_context.broker_connection_id
            or canonical.broker_provider != account_context.broker_provider
            or canonical.broker_connection_key != account_context.broker_connection_key
            or canonical.external_account_id != account_context.external_account_id
        ):
            raise UnknownInvestmentAccountError("Investment account context is stale or invalid.")
        return canonical

    def save_strategy_profile(
        self,
        account_context: InvestmentAccountContext,
        *,
        title: str | None = None,
        strategy_key: str | None = None,
        thesis: str | None = None,
        settings: dict | None = None,
        analysis_profile_key: str | None = None,
    ) -> InvestmentAccountContext:
        """Create or replace the selected account's single active strategy profile."""
        canonical = self.validate_account_context(account_context)
        if settings is not None and not isinstance(settings, dict):
            raise ValueError("Strategy settings must be a JSON object.")

        settings_json = None
        if settings is not None:
            try:
                settings_json = json.dumps(settings, ensure_ascii=False, sort_keys=True)
            except (TypeError, ValueError) as exc:
                raise ValueError("Strategy settings must contain JSON-compatible values.") from exc

        db = self.session_factory()
        try:
            profile = db.query(StrategyProfile).filter(
                StrategyProfile.investment_account_id == canonical.investment_account_id
            ).first()
            if profile is None:
                profile = StrategyProfile(investment_account_id=canonical.investment_account_id)
                db.add(profile)
            profile.title = title
            profile.strategy_key = strategy_key
            profile.thesis = thesis
            profile.settings_json = settings_json
            profile.analysis_profile_key = analysis_profile_key
            profile.updated_at = utc_now()
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return self.get_account_context(canonical.investment_account_id)

    def _get_or_create_connection(self, db) -> BrokerConnection:
        connection = self._find_connection(db)
        if connection is None:
            connection = BrokerConnection(
                provider_key=self.broker.provider_key,
                connection_key=self.connection_key,
                display_name=self.connection_name,
                enabled=True,
            )
            db.add(connection)
            db.flush()
        return connection

    def _find_connection(self, db) -> BrokerConnection | None:
        return db.query(BrokerConnection).filter(
            BrokerConnection.provider_key == self.broker.provider_key,
            BrokerConnection.connection_key == self.connection_key,
        ).first()

    @staticmethod
    def _enabled_account_rows(db, connection_id: int) -> list[InvestmentAccount]:
        return db.query(InvestmentAccount).filter(
            InvestmentAccount.broker_connection_id == connection_id,
            InvestmentAccount.enabled.is_(True),
        ).order_by(InvestmentAccount.id.asc()).all()

    @staticmethod
    def _current_account_rows(
        db,
        connection_id: int,
        seen_external_ids: set[str],
    ) -> list[InvestmentAccount]:
        if not seen_external_ids:
            return []
        rows = db.query(InvestmentAccount).filter(
            InvestmentAccount.broker_connection_id == connection_id,
            InvestmentAccount.enabled.is_(True),
            InvestmentAccount.external_account_id.in_(seen_external_ids),
        ).order_by(InvestmentAccount.id.asc()).all()
        return [row for row in rows if _is_portfolio_readable(row.status)]

    def _to_context(
        self,
        account: InvestmentAccount,
        connection: BrokerConnection,
    ) -> InvestmentAccountContext:
        strategy = account.strategy_profile
        strategy_context = None
        if strategy is not None:
            strategy_context = StrategyProfileContext(
                id=strategy.id,
                title=strategy.title,
                strategy_key=strategy.strategy_key,
                thesis=strategy.thesis,
                settings=_parse_settings(strategy.settings_json),
                analysis_profile_key=strategy.analysis_profile_key,
            )
        return InvestmentAccountContext(
            user_id=self.user.user_id,
            investment_account_id=account.id,
            broker_connection_id=connection.id,
            broker_provider=connection.provider_key,
            broker_connection_key=connection.connection_key,
            external_account_id=account.external_account_id,
            account_name=account.display_name,
            account_type=account.account_type,
            status=account.status,
            access_level=account.access_level,
            strategy=strategy_context,
        )

    @staticmethod
    def _validate_discovery(accounts: list[BrokerAccountInfo]) -> None:
        identifiers = [account.external_account_id for account in accounts]
        if any(not identifier for identifier in identifiers):
            raise ValueError("Broker returned an account without a stable identifier.")
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Broker returned duplicate account identifiers.")


def _parse_settings(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _is_portfolio_readable(status: str | None) -> bool:
    return str(status or "").strip().lower() == "open"
