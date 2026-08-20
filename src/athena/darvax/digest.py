"""DarvaX's own digest writer (AUX-4b).

Deliberately not importing ``athena.notifications`` for this, even though the
directional import rule would permit it (DarvaX -> ATHENA core is allowed).
The established convention for this satellite is to duplicate a small amount
of logic rather than depend on an ATHENA-core module -- ``signals/ema.py``'s
own docstring states the same reasoning for re-deriving its own EMA rather
than reading ATHENA's persisted indicators: "this duplication is the price of
the one-way dependency rule and is preferred to coupling." A notifications
module is a heavier, more actively-evolving dependency than an EMA formula,
so the case for staying self-contained is at least as strong here.

File-only for this milestone, matching ATHENA's own simplest default
channel. Not wired to any external service -- writing a local file is the
lowest-risk way to prove the trigger and the content are both right; a
webhook can be added later without touching this shape.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from athena.darvax.screening.near_miss import NearMissCandidate


def render_digest_text(sweep_id: str, as_of: datetime, candidates: tuple[NearMissCandidate, ...]) -> str:
    lines = [
        f"DarvaX Near-Miss Digest — {sweep_id}",
        f"as_of: {as_of.isoformat()}",
        "",
        f"Near misses ({len(candidates)}):",
    ]
    if not candidates:
        lines.append("  (none)")
    else:
        for c in candidates:
            basis = "clears" if c.buy_level_basis == "box_top" else "buy above"
            lines.append(
                f"  - {c.symbol}: now {c.close}, {basis} {c.buy_level} "
                f"({c.distance_to_breakout_pct}% away)"
            )
    return "\n".join(lines) + "\n"


def write_digest(
    output_dir: Path, sweep_id: str, as_of: datetime, candidates: tuple[NearMissCandidate, ...],
) -> tuple[Path, Path]:
    """Write the digest as JSON + text, mirroring ATHENA's own dual-format
    convention (notifications/notifiers.py's FileNotifier). Returns the two
    paths written. Raises on a write failure -- a sweep that reports success
    while its digest silently failed to write would be a worse outcome than
    a loud error, matching this project's fail-loudly convention throughout.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"near-miss-{sweep_id}"
    json_path = output_dir / f"{stem}.json"
    text_path = output_dir / f"{stem}.txt"

    payload = {
        "sweep_id": sweep_id,
        "as_of": as_of.isoformat(),
        "near_miss_count": len(candidates),
        "near_misses": [
            {
                "instrument_id": c.instrument_id,
                "symbol": c.symbol,
                "close": str(c.close),
                "buy_level": str(c.buy_level),
                "buy_level_basis": c.buy_level_basis,
                "distance_to_breakout_pct": str(c.distance_to_breakout_pct),
            }
            for c in candidates
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    text_path.write_text(render_digest_text(sweep_id, as_of, candidates), encoding="utf-8")
    return json_path, text_path


def resolve_output_dir(configured: str) -> Path:
    """Same relative-to-CWD resolution `sweep.py`'s writer already applies --
    duplicated rather than imported across the writer/reader split since
    it's two lines, matching this file's own stated convention of small
    duplication over coupling."""
    output_dir = Path(configured)
    return output_dir if output_dir.is_absolute() else Path.cwd() / output_dir


_EMPTY_DIGEST: dict = {"sweep_id": None, "as_of": None, "near_miss_count": 0, "near_misses": []}


def read_latest_digest(output_dir: Path) -> dict:
    """AUX-4c: read the most recently written digest (AUX-4b writes one per
    completed sweep, never overwriting the previous one) -- never
    recomputes near-miss detection, only reads what a sweep already
    persisted. A missing directory, no digest yet, or a corrupt file all
    degrade to the same empty shape rather than raising -- a UI read should
    never fail a page load over a stale/malformed artifact."""
    if not output_dir.exists():
        return dict(_EMPTY_DIGEST)

    candidates = sorted(
        output_dir.glob("near-miss-*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not candidates:
        return dict(_EMPTY_DIGEST)

    try:
        payload = json.loads(candidates[0].read_text(encoding="utf-8"))
        return {
            "sweep_id": payload.get("sweep_id"),
            "as_of": payload.get("as_of"),
            "near_miss_count": int(payload.get("near_miss_count", 0)),
            "near_misses": list(payload.get("near_misses", [])),
        }
    except (OSError, ValueError, KeyError, TypeError):
        return dict(_EMPTY_DIGEST)
