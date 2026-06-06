import json
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from app.backend.main_api import app


ROOT = Path(__file__).resolve().parents[1]


class WebAssetTests(unittest.TestCase):
    def test_lightweight_charts_is_local_npm_dependency(self):
        package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(package_json["dependencies"]["lightweight-charts"], "5.2.0")
        self.assertEqual(package_json["scripts"]["build:web"], "node scripts/vendor-lightweight-charts.mjs")

    def test_local_lightweight_charts_vendor_asset_exists(self):
        asset = ROOT / "app" / "backend" / "web" / "static" / "vendor" / "lightweight-charts.standalone.production.js"

        self.assertTrue(asset.exists())
        self.assertGreater(asset.stat().st_size, 100_000)

    def test_vendor_asset_is_served_without_cdn(self):
        client = TestClient(app)

        response = client.get("/static/vendor/lightweight-charts.standalone.production.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers["content-type"])
        self.assertNotIn("unpkg.com", response.text[:1000])
        self.assertNotIn("cdn.jsdelivr.net", response.text[:1000])

    def test_base_template_loads_vendor_before_app_script(self):
        template = ROOT / "app" / "backend" / "web" / "templates" / "base.html"
        html = template.read_text(encoding="utf-8")

        vendor_index = html.index("/vendor/lightweight-charts.standalone.production.js")
        app_index = html.index("/js/app.js")
        self.assertLess(vendor_index, app_index)


if __name__ == "__main__":
    unittest.main()
