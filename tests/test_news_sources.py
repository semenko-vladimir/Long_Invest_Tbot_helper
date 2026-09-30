import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.news_sources import fetch_feed


class FakeResponse:
    status_code = 200

    def __init__(self, payload: bytes):
        self.payload = payload
        self.bytes_read = 0
        self.closed = False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        for start in range(0, len(self.payload), chunk_size):
            chunk = self.payload[start:start + chunk_size]
            self.bytes_read += len(chunk)
            yield chunk

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


class NewsSourceTests(unittest.TestCase):
    @patch("app.services.news_sources._public_host", return_value=True)
    def test_large_recent_first_feed_stops_after_100_items(self, _):
        description = "x" * 15_000
        entries = "".join(
            f"<item><title>News {index}</title><link>https://example.org/{index}</link>"
            f"<pubDate>Thu, 01 Oct 2026 12:00:00 +0300</pubDate>"
            f"<description>{description}</description></item>"
            for index in range(120)
        )
        payload = f"<rss><channel>{entries}</channel></rss>".encode()
        response = FakeResponse(payload)

        items = fetch_feed("moex_main", session=FakeSession(response))

        self.assertEqual(len(items), 100)
        self.assertEqual(items[0].title, "News 0")
        self.assertEqual(items[-1].title, "News 99")
        self.assertGreater(len(payload), 1_000_000)
        self.assertLess(response.bytes_read, len(payload))
        self.assertTrue(response.closed)

    @patch("app.services.news_sources._public_host", return_value=True)
    def test_feed_remains_bounded_when_no_items_arrive(self, _):
        response = FakeResponse(b"<rss><channel>" + b"x" * 500)
        with patch("app.services.news_sources.MAX_FEED_BYTES", 100):
            with self.assertRaisesRegex(ValueError, "exceeds 10 MB"):
                fetch_feed("moex_main", session=FakeSession(response))
        self.assertTrue(response.closed)

    @patch("app.services.news_sources._public_host", return_value=True)
    def test_atom_entry_is_still_parsed(self, _):
        payload = (
            '<feed xmlns="http://www.w3.org/2005/Atom">'
            '<entry><title>Decision</title><link href="https://example.org/decision"/>'
            '<published>2026-10-01T09:00:00Z</published><summary>Details</summary>'
            '</entry></feed>'
        ).encode()
        response = FakeResponse(payload)

        items = fetch_feed("cbr_events", session=FakeSession(response),
                           now=datetime(2026, 10, 1, tzinfo=timezone.utc))

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://example.org/decision")
        self.assertEqual(items[0].summary, "Details")
        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
