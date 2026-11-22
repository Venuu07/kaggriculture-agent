"""One tiny interface for every LLM provider: `respond(system, messages, ctx) -> LLMReply`.

Switch providers with LLM_PROVIDER in .env (gemini | groq | openai | claude | offline).
All real providers are plain HTTPS calls via `requests`, so no extra SDKs are needed.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

from .. import ROOT

load_dotenv(ROOT / ".env")

# Approximate list prices, USD per 1M tokens (input, output). Free tiers cost $0 in practice.
PRICES = {
    "gemini": (0.30, 2.50),
    "groq": (0.59, 0.79),
    "openai": (0.15, 0.60),
    "claude": (1.00, 5.00),
    "offline": (0.0, 0.0),
}


@dataclass
class LLMReply:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMError(RuntimeError):
    """Raised when a provider cannot answer (no key, network, quota)."""


class Provider:
    """Base class: rate limiting, retries and cost accounting."""

    name = "base"

    def __init__(self) -> None:
        self.min_interval = float(os.getenv("LLM_MIN_INTERVAL_S", "4"))
        self._last = 0.0
        self.temperature = 0.2

    @property
    def model(self) -> str:
        return "n/a"

    def cost(self, reply: LLMReply) -> float:
        pin, pout = PRICES.get(self.name, (0.0, 0.0))
        return (reply.input_tokens * pin + reply.output_tokens * pout) / 1_000_000

    def respond(self, system: str, messages: list[dict[str, str]], ctx: dict[str, Any] | None = None) -> LLMReply:
        """Send a chat; messages are [{'role': 'user'|'assistant', 'content': str}]."""
        wait = self.min_interval - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        t0 = time.time()
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                reply = self._call(system, messages)
                reply.latency_s = time.time() - t0
                self._last = time.time()
                return reply
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                last_err = LLMError(f"{self.name} HTTP {status}: {e.response.text[:300] if e.response is not None else e}")
                if status in (429, 500, 502, 503, 504):
                    time.sleep(min(12, 3 * 2 ** attempt))
                    continue
                break
            except requests.RequestException as e:
                last_err = LLMError(f"{self.name} network error: {e}")
                time.sleep(2 * (attempt + 1))
        self._last = time.time()
        raise last_err or LLMError("unknown LLM error")

    def _call(self, system: str, messages: list[dict[str, str]]) -> LLMReply:
        raise NotImplementedError


def _key(var: str) -> str:
    key = os.getenv(var, "").strip()
    if not key:
        raise LLMError(f"{var} is not set in .env")
    return key


class GeminiProvider(Provider):
    """GEMINI_MODEL may list fallbacks, e.g. "gemini-3.6-flash,gemini-3.5-flash": a busy (503) or
    retired (404) model is skipped for the next one, and the first that answers is remembered."""

    name = "gemini"

    def __init__(self) -> None:
        super().__init__()
        raw = os.getenv("GEMINI_MODEL", "gemini-3.6-flash,gemini-3.5-flash,gemini-3.1-flash-lite")
        self.models = [m.strip() for m in raw.split(",") if m.strip()]

    @property
    def model(self) -> str:
        return self.models[0]

    def _call(self, system: str, messages: list[dict[str, str]]) -> LLMReply:
        last: requests.HTTPError | None = None
        for i, model in enumerate(list(self.models)):
            try:
                reply = self._call_model(model, system, messages)
                if i:
                    self.models.insert(0, self.models.pop(i))
                return reply
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status in (404, 503) and i + 1 < len(self.models):
                    last = e
                    continue
                raise
        raise last or LLMError("no Gemini model available")

    def _call_model(self, model: str, system: str, messages: list[dict[str, str]]) -> LLMReply:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                         for m in messages],
            "generationConfig": {"temperature": self.temperature, "responseMimeType": "application/json"},
        }
        r = requests.post(url, json=body, headers={"x-goog-api-key": _key("GEMINI_API_KEY")}, timeout=90)
        r.raise_for_status()
        data = r.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata", {})
        return LLMReply(text, usage.get("promptTokenCount", 0),
                        usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0))


class OpenAICompatProvider(Provider):
    """OpenAI and Groq share the same chat-completions API."""

    def __init__(self, name: str, base_url: str, key_var: str, model_var: str, default_model: str) -> None:
        super().__init__()
        self.name, self.base_url, self.key_var = name, base_url, key_var
        self.model_var, self.default_model = model_var, default_model

    @property
    def model(self) -> str:
        return os.getenv(self.model_var, self.default_model)

    def _call(self, system: str, messages: list[dict[str, str]]) -> LLMReply:
        body = {"model": self.model, "temperature": self.temperature,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, *messages]}
        r = requests.post(f"{self.base_url}/chat/completions", json=body, timeout=90,
                          headers={"Authorization": f"Bearer {_key(self.key_var)}"})
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage", {})
        return LLMReply(data["choices"][0]["message"]["content"] or "",
                        usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))


class ClaudeProvider(Provider):
    name = "claude"

    @property
    def model(self) -> str:
        return os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

    def _call(self, system: str, messages: list[dict[str, str]]) -> LLMReply:
        body = {"model": self.model, "max_tokens": 1500, "temperature": self.temperature,
                "system": system, "messages": messages}
        r = requests.post("https://api.anthropic.com/v1/messages", json=body, timeout=90,
                          headers={"x-api-key": _key("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"})
        r.raise_for_status()
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        return LLMReply(text, usage.get("input_tokens", 0), usage.get("output_tokens", 0))


def get_provider(name: str | None = None) -> Provider:
    """Build the provider named in `name` or LLM_PROVIDER (default: offline)."""
    name = (name or os.getenv("LLM_PROVIDER") or "offline").lower().strip()
    if name == "gemini":
        return GeminiProvider()
    if name == "groq":
        return OpenAICompatProvider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "GROQ_MODEL",
                                    "llama-3.3-70b-versatile")
    if name == "openai":
        return OpenAICompatProvider("openai", "https://api.openai.com/v1", "OPENAI_API_KEY", "OPENAI_MODEL",
                                    "gpt-4o-mini")
    if name in ("claude", "anthropic"):
        return ClaudeProvider()
    from .offline import OfflineReasoner
    return OfflineReasoner()


def provider_ready(name: str) -> tuple[bool, str]:
    """Is this provider usable right now (key present)? Returns (ok, reason)."""
    var = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY",
           "claude": "ANTHROPIC_API_KEY"}.get(name)
    if var is None:
        return True, "offline reasoner needs no key"
    return (bool(os.getenv(var, "").strip()), f"{var} {'found' if os.getenv(var, '').strip() else 'missing'} in .env")
