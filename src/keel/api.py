"""Minimal client for the Meta Model API.

OpenAI-compatible ``/chat/completions`` over ``https://api.meta.ai/v1``, using
only the standard library so the base install stays numpy-only.

Keys are read from the environment, never from code:

    MODEL_API_KEY="LLM|<id>|<secret>"     # the cookbook's variable
    META_API_KEY="..."                    # accepted as an alias
    META_API_BASE="https://api.meta.ai/v1"

The client is deliberately thin: one completion call, one health check, retries
on 429/5xx. Everything Keel needs from the API is a judge call and a black-box
target, and both are chat completions.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

DEFAULT_BASE = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"
RETRY_STATUS = {429, 500, 502, 503, 504}

#: ``transport(endpoint, payload, api_key, timeout) -> dict``
Transport = Callable[[str, dict, str, float], dict]


class ApiError(RuntimeError):
    """A non-retryable API failure, or a retry budget that ran out."""

    def __init__(self, message: str, status: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @property
    def text_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class Completion:
    text: str
    model: str
    usage: Usage
    raw: dict = field(default_factory=dict, repr=False)


def _http(endpoint: str, payload: dict | None, api_key: str, timeout: float) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    request = urllib.request.Request(
        endpoint, data=data, headers=headers, method="POST" if data else "GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise ApiError(f"HTTP {exc.code} from {endpoint}", status=exc.code, body=body) from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"network error reaching {endpoint}: {exc.reason}") from exc


class Client:
    """A tiny Meta Model API client.

    >>> client = Client()                      # reads MODEL_API_KEY
    >>> client.complete("Reply with: ok")      # doctest: +SKIP
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        *,
        timeout: float = 90.0,
        retries: int = 3,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = (
            api_key
            or os.environ.get("MODEL_API_KEY")
            or os.environ.get("META_API_KEY")
            or ""
        )
        self.base_url = (base_url or os.environ.get("META_API_BASE") or DEFAULT_BASE).rstrip("/")
        self.model = model or os.environ.get("KEEL_JUDGE_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self.retries = max(0, retries)
        self._transport = transport or _http

    def _call(self, path: str, payload: dict | None) -> dict:
        if not self.api_key:
            raise ApiError(
                "no API key: set MODEL_API_KEY (format LLM|<id>|<secret>) or pass api_key="
            )
        endpoint = f"{self.base_url}{path}"
        last: ApiError | None = None
        for attempt in range(self.retries + 1):
            try:
                return self._transport(endpoint, payload, self.api_key, self.timeout)
            except ApiError as exc:
                last = exc
                if exc.status not in RETRY_STATUS or attempt == self.retries:
                    raise
                time.sleep(min(0.5 * (2**attempt), 8.0))
        raise last or ApiError("unreachable")

    def models(self) -> list[str]:
        payload = self._call("/models", None)
        return [str(item.get("id", "")) for item in payload.get("data", [])]

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        extra: Mapping | None = None,
    ) -> Completion:
        payload: dict = {
            "model": model or self.model,
            "messages": [dict(m) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if extra:
            payload.update(dict(extra))
        raw = self._call("/chat/completions", payload)
        try:
            text = raw["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ApiError(f"unexpected response shape: {str(raw)[:300]}") from exc
        usage = raw.get("usage") or {}
        return Completion(
            text=str(text),
            model=str(raw.get("model", payload["model"])),
            usage=Usage(
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0)),
            ),
            raw=raw,
        )

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs,
    ) -> Completion:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, **kwargs)

    def health(self) -> dict:
        """What the account can actually reach. Costs one call, no tokens."""
        models = self.models()
        return {"base_url": self.base_url, "model": self.model, "models": models}
