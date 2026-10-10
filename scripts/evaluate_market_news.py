"""Collect public articles and evaluate the production article schema on local Ollama.

No user accounts, broker calls, Telegram delivery or runtime database writes.
Run from the repository root. Reports contain only public source material.
"""

import argparse
import json
import sys
import time
import re
import subprocess
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from json import dumps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.article_news_analysis import OllamaArticleAnalyzer, market_catalog, prefilter_priority
from app.services.market_screening import fetch_equity_universe
from app.integrations.moex_iss import MOEXISSClient
from app.services.media_news_sources import fetch_news_source
from app.services.news_article_text import fetch_article_document
from app.services.news_llm_config import NewsLLMConfig
from app.services.news_sources import NewsItem


def collect(path, count):
    now = datetime.now(timezone.utc)
    universe = fetch_equity_universe(MOEXISSClient(timeout_seconds=15))
    catalog = market_catalog(universe)
    groups, coverage = [], {}
    for source in ("rbc", "interfax", "kommersant", "cbr_events", "cbr_press", "moex_main", "moex_listing"):
        fetched = fetch_news_source(source, since=now - timedelta(days=2), now=now)
        coverage[source] = {"items": len(fetched.items), "complete": fetched.coverage_complete, "errors": fetched.errors}
        print(json.dumps({"source": source, **coverage[source]}, ensure_ascii=False), flush=True)
        items = [item for item in fetched.items if item.publication_time_known and now - timedelta(days=2) <= item.published_at <= now and prefilter_priority(item, catalog)]
        groups.append(sorted(items, key=lambda item: item.published_at, reverse=True))
    selected, seen = [], set()
    while any(groups) and len(selected) < count:
        for group in groups:
            if not group or len(selected) >= count:
                continue
            item = group.pop(0)
            if item.url in seen:
                continue
            seen.add(item.url)
            try:
                document = fetch_article_document(item)
                item = replace(item, full_text=document.text, published_at=document.published_at or item.published_at)
            except Exception:
                pass
            selected.append({**asdict(item), "published_at": item.published_at.isoformat()})
            print(json.dumps({"collected": len(selected), "source": item.source, "body_chars": len(item.full_text)}, ensure_ascii=False), flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"captured_at": now.isoformat(), "catalog": catalog, "coverage": coverage, "articles": selected}, ensure_ascii=False, indent=2), encoding="utf-8")
    if len(selected) < count:
        raise RuntimeError(f"Only {len(selected)} public articles available; required {count}")


class SSHModelSession:
    """Transmit only public evaluation prompts to the server's loopback Ollama."""
    trust_env = False

    def __init__(self, host):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", host):
            raise ValueError("Use a simple trusted SSH host alias.")
        self.host = host

    def post(self, url, *, json, timeout):
        request_body = dumps(json, ensure_ascii=False).encode("utf-8")
        command = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={max(10, timeout[0])}",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3", self.host,
            "curl --fail --silent --show-error --max-time " + str(timeout[1]) +
            " http://127.0.0.1:11434/api/chat -H 'Content-Type: application/json' --data-binary @-"]
        try:
            result = subprocess.run(command, input=request_body, capture_output=True, timeout=sum(timeout) + 10)
        except subprocess.TimeoutExpired as exc:
            raise requests.Timeout("SSH model transport timed out.") from exc
        if result.returncode:
            details = result.stderr.decode("utf-8", errors="replace").strip().splitlines()
            raise requests.ConnectionError(f"SSH model transport failed ({result.returncode}): " +
                                           (details[-1][:250] if details else "no transport diagnostic"))
        response = requests.Response()
        response.status_code, response._content = 200, result.stdout
        return response


def evaluate(dataset, report, model=None, base_url=None, ssh_host=None, retry_transport_only=False):
    data = json.loads(dataset.read_text(encoding="utf-8"))
    config = NewsLLMConfig.from_env()
    config = replace(config, enabled=True, model=model or config.model, base_url=base_url or config.base_url)
    analyzer = OllamaArticleAnalyzer(config, http_session=SSHModelSession(ssh_host) if ssh_host else None)
    existing = json.loads(report.read_text(encoding="utf-8")) if report.exists() else []
    completed = {item["url"] for item in existing if item.get("valid") and item.get("analyzer_version") == analyzer.version}
    if retry_transport_only:
        for record in existing:
            cause_type = record.get("cause", "").split(":", 1)[0]
            if record.get("analyzer_version") == analyzer.version and cause_type != "ConnectionError" and "Timeout" not in cause_type:
                completed.add(record["url"])
    for item_data in data["articles"]:
        if item_data["url"] in completed:
            continue
        item_data = dict(item_data)
        item_data["published_at"] = datetime.fromisoformat(item_data["published_at"])
        item_data["categories"] = tuple(item_data.get("categories", ()))
        item = NewsItem(**item_data)
        started = time.monotonic()
        record = {"url": item.url, "source": item.source, "title": item.title, "model": config.model, "analyzer_version": analyzer.version}
        try:
            record.update(valid=True, assessment=asdict(analyzer.assess_article(item, data["catalog"])))
        except Exception as exc:
            record.update(valid=False, error=str(exc), rejected_response=analyzer.last_response)
            # Public evaluation transport diagnostics, with no request payload.
            cause = exc.__cause__
            if cause is not None:
                record["cause"] = type(cause).__name__ + ": " + str(cause)[:300]
        record.update(seconds=round(time.monotonic() - started, 2), metrics=analyzer.last_metrics)
        existing = [value for value in existing if value["url"] != item.url] + [record]
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: record[key] for key in ("source", "valid", "seconds")}, ensure_ascii=False), flush=True)
    passed = sum(record["valid"] for record in existing)
    print(json.dumps({"total": len(existing), "valid": passed}), flush=True)
    return 0 if passed == len(data["articles"]) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--model")
    parser.add_argument("--base-url", help="Loopback Ollama endpoint, including an SSH forwarded local port")
    parser.add_argument("--ssh-host", help="Trusted SSH alias; send only public prompts to that server's local Ollama")
    parser.add_argument("--retry-transport-only", action="store_true", help="Keep model rejections; retry only connection/timeouts and missing articles")
    args = parser.parse_args()
    if args.collect:
        collect(args.dataset, args.count)
    if args.report:
        return evaluate(args.dataset, args.report, args.model, args.base_url, args.ssh_host, args.retry_transport_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
