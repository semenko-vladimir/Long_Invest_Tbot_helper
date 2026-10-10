"""Bounded, read-only RSS/Atom ingestion for monitoring."""

import ipaddress
import socket
from html import unescape
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import requests

from app.services.monitoring_settings import SOURCE_URLS, validate_source


MAX_FEED_ITEMS = 100
MAX_FEED_BYTES = 10_000_000


@dataclass(frozen=True)
class NewsItem:
    source: str
    title: str
    url: str
    published_at: datetime
    summary: str = ""
    full_text: str = ""
    categories: tuple[str, ...] = ()
    publication_time_known: bool = True


def _public_host(url: str) -> bool:
    host = urlsplit(url).hostname
    if not host:
        return False
    try:
        return all(ipaddress.ip_address(address[4][0]).is_global for address in socket.getaddrinfo(host, 443))
    except (OSError, ValueError):
        return False


def fetch_feed(source: str, *, session=None, now=None) -> list[NewsItem]:
    url = SOURCE_URLS[source] if source in SOURCE_URLS else validate_source(source)
    session = session or requests.Session()
    response = None
    for _ in range(3):
        if not _public_host(url):
            raise ValueError("RSS host is not publicly routable.")
        response = session.get(url, timeout=8, allow_redirects=False, stream=True,
                               headers={"User-Agent": "Tbot monitoring/1.0"})
        if response.status_code not in {301, 302, 303, 307, 308}:
            break
        target = urljoin(url, response.headers.get("Location", ""))
        response.close()
        url = validate_source(target)
    else:
        raise ValueError("Too many RSS redirects.")
    now = now or datetime.now(timezone.utc)
    result: list[NewsItem] = []
    parser = ElementTree.XMLPullParser(events=("end",))
    size = 0
    try:
        response.raise_for_status()
        for chunk in response.iter_content(32768):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_FEED_BYTES:
                raise ValueError("RSS response exceeds 10 MB before 100 items.")
            parser.feed(chunk)
            for _, node in parser.read_events():
                if node.tag.rsplit("}", 1)[-1] not in {"item", "entry"}:
                    continue
                item = _parse_item(source, node, now)
                node.clear()
                if item is not None:
                    result.append(item)
                if len(result) >= MAX_FEED_ITEMS:
                    return result
        parser.close()
        return result
    finally:
        response.close()


def _parse_item(source: str, node: ElementTree.Element, now: datetime) -> NewsItem | None:
    title = unescape(node.findtext("title") or node.findtext("{*}title") or "").strip()
    link_node = node.find("{*}link")
    link = (node.findtext("link") or (link_node.get("href") if link_node is not None else "") or "").strip()
    date_text = node.findtext("pubDate") or node.findtext("{*}published") or node.findtext("{*}updated")
    unknown_date = datetime.min.replace(tzinfo=timezone.utc)
    parsed_date = _parse_date(date_text, unknown_date)
    date_known = parsed_date != unknown_date
    published = parsed_date if date_known else now
    summary = (node.findtext("description") or node.findtext("{*}summary") or "").strip()
    if title and link.startswith(("https://", "http://")):
        categories = tuple(child.text.strip() for child in node.findall("category") if child.text)
        return NewsItem(source, title[:500], link[:1000], published, summary[:1500],
                        categories=categories, publication_time_known=date_known)
    return None


def _parse_date(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        from email.utils import parsedate_to_datetime
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return fallback
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
