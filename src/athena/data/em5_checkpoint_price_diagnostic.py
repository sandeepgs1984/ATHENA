"""EM-5 checkpoint-price live parity diagnostic — narrow, read-only,
research-only tool authorized by the Owner/Chief Architect (2026-08-28)
to determine whether ATHENA's live Kite quote path can reproduce the
exact checkpoint-price semantic the frozen EM-4 model was trained and
FINAL_TEST-validated on (`price_at_checkpoint`: open of the M5 candle
whose `ts_open == C`).

This is diagnostic-only. It does NOT modify `athena.domain.market.Quote`,
`KiteProvider.quotes()`, or `kite_ltp.py` -- those keep conflating Kite's
two distinct response timestamps (`timestamp`, the quote-snapshot time,
and `last_trade_time`, the authoritative last-executed-trade time) via
`row.get("timestamp") or row.get("last_trade_time")`. This module
parses and persists BOTH fields explicitly and separately, so the
semantic question ("was there a real trade at/after C, and when") can
be answered without touching anything a production consumer depends on.

Structural safety inherited, not reimplemented: `UrllibKiteTransport`
only allows GET on `/instruments`/`/quote` (order endpoints do not
exist in its allowlist at all) and already paces every `/quote` call
to Kite's documented <=1 req/s limit (`KiteRateLimitConfig`,
`quote_min_interval_seconds=1.0`) with bounded 429 backoff -- this
module calls that transport unmodified and inherits both guarantees
for free. No new rate-limiting logic is invented here.

No fitting, no model access, no FINAL_TEST -- this module only
observes and persists real live quote data.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.config.loader import load_kite_provider_config
from athena.data.providers.kite_transport import UrllibKiteTransport
from athena.errors import ConfigError, ProviderError

IST = ZoneInfo("Asia/Kolkata")

EM5_DIAGNOSTIC_CONTRACT_VERSION = "em5-checkpoint-price-diagnostic-v1"

#: Injected-dependency type aliases (test seams -- never a live call in a test).
FetchFn = Callable[[tuple[str, ...], datetime], dict[str, "DualTimestampObservation"]]
ClockFn = Callable[[], float]
SleepFn = Callable[[float], None]


def _parse_kite_ts(raw: str) -> datetime:
    """Identical parsing rule to kite_ltp.py's own (private) helper --
    duplicated deliberately rather than imported, so this diagnostic
    module has zero coupling to a production module's internals."""

    s = raw.strip().replace(" ", "T")
    if len(s) >= 5 and s[-5] in "+-" and ":" not in s[-5:]:
        s = f"{s[:-2]}:{s[-2:]}"
    ts = datetime.fromisoformat(s)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=IST)
    return ts


def build_diagnostic_transport(config_dir: Path) -> UrllibKiteTransport:
    """Same construction as kite_ltp.py's private `_build_transport`,
    duplicated (not imported) to keep this diagnostic fully isolated
    from any production module's internals -- per the Owner's explicit
    'do not modify shared quote semantics' constraint, this extends to
    not even importing private helpers from the modules that implement
    them."""

    import os

    api_key = (os.environ.get("KITE_API_KEY") or "").strip()
    access_token = (os.environ.get("KITE_ACCESS_TOKEN") or "").strip()
    if not api_key or not access_token:
        raise ConfigError("KITE_API_KEY/KITE_ACCESS_TOKEN missing in .env -- cannot run diagnostic")
    kite_cfg = load_kite_provider_config(config_dir)
    return UrllibKiteTransport(
        base_url=kite_cfg.base_url, api_key=api_key, access_token=access_token,
        rate_limit=kite_cfg.rate_limit,
    )


@dataclass(frozen=True, slots=True)
class DualTimestampObservation:
    """One /quote poll's raw result for one instrument -- BOTH Kite
    timestamps kept separate and explicit, never conflated."""

    instrument_id: str
    poll_request_ts: datetime  # our own wall-clock time we issued the request at
    api_timestamp: datetime | None  # Kite's "timestamp" field (quote-snapshot time)
    last_trade_time: datetime | None  # Kite's "last_trade_time" field (authoritative trade time)
    last_price: Decimal | None
    raw_fields_present: tuple[str, ...]  # which of timestamp/last_trade_time/last_price keys existed in the raw row


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def parse_dual_timestamp_row(
    instrument_id: str, row: dict | None, poll_request_ts: datetime,
) -> DualTimestampObservation:
    """Tolerant by design -- a missing field is recorded as None, never
    raised, because 'is last_trade_time actually present' is itself
    part of what the semantic canary must establish empirically."""

    if row is None:
        return DualTimestampObservation(
            instrument_id=instrument_id, poll_request_ts=poll_request_ts,
            api_timestamp=None, last_trade_time=None, last_price=None, raw_fields_present=(),
        )
    present = tuple(k for k in ("timestamp", "last_trade_time", "last_price") if row.get(k) is not None)
    api_ts_raw = row.get("timestamp")
    ltt_raw = row.get("last_trade_time")
    return DualTimestampObservation(
        instrument_id=instrument_id, poll_request_ts=poll_request_ts,
        api_timestamp=_parse_kite_ts(str(api_ts_raw)) if api_ts_raw else None,
        last_trade_time=_parse_kite_ts(str(ltt_raw)) if ltt_raw else None,
        last_price=_to_decimal(row.get("last_price")),
        raw_fields_present=present,
    )


def fetch_dual_timestamp_quotes(
    transport: UrllibKiteTransport, instrument_ids: tuple[str, ...], *, poll_request_ts: datetime,
) -> dict[str, DualTimestampObservation]:
    """ONE batched /quote request for every id (never one request per
    id) -- reuses the exact `i=` multi-param pattern KiteProvider.quotes()
    and kite_ltp.py already use. Pacing/backoff is enforced by the
    transport itself, not here."""

    if not instrument_ids:
        return {}
    payload = transport.get_json("/quote", [("i", iid) for iid in instrument_ids])
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise ProviderError("kite /quote returned malformed data")
    by_upper = {str(k).upper(): v for k, v in data.items()}
    results = {}
    for iid in instrument_ids:
        row = data.get(iid, by_upper.get(iid.upper()))
        results[iid] = parse_dual_timestamp_row(iid, row, poll_request_ts)
    return results


def observation_to_dict(obs: DualTimestampObservation) -> dict:
    return {
        "instrument_id": obs.instrument_id,
        "poll_request_ts": obs.poll_request_ts.isoformat(),
        "api_timestamp": obs.api_timestamp.isoformat() if obs.api_timestamp else None,
        "last_trade_time": obs.last_trade_time.isoformat() if obs.last_trade_time else None,
        "last_price": str(obs.last_price) if obs.last_price is not None else None,
        "raw_fields_present": list(obs.raw_fields_present),
    }


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")


def run_semantic_canary(
    *,
    fetch: FetchFn, instrument_ids: tuple[str, ...], duration_seconds: float,
    poll_interval_seconds: float, now: ClockFn, sleep: SleepFn, out_path: Path,
) -> list[DualTimestampObservation]:
    """Polls the same small instrument set repeatedly for a fixed real
    duration, persisting EVERY observation (not just qualifying ones) --
    this is what lets a human later confirm empirically whether
    `last_trade_time` only advances on a genuine new trade, whether
    repeated no-trade polls leave it unchanged, and whether `timestamp`
    and `last_trade_time` diverge. `fetch`/`now`/`sleep` are injected so
    this loop is unit-testable without any live Kite call."""

    started = now()
    observations: list[DualTimestampObservation] = []
    while (now() - started) < duration_seconds:
        poll_ts = datetime.now(tz=IST)
        batch = fetch(instrument_ids, poll_ts)
        for obs in batch.values():
            observations.append(obs)
            append_jsonl(out_path, {"kind": "semantic_canary", **observation_to_dict(obs)})
        sleep(poll_interval_seconds)
    return observations


@dataclass(frozen=True, slots=True)
class CheckpointCaptureResult:
    checkpoint: str
    session_date: str
    qualified: dict[str, DualTimestampObservation]  # instrument_id -> first qualifying observation
    no_checkpoint_price: tuple[str, ...]  # instruments that never qualified within the window


def capture_checkpoint_observations(
    *,
    fetch: FetchFn, instrument_ids: tuple[str, ...], checkpoint_instant: datetime,
    window_seconds: float, poll_interval_seconds: float, now: ClockFn, sleep: SleepFn,
    out_path: Path, checkpoint_label: str, session_date: str,
) -> CheckpointCaptureResult:
    """For each instrument, polls (batched, shared across all still-
    unqualified instruments each tick) until either its `last_trade_time`
    is observed `>= checkpoint_instant` (qualifies -- stop polling that
    instrument, per the Owner's 'no reason to continue polling' rule) or
    the window elapses (`NO_CHECKPOINT_PRICE`). Every poll, qualifying or
    not, is persisted for audit."""

    remaining = list(instrument_ids)
    qualified: dict[str, DualTimestampObservation] = {}
    started = now()

    while remaining and (now() - started) < window_seconds:
        poll_ts = datetime.now(tz=IST)
        batch = fetch(tuple(remaining), poll_ts)
        still_remaining = []
        for iid in remaining:
            obs = batch.get(iid)
            if obs is None:
                still_remaining.append(iid)
                continue
            does_qualify = obs.last_trade_time is not None and obs.last_trade_time >= checkpoint_instant
            append_jsonl(out_path, {
                "kind": "checkpoint_capture", "checkpoint": checkpoint_label,
                "session_date": session_date, "qualifies": does_qualify,
                "latency_seconds": (
                    (obs.last_trade_time - checkpoint_instant).total_seconds()
                    if does_qualify and obs.last_trade_time else None
                ),
                **observation_to_dict(obs),
            })
            if does_qualify:
                qualified[iid] = obs
            else:
                still_remaining.append(iid)
        remaining = still_remaining
        if remaining:
            sleep(poll_interval_seconds)

    return CheckpointCaptureResult(
        checkpoint=checkpoint_label, session_date=session_date,
        qualified=qualified, no_checkpoint_price=tuple(remaining),
    )
