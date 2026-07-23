"""Hard-failure alerts for host-scheduled ops (R5 / DD-9).

Channels: local file artifacts + optional webhook. Secrets stay in ``.env``
(``ATHENA_ALERT_WEBHOOK_URL``, falling back to ``ATHENA_WEBHOOK_URL``).
No SMTP in R5 (email remains deferred).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from athena.config.models import FailureAlertsConfig
from athena.errors import AthenaError


@dataclass(frozen=True, slots=True)
class FailureAlert:
    """Immutable alert payload for a hard ops failure."""

    alert_id: str
    as_of: datetime
    title: str
    detail: str
    source: str
    exit_code: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "as_of": self.as_of.isoformat(),
            "title": self.title,
            "detail": self.detail,
            "source": self.source,
            "exit_code": self.exit_code,
            "kind": "athena_failure_alert",
        }

    def to_text(self) -> str:
        return (
            f"ATHENA FAILURE ALERT\n"
            f"id      : {self.alert_id}\n"
            f"as_of   : {self.as_of.isoformat()}\n"
            f"source  : {self.source}\n"
            f"title   : {self.title}\n"
            f"detail  : {self.detail}\n"
            f"exit    : {self.exit_code}\n"
        )


@dataclass(frozen=True, slots=True)
class AlertDeliveryReceipt:
    channel: str
    ok: bool
    detail: str
    target: str = ""


class FailureAlertError(AthenaError):
    """Alert delivery failed after a hard ops error."""


def resolve_alert_webhook_url() -> str:
    """Prefer dedicated alert URL; fall back to briefing webhook."""
    return (
        os.environ.get("ATHENA_ALERT_WEBHOOK_URL", "").strip()
        or os.environ.get("ATHENA_WEBHOOK_URL", "").strip()
    )


def make_alert_id(as_of: datetime, source: str) -> str:
    stamp = as_of.strftime("%Y%m%dT%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in source)[:40]
    return f"alert-{stamp}-{safe}"


class FailureAlertDispatcher:
    """Write file alerts and/or POST webhook for hard failures."""

    def __init__(
        self,
        config: FailureAlertsConfig,
        *,
        repo_root: Path,
        tzinfo: ZoneInfo,
    ) -> None:
        self._config = config
        self._repo_root = Path(repo_root)
        self._tzinfo = tzinfo

    def dispatch(
        self,
        *,
        title: str,
        detail: str,
        source: str,
        as_of: datetime | None = None,
        exit_code: int = 1,
    ) -> tuple[FailureAlert, list[AlertDeliveryReceipt]]:
        if not self._config.enabled:
            raise FailureAlertError("failure alerts are disabled in host_ops.json")

        when = as_of or datetime.now(self._tzinfo)
        if when.tzinfo is None:
            when = when.replace(tzinfo=self._tzinfo)
        alert = FailureAlert(
            alert_id=make_alert_id(when, source),
            as_of=when,
            title=title.strip() or "ATHENA failure",
            detail=detail.strip() or "(no detail)",
            source=source,
            exit_code=exit_code,
        )

        receipts: list[AlertDeliveryReceipt] = []
        if self._config.file_enabled:
            receipts.append(self._write_file(alert))
        if self._config.webhook_enabled:
            receipts.append(self._post_webhook(alert))

        if not receipts:
            raise FailureAlertError(
                "failure alerts enabled but no channels are on "
                "(enable file_enabled and/or webhook_enabled)"
            )
        if not any(r.ok for r in receipts):
            joined = "; ".join(f"{r.channel}: {r.detail}" for r in receipts)
            raise FailureAlertError(f"all failure alert channels failed: {joined}")
        return alert, receipts

    def _write_file(self, alert: FailureAlert) -> AlertDeliveryReceipt:
        out = Path(self._config.output_dir)
        if not out.is_absolute():
            out = self._repo_root / out
        out.mkdir(parents=True, exist_ok=True)
        json_path = out / f"{alert.alert_id}.json"
        text_path = out / f"{alert.alert_id}.txt"
        json_path.write_text(json.dumps(alert.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        text_path.write_text(alert.to_text(), encoding="utf-8")
        return AlertDeliveryReceipt(
            channel="file",
            ok=True,
            detail=f"wrote {json_path.name} and {text_path.name}",
            target=str(out),
        )

    def _post_webhook(self, alert: FailureAlert) -> AlertDeliveryReceipt:
        url = resolve_alert_webhook_url()
        if not url:
            return AlertDeliveryReceipt(
                channel="webhook",
                ok=False,
                detail=(
                    "ATHENA_ALERT_WEBHOOK_URL / ATHENA_WEBHOOK_URL not set; "
                    "file alert still applies if enabled"
                ),
                target="",
            )
        body = json.dumps(alert.to_dict(), sort_keys=True).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._config.webhook_timeout_seconds) as resp:
                code = getattr(resp, "status", None) or resp.getcode()
                if int(code) >= 400:
                    return AlertDeliveryReceipt(
                        channel="webhook",
                        ok=False,
                        detail=f"HTTP {code}",
                        target="ATHENA_ALERT_WEBHOOK_URL|ATHENA_WEBHOOK_URL",
                    )
        except urllib.error.URLError as exc:
            return AlertDeliveryReceipt(
                channel="webhook",
                ok=False,
                detail=f"delivery failed: {exc}",
                target="ATHENA_ALERT_WEBHOOK_URL|ATHENA_WEBHOOK_URL",
            )
        return AlertDeliveryReceipt(
            channel="webhook",
            ok=True,
            detail=f"posted {alert.alert_id}",
            target="ATHENA_ALERT_WEBHOOK_URL|ATHENA_WEBHOOK_URL",
        )
