import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime

from app.datahub.schemas import (
    DataHubDataGap,
    DataHubError,
    DataHubMetadata,
    DataHubResult,
)
from app.datahub.topics import parse_topic


NOW = datetime(2026, 6, 1, 12, 0, 0)


class DataHubSchemaTests(unittest.TestCase):
    def test_data_gap_defaults_and_immutability(self):
        gap = DataHubDataGap(category="ticker", description="Ticker is invalid.")

        self.assertEqual(gap.severity, "medium")
        with self.assertRaises(FrozenInstanceError):
            gap.category = "source"  # type: ignore[misc]

    def test_error_defaults(self):
        error = DataHubError(message="Source unavailable.")

        self.assertEqual(error.category, "source")
        self.assertEqual(error.severity, "medium")

    def test_metadata_carries_freshness_delay_and_cache_fields(self):
        metadata = DataHubMetadata(
            topic="ru:quote:SBER",
            source="T_INVEST",
            fetched_at=NOW,
            as_of_date="2026-06-01",
            freshness="current",
            delay_status="broker_api",
            ttl_seconds=60,
            cached=True,
            cache_key="ru:quote:SBER:T_INVEST",
        )

        self.assertEqual(metadata.source, "T_INVEST")
        self.assertEqual(metadata.freshness, "current")
        self.assertEqual(metadata.delay_status, "broker_api")
        self.assertTrue(metadata.cached)
        self.assertEqual(metadata.cache_key, "ru:quote:SBER:T_INVEST")

    def test_result_defaults_are_independent(self):
        first = DataHubResult(topic="ru:instrument:SBER")
        second = DataHubResult(topic="ru:instrument:GAZP")

        first.data["ticker"] = "SBER"
        first.data_gaps.append(DataHubDataGap(category="profile", description="Missing profile."))
        first.errors.append(DataHubError(message="Adapter failed."))

        self.assertEqual(second.data, {})
        self.assertEqual(second.data_gaps, [])
        self.assertEqual(second.errors, [])

    def test_result_accepts_parsed_normalized_topic(self):
        topic = parse_topic("RU:Quote:sber")
        metadata = DataHubMetadata(
            topic=topic.normalized,
            source="fake-source",
            fetched_at=NOW,
            freshness="latest_available",
            delay_status="unknown",
            ttl_seconds=30,
        )
        result = DataHubResult(
            topic=topic.normalized,
            data={"ticker": topic.ticker, "price": None},
            metadata=metadata,
            data_gaps=[DataHubDataGap(category="price", description="No latest price available.", severity="high")],
        )

        self.assertEqual(result.topic, "ru:quote:SBER")
        self.assertEqual(result.data["ticker"], "SBER")
        self.assertEqual(result.metadata.source, "fake-source")
        self.assertEqual(result.data_gaps[0].severity, "high")


if __name__ == "__main__":
    unittest.main()
