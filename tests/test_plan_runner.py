from types import SimpleNamespace
from unittest.mock import MagicMock
import unittest

from app.services.orders import OrderConfirmCommand, OrderExecutionBlocked
from app.services.plan_runner import PlanRunner, _is_preview_expired
from app.services.price_conditions import PriceConditionResult


def fake_plan(**kwargs):
    values = dict(
        plan_id=1, ticker="SBER", operation="buy", lots=2,
        price_rule="any", price_limit=None, pct_threshold=None, avg_period_days=None,
    )
    values.update(kwargs)
    return SimpleNamespace(**values)


def fake_preview(**kwargs):
    values = dict(estimated_price=100.0, estimated_value=200.0, confirm_token="tok-old")
    values.update(kwargs)
    return SimpleNamespace(**values)


def fake_exec_result(**kwargs):
    values = dict(order_id="ord-42")
    values.update(kwargs)
    return SimpleNamespace(**values)


class PlanRunnerExecuteTests(unittest.TestCase):

    def make_runner(self, **overrides):
        notify = MagicMock()
        defaults = dict(
            plan_service=MagicMock(),
            price_condition_service=MagicMock(),
            confirmation_service=MagicMock(),
            order_service=MagicMock(),
            session_factory=MagicMock(return_value=MagicMock()),
            telegram_chat_id=42,
            notify_fn=notify,
            send_confirmation_fn=MagicMock(),
        )
        defaults.update(overrides)
        runner = PlanRunner(**defaults)
        runner._record_execution = MagicMock()
        runner._record_skip = MagicMock()
        return runner

    def test_execute_happy_path(self):
        """execute() succeeds on first try — record execution and send ✅ notification."""
        runner = self.make_runner()
        plan = fake_plan()
        preview = fake_preview()
        runner.order_service.execute.return_value = fake_exec_result()

        runner._execute(plan_id=1, plan=plan, preview=preview)

        runner._record_execution.assert_called_once_with(1, "SBER", "ord-42", 200.0)
        runner.notify.assert_called_once()
        self.assertIn("✅", runner.notify.call_args[0][1])
        runner._record_skip.assert_not_called()

    def test_execute_expired_token_retry_succeeds(self):
        """
        First execute raises an 'expired' error → re-preview → condition OK →
        execute with fresh token succeeds → record and notify ✅.
        """
        runner = self.make_runner()
        plan = fake_plan()
        old_preview = fake_preview(confirm_token="tok-old")
        fresh = fake_preview(confirm_token="tok-new", estimated_price=105.0, estimated_value=210.0)

        runner.order_service.execute.side_effect = [
            OrderExecutionBlocked("This preview has expired or was already used. Preview the order again."),
            fake_exec_result(),
        ]
        runner.order_service.preview.return_value = fresh
        runner.price_condition_service.check.return_value = PriceConditionResult(
            allowed=True, reason="OK", current_price=105.0
        )

        runner._execute(plan_id=1, plan=plan, preview=old_preview)

        # second execute() call must use the fresh token, not the old one
        second_call_cmd = runner.order_service.execute.call_args_list[1].args[0]
        self.assertEqual(second_call_cmd.confirm_token, "tok-new")

        runner._record_execution.assert_called_once_with(1, "SBER", "ord-42", 210.0)
        runner._record_skip.assert_not_called()
        notify_texts = [call[0][1] for call in runner.notify.call_args_list]
        self.assertTrue(any("✅" in t for t in notify_texts))

    def test_execute_expired_token_retry_condition_fails(self):
        """
        First execute raises 'expired' → re-preview → price condition fails →
        record skip with 'price_condition_on_retry' and notify ⏭.
        """
        runner = self.make_runner()
        plan = fake_plan()
        old_preview = fake_preview(confirm_token="tok-old")
        fresh = fake_preview(confirm_token="tok-new", estimated_price=150.0, estimated_value=300.0)

        runner.order_service.execute.side_effect = OrderExecutionBlocked(
            "This preview has expired or was already used. Preview the order again."
        )
        runner.order_service.preview.return_value = fresh
        runner.price_condition_service.check.return_value = PriceConditionResult(
            allowed=False, reason="Цена 150₽ > лимит 120₽", current_price=150.0
        )

        runner._execute(plan_id=1, plan=plan, preview=old_preview)

        runner._record_skip.assert_called_once_with(1, "SBER", "price_condition_on_retry")
        runner._record_execution.assert_not_called()
        runner.notify.assert_called_once()
        self.assertIn("⏭", runner.notify.call_args[0][1])

    def test_execute_non_expired_blocked(self):
        """
        Non-expired OrderExecutionBlocked (e.g. trading disabled) →
        notify ❌, no retry, no record.
        """
        runner = self.make_runner()
        plan = fake_plan()
        preview = fake_preview()
        runner.order_service.execute.side_effect = OrderExecutionBlocked(
            "Execution is blocked because production trading is disabled."
        )
        runner._execute_with_fresh_preview = MagicMock()

        runner._execute(plan_id=1, plan=plan, preview=preview)

        runner._execute_with_fresh_preview.assert_not_called()
        runner._record_execution.assert_not_called()
        runner.notify.assert_called_once()
        self.assertIn("❌", runner.notify.call_args[0][1])


class IsPreviewExpiredTests(unittest.TestCase):

    def test_primary_expiry_message(self):
        exc = OrderExecutionBlocked("This preview has expired or was already used. Preview the order again.")
        self.assertTrue(_is_preview_expired(exc))

    def test_secondary_expiry_message(self):
        exc = OrderExecutionBlocked("This preview has expired. Preview the order again.")
        self.assertTrue(_is_preview_expired(exc))

    def test_non_expiry_blocked_message(self):
        exc = OrderExecutionBlocked("Execution is blocked because production trading is disabled.")
        self.assertFalse(_is_preview_expired(exc))

    def test_ticker_mismatch_not_expiry(self):
        exc = OrderExecutionBlocked("The confirmation does not match the preview. Preview the order again.")
        self.assertFalse(_is_preview_expired(exc))
