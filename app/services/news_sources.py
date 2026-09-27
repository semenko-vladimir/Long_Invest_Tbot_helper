"""Bounded, read-only RSS/Atom ingestion for monitoring."""

import ipaddress
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import requests

from app.services.monitoring_settings import SOURCE_URLS, validate_source


@dataclass(frozen=True)
class NewsItem:
    source: str
    title: str
    url: str
    published_at: datetime
    summary: str = ""


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
    try:
        response.raise_for_status()
        chunks = []
        size = 0
        for chunk in response.iter_content(32768):
            size += len(chunk)
            if size > 1_000_000:
                raise ValueError("RSS response exceeds 1 MB.")
            chunks.append(chunk)
        root = ElementTree.fromstring(b"".join(chunks))
    finally:
        response.close()
    now = now or datetime.now(timezone.utc)
    result = []
    for node in list(root.findall(".//item")) + list(root.findall(".//{*}entry")):
        title = (node.findtext("title") or node.findtext("{*}title") or "").strip()
        link_node = node.find("{*}link")
        link = (node.findtext("link") or (link_node.get("href") if link_node is not None else "") or "").strip()
        date_text = node.findtext("pubDate") or node.findtext("{*}published") or node.findtext("{*}updated")
        published = _parse_date(date_text, now)
        summary = (node.findtext("description") or node.findtext("{*}summary") or "").strip()
        if title and link.startswith(("https://", "http://")):
            result.append(NewsItem(source, title[:500], link[:1000], published, summary[:1500]))
    return result[:100]


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
