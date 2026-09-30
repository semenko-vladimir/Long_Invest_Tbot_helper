import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.news_article_text import ArticleTextUnavailable, fetch_article_text
from app.services.news_sources import NewsItem


class FakeResponse:
    def __init__(self, body: bytes, *, status=200, content_type="text/html; charset=utf-8"):
        self.body = body
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.encoding = "utf-8"
        self.closed = False

    def iter_content(self, size):
        for start in range(0, len(self.body), size):
            yield self.body[start:start + size]

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.trust_env = True

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class NewsArticleTextTests(unittest.TestCase):
    def item(self, source, url):
        return NewsItem(source, "Новость", url, datetime(2026, 10, 1, tzinfo=timezone.utc))

    @patch("app.services.news_article_text._public_host", return_value=True)
    def test_extracts_official_moex_article_without_navigation_or_scripts(self, _):
        html = ('<nav>Меню</nav><div class="news_text"><p>Торги <b>SBER</b> приостановлены.</p>'
                '<script>ignore</script><table><tr><td>Торговый код</td><td>RU000A10B925</td>'
                '</tr></table></div><footer>Контакты</footer>').encode()
        response = FakeResponse(html)
        session = FakeSession(response)
        text = fetch_article_text(self.item("moex_listing", "https://www.moex.com/n104716?nt=104"), session=session)
        self.assertIn("SBER", text)
        self.assertIn("RU000A10B925", text)
        self.assertNotIn("Меню", text)
        self.assertNotIn("ignore", text)
        self.assertNotIn("Контакты", text)
        self.assertFalse(session.trust_env)
        self.assertFalse(session.calls[0][1]["allow_redirects"])
        self.assertTrue(response.closed)

    @patch("app.services.news_article_text._public_host", return_value=True)
    def test_extracts_cbr_event_with_no_rss_summary(self, _):
        session = FakeSession(FakeResponse(('<div class="lead-text"><p>Ожидания граждан выросли.</p></div>'
                                           '<div class="landing-text"><p>Инфляционные ожидания выросли.</p></div>').encode()))
        text = fetch_article_text(self.item("cbr_events", "https://www.cbr.ru/press/event/?id=32879"), session=session)
        self.assertEqual(text, "Ожидания граждан выросли. Инфляционные ожидания выросли.")

    def test_rejects_unapproved_urls_without_request(self):
        for url in ("http://www.moex.com/n1", "https://localhost/n1", "https://www.moex.com.evil.test/n1",
                    "https://www.moex.com/n1?next=https://example.org", "https://www.moex.com/other",
                    "https://www.cbr.ru/press/event/?id=1&next=2"):
            with self.subTest(url=url):
                session = FakeSession(FakeResponse(b""))
                self.assertEqual(fetch_article_text(self.item("moex_main", url), session=session), "")
                self.assertFalse(session.calls)

    @patch("app.services.news_article_text._public_host", return_value=True)
    def test_rejects_redirects_and_oversized_pages(self, _):
        item = self.item("moex_main", "https://www.moex.com/n104716")
        for response in (FakeResponse(b"", status=302), FakeResponse(b"x" * 513_000)):
            with self.subTest(status=response.status_code, size=len(response.body)):
                with self.assertRaises(ArticleTextUnavailable):
                    fetch_article_text(item, session=FakeSession(response))
                self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
