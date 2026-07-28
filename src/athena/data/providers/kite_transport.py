"""Allowlisted HTTP transport for Kite Connect market-data endpoints (R4).

STRUCTURAL SAFETY: only GET on market-data paths. No order/trade/GTT/portfolio
endpoints exist here — order placement remains impossible by construction
(ADR-002, ATHENA-000).

ADR-007 / MI-5: configurable per-class pacing and bounded 429 retry live here so
every Kite caller (CLI daily, scoped validate, full-universe job) inherits them.
Pacing changes wall-clock only — never which candles/quotes are returned.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol
from urllib.parse import urlencode

from athena.config.models import KiteRateLimitConfig
from athena.errors import ProviderError

#: Paths (prefix match) the live transport may call. Anything else fails loudly.
_ALLOWED_PATH_PREFIXES = (
    "/instruments",
    "/quote",
)

_KITE_VERSION = "3"

QueryParams = Mapping[str, str] | Sequence[tuple[str, str]] | None
SleepFn = Callable[[float], None]
ClockFn = Callable[[], float]


class KiteTransport(Protocol):
    """Minimal GET surface used by ``KiteProvider`` (injectable for tests)."""

    def get_text(self, path: str, params: QueryParams = None) -> str: ...

    def get_json(self, path: str, params: QueryParams = None) -> dict: ...


def _assert_allowed(path: str) -> None:
    if path == "/quote" or path.startswith("/quote/"):
        return
    if path == "/instruments" or path.startswith("/instruments/"):
        return
    raise ProviderError(
        f"kite transport refused path '{path}': only market-data GETs are allowed"
    )


def _encode_params(params: QueryParams) -> str:
    if not params:
        return ""
    if isinstance(params, Mapping):
        return urlencode(list(params.items()))
    return urlencode(list(params))


def endpoint_class(path: str) -> str:
    """Classify a Kite path into a pacing bucket (historical / quote / other)."""
    if path == "/quote" or path.startswith("/quote/"):
        return "quote"
    if "/instruments/historical/" in path:
        return "historical"
    return "other"


class UrllibKiteTransport:
    """Stdlib HTTPS client for Kite Connect v3 (GET-only, allowlisted)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        access_token: str,
        timeout_s: float = 30.0,
        rate_limit: KiteRateLimitConfig | None = None,
        sleep: SleepFn = time.sleep,
        clock: ClockFn = time.monotonic,
    ) -> None:
        if not api_key.strip():
            raise ProviderError("KITE_API_KEY is missing or empty (.env)")
        if not access_token.strip():
            raise ProviderError("KITE_ACCESS_TOKEN is missing or empty (.env)")
        self._base = base_url.rstrip("/")
        self._api_key = api_key.strip()
        self._access_token = access_token.strip()
        self._timeout_s = timeout_s
        self._rate_limit = rate_limit or KiteRateLimitConfig()
        self._sleep = sleep
        self._clock = clock
        self._pace_lock = threading.Lock()
        self._last_request_at: dict[str, float] = {}

    def get_text(self, path: str, params: QueryParams = None) -> str:
        return self._request(path, params).decode("utf-8")

    def get_json(self, path: str, params: QueryParams = None) -> dict:
        raw = self.get_text(path, params)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"kite returned non-JSON for {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ProviderError(f"kite returned unexpected JSON type for {path}")
        status = payload.get("status")
        if status is not None and status != "success":
            message = payload.get("message") or payload.get("error_type") or status
            raise ProviderError(f"kite API error on {path}: {message}")
        return payload

    def _min_interval(self, klass: str) -> float:
        cfg = self._rate_limit
        if klass == "quote":
            return float(cfg.quote_min_interval_seconds)
        if klass == "historical":
            return float(cfg.historical_min_interval_seconds)
        return float(cfg.other_min_interval_seconds)

    def _pace(self, path: str) -> None:
        """Wait until this end-point class's minimum interval has elapsed."""
        klass = endpoint_class(path)
        min_interval = self._min_interval(klass)
        with self._pace_lock:
            now = self._clock()
            last = self._last_request_at.get(klass)
            if last is not None:
                wait = min_interval - (now - last)
                if wait > 0:
                    self._sleep(wait)
                    now = self._clock()
            self._last_request_at[klass] = now

    def _request(self, path: str, params: QueryParams) -> bytes:
        if not path.startswith("/"):
            raise ProviderError(f"kite path must be absolute ('/…'), got '{path}'")
        _assert_allowed(path)
        query = _encode_params(params)
        url = f"{self._base}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "X-Kite-Version": _KITE_VERSION,
                "Authorization": f"token {self._api_key}:{self._access_token}",
            },
        )
        attempts = 0
        max_retries = int(self._rate_limit.max_429_retries)
        while True:
            self._pace(path)
            try:
                with urllib.request.urlopen(request, timeout=self._timeout_s) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and attempts < max_retries:
                    attempts += 1
                    backoff = (
                        float(self._rate_limit.retry_backoff_base_seconds)
                        * (2 ** (attempts - 1))
                    )
                    self._sleep(backoff)
                    continue
                raise ProviderError(
                    f"kite HTTP {exc.code} on {path}: {body[:500] or exc.reason}"
                ) from exc
            except urllib.error.URLError as exc:
                raise ProviderError(
                    f"kite network failure on {path}: {exc.reason}"
                ) from exc
