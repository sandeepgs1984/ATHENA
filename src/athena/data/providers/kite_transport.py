"""Allowlisted HTTP transport for Kite Connect market-data endpoints (R4).

STRUCTURAL SAFETY: only GET on market-data paths. No order/trade/GTT/portfolio
endpoints exist here — order placement remains impossible by construction
(ADR-002, ATHENA-000).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Protocol
from urllib.parse import urlencode

from athena.errors import ProviderError

#: Paths (prefix match) the live transport may call. Anything else fails loudly.
_ALLOWED_PATH_PREFIXES = (
    "/instruments",
    "/quote",
)

_KITE_VERSION = "3"

QueryParams = Mapping[str, str] | Sequence[tuple[str, str]] | None


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


class UrllibKiteTransport:
    """Stdlib HTTPS client for Kite Connect v3 (GET-only, allowlisted)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        access_token: str,
        timeout_s: float = 30.0,
    ) -> None:
        if not api_key.strip():
            raise ProviderError("KITE_API_KEY is missing or empty (.env)")
        if not access_token.strip():
            raise ProviderError("KITE_ACCESS_TOKEN is missing or empty (.env)")
        self._base = base_url.rstrip("/")
        self._api_key = api_key.strip()
        self._access_token = access_token.strip()
        self._timeout_s = timeout_s

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
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(
                f"kite HTTP {exc.code} on {path}: {body[:500] or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"kite network failure on {path}: {exc.reason}") from exc
