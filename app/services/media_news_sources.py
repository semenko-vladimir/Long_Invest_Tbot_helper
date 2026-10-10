"""RSS plus bounded financial-section adapters for the three selected media."""

import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from app.services.news_sources import NewsItem, _parse_date, fetch_feed
from app.services.news_urls import canonical_news_url, fetch_public_html


MEDIA_SECTIONS = {
    "rbc": ("https://www.rbc.ru/rubric/economics", "https://www.rbc.ru/rubric/finances", "https://www.rbc.ru/rubric/business"),
    "interfax": ("https://www.interfax.ru/business/",),
    "kommersant": ("https://www.kommersant.ru/rubric/3", "https://www.kommersant.ru/rubric/4", "https://www.kommersant.ru/rubric/40"),
}
MEDIA_HOSTS = {
    "rbc": {"rbc.ru", "www.rbc.ru"},
    "interfax": {"interfax.ru", "www.interfax.ru"},
    "kommersant": {"kommersant.ru", "www.kommersant.ru"},
}


def is_article_url(source: str, url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in MEDIA_HOSTS.get(source, set()):
        return False
    patterns = {
        "rbc": r"/(?:[^/]+/\d{2}/\d{2}/\d{4}|rbcfreenews)/[a-f0-9]+/?$",
        "interfax": r"/(?:business|russia|world)/\d+/?$",
        "kommersant": r"/doc/\d+/?$",
    }
    return bool(re.fullmatch(patterns[source], parts.path))


@dataclass(frozen=True)
class NewsFetchResult:
    items: tuple[NewsItem, ...]
    coverage_complete: bool
    errors: tuple[str, ...] = ()


class SectionParser(HTMLParser):
    """Extract article links, metadata, dates and rel=next without page chrome."""
    def __init__(self, source: str, base_url: str, now: datetime):
        super().__init__(convert_charrefs=True)
        self.source, self.base_url, self.now = source, base_url, now
        self.items = {}
        self.current = None
        self.parts = []
        self.next_url = None
        self.script = None
        self.scripts = []
        self.card = None
        self.card_parts = []
        self.metadata_items = {}
        self.more_exists = False
        self.link_date = None

    def categories(self, url):
        path = urlsplit(url).path
        return ("economics",) if ((self.source == "rbc" and path.split("/")[1] in {"economics", "finances", "business"})
                                  or (self.source == "interfax" and path.startswith("/business/"))) else ()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.source == "interfax" and tag == "time" and attrs.get("datetime"):
            try:
                stamp = datetime.fromisoformat(attrs["datetime"])
                self.link_date = (stamp if stamp.tzinfo else stamp.replace(tzinfo=ZoneInfo("Europe/Moscow"))).astimezone(timezone.utc)
            except ValueError:
                self.link_date = None
        if tag == "script" and (attrs.get("type") == "application/ld+json" or attrs.get("id") == "__NEXT_DATA__"):
            self.script = []
        if self.source == "kommersant" and tag == "article" and attrs.get("data-article-url"):
            self.card, self.card_parts = attrs, []
        if "data-archive-param-after" in attrs:
            self.more_exists = True
        if self.source == "interfax" and "getMoreTimeline" in attrs.get("onclick", ""):
            self.more_exists = True
        if tag == "a":
            url = canonical_news_url(urljoin(self.base_url, attrs.get("href", "")))
            if "next" in attrs.get("rel", "").split() or attrs.get("aria-label", "").lower() in {"next", "следующая страница"}:
                self.next_url = url
            if is_article_url(self.source, url):
                self.current, self.parts = url, []
                title = attrs.get("title") or attrs.get("data-title")
                if title:
                    self.parts.append(title)
        if tag == "link" and "next" in attrs.get("rel", "").split():
            self.next_url = urljoin(self.base_url, attrs.get("href", ""))

    def handle_data(self, data):
        if self.card is not None:
            self.card_parts.append(data)
        if self.script is not None:
            self.script.append(data)
        elif self.current:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "article" and self.card is not None:
            url = canonical_news_url(self.card["data-article-url"])
            date_match = re.search(r"\d{2}\.\d{2}\.\d{4},\s*\d{2}:\d{2}", " ".join(self.card_parts))
            if is_article_url(self.source, url):
                stamp = datetime.strptime(date_match[0], "%d.%m.%Y, %H:%M").replace(tzinfo=ZoneInfo("Europe/Moscow")).astimezone(timezone.utc) if date_match else self.now
                categories = ("economics",) if set(self.card.get("data-article-rubric-ids", "").split(",")) & {"3", "4", "40"} else ()
                self.metadata_items[url] = NewsItem(self.source, self.card.get("data-article-title", "")[:500], url, stamp,
                    self.card.get("data-article-description", ""), categories=categories, publication_time_known=bool(date_match))
            self.card = None
        if tag == "script" and self.script is not None:
            try:
                self.scripts.append(json.loads("".join(self.script)))
            except ValueError:
                pass
            self.script = None
        if tag == "a" and self.current:
            title = " ".join(" ".join(self.parts).split())[:500]
            if len(title) >= 12:
                item = NewsItem(self.source, title, self.current, self.link_date or self.now,
                    categories=self.categories(self.current), publication_time_known=self.link_date is not None)
                self.items.setdefault(self.current, item)
                if self.link_date:
                    self.metadata_items[self.current] = item
                self.link_date = None
            self.current = None

    def finish(self):
        def visit(value):
            if isinstance(value, list):
                for entry in value:
                    visit(entry)
            elif isinstance(value, dict):
                # Current RBC pages expose dated financial cards in their public Next.js payload.
                if "props" in value and self.source == "rbc":
                    materials = value.get("props", {}).get("pageProps", {}).get("materials", {})
                    self.more_exists = bool(materials.get("moreExists"))
                    visit(materials.get("items", []))
                    return
                url = value.get("url") or value.get("@id")
                title = value.get("headline") or value.get("title") or value.get("name")
                if isinstance(url, str) and isinstance(title, str):
                    url = canonical_news_url(urljoin(self.base_url, url))
                    if is_article_url(self.source, url):
                        date = value.get("datePublished") or value.get("publishDate")
                        categories = self.categories(url)
                        if self.source == "rbc" and (value.get("rubric") or {}).get("nick") in {"economics", "finances", "business"}:
                            categories = ("economics",)
                        if date or url not in self.metadata_items:
                            unknown_date = datetime.min.replace(tzinfo=timezone.utc)
                            parsed_date = _parse_date(date, unknown_date)
                            known = parsed_date != unknown_date
                            self.metadata_items[url] = NewsItem(self.source, title[:500], url, parsed_date if known else self.now,
                                str(value.get("description") or value.get("anons") or "")[:1500], categories=categories,
                                publication_time_known=known)
                for child in value.values():
                    if isinstance(child, (dict, list)):
                        visit(child)
        for script in self.scripts:
            visit(script)
        return tuple((self.metadata_items or self.items).values())


def fetch_news_source(source: str, *, since=None, max_pages=5, feed_fetcher=fetch_feed, page_fetcher=fetch_public_html,
                      now=None) -> NewsFetchResult:
    now = now or datetime.now(timezone.utc)
    errors, items = [], {}
    feed_ok = False
    try:
        for item in feed_fetcher(source):
            url = canonical_news_url(item.url)
            items[url] = replace(item, url=url)
        feed_ok = True
    except Exception as exc:
        errors.append("rss:" + type(exc).__name__)
    if source not in MEDIA_SECTIONS:
        return NewsFetchResult(tuple(items.values()), feed_ok, tuple(errors))
    complete = feed_ok
    pages_left = max_pages
    for section_index, section in enumerate(MEDIA_SECTIONS[source]):
        url, seen, reached_end = section, set(), False
        page_limit = max(0, pages_left - (len(MEDIA_SECTIONS[source]) - section_index - 1))
        for _ in range(page_limit):
            if url in seen:
                break
            seen.add(url)
            pages_left -= 1
            try:
                try:
                    html = page_fetcher(url, MEDIA_HOSTS[source])
                except Exception:
                    html = page_fetcher(url, MEDIA_HOSTS[source])
                parser = SectionParser(source, url, now)
                parser.feed(html)
                found = parser.finish()
                if not found:
                    raise ValueError("Section contained no article links.")
                for item in found:
                    previous = items.get(item.url)
                    if previous is None or (item.publication_time_known and not previous.publication_time_known):
                        items[item.url] = item
                known_dates = [item.published_at for item in found if item.publication_time_known]
                if since and known_dates and len(known_dates) == len(found) and min(known_dates) <= since:
                    reached_end = True
                    break
                if not parser.next_url:
                    # Without dated metadata or pagination, completeness cannot be promised.
                    reached_end = bool(known_dates) and len(known_dates) == len(found) and not parser.more_exists
                    break
                url = parser.next_url
            except Exception as exc:
                errors.append("section:" + type(exc).__name__)
                break
        complete = complete and reached_end
    return NewsFetchResult(tuple(items.values()), complete, tuple(errors))
