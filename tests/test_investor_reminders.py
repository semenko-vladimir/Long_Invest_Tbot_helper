"""
Tests for app/client/config/investor_reminders.py

Coverage:
  configure_investor_reminders()
    - returns immediately when reminders are disabled
    - returns and logs warning when no users are configured
    - returns and logs error when UserContextResolver raises
    - returns and logs error when reminder time format is invalid (out-of-range, non-numeric)
    - schedules one job for a single user (verifies job id, args, hour, minute)
    - schedules one job per enabled user when multiple users are configured
    - each job uses its owner's telegram_chat_id
    - shuts down an existing scheduler before creating a new one
    - boundary times 00:00 and 23:59 are accepted
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("BOT_TOKEN", "123456:TEST")

from app.client.config import investor_reminders
from app.services.user_context import UserContext


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def _make_user(*, user_id="alice", chat_id=111111):
    return UserContext(
        user_id=user_id,
        display_name=user_id.capitalize(),
        telegram_chat_id=chat_id,
        broker_fee=0.05,
        db_path=f"data/users/{user_id}/database.db",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class InvestorRemindersTests(unittest.TestCase):
    def setUp(self):
        investor_reminders.investor_reminder_scheduler = None

    def _run(self, *, enabled=True, time="09:00", users=None, resolver_raises=None):
        """
        Runs configure_investor_reminders() with all external dependencies mocked.
        Returns (resolver_instance_mock, scheduler_instance_mock, scheduler_class_mock).
        """
        if users is None:
            users = [_make_user()]

        resolver_cls_mock = mock.MagicMock()
        resolver_instance_mock = resolver_cls_mock.return_value
        if resolver_raises is not None:
            resolver_instance_mock.enabled_users.side_effect = resolver_raises
        else:
            resolver_instance_mock.enabled_users.return_value = users

        scheduler_cls_mock = mock.MagicMock()
        scheduler_instance_mock = scheduler_cls_mock.return_value

        with mock.patch(
            "app.client.config.investor_reminders.investor_reminders_enabled",
            return_value=enabled,
        ), mock.patch(
            "app.client.config.investor_reminders.get_investor_reminder_time",
            return_value=time,
        ), mock.patch(
            "app.client.config.investor_reminders.UserContextResolver",
            resolver_cls_mock,
        ), mock.patch(
            "apscheduler.schedulers.background.BackgroundScheduler",
            scheduler_cls_mock,
        ):
            investor_reminders.configure_investor_reminders()

        return resolver_instance_mock, scheduler_instance_mock, scheduler_cls_mock

    # ---- early-exit paths ------------------------------------------------

    def test_skips_when_reminders_are_disabled(self):
        _, scheduler_instance, _ = self._run(enabled=False)
        scheduler_instance.add_job.assert_not_called()
        scheduler_instance.start.assert_not_called()

    def test_skips_and_logs_warning_when_no_users_configured(self):
        with mock.patch.object(investor_reminders.logger, "warning") as mock_warn:
            _, scheduler_instance, _ = self._run(users=[])
        scheduler_instance.add_job.assert_not_called()
        mock_warn.assert_called_once()
        self.assertIn("no users", mock_warn.call_args.args[0].lower())

    def test_logs_error_when_user_resolver_raises(self):
        with mock.patch.object(investor_reminders.logger, "error") as mock_err:
            _, scheduler_instance, _ = self._run(
                resolver_raises=Exception("users.json not found")
            )
        scheduler_instance.add_job.assert_not_called()
        mock_err.assert_called_once()

    def test_logs_error_on_out_of_range_reminder_time(self):
        with mock.patch.object(investor_reminders.logger, "error") as mock_err:
            _, scheduler_instance, _ = self._run(time="25:99")
        scheduler_instance.add_job.assert_not_called()
        mock_err.assert_called_once()
        self.assertIn("INVESTOR_REMINDER_TIME", mock_err.call_args.args[0])

    def test_logs_error_on_non_numeric_reminder_time(self):
        with mock.patch.object(investor_reminders.logger, "error") as mock_err:
            _, scheduler_instance, _ = self._run(time="nine:00")
        scheduler_instance.add_job.assert_not_called()
        mock_err.assert_called_once()

    # ---- scheduling behaviour --------------------------------------------

    def test_schedules_one_job_for_a_single_user(self):
        user = _make_user(user_id="alice", chat_id=111111)
        _, scheduler_instance, _ = self._run(users=[user], time="08:30")

        scheduler_instance.start.assert_called_once()
        self.assertEqual(scheduler_instance.add_job.call_count, 1)
        kw = scheduler_instance.add_job.call_args.kwargs
        self.assertEqual(kw["id"], "investor_daily_reminder_alice")
        self.assertEqual(kw["args"], [111111])
        self.assertEqual(kw["hour"], 8)
        self.assertEqual(kw["minute"], 30)

    def test_schedules_one_job_per_enabled_user(self):
        users = [
            _make_user(user_id="alice", chat_id=111111),
            _make_user(user_id="bob", chat_id=222222),
        ]
        _, scheduler_instance, _ = self._run(users=users)

        self.assertEqual(scheduler_instance.add_job.call_count, 2)
        job_ids = {c.kwargs["id"] for c in scheduler_instance.add_job.call_args_list}
        self.assertEqual(job_ids, {"investor_daily_reminder_alice", "investor_daily_reminder_bob"})

    def test_each_user_job_uses_their_own_chat_id(self):
        users = [
            _make_user(user_id="alice", chat_id=111111),
            _make_user(user_id="bob", chat_id=222222),
        ]
        _, scheduler_instance, _ = self._run(users=users)

        chat_ids = {c.kwargs["args"][0] for c in scheduler_instance.add_job.call_args_list}
        self.assertEqual(chat_ids, {111111, 222222})

    def test_shuts_down_existing_scheduler_before_creating_new_one(self):
        old_scheduler = mock.MagicMock()
        investor_reminders.investor_reminder_scheduler = old_scheduler

        self._run()

        old_scheduler.shutdown.assert_called_once()

    # ---- time boundary cases ---------------------------------------------

    def test_midnight_time_is_valid(self):
        _, scheduler_instance, _ = self._run(time="00:00")
        scheduler_instance.start.assert_called_once()

    def test_end_of_day_time_is_valid(self):
        _, scheduler_instance, _ = self._run(time="23:59")
        scheduler_instance.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
