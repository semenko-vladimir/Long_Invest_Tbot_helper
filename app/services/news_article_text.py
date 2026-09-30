"""Bounded text extraction from official MOEX and Bank of Russia news pages."""

import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import requests

from app.services.news_sources import _public_host


MAX_PAGE_BYTES = 512_000
MAX_TEXT_CHARS = 6_000
_MOEX_SOURCES = {"moex_main", "moex_listing"}
_CBR_SOURCES = {"cbr_events", "cbr_press"}
_BLOCK_TAGS = {"br", "div", "h1", "h2", "h3", "li", "p", "td", "th", "tr"}
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "wbr"}


class ArticleTextUnavailable(RuntimeError):
    """An official page could not be read or did not contain article text."""


def _target_classes(source: str, url: str) -> tuple[str, ...]:
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443)
                or parts.fragment):
            return ()
    except ValueError:
        return ()
    if not parts.hostname:
        return ()
    if source in _MOEX_SOURCES and parts.hostname in {"www.moex.com", "moex.com"}:
        if re.fullmatch(r"/n\d+", parts.path) and (not parts.query or re.fullmatch(r"nt=\d+", parts.query)):
            return ("news_text",)
    if source in _CBR_SOURCES and parts.hostname in {"www.cbr.ru", "cbr.ru"}:
        try:
            query = parse_qs(parts.query, strict_parsing=True)
        except ValueError:
            return ()
        if (parts.path.casefold() == "/press/event/" and set(query) == {"id"}
                and len(query["id"]) == 1 and query["id"][0].isdigit()):
            return ("lead-text", "landing-text")
        if (parts.path.casefold() == "/press/pr/" and set(query) == {"file"}
                and len(query["file"]) == 1 and re.fullmatch(r"[A-Za-z0-9_.-]+", query["file"][0])):
            return ("lead-text", "landing-text")
    return ()


class _ArticleParser(HTMLParser):
    def __init__(self, target_classes: tuple[str, ...]):
        super().__init__(convert_charrefs=True)
        self.target_classes = target_classes
        self.depth = 0
        self.suppressed = 0
        self.parts: list[str] = []
        self.length = 0
        self.found = False

    def handle_starttag(self, tag, attrs):
        if self.depth:
            if tag in {"script", "style", "iframe"}:
                self.suppressed += 1
            if not self.suppressed and tag in _BLOCK_TAGS:
                self._append(" ")
            if tag not in _VOID_TAGS:
                self.depth += 1
        elif tag == "div" and any(value in dict(attrs).get("class", "").split()
                                   for value in self.target_classes):
            self.depth = 1
            self.found = True
            self._append(" ")

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag in {"script", "style", "iframe"} and self.suppressed:
            self.suppressed -= 1
        if not self.suppressed and tag in _BLOCK_TAGS:
            self._append(" ")
        if tag not in _VOID_TAGS:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and not self.suppressed:
            self._append(data)

    def _append(self, value: str):
        remaining = MAX_TEXT_CHARS + 1 - self.length
        if remaining > 0:
            value = value[:remaining]
            self.parts.append(value)
            self.length += len(value)

    def text(self) -> str:
        return " ".join("".join(self.parts).split())[:MAX_TEXT_CHARS]


def fetch_article_text(item, *, session=None) -> str:
    targets = _target_classes(item.source, item.url)
    if not targets:
        return ""
    if not _public_host(item.url):
        raise ArticleTextUnavailable("Article host is not publicly routable.")
    http = session or requests.Session()
    http.trust_env = False
    response = None
    try:
        response = http.get(item.url, timeout=(5, 12), allow_redirects=False, stream=True,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; TbotNews/1.0)",
                                     "Accept": "text/html"})
        if response.status_code != 200:
            raise ArticleTextUnavailable("Official article returned a non-200 status.")
        if not response.headers.get("Content-Type", "").lower().startswith("text/html"):
            raise ArticleTextUnavailable("Official article is not HTML.")
        if int(response.headers.get("Content-Length", "0") or "0") > MAX_PAGE_BYTES:
            raise ArticleTextUnavailable("Official article exceeds the size limit.")
        chunks = []
        size = 0
        for chunk in response.iter_content(16384):
            size += len(chunk)
            if size > MAX_PAGE_BYTES:
                raise ArticleTextUnavailable("Official article exceeds the size limit.")
            chunks.append(chunk)
        try:
            html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        except LookupError:
            html = b"".join(chunks).decode("utf-8", errors="replace")
        parser = _ArticleParser(targets)
        parser.feed(html)
        result = parser.text()
        if not parser.found or not result:
            raise ArticleTextUnavailable("Official article text was not found.")
        return result
    except requests.RequestException as exc:
        raise ArticleTextUnavailable("Official article request failed.") from exc
    finally:
        if response is not None:
            response.close()
