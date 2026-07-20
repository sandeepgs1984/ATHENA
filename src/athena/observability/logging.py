"""JSON-lines logging (ATHENA-002 §10).

Every record: ts, level, module, run_id, cycle_id, event, payload.
Secrets are structurally excluded: payload keys matching redaction patterns
are masked before serialization. Logs are diagnostics — anything needed to
explain a decision lives in the DB, never only in logs.
"""

from __future__ import annotations

import contextvars
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("athena_run_id", default="-")
_cycle_id: contextvars.ContextVar[str] = contextvars.ContextVar("athena_cycle_id", default="-")

#: Payload keys containing any of these substrings are redacted (S-1).
REDACTED_KEY_MARKERS = ("token", "secret", "password", "api_key", "apikey", "auth")

_REDACTED = "***REDACTED***"


def set_run_context(run_id: str, cycle_id: str = "-") -> None:
    """Bind run/cycle identifiers to all subsequent log records in this context."""
    _run_id.set(run_id)
    _cycle_id.set(cycle_id)


def _redact(payload: Mapping[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if any(marker in key.lower() for marker in REDACTED_KEY_MARKERS):
            clean[key] = _REDACTED
        elif isinstance(value, Mapping):
            clean[key] = _redact(value)
        else:
            clean[key] = value
    return clean


class JsonLineFormatter(logging.Formatter):
    """One JSON object per line; deterministic key order."""

    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "payload", None)
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "run_id": _run_id.get(),
            "cycle_id": _cycle_id.get(),
            "event": record.getMessage(),
            "payload": _redact(payload) if isinstance(payload, Mapping) else {},
        }
        return json.dumps(entry, sort_keys=True, default=str)


def setup_logging(log_dir: Path, level: str = "INFO", *, also_console: bool = False,
                  today: Optional[datetime] = None) -> Path:
    """Configure the root 'athena' logger to write logs/athena-YYYYMMDD.jsonl."""

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = (today or datetime.now(timezone.utc)).strftime("%Y%m%d")
    log_path = log_dir / f"athena-{stamp}.jsonl"

    logger = logging.getLogger("athena")
    logger.setLevel(level.upper())
    logger.handlers.clear()
    logger.propagate = False

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(JsonLineFormatter())
    logger.addHandler(file_handler)

    if also_console:
        console = logging.StreamHandler()
        console.setFormatter(JsonLineFormatter())
        logger.addHandler(console)

    return log_path


def log_event(module: str, event: str, payload: Optional[Mapping[str, Any]] = None,
              level: int = logging.INFO) -> None:
    """Convenience: structured event log with payload redaction."""
    logging.getLogger(f"athena.{module}").log(level, event, extra={"payload": payload or {}})
