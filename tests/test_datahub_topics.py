import unittest

from app.datahub.topics import DataHubTopic, TopicValidationError, parse_topic


class DataHubTopicParsingTests(unittest.TestCase):
    def assert_topic(
        self,
        raw_topic: str,
        *,
        normalized: str,
        group: str,
        parts: tuple[str, ...],
        ticker: str = None,
        interval: str = None,
        provider: str = None,
        metric: str = None,
        scope: str = None,
        detail: str = None,
    ) -> DataHubTopic:
        topic = parse_topic(raw_topic)

        self.assertEqual(topic.normalized, normalized)
        self.assertEqual(topic.namespace, "ru")
        self.assertEqual(topic.group, group)
        self.assertEqual(topic.parts, parts)
        self.assertEqual(topic.ticker, ticker)
        self.assertEqual(topic.interval, interval)
        self.assertEqual(topic.provider, provider)
        self.assertEqual(topic.metric, metric)
        self.assertEqual(topic.scope, scope)
        self.assertEqual(topic.detail, detail)
        return topic

    def test_instrument_topic_normalizes_ticker_and_case(self):
        topic = self.assert_topic(
            " RU:Instrument:sber ",
            normalized="ru:instrument:SBER",
            group="instrument",
            parts=("SBER",),
            ticker="SBER",
        )

        self.assertEqual(topic.raw, "RU:Instrument:sber")

    def test_quote_topic_parses(self):
        self.assert_topic(
            "ru:quote:GAZP",
            normalized="ru:quote:GAZP",
            group="quote",
            parts=("GAZP",),
            ticker="GAZP",
        )

    def test_daily_candles_topic_parses(self):
        self.assert_topic(
            "ru:candles:rual:1D",
            normalized="ru:candles:RUAL:1d",
            group="candles",
            parts=("RUAL", "1d"),
            ticker="RUAL",
            interval="1d",
        )

    def test_portfolio_summary_topic_parses(self):
        self.assert_topic(
            "ru:portfolio:summary:DEFAULT",
            normalized="ru:portfolio:summary:default",
            group="portfolio",
            parts=("summary", "default"),
            scope="default",
            detail="summary",
        )

    def test_portfolio_position_topic_parses(self):
        self.assert_topic(
            "ru:portfolio:position:lkoh",
            normalized="ru:portfolio:position:LKOH",
            group="portfolio",
            parts=("position", "LKOH"),
            ticker="LKOH",
            detail="position",
        )

    def test_watchlist_topic_parses(self):
        self.assert_topic(
            "ru:watchlist:default",
            normalized="ru:watchlist:default",
            group="watchlist",
            parts=("default",),
            scope="default",
        )

    def test_cbr_macro_topics_parse(self):
        for metric in ("key_rate", "usd_rub", "cny_rub"):
            with self.subTest(metric=metric):
                self.assert_topic(
                    f"ru:macro:cbr:{metric}",
                    normalized=f"ru:macro:cbr:{metric}",
                    group="macro",
                    parts=("cbr", metric),
                    provider="cbr",
                    metric=metric,
                )

    def test_moex_index_topic_parses(self):
        self.assert_topic(
            "ru:macro:moex:index:imoex",
            normalized="ru:macro:moex:index:IMOEX",
            group="macro",
            parts=("moex", "index", "IMOEX"),
            ticker="IMOEX",
            provider="moex",
            metric="index",
        )

    def test_issuer_topics_parse(self):
        cases = (
            ("ru:issuer:sber:profile", "profile"),
            ("ru:issuer:sber:dividends", "dividends"),
        )
        for raw_topic, detail in cases:
            with self.subTest(raw_topic=raw_topic):
                self.assert_topic(
                    raw_topic,
                    normalized=f"ru:issuer:SBER:{detail}",
                    group="issuer",
                    parts=("SBER", detail),
                    ticker="SBER",
                    detail=detail,
                )

    def test_invalid_topics_raise_validation_error(self):
        invalid_topics = (
            "",
            "us:quote:SBER",
            "ru",
            "ru:",
            "ru:unknown:SBER",
            "ru:instrument:",
            "ru:instrument:S BER",
            "ru:instrument:SBER.ME",
            "ru:instrument:SBER/../TOKEN",
            "ru:candles:SBER:1h",
            "ru:candles:SBER",
            "ru:portfolio:summary:other",
            "ru:portfolio:unknown:SBER",
            "ru:watchlist:all",
            "ru:macro:fred:key_rate",
            "ru:macro:cbr:eur_rub",
            "ru:macro:moex:quote:IMOEX",
            "ru:macro:moex:index:IMOEX:extra",
            "ru:issuer:SBER:signals",
        )

        for raw_topic in invalid_topics:
            with self.subTest(raw_topic=raw_topic):
                with self.assertRaises(TopicValidationError):
                    parse_topic(raw_topic)


if __name__ == "__main__":
    unittest.main()
