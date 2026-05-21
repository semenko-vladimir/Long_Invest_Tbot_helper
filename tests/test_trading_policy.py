"""
Tests for app/services/trading_policy.py

Coverage:
  TradingPolicyService.check_auto_execution()
    - mode-based blocks (plans disabled, prod mode, trading unavailable)
    - per-order limit boundaries (== allowed, > blocked, zero)
    - daily limit boundaries (== allowed, > blocked, exhausted, zero)
    - ledger interaction (allowed => no record_blocked, blocked => record_blocked)
    - multiple block reasons accumulate
  TradingPolicyService.require_plans_enabled()
  TradingPolicyService.current_status() — summary strings and limit display
  PolicyCheckResult — allowed flag and message property
  InvestmentPlanExecutionLedger.daily_total() — DB filtering logic
    (in-memory SQLite; tests the real query, not a stub)
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import unittest
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.backend.models.database import Base
from app.backend.models.trading import InvestmentPlanExecution
from app.services.mode import ModeContext
from app.services.trading_policy import (
    AutoExecutionRequest,
    InvestmentPlanExecutionLedger,
    PolicyCheckResult,
    TradingPolicyError,
    TradingPolicyService,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeModeService:
    def __init__(self, *, mode="sandbox", trading_available=True):
        self.mode = mode
        self.trading_available = trading_available

    def current(self):
        return ModeContext(
            mode=self.mode,
            is_sandbox=self.mode == "sandbox",
            prod_trading_allowed=self.mode == "prod" and self.trading_available,
            trading_available=self.trading_available,
            banner_title=f"Mode: {self.mode}",
            banner_message="Test mode",
        )


class RecordingLedger:
    """Fake ledger that records all method calls for assertion."""
    def __init__(self, *, daily_total=0.0):
        self._daily_total = daily_total
        self.blocked_calls: list = []
        self.executed_calls: list = []

    def daily_total(self, *, now=None):
        return self._daily_total

    def record_blocked(self, *, request, reason):
        self.blocked_calls.append((request, reason))

    def record_executed(self, *, request, order_id):
        self.executed_calls.append((request, order_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def _patch_config(
    *,
    plans_enabled=True,
    auto_investing=True,
    max_order=5_000.0,
    max_daily=20_000.0,
):
    """Patches all four config read functions used by TradingPolicyService."""
    with mock.patch("app.services.trading_policy.investment_plans_enabled", return_value=plans_enabled), \
         mock.patch("app.services.trading_policy.allow_auto_investing", return_value=auto_investing), \
         mock.patch("app.services.trading_policy.get_max_order_rub", return_value=max_order), \
         mock.patch("app.services.trading_policy.get_max_daily_invest_rub", return_value=max_daily):
        yield


def _make_request(*, estimated_value=1_000.0, confirmation_required=False):
    return AutoExecutionRequest(
        plan_id=1,
        ticker="SBER",
        estimated_value=estimated_value,
        confirmation_required=confirmation_required,
    )


def _make_in_memory_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


# ---------------------------------------------------------------------------
# TradingPolicyService tests
# ---------------------------------------------------------------------------

class TradingPolicyServiceTests(unittest.TestCase):
    def _build(self, *, mode="sandbox", trading_available=True, daily_total=0.0):
        ledger = RecordingLedger(daily_total=daily_total)
        service = TradingPolicyService(
            mode_service=FakeModeService(mode=mode, trading_available=trading_available),
            ledger=ledger,
        )
        return service, ledger

    # ---- mode-based blocks ------------------------------------------------

    def test_blocks_when_investment_plans_are_disabled(self):
        service, ledger = self._build()
        with _patch_config(plans_enabled=False, auto_investing=True):
            result = service.check_auto_execution(_make_request())

        self.assertFalse(result.allowed)
        self.assertIn("Investment plans are disabled", result.message)
        self.assertEqual(len(ledger.blocked_calls), 1)

    def test_blocks_in_prod_mode_when_auto_investing_is_configured(self):
        service, _ = self._build(mode="prod", trading_available=True)
        with _patch_config(auto_investing=True):
            result = service.check_auto_execution(_make_request())

        self.assertFalse(result.allowed)
        self.assertIn("allowed only in sandbox mode", result.message)

    def test_blocks_when_trading_is_unavailable_even_in_sandbox(self):
        service, _ = self._build(mode="sandbox", trading_available=False)
        with _patch_config(auto_investing=True):
            result = service.check_auto_execution(_make_request())

        self.assertFalse(result.allowed)
        self.assertIn("Trading is blocked", result.message)

    # ---- per-order limit boundaries ---------------------------------------

    def test_allows_order_at_exactly_the_per_order_limit(self):
        # Condition is strictly >, so == is permitted.
        service, _ = self._build()
        with _patch_config(max_order=1_000.0, max_daily=20_000.0):
            result = service.check_auto_execution(_make_request(estimated_value=1_000.0))

        self.assertTrue(result.allowed)

    def test_blocks_order_one_cent_over_the_per_order_limit(self):
        service, _ = self._build()
        with _patch_config(max_order=999.99, max_daily=20_000.0):
            result = service.check_auto_execution(_make_request(estimated_value=1_000.0))

        self.assertFalse(result.allowed)
        self.assertIn("exceeds MAX_ORDER_RUB", result.message)

    def test_blocks_when_max_order_rub_is_zero(self):
        service, _ = self._build()
        with _patch_config(max_order=0.0, max_daily=20_000.0):
            result = service.check_auto_execution(_make_request())

        self.assertFalse(result.allowed)
        self.assertIn("MAX_ORDER_RUB", result.message)

    # ---- daily limit boundaries -------------------------------------------

    def test_allows_order_that_exactly_fills_the_remaining_daily_budget(self):
        # daily_used(900) + estimated(100) == max_daily(1000): condition is >, so allowed.
        service, _ = self._build(daily_total=900.0)
        with _patch_config(max_order=5_000.0, max_daily=1_000.0):
            result = service.check_auto_execution(_make_request(estimated_value=100.0))

        self.assertTrue(result.allowed)

    def test_blocks_order_that_exceeds_the_daily_budget_by_one(self):
        # daily_used(900) + estimated(101) > max_daily(1000): blocked.
        service, _ = self._build(daily_total=900.0)
        with _patch_config(max_order=5_000.0, max_daily=1_000.0):
            result = service.check_auto_execution(_make_request(estimated_value=101.0))

        self.assertFalse(result.allowed)
        self.assertIn("exceed MAX_DAILY_INVEST_RUB", result.message)

    def test_blocks_when_the_daily_budget_is_fully_exhausted(self):
        # daily_used equals max_daily; any new order exceeds it.
        service, _ = self._build(daily_total=1_000.0)
        with _patch_config(max_order=5_000.0, max_daily=1_000.0):
            result = service.check_auto_execution(_make_request(estimated_value=1.0))

        self.assertFalse(result.allowed)

    def test_blocks_when_max_daily_rub_is_zero(self):
        service, _ = self._build()
        with _patch_config(max_order=5_000.0, max_daily=0.0):
            result = service.check_auto_execution(_make_request())

        self.assertFalse(result.allowed)
        self.assertIn("MAX_DAILY_INVEST_RUB", result.message)

    # ---- ledger interaction -----------------------------------------------

    def test_allowed_result_does_not_call_record_blocked(self):
        service, ledger = self._build()
        with _patch_config():
            result = service.check_auto_execution(_make_request())

        self.assertTrue(result.allowed)
        self.assertEqual(len(ledger.blocked_calls), 0)

    def test_blocked_result_calls_record_blocked_exactly_once(self):
        service, ledger = self._build()
        with _patch_config(auto_investing=False):
            result = service.check_auto_execution(_make_request())

        self.assertFalse(result.allowed)
        self.assertEqual(len(ledger.blocked_calls), 1)
        recorded_request, recorded_reason = ledger.blocked_calls[0]
        self.assertEqual(recorded_request.ticker, "SBER")
        self.assertIn("Auto-investing is disabled", recorded_reason)

    def test_multiple_independent_block_reasons_all_appear_in_message(self):
        # auto_investing=False adds one reason; confirmation_required=True adds another.
        service, _ = self._build()
        with _patch_config(auto_investing=False):
            result = service.check_auto_execution(_make_request(confirmation_required=True))

        self.assertFalse(result.allowed)
        self.assertIn("Auto-investing is disabled", result.message)
        self.assertIn("requires manual confirmation", result.message)

    # ---- require_plans_enabled --------------------------------------------

    def test_require_plans_enabled_raises_trading_policy_error_when_disabled(self):
        service, _ = self._build()
        with mock.patch("app.services.trading_policy.investment_plans_enabled", return_value=False):
            with self.assertRaises(TradingPolicyError):
                service.require_plans_enabled()

    def test_require_plans_enabled_does_not_raise_when_enabled(self):
        service, _ = self._build()
        with mock.patch("app.services.trading_policy.investment_plans_enabled", return_value=True):
            service.require_plans_enabled()  # must not raise

    # ---- current_status summary strings -----------------------------------

    def test_summary_when_plans_are_disabled(self):
        service, _ = self._build()
        with _patch_config(plans_enabled=False):
            status = service.current_status()

        self.assertEqual(status.summary, "Investment plans are unavailable.")

    def test_summary_when_auto_investing_is_disabled(self):
        service, _ = self._build()
        with _patch_config(auto_investing=False):
            status = service.current_status()

        self.assertEqual(status.summary, "Plans are enabled in proposal/manual confirmation mode.")

    def test_summary_when_auto_is_configured_but_mode_is_not_sandbox(self):
        service, _ = self._build(mode="prod", trading_available=True)
        with _patch_config(auto_investing=True):
            status = service.current_status()

        self.assertEqual(status.summary, "Auto-investing is configured but blocked in this mode.")

    def test_summary_when_sandbox_auto_investing_is_fully_nominal(self):
        service, _ = self._build(mode="sandbox", trading_available=True)
        with _patch_config(auto_investing=True):
            status = service.current_status()

        self.assertEqual(status.summary, "Auto-investing is constrained by mode checks and RUB limits.")

    # ---- current_status daily remaining -----------------------------------

    def test_daily_remaining_is_zero_when_budget_is_exactly_exhausted(self):
        service, _ = self._build(daily_total=20_000.0)
        with _patch_config(max_daily=20_000.0):
            status = service.current_status()

        self.assertEqual(status.daily_remaining_rub, 0.0)


# ---------------------------------------------------------------------------
# PolicyCheckResult tests
# ---------------------------------------------------------------------------

class PolicyCheckResultTests(unittest.TestCase):
    def test_allowed_when_no_reasons(self):
        result = PolicyCheckResult(allowed=True, reasons=[])
        self.assertTrue(result.allowed)

    def test_not_allowed_when_reasons_are_present(self):
        result = PolicyCheckResult(allowed=False, reasons=["reason A"])
        self.assertFalse(result.allowed)

    def test_message_joins_reasons_with_a_single_space(self):
        result = PolicyCheckResult(allowed=False, reasons=["reason A", "reason B"])
        self.assertEqual(result.message, "reason A reason B")

    def test_message_is_empty_string_when_no_reasons(self):
        result = PolicyCheckResult(allowed=True, reasons=[])
        self.assertEqual(result.message, "")


# ---------------------------------------------------------------------------
# InvestmentPlanExecutionLedger tests (real in-memory SQLite)
# ---------------------------------------------------------------------------

class InvestmentPlanExecutionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.session_factory = _make_in_memory_session_factory()

    def _insert(self, *, status="executed", amount_rub=1_000.0, created_at=None):
        if created_at is None:
            created_at = datetime.utcnow()
        db = self.session_factory()
        try:
            db.add(InvestmentPlanExecution(
                plan_id=1,
                ticker="SBER",
                amount_rub=amount_rub,
                status=status,
                execution_mode="auto",
                created_at=created_at,
            ))
            db.commit()
        finally:
            db.close()

    def test_returns_zero_with_no_records(self):
        ledger = InvestmentPlanExecutionLedger(session_factory=self.session_factory)
        self.assertEqual(ledger.daily_total(), 0.0)

    def test_sums_multiple_executed_records_for_today(self):
        self._insert(amount_rub=1_000.0)
        self._insert(amount_rub=500.0)
        ledger = InvestmentPlanExecutionLedger(session_factory=self.session_factory)
        self.assertEqual(ledger.daily_total(), 1_500.0)

    def test_excludes_blocked_records_from_sum(self):
        self._insert(status="blocked", amount_rub=9_000.0)
        self._insert(status="executed", amount_rub=200.0)
        ledger = InvestmentPlanExecutionLedger(session_factory=self.session_factory)
        self.assertEqual(ledger.daily_total(), 200.0)

    def test_excludes_records_from_yesterday(self):
        yesterday = datetime.utcnow() - timedelta(days=1)
        self._insert(amount_rub=9_000.0, created_at=yesterday)
        self._insert(amount_rub=300.0)  # today
        ledger = InvestmentPlanExecutionLedger(session_factory=self.session_factory)
        self.assertEqual(ledger.daily_total(), 300.0)

    def test_excludes_records_from_tomorrow(self):
        tomorrow = datetime.utcnow() + timedelta(days=1)
        self._insert(amount_rub=9_000.0, created_at=tomorrow)
        self._insert(amount_rub=100.0)  # today
        ledger = InvestmentPlanExecutionLedger(session_factory=self.session_factory)
        self.assertEqual(ledger.daily_total(), 100.0)

    def test_respects_explicit_now_parameter_for_date_window(self):
        target_date = datetime(2026, 3, 15, 12, 0)
        other_date = datetime(2026, 3, 14, 12, 0)
        self._insert(amount_rub=1_000.0, created_at=target_date)
        self._insert(amount_rub=9_999.0, created_at=other_date)
        ledger = InvestmentPlanExecutionLedger(session_factory=self.session_factory)
        self.assertEqual(ledger.daily_total(now=target_date), 1_000.0)

    def test_normalizes_explicit_timezone_aware_now_to_utc(self):
        moscow_time = datetime(2026, 3, 15, 1, 30, tzinfo=timezone(timedelta(hours=3)))
        utc_date = datetime(2026, 3, 14, 12, 0)
        local_date = datetime(2026, 3, 15, 12, 0)
        self._insert(amount_rub=1_000.0, created_at=utc_date)
        self._insert(amount_rub=9_999.0, created_at=local_date)
        ledger = InvestmentPlanExecutionLedger(session_factory=self.session_factory)
        self.assertEqual(ledger.daily_total(now=moscow_time), 1_000.0)

    def test_returns_zero_when_only_blocked_and_old_records_exist(self):
        yesterday = datetime.utcnow() - timedelta(days=1)
        self._insert(status="blocked", amount_rub=500.0)          # today, wrong status
        self._insert(status="executed", amount_rub=200.0, created_at=yesterday)  # wrong date
        ledger = InvestmentPlanExecutionLedger(session_factory=self.session_factory)
        self.assertEqual(ledger.daily_total(), 0.0)


if __name__ == "__main__":
    unittest.main()
