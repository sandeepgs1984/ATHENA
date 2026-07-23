"""Pluggable briefing notifiers (M10.3).

Dispatch only — no briefing assembly. Secrets stay in environment variables.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

from athena.errors import BriefingError
from athena.notifications.models import DailyBriefing, DeliveryReceipt


class Notifier(Protocol):
    def notify(self, briefing: DailyBriefing) -> DeliveryReceipt: ...


class FileNotifier:
    """Write briefing JSON + text under an output directory (tests / dry-run)."""

    def __init__(self, output_dir: str | Path) -> None:
        self._output_dir = Path(output_dir)

    def notify(self, briefing: DailyBriefing) -> DeliveryReceipt:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self._output_dir / f"{briefing.briefing_id}.json"
        text_path = self._output_dir / f"{briefing.briefing_id}.txt"
        json_path.write_text(briefing.to_json() + "\n", encoding="utf-8")
        text_path.write_text(briefing.to_text(), encoding="utf-8")
        return DeliveryReceipt(
            channel="file",
            ok=True,
            detail=f"wrote {json_path.name} and {text_path.name}",
            target=str(self._output_dir),
        )


class WebhookNotifier:
    """POST briefing JSON to ``ATHENA_WEBHOOK_URL`` (never from config JSON)."""

    def __init__(self, *, timeout_seconds: int = 10, url: str | None = None) -> None:
        self._timeout = timeout_seconds
        self._url = url if url is not None else os.environ.get("ATHENA_WEBHOOK_URL", "").strip()

    def notify(self, briefing: DailyBriefing) -> DeliveryReceipt:
        if not self._url:
            raise BriefingError(
                "webhook channel enabled but ATHENA_WEBHOOK_URL is not set in the environment"
            )
        body = json.dumps({
            "briefing_id": briefing.briefing_id,
            "status": briefing.status.value,
            "as_of": briefing.as_of.isoformat(),
            "text_summary": briefing.text_summary,
            "machine": dict(briefing.machine),
        }, sort_keys=True).encode("utf-8")
        request = urllib.request.Request(
            self._url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:
                code = getattr(resp, "status", None) or resp.getcode()
                if int(code) >= 400:
                    raise BriefingError(f"webhook returned HTTP {code}")
        except urllib.error.URLError as exc:
            raise BriefingError(f"webhook delivery failed: {exc}") from exc
        return DeliveryReceipt(
            channel="webhook",
            ok=True,
            detail=f"posted briefing {briefing.briefing_id}",
            target="ATHENA_WEBHOOK_URL",
        )


class EmailNotifier:
    """Email channel reserved for P8.9 — M10.3 refuses if enabled without SMTP wiring."""

    def notify(self, briefing: DailyBriefing) -> DeliveryReceipt:
        raise BriefingError(
            "email channel is enabled but SMTP delivery is not implemented in M10.3; "
            "disable channels.email or use file/webhook"
        )
