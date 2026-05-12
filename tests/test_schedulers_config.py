import ast
import builtins
import os
from pathlib import Path
import unittest
from unittest import mock


os.environ.setdefault("BOT_TOKEN", "123456:TEST")

from app.client.config import schedulers_config


class SchedulerConfigSafetyTests(unittest.TestCase):
    def test_configure_strategy_scheduler_is_noop_even_when_enabled(self):
        real_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            forbidden = {
                "app.client.api.strategy_client",
                "app.client.strategy.strategy_run",
                "apscheduler.schedulers.background",
            }
            if name in forbidden:
                raise AssertionError(f"Unexpected legacy scheduler import: {name}")
            return real_import(name, *args, **kwargs)

        with mock.patch.dict(os.environ, {"ENABLE_STRATEGY_SCHEDULER": "true"}, clear=False), \
            mock.patch.object(schedulers_config, "logger") as logger, \
            mock.patch("builtins.__import__", side_effect=guarded_import):
            result = schedulers_config.configure_strategy_scheduler()

        self.assertIsNone(result)
        logger.warning.assert_called_once()
        self.assertIn("ignored", logger.warning.call_args.args[0])

    def test_configure_strategy_scheduler_logs_disabled_when_env_is_off(self):
        with mock.patch.dict(os.environ, {"ENABLE_STRATEGY_SCHEDULER": "false"}, clear=False), \
            mock.patch.object(schedulers_config, "logger") as logger:
            result = schedulers_config.configure_strategy_scheduler()

        self.assertIsNone(result)
        logger.info.assert_called_once()
        self.assertIn("disabled for investor v1", logger.info.call_args.args[0])

    def test_configure_schedulers_respects_disabled_background_default(self):
        with mock.patch.object(schedulers_config, "background_schedulers_enabled", return_value=False), \
            mock.patch.object(schedulers_config, "configure_market_scheduler") as market_scheduler, \
            mock.patch.object(schedulers_config, "configure_strategy_scheduler") as strategy_scheduler:
            schedulers_config.configure_schedulers()

        market_scheduler.assert_not_called()
        strategy_scheduler.assert_not_called()

    def test_scheduler_config_has_no_active_strategy_scheduler_path(self):
        source_path = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "client"
            / "config"
            / "schedulers_config.py"
        )
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported_modules = set()
        imported_names = set()
        attribute_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
                imported_names.update(alias.asname or alias.name.split(".")[-1] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
                imported_names.update(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, ast.Attribute):
                attribute_names.add(node.attr)

        self.assertNotIn("app.client.strategy.strategy_run", imported_modules)
        self.assertNotIn("app.client.api.strategy_client", imported_modules)
        self.assertNotIn("strategy_run", imported_names)
        self.assertNotIn("StrategyApiClient", imported_names)
        self.assertNotIn("strategy_scheduler", imported_names)
        self.assertNotIn("post_order", attribute_names)
        self.assertNotIn("post_sandbox_order", attribute_names)

    def test_review_only_scheduler_modules_do_not_place_orders(self):
        root = Path(__file__).resolve().parents[1]
        checked_paths = [
            root / "app" / "client" / "config" / "investor_reminders.py",
        ]

        forbidden_imports = {
            "app.services.orders",
            "app.integrations.tinvest",
            "app.client.strategy.strategy_run",
        }
        forbidden_names = {
            "OrderService",
            "OrderConfirmCommand",
            "TradingApiClient",
            "TInvestBroker",
            "Client",
        }
        forbidden_attributes = {
            "post_order",
            "post_sandbox_order",
            "place_order",
        }

        for path in checked_paths:
            with self.subTest(path=path):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                imported_modules = set()
                imported_names = set()
                attribute_names = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported_modules.update(alias.name for alias in node.names)
                        imported_names.update(alias.asname or alias.name.split(".")[-1] for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported_modules.add(node.module)
                        imported_names.update(alias.asname or alias.name for alias in node.names)
                    elif isinstance(node, ast.Attribute):
                        attribute_names.add(node.attr)

                self.assertTrue(imported_modules.isdisjoint(forbidden_imports))
                self.assertTrue(imported_names.isdisjoint(forbidden_names))
                self.assertTrue(attribute_names.isdisjoint(forbidden_attributes))

    def test_legacy_notifications_handler_is_removed(self):
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / "app" / "client" / "handlers" / "notifications").exists())


if __name__ == "__main__":
    unittest.main()
