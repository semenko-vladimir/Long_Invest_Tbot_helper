import ast
from pathlib import Path
import unittest
from unittest import mock

from app.client.config import schedulers_config


class SchedulerConfigSafetyTests(unittest.TestCase):
    def test_configure_schedulers_respects_disabled_background_default(self):
        with mock.patch.object(schedulers_config, "background_schedulers_enabled", return_value=False), \
            mock.patch.object(schedulers_config, "configure_market_scheduler") as market_scheduler, \
            mock.patch.object(schedulers_config, "configure_plan_scheduler") as plan_scheduler, \
            mock.patch.object(schedulers_config, "configure_anti_greedy_scheduler") as anti_greedy_scheduler:
            schedulers_config.configure_schedulers()

        market_scheduler.assert_not_called()
        plan_scheduler.assert_not_called()
        anti_greedy_scheduler.assert_not_called()

    def test_configure_schedulers_runs_only_active_single_owner_schedulers(self):
        with mock.patch.object(schedulers_config, "background_schedulers_enabled", return_value=True), \
            mock.patch.object(schedulers_config, "configure_market_scheduler") as market_scheduler, \
            mock.patch.object(schedulers_config, "configure_plan_scheduler") as plan_scheduler, \
            mock.patch.object(schedulers_config, "configure_anti_greedy_scheduler") as anti_greedy_scheduler:
            schedulers_config.configure_schedulers()

        market_scheduler.assert_called_once()
        plan_scheduler.assert_called_once()
        anti_greedy_scheduler.assert_called_once()

    def test_scheduler_config_has_no_strategy_scheduler_or_direct_order_calls(self):
        source_path = Path(__file__).resolve().parents[1] / "app" / "client" / "config" / "schedulers_config.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

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
        self.assertNotIn("app.services.strategy_registry", imported_modules)
        self.assertNotIn("strategy_run", imported_names)
        self.assertNotIn("StrategyApiClient", imported_names)
        self.assertNotIn("TradingApiClient", imported_names)
        self.assertNotIn("place_order", attribute_names)
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
