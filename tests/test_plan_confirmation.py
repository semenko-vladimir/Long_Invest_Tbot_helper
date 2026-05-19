import unittest
from unittest.mock import MagicMock

from app.services.plan_confirmation import PlanConfirmationService


def issue_token_for(service: PlanConfirmationService, *, chat_id=None, on_confirm=None, on_skip=None):
    return service.issue_token(
        plan_id=1,
        ticker="SBER",
        operation="buy",
        lots=2,
        current_price=100.0,
        price_condition_reason="ok",
        on_confirm=on_confirm or (lambda: None),
        on_skip=on_skip or (lambda reason: None),
        chat_id=chat_id,
    )


class PlanConfirmationServiceChatBindingTests(unittest.TestCase):
    def test_unbound_token_can_be_confirmed_by_any_chat(self):
        service = PlanConfirmationService()
        on_confirm = MagicMock()
        token = issue_token_for(service, on_confirm=on_confirm)

        self.assertTrue(service.confirm(token))
        on_confirm.assert_called_once()

    def test_bound_token_can_be_confirmed_by_owner_chat(self):
        service = PlanConfirmationService()
        on_confirm = MagicMock()
        token = issue_token_for(service, chat_id=42, on_confirm=on_confirm)

        self.assertTrue(service.confirm(token, chat_id=42))
        on_confirm.assert_called_once()

    def test_bound_token_rejected_for_wrong_chat(self):
        service = PlanConfirmationService()
        on_confirm = MagicMock()
        on_skip = MagicMock()
        token = issue_token_for(
            service,
            chat_id=42,
            on_confirm=on_confirm,
            on_skip=on_skip,
        )

        self.assertFalse(service.confirm(token, chat_id=999))
        on_confirm.assert_not_called()
        # Still consumable by the correct chat afterward.
        self.assertTrue(service.confirm(token, chat_id=42))
        on_confirm.assert_called_once()

    def test_bound_token_rejected_when_chat_id_missing(self):
        service = PlanConfirmationService()
        on_confirm = MagicMock()
        token = issue_token_for(service, chat_id=42, on_confirm=on_confirm)

        self.assertFalse(service.confirm(token))
        on_confirm.assert_not_called()

    def test_confirm_then_second_call_returns_false_single_use(self):
        service = PlanConfirmationService()
        on_confirm = MagicMock()
        token = issue_token_for(service, chat_id=42, on_confirm=on_confirm)

        self.assertTrue(service.confirm(token, chat_id=42))
        self.assertFalse(service.confirm(token, chat_id=42))
        on_confirm.assert_called_once()

    def test_skip_from_wrong_chat_does_not_invalidate_token(self):
        service = PlanConfirmationService()
        on_confirm = MagicMock()
        on_skip = MagicMock()
        token = issue_token_for(
            service,
            chat_id=42,
            on_confirm=on_confirm,
            on_skip=on_skip,
        )

        self.assertFalse(service.skip(token, chat_id=999))
        on_skip.assert_not_called()

        self.assertTrue(service.confirm(token, chat_id=42))
        on_confirm.assert_called_once()


if __name__ == "__main__":
    unittest.main()
