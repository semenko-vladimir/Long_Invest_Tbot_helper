from datetime import datetime
import unittest
from unittest import mock

from app.services.investment_plans import (
    InvestmentPlanView,
    InvestmentPlanService,
    InvestmentPlanServiceError,
    NextRunCalculator,
    PlanDefinition,
)
from app.services.mode import ModeContext
from app.services.orders import OrderPreviewResult
from app.services.trading_policy import AutoExecutionRequest, TradingPolicyService


class FakeModeService:
    def __init__(self, mode="sandbox", trading_available=True):
        self.mode = mode
        self.trading_available = trading_available

    def current(self):
        return ModeContext(
            mode=self.mode,
            is_sandbox=self.mode == "sandbox",
            prod_trading_allowed=False,
            trading_available=self.trading_available,
            banner_title=f"Mode: {self.mode}",
            banner_message="Test mode",
        )


class FakeLedger:
    def __init__(self, daily_total=0.0):
        self.daily_total_value = daily_total
        self.blocked = []

    def daily_total(self, now=None):
        return self.daily_total_value

    def record_blocked(self, *, request, reason):
        self.blocked.append((request, reason))


class FakeOrderService:
    def __init__(self):
        self.preview_requests = []

    def preview(self, request):
        self.preview_requests.append(request)
        return OrderPreviewResult(
            operation=request.operation,
            operation_label=request.operation.title(),
            ticker=request.ticker,
            lots=request.lots,
            instrument_name="Sber",
            figi="FIGI-SBER",
            estimated_price=101.0,
            estimated_value=1_010.0,
            estimated_price_display="101.00 RUB",
            estimated_value_display="1 010.00 RUB",
            order_type=request.order_type,
            mode=FakeModeService().current(),
            trading_enabled=True,
            can_execute=True,
            requires_ticker_confirmation=False,
            warnings=[],
            confirm_token="preview-token",
        )


class InvestmentPlanTests(unittest.TestCase):
    def test_next_run_daily_moves_to_tomorrow_after_scheduled_time(self):
        calculator = NextRunCalculator()

        result = calculator.calculate(
            schedule="daily",
            time_text="09:00",
            created_at=datetime(2026, 4, 1, 12, 0),
            now=datetime(2026, 4, 11, 10, 0),
        )

        self.assertEqual(result, datetime(2026, 4, 12, 9, 0))

    def test_next_run_weekly_uses_created_weekday_as_anchor(self):
        calculator = NextRunCalculator()

        result = calculator.calculate(
            schedule="weekly",
            time_text="09:30",
            created_at=datetime(2026, 4, 6, 12, 0),
            now=datetime(2026, 4, 7, 10, 0),
        )

        self.assertEqual(result, datetime(2026, 4, 13, 9, 30))

    def test_next_run_monthly_clamps_missing_calendar_day(self):
        calculator = NextRunCalculator()

        result = calculator.calculate(
            schedule="monthly",
            time_text="08:15",
            created_at=datetime(2026, 1, 31, 12, 0),
            now=datetime(2026, 2, 1, 10, 0),
        )

        self.assertEqual(result, datetime(2026, 2, 28, 8, 15))

    def test_plan_definition_normalizes_safe_defaults(self):
        service = InvestmentPlanService(order_service=object())

        result = service._normalize_definition(
            PlanDefinition(
                ticker=" sber ",
                lots=2,
                schedule="Monthly",
                time="9:05",
            )
        )

        self.assertEqual(result.ticker, "SBER")
        self.assertEqual(result.lots, 2)
        self.assertEqual(result.schedule, "monthly")
        self.assertEqual(result.time, "09:05")
        self.assertEqual(result.price_rule, "current_market")
        self.assertEqual(result.order_type, "limit")
        self.assertTrue(result.confirmation_required)

    def test_plan_definition_rejects_unsupported_price_rule(self):
        service = InvestmentPlanService(order_service=object())

        with self.assertRaises(InvestmentPlanServiceError):
            service._normalize_definition(
                PlanDefinition(
                    ticker="SBER",
                    lots=1,
                    schedule="daily",
                    time="09:00",
                    price_rule="auto_best",
                )
            )

    def test_previous_day_average_discount_defaults_to_daily_buy_with_half_percent(self):
        service = InvestmentPlanService(order_service=object())

        result = service._normalize_definition(
            PlanDefinition(
                ticker="sber",
                lots=1,
                schedule="daily",
                time="09:00",
                price_rule="previous_day_average_discount",
            )
        )

        self.assertEqual(result.operation, "buy")
        self.assertEqual(result.price_rule, "previous_day_average_discount")
        self.assertEqual(result.pct_threshold, 0.5)
        self.assertIsNone(result.price_limit)
        self.assertIsNone(result.avg_period_days)
        self.assertEqual(result.confirmation_mode, "telegram_confirm")

    def test_previous_day_average_discount_rejects_sell_plan(self):
        service = InvestmentPlanService(order_service=object())

        with self.assertRaisesRegex(InvestmentPlanServiceError, "only for buy"):
            service._normalize_definition(
                PlanDefinition(
                    ticker="SBER",
                    lots=1,
                    schedule="daily",
                    time="09:00",
                    price_rule="previous_day_average_discount",
                    operation="sell",
                )
            )

    def test_policy_blocks_auto_when_flags_are_off(self):
        service = TradingPolicyService(mode_service=FakeModeService(), ledger=FakeLedger())

        with mock.patch("app.services.trading_policy.investment_plans_enabled", return_value=True), \
            mock.patch("app.services.trading_policy.allow_auto_investing", return_value=False), \
            mock.patch("app.services.trading_policy.get_max_order_rub", return_value=10_000.0), \
            mock.patch("app.services.trading_policy.get_max_daily_invest_rub", return_value=20_000.0):
            result = service.check_auto_execution(
                AutoExecutionRequest(
                    plan_id=1,
                    ticker="SBER",
                    estimated_value=1_000.0,
                    confirmation_required=False,
                )
            )

        self.assertFalse(result.allowed)
        self.assertIn("Auto-investing is disabled", result.message)

    def test_policy_blocks_plan_that_still_requires_manual_confirmation(self):
        ledger = FakeLedger()
        service = TradingPolicyService(mode_service=FakeModeService(), ledger=ledger)

        with mock.patch("app.services.trading_policy.investment_plans_enabled", return_value=True), \
            mock.patch("app.services.trading_policy.allow_auto_investing", return_value=True), \
            mock.patch("app.services.trading_policy.get_max_order_rub", return_value=10_000.0), \
            mock.patch("app.services.trading_policy.get_max_daily_invest_rub", return_value=20_000.0):
            result = service.check_auto_execution(
                AutoExecutionRequest(
                    plan_id=1,
                    ticker="SBER",
                    estimated_value=1_000.0,
                    confirmation_required=True,
                )
            )

        self.assertFalse(result.allowed)
        self.assertIn("requires manual confirmation", result.message)
        self.assertEqual(len(ledger.blocked), 1)

    def test_policy_blocks_order_limit_breach(self):
        ledger = FakeLedger()
        service = TradingPolicyService(mode_service=FakeModeService(), ledger=ledger)

        with mock.patch("app.services.trading_policy.investment_plans_enabled", return_value=True), \
            mock.patch("app.services.trading_policy.allow_auto_investing", return_value=True), \
            mock.patch("app.services.trading_policy.get_max_order_rub", return_value=500.0), \
            mock.patch("app.services.trading_policy.get_max_daily_invest_rub", return_value=20_000.0):
            result = service.check_auto_execution(
                AutoExecutionRequest(
                    plan_id=1,
                    ticker="SBER",
                    estimated_value=1_000.0,
                    confirmation_required=False,
                )
            )

        self.assertFalse(result.allowed)
        self.assertIn("exceeds MAX_ORDER_RUB", result.message)
        self.assertEqual(len(ledger.blocked), 1)

    def test_policy_blocks_daily_limit_breach(self):
        service = TradingPolicyService(mode_service=FakeModeService(), ledger=FakeLedger(daily_total=900.0))

        with mock.patch("app.services.trading_policy.investment_plans_enabled", return_value=True), \
            mock.patch("app.services.trading_policy.allow_auto_investing", return_value=True), \
            mock.patch("app.services.trading_policy.get_max_order_rub", return_value=5_000.0), \
            mock.patch("app.services.trading_policy.get_max_daily_invest_rub", return_value=1_000.0):
            result = service.check_auto_execution(
                AutoExecutionRequest(
                    plan_id=1,
                    ticker="SBER",
                    estimated_value=200.0,
                    confirmation_required=False,
                )
            )

        self.assertFalse(result.allowed)
        self.assertIn("exceed MAX_DAILY_INVEST_RUB", result.message)

    def test_policy_allows_sandbox_auto_with_limits_and_no_manual_confirmation(self):
        service = TradingPolicyService(mode_service=FakeModeService(), ledger=FakeLedger(daily_total=100.0))

        with mock.patch("app.services.trading_policy.investment_plans_enabled", return_value=True), \
            mock.patch("app.services.trading_policy.allow_auto_investing", return_value=True), \
            mock.patch("app.services.trading_policy.get_max_order_rub", return_value=5_000.0), \
            mock.patch("app.services.trading_policy.get_max_daily_invest_rub", return_value=10_000.0):
            result = service.check_auto_execution(
                AutoExecutionRequest(
                    plan_id=1,
                    ticker="SBER",
                    estimated_value=1_000.0,
                    confirmation_required=False,
                )
            )

        self.assertTrue(result.allowed)

    def test_plan_proposal_uses_order_preview_and_fixed_generated_time(self):
        order_service = FakeOrderService()
        service = InvestmentPlanService(
            order_service=order_service,
            now_provider=lambda: datetime(2026, 4, 12, 9, 30),
        )
        plan = InvestmentPlanView(
            id=7,
            ticker="SBER",
            lots=3,
            schedule="monthly",
            schedule_label="Monthly",
            time="09:00",
            price_rule="current_market",
            price_rule_label="Current market price",
            order_type="limit",
            order_type_label="Limit",
            confirmation_required=True,
            confirmation_label="Required",
            next_run_at="2026-04-12T09:00",
            next_run_display="2026-04-12 09:00",
        )

        proposal = service.generate_order_proposal_for_plan(plan)

        self.assertEqual(proposal.plan, plan)
        self.assertEqual(proposal.proposed_lots, 3)
        self.assertEqual(proposal.proposed_limit_price, 101.0)
        self.assertEqual(proposal.generated_at, "2026-04-12 09:30")
        self.assertEqual(order_service.preview_requests[0].operation, "buy")
        self.assertEqual(order_service.preview_requests[0].ticker, "SBER")
        self.assertEqual(order_service.preview_requests[0].lots, 3)


if __name__ == "__main__":
    unittest.main()
