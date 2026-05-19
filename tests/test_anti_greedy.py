from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.services.anti_greedy import (
    AntiGreedyCandidate,
    AntiGreedyPolicyService,
    AntiGreedyRunner,
)
from app.services.orders import OrderPreviewRequest
from app.services.portfolio import PortfolioPosition


def make_position(**kwargs):
    values = dict(
        ticker="SBER",
        name="Sber",
        quantity=25.0,
        quantity_display="25.00",
        average_price=100.0,
        average_price_display="100.00 RUB",
        current_price=121.0,
        current_price_display="121.00 RUB",
        pnl=525.0,
        return_percent=21.0,
        currency="RUB",
        pnl_class="positive",
        pnl_display="+525.00 RUB",
        return_display="+21.00%",
    )
    values.update(kwargs)
    return PortfolioPosition(**values)


def make_candidate(**kwargs):
    values = dict(
        ticker="SBER",
        return_percent=21.0,
        average_price=100.0,
        current_price=121.0,
        quantity=25.0,
        lot_size=10,
        lots=2,
        threshold_pct=20.0,
        reason="Профит +21.00% выше anti-greedy порога 20.00%.",
    )
    values.update(kwargs)
    return AntiGreedyCandidate(**values)


class FakePortfolioService:
    def __init__(self, positions=None, error=None):
        self.positions = positions or []
        self.error = error

    def get_portfolio_view(self):
        return SimpleNamespace(positions=self.positions, error=self.error)


class FakeBroker:
    def __init__(self, lot_size=10):
        self.lot_size = lot_size
        self.resolved = []

    def resolve_unique_instrument(self, token, ticker):
        self.resolved.append((token, ticker))
        return SimpleNamespace(figi=f"figi-{ticker}", ticker=ticker, name=ticker)

    def get_lot_size(self, token, figi):
        return self.lot_size


class FakeOrderService:
    def __init__(self):
        self.preview_calls = []
        self.execute_calls = []
        self.preview_token = "fresh-token"

    def preview(self, request: OrderPreviewRequest):
        self.preview_calls.append(request)
        return SimpleNamespace(
            estimated_price=121.0,
            estimated_value=121.0 * request.lots * 10,
            confirm_token=self.preview_token,
        )

    def execute(self, command):
        self.execute_calls.append(command)
        return SimpleNamespace(order_id="order-1")


class FakeConfirmationService:
    def __init__(self):
        self.issue_calls = []

    def issue_token(self, **kwargs):
        self.issue_calls.append(kwargs)
        return "anti-token"


class AntiGreedyPolicyServiceTests(unittest.TestCase):
    def test_finds_profitable_position_above_threshold_and_converts_units_to_lots(self):
        broker = FakeBroker(lot_size=10)
        service = AntiGreedyPolicyService(
            portfolio_service=FakePortfolioService([make_position(quantity=25.0, return_percent=21.0)]),
            broker=broker,
            token_provider=lambda: "token",
            threshold_pct=20.0,
        )

        candidates = service.find_candidates()

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.ticker, "SBER")
        self.assertEqual(candidate.lots, 2)
        self.assertEqual(candidate.lot_size, 10)
        self.assertIn("+21.00%", candidate.reason)
        self.assertIn("20.00%", candidate.reason)

    def test_skips_position_at_threshold_or_below_one_lot(self):
        service = AntiGreedyPolicyService(
            portfolio_service=FakePortfolioService(
                [
                    make_position(ticker="SBER", quantity=25.0, return_percent=20.0),
                    make_position(ticker="GAZP", quantity=9.0, return_percent=25.0),
                ]
            ),
            broker=FakeBroker(lot_size=10),
            token_provider=lambda: "token",
            threshold_pct=20.0,
        )

        self.assertEqual(service.find_candidates(), [])


class AntiGreedyRunnerTests(unittest.TestCase):
    def make_runner(self, policy_service):
        order_service = FakeOrderService()
        confirmation_service = FakeConfirmationService()
        notify = MagicMock()
        send_confirmation = MagicMock()
        runner = AntiGreedyRunner(
            policy_service=policy_service,
            confirmation_service=confirmation_service,
            order_service=order_service,
            telegram_chat_id=42,
            notify_fn=notify,
            send_confirmation_fn=send_confirmation,
        )
        return runner, order_service, confirmation_service, notify, send_confirmation

    def test_run_sends_confirmation_without_executing_order(self):
        policy_service = MagicMock()
        policy_service.find_candidates.return_value = [make_candidate()]
        runner, order_service, confirmation_service, notify, send_confirmation = self.make_runner(policy_service)

        result = runner.run()

        self.assertEqual(result.status, "sent_for_confirmation")
        self.assertEqual(result.sent_for_confirmation, 1)
        self.assertEqual(len(confirmation_service.issue_calls), 1)
        # Confirmation token is bound to the runner's chat_id so a leaked token
        # cannot be confirmed from a different Telegram chat.
        self.assertEqual(confirmation_service.issue_calls[0]["chat_id"], 42)
        self.assertEqual(send_confirmation.call_count, 1)
        self.assertEqual(order_service.preview_calls[0].operation, "sell")
        self.assertEqual(order_service.execute_calls, [])
        notify.assert_not_called()

    def test_confirm_rechecks_position_and_executes_with_fresh_preview_token(self):
        candidate = make_candidate(lots=2)
        fresh_candidate = make_candidate(lots=1)
        policy_service = MagicMock()
        policy_service.candidate_for_ticker.return_value = fresh_candidate
        runner, order_service, _, notify, _ = self.make_runner(policy_service)

        runner._execute(candidate)

        self.assertEqual(len(order_service.preview_calls), 1)
        self.assertEqual(order_service.preview_calls[0].lots, 1)
        self.assertEqual(len(order_service.execute_calls), 1)
        command = order_service.execute_calls[0]
        self.assertEqual(command.operation, "sell")
        self.assertEqual(command.ticker, "SBER")
        self.assertEqual(command.lots, 1)
        self.assertEqual(command.confirm_token, "fresh-token")
        notify.assert_called_once()
        self.assertIn("Anti-greedy продажа отправлена", notify.call_args[0][1])

    def test_confirm_skips_when_position_is_no_longer_above_threshold(self):
        policy_service = MagicMock()
        policy_service.candidate_for_ticker.return_value = None
        runner, order_service, _, notify, _ = self.make_runner(policy_service)

        runner._execute(make_candidate())

        self.assertEqual(order_service.preview_calls, [])
        self.assertEqual(order_service.execute_calls, [])
        notify.assert_called_once()
        self.assertIn("больше не выше порога", notify.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
