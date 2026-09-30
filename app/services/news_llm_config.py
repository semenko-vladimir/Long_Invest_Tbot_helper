"""Explicit, local-only Ollama configuration for account news analysis."""

import hashlib
import json
import os
from dataclasses import dataclass
from urllib.parse import urlsplit


DEFAULT_MODEL = "hf.co/unsloth/Qwen3.5-4B-GGUF:Q6_K"
PROMPT_VERSION = "account-news-v2"


@dataclass(frozen=True)
class NewsLLMConfig:
    enabled: bool = False
    base_url: str = "http://127.0.0.1:11434"
    model: str = DEFAULT_MODEL
    connect_timeout: int = 5
    read_timeout: int = 240

    @property
    def analyzer_version(self) -> str:
        fingerprint = json.dumps({"model": self.model, "prompt": PROMPT_VERSION,
                                  "num_ctx": 8192, "num_batch": 64, "num_predict": 2048,
                                  "temperature": 0, "think": False}, sort_keys=True)
        return "ollama-" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def from_env(cls) -> "NewsLLMConfig":
        enabled_text = os.getenv("NEWS_LLM_ENABLED", "false").strip().lower()
        if enabled_text not in {"true", "false"}:
            raise ValueError("NEWS_LLM_ENABLED must be true or false.")
        try:
            config = cls(
                enabled=enabled_text == "true",
                base_url=os.getenv("NEWS_OLLAMA_BASE_URL", cls.base_url).strip().rstrip("/"),
                model=os.getenv("NEWS_OLLAMA_MODEL", DEFAULT_MODEL).strip(),
                connect_timeout=int(os.getenv("NEWS_OLLAMA_CONNECT_TIMEOUT_SECONDS", "5")),
                read_timeout=int(os.getenv("NEWS_OLLAMA_READ_TIMEOUT_SECONDS", "240")),
            )
        except ValueError as exc:
            raise ValueError("Ollama timeouts must be whole seconds.") from exc
        config.validate()
        return config

    def validate(self) -> None:
        parts = urlsplit(self.base_url)
        if (parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "::1"}
                or parts.username or parts.password or parts.path or parts.query or parts.fragment
                or parts.port is None):
            raise ValueError("NEWS_OLLAMA_BASE_URL must be an HTTP loopback address with a port.")
        if not self.model or len(self.model) > 200:
            raise ValueError("NEWS_OLLAMA_MODEL must name a local model.")
        if not 1 <= self.connect_timeout <= 30 or not 10 <= self.read_timeout <= 540:
            raise ValueError("Ollama timeouts are outside their allowed ranges.")
