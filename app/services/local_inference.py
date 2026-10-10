"""Shared serialization and strict transport for the installed local model."""

import json
from threading import Lock

import requests

INFERENCE_LOCK = Lock()


class NewsAnalysisUnavailable(RuntimeError):
    """A local model request or its structured response could not be used."""


class LocalStructuredClient:
    def __init__(self, config, *, http_session=None):
        config.validate()
        self.config = config
        self.http = http_session or requests.Session()
        self.http.trust_env = False

    def request(self, system, payload, schema, *, num_predict=768):
        request = {
            "model": self.config.model, "stream": False, "think": False, "format": schema,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            "options": {"num_ctx": 8192, "num_batch": 64, "num_predict": num_predict, "temperature": 0},
        }
        try:
            with INFERENCE_LOCK:
                response = self.http.post(self.config.base_url + "/api/chat", json=request,
                                          timeout=(self.config.connect_timeout, self.config.read_timeout))
                response.raise_for_status()
                envelope = response.json()
            if not isinstance(envelope, dict) or envelope.get("done") is not True or envelope.get("done_reason") not in (None, "stop"):
                raise ValueError("Incomplete local model response")
            content = (envelope.get("message") or {}).get("content")
            if not isinstance(content, str) or not 0 < len(content) <= 16384:
                raise ValueError("Empty or oversized model response")
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("Expected a structured object")
            metrics = {key: envelope.get(key) for key in ("total_duration", "load_duration", "prompt_eval_count", "eval_count", "eval_duration")
                       if isinstance(envelope.get(key), (int, float))}
            return result, metrics
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            raise NewsAnalysisUnavailable("Local structured response was unavailable or invalid.") from exc
