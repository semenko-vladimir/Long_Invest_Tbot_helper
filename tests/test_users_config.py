import json
import os
from pathlib import Path
import unittest
from unittest import mock

from app.client import config as app_config
from app.client.config.users import load_users_config
from app.services.user_context import UnknownUserError, UserContextResolver


ROOT = Path(__file__).resolve().parents[1]
TEST_USERS_PATH = ROOT / ".test-users-config.json"
MISSING_USERS_PATH = ROOT / ".missing-users-config.json"


class UsersConfigTests(unittest.TestCase):
    def tearDown(self):
        TEST_USERS_PATH.unlink(missing_ok=True)

    def write_users(self, payload: dict) -> Path:
        TEST_USERS_PATH.write_text(json.dumps(payload), encoding="utf-8")
        return TEST_USERS_PATH

    def users_payload(self) -> dict:
        return {
            "default_web_user_id": "default",
            "users": [
                {
                    "id": "default",
                    "name": "Default Investor",
                    "telegram_chat_id": "111",
                    "sandbox_token": "sandbox-default",
                    "token": "",
                    "broker_fee": 0.3,
                    "db_path": "data/users/default/database.db",
                    "enabled": True,
                },
                {
                    "id": "olga",
                    "name": "Olga",
                    "telegram_chat_id": "222",
                    "sandbox_token": "sandbox-olga",
                    "token": "prod-olga",
                    "broker_fee": 0.2,
                    "enabled": True,
                },
            ],
        }

    def test_load_users_config_parses_users_and_default_web_user(self):
        path = self.write_users(self.users_payload())

        with mock.patch.dict(os.environ, {"USERS_CONFIG_PATH": str(path)}, clear=True), \
            mock.patch("app.client.config.users.load_dotenv"):
            config = load_users_config()

        self.assertEqual(len(config.users), 2)
        self.assertEqual(config.default_web_user().user_id, "default")
        self.assertEqual(config.get_user_by_chat_id(222).user_id, "olga")
        self.assertEqual(config.get_user("olga").db_path, "data/users/olga/database.db")

    def test_default_web_user_env_overrides_json_default(self):
        path = self.write_users(self.users_payload())

        with mock.patch.dict(
            os.environ,
            {"USERS_CONFIG_PATH": str(path), "DEFAULT_WEB_USER_ID": "olga"},
            clear=True,
        ), mock.patch("app.client.config.users.load_dotenv"):
            config = load_users_config()

        self.assertEqual(config.default_web_user().user_id, "olga")

    def test_user_context_resolver_maps_chat_id_and_blocks_unknown(self):
        path = self.write_users(self.users_payload())
        with mock.patch.dict(os.environ, {"USERS_CONFIG_PATH": str(path)}, clear=True), \
            mock.patch("app.client.config.users.load_dotenv"):
            users_config = load_users_config()

        resolver = UserContextResolver(config_loader=lambda: users_config)
        user = resolver.resolve_telegram_chat("222")

        self.assertEqual(user.user_id, "olga")
        self.assertEqual(user.telegram_chat_id, 222)
        self.assertEqual(user.active_token("sandbox"), "sandbox-olga")
        self.assertEqual(user.active_token("prod"), "prod-olga")
        with self.assertRaises(UnknownUserError):
            resolver.resolve_telegram_chat(333)

    def test_runtime_token_helpers_use_default_web_user_when_users_json_is_configured(self):
        path = self.write_users(self.users_payload())

        with mock.patch.dict(
            os.environ,
            {
                "USERS_CONFIG_PATH": str(path),
                "DEFAULT_WEB_USER_ID": "olga",
                "APP_MODE": "sandbox",
            },
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"), \
            mock.patch("app.client.config.users.load_dotenv"):
            tokens = app_config.get_tokens()
            active_token = app_config.get_active_invest_token()
            broker_fee = app_config.get_broker_fee()

        self.assertEqual(tokens["sandbox_token"], "sandbox-olga")
        self.assertEqual(tokens["token"], "prod-olga")
        self.assertEqual(active_token, "sandbox-olga")
        self.assertEqual(broker_fee, 0.2)

    def test_validate_startup_config_accepts_users_json_without_legacy_chat_id(self):
        path = self.write_users(self.users_payload())

        with mock.patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "123456:TEST",
                "USERS_CONFIG_PATH": str(path),
                "APP_MODE": "sandbox",
            },
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"), \
            mock.patch("app.client.config.users.load_dotenv"):
            app_config.validate_startup_config()

    def test_legacy_env_tokens_still_work_when_users_json_is_not_configured(self):
        with mock.patch.dict(
            os.environ,
            {
                "APP_MODE": "sandbox",
                "SANDBOX_TOKEN": "legacy-sandbox",
                "TOKEN": "legacy-prod",
            },
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"), \
            mock.patch("app.client.config.users.load_dotenv"), \
            mock.patch("app.client.config.users.DEFAULT_USERS_CONFIG", MISSING_USERS_PATH):
            tokens = app_config.get_tokens()
            active_token = app_config.get_active_invest_token()

        self.assertEqual(tokens["sandbox_token"], "legacy-sandbox")
        self.assertEqual(tokens["token"], "legacy-prod")
        self.assertEqual(active_token, "legacy-sandbox")

    def test_duplicate_chat_ids_are_rejected(self):
        payload = self.users_payload()
        payload["users"][1]["telegram_chat_id"] = "111"
        path = self.write_users(payload)

        with mock.patch.dict(os.environ, {"USERS_CONFIG_PATH": str(path)}, clear=True), \
            mock.patch("app.client.config.users.load_dotenv"):
            with self.assertRaisesRegex(app_config.ConfigError, "Duplicate telegram_chat_id"):
                load_users_config()


if __name__ == "__main__":
    unittest.main()
