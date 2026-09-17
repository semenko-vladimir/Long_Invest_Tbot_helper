import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DATAHUB_DIR = ROOT / "app" / "datahub"


FORBIDDEN_PREFIXES = (
    "app.services.orders",
    "app.services.trading_policy",
    "app.client.handlers.orders",
    "app.client.handlers.signals",
    "app.client.handlers.mls",
    "app.client.orders",
    "app.client.signals",
    "app.client.strategy",
    "app.client.api.signals_client",
    "app.client.api.strategy_client",
    "app.services.llm",
    "app.services.signals",
    "app.services.strategy",
    "g4f",
    "keras",
    "sklearn",
    "tensorflow",
)

FORBIDDEN_NAMES = {
    "OrderService",
    "OrderPreviewRequest",
    "OrderConfirmCommand",
    "BUY",
    "SELL",
    "HOLD",
    "WATCH",
    "AVOID",
}

FORBIDDEN_ATTRIBUTES = {
    "preview",
    "execute",
    "place_order",
    "post_order",
    "buy",
    "sell",
}


class DataHubBoundaryTests(unittest.TestCase):
    def test_datahub_package_exists(self):
        self.assertTrue(DATAHUB_DIR.exists())

    def test_datahub_imports_no_trading_signal_llm_or_ml_modules(self):
        forbidden_imports = set()
        forbidden_imported_names = set()
        forbidden_attributes = set()

        for path in DATAHUB_DIR.rglob("*.py"):
            with self.subTest(path=path.relative_to(ROOT)):
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

                forbidden_imports.update(
                    module
                    for module in imported_modules
                    if any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_PREFIXES)
                )
                forbidden_imported_names.update(FORBIDDEN_NAMES.intersection(imported_names))
                forbidden_attributes.update(FORBIDDEN_ATTRIBUTES.intersection(attribute_names))

        self.assertEqual(sorted(forbidden_imports), [])
        self.assertEqual(forbidden_imported_names, set())
        self.assertEqual(forbidden_attributes, set())


if __name__ == "__main__":
    unittest.main()
