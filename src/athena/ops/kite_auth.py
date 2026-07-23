"""Interactive Kite Connect session helper (daily access_token → ``.env``).

Does not place orders. Only POSTs to ``/session/token`` for the login exchange,
then writes ``KITE_*`` keys into ``.env``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from getpass import getpass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Event
from urllib.parse import parse_qs, urlparse

from athena.errors import AthenaError, ProviderError

_LOGIN_URL = "https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
_TOKEN_URL = "https://api.kite.trade/session/token"
_PROFILE_URL = "https://api.kite.trade/user/profile"
_ENV_KEYS = ("KITE_API_KEY", "KITE_API_SECRET", "KITE_ACCESS_TOKEN")


@dataclass(frozen=True, slots=True)
class KiteVerifyResult:
    """Outcome of post-auth credential verification."""

    ok: bool
    detail: str
    user_id: str | None = None
    source_env: Path | None = None


def login_url(api_key: str) -> str:
    return _LOGIN_URL.format(api_key=urllib.parse.quote(api_key.strip(), safe=""))


def checksum(api_key: str, request_token: str, api_secret: str) -> str:
    return hashlib.sha256(f"{api_key}{request_token}{api_secret}".encode()).hexdigest()


def extract_request_token(raw: str) -> str:
    """Accept a bare token or a full redirect URL containing ``request_token=``."""
    text = raw.strip().strip('"').strip("'")
    if not text:
        raise ProviderError("request_token is empty")

    if "request_token=" in text:
        candidate = text
        if "://" not in candidate and candidate.startswith("127."):
            candidate = "http://" + candidate
        if "://" in candidate:
            query = urlparse(candidate).query
        elif candidate.startswith("?"):
            query = candidate[1:]
        else:
            query = candidate
        values = parse_qs(query).get("request_token") or []
        if not values or not values[0].strip():
            raise ProviderError("could not find request_token in the pasted URL")
        return values[0].strip()

    if re.fullmatch(r"[A-Za-z0-9]+", text):
        return text
    raise ProviderError("paste either the request_token value or the full redirect URL")


def exchange_access_token(*, api_key: str, api_secret: str, request_token: str) -> str:
    body = urllib.parse.urlencode(
        {
            "api_key": api_key,
            "request_token": request_token,
            "checksum": checksum(api_key, request_token, api_secret),
        }
    ).encode()
    req = urllib.request.Request(
        _TOKEN_URL,
        data=body,
        headers={
            "X-Kite-Version": "3",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"kite session/token HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"kite session/token network failure: {exc.reason}") from exc

    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ProviderError(f"kite session/token failed: {payload}")
    data = payload.get("data") or {}
    token = (data.get("access_token") or "").strip()
    if not token:
        raise ProviderError("kite session/token response missing access_token")
    return token


def upsert_env_file(path: Path, updates: dict[str, str]) -> None:
    """Create or update ``.env`` keys without wiping unrelated lines."""
    path = Path(path)
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()

    remaining = dict(updates)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    if out and out[-1] != "":
        out.append("")
    for key, value in remaining.items():
        out.append(f"{key}={value}")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _read_env_file_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _prompt(label: str, *, default: str = "", secret: bool = False) -> str:
    if default and secret:
        hint = " [saved ········]"
    elif default:
        hint = f" [{default}]"
    else:
        hint = ""
    prompt = f"{label}{hint}: "
    value = getpass(prompt) if secret else input(prompt)
    value = value.strip()
    return value or default


def _wait_for_redirect_token(*, host: str, port: int, timeout_s: float = 300.0) -> str:
    done = Event()
    box: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            params = parse_qs(urlparse(self.path).query)
            token = (params.get("request_token") or [""])[0]
            status = (params.get("status") or [""])[0]
            if token and status == "success":
                box["token"] = token
                body = (
                    b"<html><body><h1>ATHENA</h1>"
                    b"<p>Login OK. You can close this tab.</p></body></html>"
                )
                self.send_response(200)
            else:
                body = (
                    b"<html><body><h1>ATHENA</h1>"
                    b"<p>Login failed or missing token.</p></body></html>"
                )
                self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            done.set()

        def log_message(self, *_args: object) -> None:
            return

    server = HTTPServer((host, port), Handler)
    server.timeout = 1.0
    deadline = time.monotonic() + timeout_s
    try:
        while not done.is_set() and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if "token" not in box:
        raise ProviderError(
            f"timed out waiting for redirect on http://{host}:{port}/ — "
            "Authorize in the browser, or omit --listen and paste the URL"
        )
    return box["token"]


def force_inject_kite_env(env_path: Path) -> dict[str, str]:
    """Overwrite process ``KITE_*`` from ``.env`` (not setdefault — always reinject)."""
    path = Path(env_path)
    if not path.is_file():
        raise ProviderError(f"cannot inject Kite credentials: missing {path}")
    file_vals = _read_env_file_values(path)
    injected: dict[str, str] = {}
    for key in _ENV_KEYS:
        value = (file_vals.get(key) or "").strip()
        if value:
            os.environ[key] = value
            injected[key] = value
    if not injected.get("KITE_API_KEY") or not injected.get("KITE_ACCESS_TOKEN"):
        raise ProviderError(
            f"{path} must contain non-empty KITE_API_KEY and KITE_ACCESS_TOKEN after auth"
        )
    return injected


def verify_kite_credentials(
    *,
    api_key: str,
    access_token: str,
    expected_access_token: str | None = None,
) -> KiteVerifyResult:
    """Confirm credentials with an authenticated Kite ``/user/profile`` GET.

    If ``expected_access_token`` is set, also assert the injected token matches
    what was just written (guards against stale env / wrong file).
    """
    if expected_access_token is not None and access_token != expected_access_token:
        return KiteVerifyResult(
            ok=False,
            detail=(
                "injected KITE_ACCESS_TOKEN does not match the token just written "
                "(stale env or wrong .env file)"
            ),
        )
    if not api_key.strip() or not access_token.strip():
        return KiteVerifyResult(ok=False, detail="api_key or access_token is empty")

    req = urllib.request.Request(
        _PROFILE_URL,
        method="GET",
        headers={
            "X-Kite-Version": "3",
            "Authorization": f"token {api_key}:{access_token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return KiteVerifyResult(
            ok=False,
            detail=f"kite /user/profile HTTP {exc.code}: {detail[:300]}",
        )
    except urllib.error.URLError as exc:
        return KiteVerifyResult(ok=False, detail=f"kite /user/profile network failure: {exc.reason}")

    if not isinstance(payload, dict) or payload.get("status") != "success":
        return KiteVerifyResult(ok=False, detail=f"kite /user/profile failed: {payload}")
    data = payload.get("data") or {}
    user_id = str(data.get("user_id") or "").strip() or None
    name = str(data.get("user_shortname") or data.get("user_name") or "").strip()
    who = f"{user_id}" + (f" ({name})" if name else "")
    return KiteVerifyResult(
        ok=True,
        detail=f"session OK — authenticated as {who or 'kite user'}",
        user_id=user_id,
    )


def verify_env_injection(env_path: Path, *, expected_access_token: str) -> KiteVerifyResult:
    """Re-read ``.env``, force-inject into ``os.environ``, then hit Kite profile."""
    injected = force_inject_kite_env(env_path)
    result = verify_kite_credentials(
        api_key=injected["KITE_API_KEY"],
        access_token=injected["KITE_ACCESS_TOKEN"],
        expected_access_token=expected_access_token,
    )
    return KiteVerifyResult(
        ok=result.ok,
        detail=result.detail,
        user_id=result.user_id,
        source_env=Path(env_path),
    )


def run_interactive_kite_auth(
    *,
    repo_root: Path,
    open_browser: bool = True,
    listen_port: int | None = None,
    verify: bool = True,
    print_fn: Callable[[str], None] = print,
) -> Path:
    """Prompt → exchange → write ``.env`` → optional verify. Returns path to ``.env``."""
    env_path = Path(repo_root) / ".env"
    file_vals = _read_env_file_values(env_path)
    existing = {
        k: (os.environ.get(k, "").strip() or file_vals.get(k, "").strip())
        for k in _ENV_KEYS
    }

    print_fn("ATHENA Kite daily auth — writes access token to .env")
    print_fn("Read-only session exchange. ATHENA never places orders.")
    print_fn("")

    api_key = _prompt("KITE_API_KEY", default=existing["KITE_API_KEY"], secret=False)
    api_secret = _prompt("KITE_API_SECRET", default=existing["KITE_API_SECRET"], secret=True)
    if not api_key or not api_secret:
        raise AthenaError("KITE_API_KEY and KITE_API_SECRET are required")

    url = login_url(api_key)
    print_fn("")
    print_fn("1) Open this login URL and tap Authorize:")
    print_fn(f"   {url}")
    if open_browser:
        webbrowser.open(url)

    if listen_port is not None:
        print_fn("")
        print_fn(
            f"2) Waiting on http://127.0.0.1:{listen_port}/ "
            "(Kite Redirect URL must match this exactly)…"
        )
        request_token = _wait_for_redirect_token(host="127.0.0.1", port=listen_port)
        print_fn("   Captured request_token from redirect.")
    else:
        print_fn("")
        print_fn("2) After Authorize, Chrome may say 'refused to connect' — that is OK.")
        print_fn("   Paste the full redirect URL from the address bar (or just request_token):")
        request_token = extract_request_token(input("> ").strip())

    print_fn("3) Exchanging request_token for access_token…")
    access_token = exchange_access_token(
        api_key=api_key, api_secret=api_secret, request_token=request_token
    )
    upsert_env_file(
        env_path,
        {
            "KITE_API_KEY": api_key,
            "KITE_API_SECRET": api_secret,
            "KITE_ACCESS_TOKEN": access_token,
        },
    )
    print_fn(f"4) Wrote KITE_ACCESS_TOKEN to {env_path}")

    print_fn("5) Re-injecting credentials from .env into this process…")
    force_inject_kite_env(env_path)

    if verify:
        print_fn("6) Verifying with authenticated Kite /user/profile…")
        result = verify_env_injection(env_path, expected_access_token=access_token)
        if not result.ok:
            raise ProviderError(f"kite auth verify failed: {result.detail}")
        print_fn(f"   VERIFY OK — {result.detail}")
    else:
        print_fn("6) Verify skipped (--skip-verify).")

    print_fn("   Done.")
    return env_path