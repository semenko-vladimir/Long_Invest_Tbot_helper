import unittest

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.backend.models.accounts import (
    BrokerConnection,
    InvestmentAccount,
    PortfolioSnapshot,
    PositionSnapshot,
)
from app.backend.models.database import Base
from app.integrations.broker import BrokerAccountInfo
from app.services.accounts import AccountRegistryService, InvestmentAccountContext, UnknownInvestmentAccountError
from app.services.mode import ModeContext
from app.services.portfolio import PortfolioService
from app.services.user_context import UserContext


class FakeModeService:
    def current(self):
        return ModeContext(
            mode="prod",
            is_sandbox=False,
            prod_trading_allowed=False,
            trading_available=False,
            banner_title="Mode: prod, trading disabled",
            banner_message="Read only",
        )


class FakeBroker:
    provider_key = "tinvest"

    def __init__(self, accounts):
        self.accounts = list(accounts)
        self.portfolios = {}

    def list_accounts(self, token, *, sandbox):
        return list(self.accounts)

    def get_portfolio(self, token, *, account_id, sandbox):
        return self.portfolios[account_id]

    def get_instrument_name(self, token, figi):
        return None


def info(external_id: str, name: str | None = None) -> BrokerAccountInfo:
    return BrokerAccountInfo(
        external_account_id=external_id,
        name=name or f"Account {external_id}",
        account_type="BROKER",
        status="OPEN",
        access_level="FULL_ACCESS",
    )


class AccountRegistryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.user = UserContext(
            user_id="user-1",
            display_name="User",
            telegram_chat_id=1,
            broker_fee=0.3,
            db_path=":memory:",
            token="not-a-real-token",
        )

    def tearDown(self):
        self.engine.dispose()

    def registry(self, broker):
        return AccountRegistryService(
            broker=broker,
            session_factory=self.session_factory,
            user=self.user,
            mode_service=FakeModeService(),
            token_provider=lambda: "not-a-real-token",
        )

    def test_discovers_one_two_and_three_or_more_accounts(self):
        for count in (1, 2, 4):
            with self.subTest(count=count):
                engine = create_engine("sqlite://")
                Base.metadata.create_all(engine)
                factory = sessionmaker(bind=engine)
                broker = FakeBroker([info(str(index)) for index in range(count)])
                registry = AccountRegistryService(
                    broker=broker,
                    session_factory=factory,
                    user=self.user,
                    mode_service=FakeModeService(),
                    token_provider=lambda: "token",
                )
                self.assertEqual(len(registry.sync_accounts().accounts), count)
                engine.dispose()

    def test_upsert_is_order_independent_and_later_iis_is_discovered(self):
        broker = FakeBroker([info("ordinary-a"), info("ordinary-b")])
        registry = self.registry(broker)
        first = registry.sync_accounts()
        first_ids = {item.external_account_id: item.investment_account_id for item in first.accounts}

        broker.accounts = [info("ordinary-b", "Renamed B"), info("ordinary-a"), info("iis", "IIS")]
        second = registry.sync_accounts()
        second_ids = {item.external_account_id: item.investment_account_id for item in second.accounts}

        self.assertEqual(second.created_count, 1)
        self.assertEqual(second_ids["ordinary-a"], first_ids["ordinary-a"])
        self.assertEqual(second_ids["ordinary-b"], first_ids["ordinary-b"])
        self.assertIn("iis", second_ids)
        db = self.session_factory()
        try:
            self.assertEqual(db.query(InvestmentAccount).count(), 3)
            self.assertEqual(
                db.query(InvestmentAccount).filter_by(external_account_id="ordinary-b").one().display_name,
                "Renamed B",
            )
        finally:
            db.close()

    def test_missing_account_is_not_deleted_or_disabled_after_one_response(self):
        broker = FakeBroker([info("a"), info("b")])
        registry = self.registry(broker)
        first = registry.sync_accounts()
        first_ids = {
            item.external_account_id: item.investment_account_id
            for item in first.accounts
        }
        broker.accounts = [info("a")]
        second = registry.sync_accounts()

        self.assertEqual({item.external_account_id for item in second.accounts}, {"a"})
        self.assertEqual({item.external_account_id for item in registry.list_enabled_accounts()}, {"a", "b"})

        broker.accounts = [info("b"), info("a")]
        third = registry.sync_accounts()
        third_ids = {
            item.external_account_id: item.investment_account_id
            for item in third.accounts
        }
        self.assertEqual(third_ids, first_ids)
        db = self.session_factory()
        try:
            self.assertEqual(db.query(InvestmentAccount).count(), 2)
        finally:
            db.close()

    def test_aggregate_after_fresh_sync_excludes_historical_missing_account(self):
        broker = FakeBroker([info("a"), info("b")])
        registry = self.registry(broker)
        registry.sync_accounts()
        broker.accounts = [info("a")]
        broker.portfolios = {
            "a": {"total_amount_portfolio": 110, "positions": []},
        }
        service = PortfolioService(
            broker=broker,
            mode_service=FakeModeService(),
            token_provider=lambda: "token",
            account_registry=registry,
            session_factory=self.session_factory,
        )

        aggregate = service.get_aggregate_portfolio()

        self.assertEqual(
            [view.account.external_account_id for view in aggregate.accounts],
            ["a"],
        )
        self.assertEqual(aggregate.total_value, 110)

    def test_closed_and_new_accounts_are_persisted_but_excluded_from_current_sync(self):
        broker = FakeBroker([
            info("open"),
            BrokerAccountInfo("closed", "Closed", status="closed"),
            BrokerAccountInfo("new", "New", status="new"),
        ])
        registry = self.registry(broker)

        result = registry.sync_accounts()

        self.assertEqual([item.external_account_id for item in result.accounts], ["open"])
        db = self.session_factory()
        try:
            self.assertEqual(db.query(InvestmentAccount).count(), 3)
            self.assertEqual(db.query(InvestmentAccount).filter_by(external_account_id="closed").one().status, "closed")
        finally:
            db.close()

    def test_context_from_another_user_cannot_be_validated(self):
        broker = FakeBroker([info("a")])
        registry = self.registry(broker)
        context = registry.sync_accounts().accounts[0]
        foreign_context = InvestmentAccountContext(
            **{**context.__dict__, "user_id": "another-user"}
        )

        with self.assertRaisesRegex(UnknownInvestmentAccountError, "current user"):
            registry.validate_account_context(foreign_context)

    def test_strategy_profiles_and_snapshots_are_account_scoped(self):
        broker = FakeBroker([info("a"), info("b")])
        registry = self.registry(broker)
        accounts = registry.sync_accounts().accounts
        account_a, account_b = accounts
        registry.save_strategy_profile(
            account_a,
            title="Income",
            thesis="Hold dividend compounders",
            settings={"horizon": "long"},
        )
        registry.save_strategy_profile(
            account_b,
            title="Growth",
            thesis="Accept volatility for growth",
            settings={"risk": "high"},
            analysis_profile_key="growth-long-horizon",
        )

        first_profile_id = registry.get_account_context(
            account_a.investment_account_id
        ).strategy.id
        updated_a = registry.save_strategy_profile(
            account_a,
            title="Income and quality",
            thesis="Hold dividend compounders",
            settings={"horizon": "long"},
        )
        self.assertEqual(updated_a.strategy.id, first_profile_id)

        refreshed = {item.external_account_id: item for item in registry.list_enabled_accounts()}
        self.assertEqual(refreshed["a"].strategy.title, "Income and quality")
        self.assertEqual(refreshed["a"].strategy.thesis, "Hold dividend compounders")
        self.assertEqual(refreshed["b"].strategy.settings, {"risk": "high"})
        self.assertEqual(refreshed["b"].strategy.analysis_profile_key, "growth-long-horizon")
        self.assertNotEqual(refreshed["a"].strategy.id, refreshed["b"].strategy.id)

        same_position = {
            "ticker": "SBER",
            "figi": "FIGI-SBER",
            "instrument_uid": "UID-SBER",
            "quantity": 1,
            "average_position_price": 100,
            "current_price_one": 110,
            "current_price": 110,
            "expected_yield": 10,
        }
        broker.portfolios = {
            "a": {"total_amount_portfolio": 110, "positions": [same_position]},
            "b": {"total_amount_portfolio": 220, "positions": [{**same_position, "quantity": 2, "current_price": 220}]},
        }
        service = PortfolioService(
            broker=broker,
            mode_service=FakeModeService(),
            token_provider=lambda: "token",
            account_registry=registry,
            session_factory=self.session_factory,
        )
        service.get_aggregate_portfolio(sync_accounts=False)

        db = self.session_factory()
        try:
            snapshots = db.query(PortfolioSnapshot).all()
            positions = db.query(PositionSnapshot).filter_by(ticker="SBER").all()
            self.assertEqual({row.investment_account_id for row in snapshots}, {
                account_a.investment_account_id,
                account_b.investment_account_id,
            })
            self.assertEqual(len(positions), 2)
            self.assertEqual({row.investment_account_id for row in positions}, {
                account_a.investment_account_id,
                account_b.investment_account_id,
            })
        finally:
            db.close()

    def test_new_tables_contain_no_credential_columns(self):
        inspector = inspect(self.engine)
        for table_name in (
            "broker_connections",
            "investment_accounts",
            "strategy_profiles",
            "portfolio_snapshots",
            "position_snapshots",
        ):
            columns = {column["name"].lower() for column in inspector.get_columns(table_name)}
            self.assertFalse(columns.intersection({"token", "secret", "password", "api_key"}))


if __name__ == "__main__":
    unittest.main()
