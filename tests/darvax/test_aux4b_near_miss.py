"""AUX-4b: DarvaX's own near-miss digest, written once per completed sweep.

Not scheduled -- the owner confirmed this is the right trigger specifically
because it inherits DX-4a's "never scheduled" design by construction: a
digest can only ever fire as a side effect of a sweep the owner already
started. Reuses distance_to_breakout_pct (DX-3, already persisted) rather
than a new computation -- the same field the Levels view's "Approaching
their level" zone already reads.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

from athena.darvax.config import DarvaxConfig
from athena.darvax.digest import render_digest_text, write_digest
from athena.darvax.screening.models import DarvasRule, DarvaxSignalType, DarvaxTier, ScreenResult
from athena.darvax.screening.near_miss import near_miss_candidates
from athena.darvax.screening.sweep import SweepRunner
from athena.darvax.store.repository import DarvaxRepository

BASE = datetime(2026, 8, 20, tzinfo=timezone.utc)


def _result(
    instrument_id: str = "NSE:VSSL",
    *,
    tier: DarvaxTier = DarvaxTier.WATCH,
    distance: str | None = "1.5",
    trigger: str | None = None,
    box_top: str | None = "335.95",
    breakout_reference: str | None = "box_top",
) -> ScreenResult:
    return ScreenResult(
        sweep_id="swp-1", instrument_id=instrument_id, signal_id=f"s-{instrument_id}",
        tier=tier, signal_type=DarvaxSignalType.INSIDE_TOPMOST_BOX,
        darvas_rule=DarvasRule.A_HOLD_WHILE_IN_TOPMOST_BOX, rank=1,
        close=Decimal("330.00"), explanation="e",
        trigger_price=Decimal(trigger) if trigger is not None else None,
        box_top=Decimal(box_top) if box_top is not None else None,
        breakout_reference=breakout_reference,
        distance_to_breakout_pct=Decimal(distance) if distance is not None else None,
    )


# --------------------------------------------------------------------------- #
# 1. near_miss_candidates — pure classification
# --------------------------------------------------------------------------- #


def test_a_watch_row_within_margin_is_a_candidate():
    results = [_result(distance="1.5")]
    out = near_miss_candidates(results, max_pct=Decimal("2"))
    assert len(out) == 1
    assert out[0].symbol == "VSSL"
    assert out[0].distance_to_breakout_pct == Decimal("1.5")


def test_a_watch_row_beyond_the_margin_is_excluded():
    results = [_result(distance="5.0")]
    assert near_miss_candidates(results, max_pct=Decimal("2")) == ()


def test_a_row_already_past_its_level_is_excluded():
    """Negative distance means price is already through the level -- that's
    what the ACTIONABLE tier already reports. Repeating it here would
    misdescribe something that already happened as about to happen."""
    results = [_result(distance="-0.5")]
    assert near_miss_candidates(results, max_pct=Decimal("2")) == ()


def test_a_non_watch_tier_is_never_a_near_miss():
    results = [_result(tier=DarvaxTier.ACTIONABLE, distance="0.5")]
    assert near_miss_candidates(results, max_pct=Decimal("2")) == ()


def test_a_row_with_neither_trigger_nor_box_top_is_excluded_not_guessed():
    results = [_result(trigger=None, box_top=None)]
    assert near_miss_candidates(results, max_pct=Decimal("2")) == ()


def test_a_row_missing_distance_is_excluded_not_guessed():
    results = [_result(distance=None)]
    assert near_miss_candidates(results, max_pct=Decimal("2")) == ()


def test_trigger_price_wins_over_box_top_when_both_are_set():
    """Mirrors distance_to_breakout()'s own precedence in engine.py: prefer
    the entry trigger when DX-3 recorded one, box_top only as a fallback."""
    results = [_result(trigger="330.50", box_top="335.95", breakout_reference="trigger_price")]
    out = near_miss_candidates(results, max_pct=Decimal("2"))
    assert out[0].buy_level == Decimal("330.50")
    assert out[0].buy_level_basis == "trigger_price"


def test_box_top_fallback_is_what_almost_every_real_watch_row_uses():
    """Caught via live verification: DX-3 sets trigger_price only alongside a
    stop, so on a real sweep every single WATCH row with a distance used the
    box_top fallback (484 of 484, measured). An earlier version of this
    filter required trigger_price specifically and silently discarded all of
    them -- this is the regression guard for that exact defect."""
    results = [_result(trigger=None, box_top="335.95", breakout_reference="box_top")]
    out = near_miss_candidates(results, max_pct=Decimal("2"))
    assert len(out) == 1
    assert out[0].buy_level == Decimal("335.95")
    assert out[0].buy_level_basis == "box_top"


def test_candidates_are_sorted_nearest_first():
    results = [
        _result(instrument_id="NSE:FAR", distance="1.9"),
        _result(instrument_id="NSE:NEAR", distance="0.1"),
    ]
    out = near_miss_candidates(results, max_pct=Decimal("2"))
    assert [c.symbol for c in out] == ["NEAR", "FAR"]


# --------------------------------------------------------------------------- #
# 2. digest.py — the writer itself
# --------------------------------------------------------------------------- #


def test_write_digest_produces_json_and_text(tmp_path):
    candidates = near_miss_candidates([_result()], max_pct=Decimal("2"))
    json_path, text_path = write_digest(tmp_path, "swp-1", BASE, candidates)
    assert json_path.exists() and text_path.exists()
    payload = json.loads(json_path.read_text())
    assert payload["near_miss_count"] == 1
    assert payload["near_misses"][0]["symbol"] == "VSSL"
    assert "VSSL" in text_path.read_text()


def test_render_digest_text_says_none_when_empty():
    text = render_digest_text("swp-1", BASE, ())
    assert "Near misses (0)" in text
    assert "(none)" in text


# --------------------------------------------------------------------------- #
# 3. Wired into the sweep -- fires once per completed sweep, never scheduled
# --------------------------------------------------------------------------- #


class _StubMarketData:
    def list_instruments(self):
        return []


def test_sweep_writes_a_digest_on_completion(tmp_path):
    repo = DarvaxRepository(str(tmp_path / "darvax.db"))
    repo.initialize()
    cfg = DarvaxConfig()
    object.__setattr__(cfg.near_miss, "output_dir", str(tmp_path / "digests"))
    runner = SweepRunner(
        market_data=_StubMarketData(), store=repo, config=cfg, darvax_version="test",
    )
    sweep_id = runner.start()
    runner.join(timeout=5)
    digest_files = list((tmp_path / "digests").glob("near-miss-*.json"))
    assert len(digest_files) == 1
    assert sweep_id in digest_files[0].name
    repo.close()


def test_sweep_skips_the_digest_when_near_miss_is_disabled(tmp_path):
    repo = DarvaxRepository(str(tmp_path / "darvax.db"))
    repo.initialize()
    cfg = DarvaxConfig()
    object.__setattr__(cfg.near_miss, "enabled", False)
    object.__setattr__(cfg.near_miss, "output_dir", str(tmp_path / "digests"))
    runner = SweepRunner(
        market_data=_StubMarketData(), store=repo, config=cfg, darvax_version="test",
    )
    runner.start()
    runner.join(timeout=5)
    assert not (tmp_path / "digests").exists()
    repo.close()


def test_a_digest_write_failure_does_not_fail_the_sweep(tmp_path, monkeypatch):
    """The sweep already completed and was recorded as such by the time the
    digest is written -- a write failure here must be logged, not allowed to
    retroactively break what already succeeded."""
    repo = DarvaxRepository(str(tmp_path / "darvax.db"))
    repo.initialize()
    cfg = DarvaxConfig()
    # A file sitting where the digest directory needs to be created makes
    # mkdir(parents=True) raise -- a real, not synthetic, failure mode.
    blocker = tmp_path / "digests"
    blocker.write_text("not a directory")
    object.__setattr__(cfg.near_miss, "output_dir", str(blocker))
    runner = SweepRunner(
        market_data=_StubMarketData(), store=repo, config=cfg, darvax_version="test",
    )
    runner.start()
    runner.join(timeout=5)
    assert runner.progress().state == "completed"
    repo.close()
