"""Unit tests for app/research/schemas.py — typed analytics types."""
import unittest
from datetime import datetime

from app.research.schemas import (
    AnalysisSignal,
    DataGap,
    InstrumentIdentity,
    MarketSnapshot,
    ResearchReport,
    RiskFactor,
    SourceFreshness,
)

NOW = datetime(2026, 1, 1, 12, 0, 0)


class RiskFactorTests(unittest.TestCase):
    def test_defaults(self):
        rf = RiskFactor(category="regulatory", description="Pending regulation change")
        self.assertEqual(rf.level, "medium")
        self.assertIsNone(rf.source)

    def test_all_levels_valid(self):
        for level in ("low", "medium", "high", "critical"):
            rf = RiskFactor(category="test", description="desc", level=level)
            self.assertEqual(rf.level, level)

    def test_frozen(self):
        rf = RiskFactor(category="x", description="y")
        with self.assertRaises(Exception):
            rf.category = "z"  # type: ignore[misc]

    def test_with_source(self):
        rf = RiskFactor(category="valuation", description="High P/E", level="high", source="local-analysis")
        self.assertEqual(rf.source, "local-analysis")


class AnalysisSignalTests(unittest.TestCase):
    def test_defaults(self):
        sig = AnalysisSignal(rating="HOLD", rationale="Stable dividend payer, wait for better entry.")
        self.assertEqual(sig.rating, "HOLD")
        self.assertEqual(sig.generated_by, "local-analysis")
        self.assertIsNone(sig.confidence)
        self.assertEqual(sig.caveats, [])

    def test_all_ratings_valid(self):
        for rating in ("BUY", "HOLD", "SELL", "WATCH", "AVOID"):
            sig = AnalysisSignal(rating=rating, rationale="test")
            self.assertEqual(sig.rating, rating)

    def test_with_confidence_and_caveats(self):
        sig = AnalysisSignal(
            rating="BUY",
            rationale="Strong fundamentals",
            confidence=0.72,
            caveats=["Data may be stale", "No macro context available"],
        )
        self.assertAlmostEqual(sig.confidence, 0.72)
        self.assertEqual(len(sig.caveats), 2)

    def test_disclaimer_not_on_signal(self):
        # AnalysisSignal does not carry the disclaimer itself — that lives on ResearchReport.
        sig = AnalysisSignal(rating="SELL", rationale="Weak earnings trend")
        self.assertFalse(hasattr(sig, "disclaimer"))

    def test_frozen(self):
        sig = AnalysisSignal(rating="WATCH", rationale="Monitoring for entry")
        with self.assertRaises(Exception):
            sig.rating = "BUY"  # type: ignore[misc]


class ResearchReportTypedFieldsTests(unittest.TestCase):
    def _minimal_report(self) -> ResearchReport:
        return ResearchReport(ticker="SBER", generated_at=NOW)

    def test_new_fields_default_empty(self):
        r = self._minimal_report()
        self.assertEqual(r.risk_factors, [])
        self.assertEqual(r.analysis_signals, [])

    def test_existing_fields_still_present(self):
        r = self._minimal_report()
        self.assertEqual(r.risks, [])
        self.assertIsNone(r.educational_rating)
        self.assertIn("Educational", r.disclaimer)

    def test_report_with_typed_fields(self):
        rf = RiskFactor(category="sector", description="Energy sector headwinds", level="high")
        sig = AnalysisSignal(
            rating="WATCH",
            rationale="Monitor oil price impact on revenue",
            confidence=0.60,
        )
        r = ResearchReport(
            ticker="NVTK",
            generated_at=NOW,
            risk_factors=[rf],
            analysis_signals=[sig],
        )
        self.assertEqual(len(r.risk_factors), 1)
        self.assertEqual(r.risk_factors[0].level, "high")
        self.assertEqual(r.analysis_signals[0].rating, "WATCH")

    def test_disclaimer_always_present(self):
        r = self._minimal_report()
        self.assertIn("not personal investment advice", r.disclaimer)
        self.assertIn("must not trigger broker orders", r.disclaimer)

    def test_backward_compatible_construction(self):
        """Existing code that builds ResearchReport without new fields must still work."""
        r = ResearchReport(
            ticker="GAZP",
            generated_at=NOW,
            instrument_identity=InstrumentIdentity(ticker="GAZP", name="Газпром"),
            market_snapshot=MarketSnapshot(current_price=165.0, currency="RUB", captured_at=NOW),
            risks=["Sanction risk"],
            data_gaps=[DataGap(category="financials", description="No recent report", severity="high")],
            freshness=[SourceFreshness(source_name="local-fundamentals", fetched_at=NOW)],
        )
        self.assertEqual(r.ticker, "GAZP")
        self.assertEqual(r.risk_factors, [])
        self.assertEqual(r.analysis_signals, [])


if __name__ == "__main__":
    unittest.main()
