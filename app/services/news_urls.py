"""Conservative URL identity and bounded public-page reads for news adapters."""

import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests

from app.services.news_sources import _public_host


def canonical_news_url(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    pairs = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in {"from", "ref", "yclid", "gclid"}]
    # MOEX's nt only selects the display section of an already identified article.
    if host in {"moex.com", "www.moex.com"} and parts.path.startswith("/n"):
        pairs = [(key, value) for key, value in pairs if key != "nt"]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(sorted(pairs)), ""))


def fetch_public_html(url: str, hosts: set[str], *, session=None, max_bytes=1_500_000) -> str:
    """Every redirect stays on the adapter's allowlist and on public HTTPS."""
    http = session or requests.Session()
    http.trust_env = False
    deadline = time.monotonic() + 35
    try:
        for _ in range(3):
            parts = urlsplit(url)
            if (parts.scheme != "https" or parts.hostname not in hosts or parts.username or parts.password
                    or parts.port not in (None, 443) or not _public_host(url)):
                raise ValueError("Unapproved public news page.")
            response = http.get(url, timeout=(5, 12), allow_redirects=False, stream=True,
                                headers={"User-Agent": "Mozilla/5.0 (compatible; TbotNews/1.0)", "Accept": "text/html"})
            try:
                if response.status_code in {301, 302, 303, 307, 308}:
                    url = urljoin(url, response.headers.get("Location", ""))
                    continue
                response.raise_for_status()
                if not response.headers.get("Content-Type", "").lower().startswith("text/html"):
                    raise ValueError("News page is not HTML.")
                chunks, size = [], 0
                for chunk in response.iter_content(16384):
                    size += len(chunk)
                    if size > max_bytes or time.monotonic() > deadline:
                        raise ValueError("News page exceeded the read limit.")
                    chunks.append(chunk)
                raw = b"".join(chunks)
                encoding = response.encoding
                if not encoding or encoding.lower() == "iso-8859-1":
                    encoding = "utf-8"
                return raw.decode(encoding, errors="replace")
            finally:
                response.close()
        raise ValueError("Too many news redirects.")
    finally:
        if session is None:
            http.close()
