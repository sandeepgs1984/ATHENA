"""EM-5 production canary gate -- the fail-fast operational gate required
before full-universe live scanning, per
`docs/design/EM-5-LIVE-SCANNER-CONTRACT.md` Section 14 ("Fail-Fast
Operational Gate -- mature-history TRAIN completeness floor"). This directly
reuses CLAUDE.md's already-adopted "Expensive external-data runs" canary
rule (adopted 2026-08-24, after the EM-1r3 production incident -- see
`src/athena/data/em1r3_production_canary.py`, the reference implementation
this module's shape mirrors) -- not a new policy invented for EM-5.

Makes ZERO Kite provider/network calls: the canary re-scans one already-
elapsed, already-ingested real historical session using ATHENA's own
persisted candles as the checkpoint reference price (the real M5 candle
whose `ts_open == checkpoint_instant`, i.e. exactly the frozen model's own
training-time `price_at_checkpoint(C)` definition -- see
`evidence_assembly.py`'s docstring). This is real, not synthetic, data;
using it instead of a live quote is strictly *more* faithful to what the
frozen model saw at fit time, and the live parity diagnostic (contract
Section 2) already showed live-quote and historical-candle-open agree to
within 0.0685%.

Numeric floor and mature-history baseline below are the exact values
measured and recorded in the contract's Section 14 table -- not re-derived
here (that measurement required the full EM-1r3/EM-2 research corpus,
out of scope for an operational gate module).
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from datetime import time as time_of_day
from datetime import tzinfo as tzinfo_type
from pathlib import Path

from athena.domain.enums import SessionType, Timeframe
from athena.explosive_move.contracts import CANDIDATE_CHECKPOINTS_IST
from athena.explosive_move.evidence_contract import ALL_FIELDS, Classification
from athena.explosive_move.live.checkpoint_reference_price import CheckpointReferencePrice
from athena.explosive_move.live.evidence_assembly import (
    assemble_candidate_row,
    historical_cumulative_volumes_through_checkpoint,
)
from athena.explosive_move.live.frozen_inference import FrozenModelIntegrityError, load_frozen_model
from athena.explosive_move.live.market_data_port import EmrMarketDataPort
from athena.explosive_move.live.regime_source import build_canonical_regime_lookup
from athena.explosive_move.live.scanner import (
    DAILY_BAR_LOOKBACK_CALENDAR_DAYS,
    FAMILIES_THRESHOLDS,
    REL_VOLUME_LOOKBACK_CALENDAR_DAYS,
    REL_VOLUME_LOOKBACK_SESSIONS,
    ScanCycleConfig,
    _daily_bar_from_d1_candle,
    _group_by_session_date,
    run_scan_cycle,
)
from athena.explosive_move.store.repository import EmrRepository

#: Per checkpoint, on the canary's real symbol slice restricted to
#: mature-history instruments -- roughly 1pp below the measured
#: 99.9929%-100% mature-history baseline (contract Section 14), giving
#: real headroom for the one genuine, already-understood edge case
#: (zero-cumulative-volume VWAP at 09:20) while still failing closed by
#: nearly two orders of magnitude of margin on anything resembling the
#: EM-1r3 incident's ~0% usable admission.
CANARY_COMPLETENESS_FLOOR = 0.99

#: A checkpoint's real canary completeness may not fall more than this
#: many percentage points below its own measured mature-history baseline
#: -- a relative systemic-regression check, independent of the absolute
#: floor above (appropriately tight given the baseline itself is
#: 99.99-100%, so even a small relative regression is meaningful).
MAX_COMPLETENESS_REGRESSION_PERCENTAGE_POINTS = 2.0

#: Measured mature-history all-22-fields-known rate per checkpoint
#: (contract Section 14 table, 182,326 real mature TRAIN rows). Checkpoints
#: not listed here have no recorded baseline and cannot be regression-
#: checked (the canary fails closed rather than silently skipping).
MATURE_HISTORY_BASELINE_KNOWN_RATE: dict[str, float] = {
    "09:20": 0.999929,
    "09:30": 1.0,
    "09:45": 1.0,
    "10:00": 1.0,
    "10:30": 1.0,
    "11:00": 1.0,
    "12:00": 1.0,
    "13:00": 1.0,
    "14:00": 1.0,
}

#: "Mature" per contract Section 14: an instrument has at least this many
#: admitted daily bars strictly before the session, derived from the frozen
#: evidence contract itself (the maximum `minimum_lookback_sessions` across
#: all CANDIDATE_FEATURE fields) -- never hardcoded, never fitted to an
#: observed-completeness curve.
MATURE_HISTORY_MINIMUM_SESSIONS: int = max(
    f.minimum_lookback_sessions
    for f in ALL_FIELDS
    if f.classification is Classification.CANDIDATE_FEATURE and f.minimum_lookback_sessions is not None
)
assert MATURE_HISTORY_MINIMUM_SESSIONS == 50, (
    f"contract Section 14 pins the mature-history floor at 50 sessions (SMA50_REL); "
    f"evidence_contract now reports {MATURE_HISTORY_MINIMUM_SESSIONS} -- the Section 14 "
    f"baseline table above was measured against 50 and must be re-measured before this "
    f"assertion is updated"
)

#: Wide enough to reliably observe 50+ prior admitted daily bars even
#: across weekends/holidays -- same margin `scanner.py` uses for the same
#: purpose.
_MATURITY_LOOKBACK_CALENDAR_DAYS = DAILY_BAR_LOOKBACK_CALENDAR_DAYS


@dataclass(frozen=True, slots=True)
class HardInvariantOutcome:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class CheckpointCompleteness:
    checkpoint: str
    mature_row_count: int
    all_fields_known_count: int
    all_fields_known_rate: float
    baseline_rate: float | None
    regression_percentage_points: float | None
    passes_floor: bool
    passes_regression_bound: bool


@dataclass(frozen=True, slots=True)
class CanaryGateResult:
    passed: bool
    session_date: date
    checkpoints: tuple[str, ...]
    mature_instrument_ids: tuple[str, ...]
    completeness: tuple[CheckpointCompleteness, ...]
    hard_invariants: tuple[HardInvariantOutcome, ...]
    failure_reasons: tuple[str, ...]
    #: Session-level canonical regime (same for every checkpoint this
    #: session -- RegimeEngine has no intraday concept), as returned by
    #: `regime_source.build_canonical_regime_lookup`.
    regime_assessment: dict[str, str] = field(default_factory=dict)
    #: checkpoint -> field_name -> count of mature instruments where that
    #: field was known, verified during the boundary-regression pass
    #: (real candles, real regime, real rel-volume history -- ground truth,
    #: not the live substitution path).
    field_known_count: dict[str, dict[str, int]] = field(default_factory=dict)
    #: checkpoint -> count of mature instruments the field pass actually
    #: verified (denominator for field_known_count's rates).
    field_verified_count: dict[str, int] = field(default_factory=dict)
    #: checkpoint -> {"universe": mature instrument count, "qualified":
    #: instruments with a real checkpoint reference price}.
    checkpoint_price_coverage: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "session_date": self.session_date.isoformat(),
            "checkpoints": list(self.checkpoints),
            "mature_instrument_count": len(self.mature_instrument_ids),
            "regime_assessment": self.regime_assessment,
            "completeness": [
                {
                    "checkpoint": c.checkpoint,
                    "mature_row_count": c.mature_row_count,
                    "all_fields_known_count": c.all_fields_known_count,
                    "all_fields_known_rate": round(c.all_fields_known_rate, 6),
                    "baseline_rate": c.baseline_rate,
                    "regression_percentage_points": c.regression_percentage_points,
                    "passes_floor": c.passes_floor,
                    "passes_regression_bound": c.passes_regression_bound,
                    "field_known_rate": {
                        name: round(count / self.field_verified_count[c.checkpoint], 6)
                        for name, count in self.field_known_count.get(c.checkpoint, {}).items()
                    } if self.field_verified_count.get(c.checkpoint) else {},
                    "checkpoint_price_coverage": self.checkpoint_price_coverage.get(c.checkpoint, {}),
                }
                for c in self.completeness
            ],
            "hard_invariants": [
                {"name": h.name, "passed": h.passed, "detail": h.detail} for h in self.hard_invariants
            ],
            "failure_reasons": list(self.failure_reasons),
        }


def select_mature_history_instruments(
    *,
    market_port: EmrMarketDataPort,
    universe_ids: tuple[str, ...],
    session_date: date,
    tzinfo: tzinfo_type,
    minimum_sessions: int = MATURE_HISTORY_MINIMUM_SESSIONS,
) -> tuple[str, ...]:
    """Real D1 admitted-session counts strictly before `session_date`, per
    the exact mature-history definition contract Section 14 froze: an
    instrument is mature iff it already has `>= minimum_sessions` admitted
    daily bars before this session."""

    if not universe_ids:
        return ()
    start = session_date - timedelta(days=_MATURITY_LOOKBACK_CALENDAR_DAYS)
    end = session_date - timedelta(days=1)
    daily_by_symbol = market_port.candles_for_instruments(
        universe_ids, Timeframe.D1,
        datetime.combine(start, time_of_day(0, 0), tzinfo=tzinfo),
        datetime.combine(end, time_of_day(23, 59), tzinfo=tzinfo),
    )
    return tuple(
        iid for iid in universe_ids
        if len({c.ts_open.date() for c in daily_by_symbol.get(iid, ())}) >= minimum_sessions
    )


def _check_frozen_artifact_integrity(
    *, config_dir: Path, model_version: str, families_thresholds: tuple[tuple[str, int], ...],
) -> HardInvariantOutcome:
    failures: list[str] = []
    for family, threshold in families_thresholds:
        try:
            load_frozen_model(config_dir=config_dir, version=model_version, family=family, threshold_percent=threshold)
        except FrozenModelIntegrityError as exc:
            failures.append(f"{family}_{threshold}: {exc}")
    if failures:
        return HardInvariantOutcome("FROZEN_ARTIFACT_INTEGRITY", False, "; ".join(failures))
    return HardInvariantOutcome(
        "FROZEN_ARTIFACT_INTEGRITY", True, f"{len(families_thresholds)} artifacts verified against manifest SHA256",
    )


def _real_candle_checkpoint_price_collector(
    market_port: EmrMarketDataPort,
) -> Callable[..., tuple[dict[str, CheckpointReferencePrice], tuple[str, ...], int]]:
    """A `collect_checkpoint_prices`-shaped callable that makes NO provider
    call: it looks up the real, already-ingested M5 candle whose
    `ts_open == checkpoint_instant` and uses its `open` as the checkpoint
    reference price -- exactly the frozen model's own training-time
    `price_at_checkpoint(C)` definition. Returns `quote_request_count = 0`
    always (no Kite polling loop ever runs)."""

    def _collect(
        *, instrument_ids: tuple[str, ...], checkpoint_instant: datetime, **_kwargs,
    ) -> tuple[dict[str, CheckpointReferencePrice], tuple[str, ...], int]:
        candles_by_symbol = market_port.candles_for_instruments(
            instrument_ids, Timeframe.M5, checkpoint_instant, checkpoint_instant,
        )
        qualified: dict[str, CheckpointReferencePrice] = {}
        no_price: list[str] = []
        for iid in instrument_ids:
            at_checkpoint = next(
                (c for c in candles_by_symbol.get(iid, ()) if c.ts_open == checkpoint_instant), None,
            )
            if at_checkpoint is None:
                no_price.append(iid)
                continue
            qualified[iid] = CheckpointReferencePrice(
                instrument_id=iid, checkpoint_instant=checkpoint_instant,
                reference_price_semantic="FIRST_OBSERVED_POST_CHECKPOINT_TRADE",
                last_price=at_checkpoint.open, last_trade_time=checkpoint_instant,
                snapshot_timestamp=None, latency_seconds=0.0, provider="canary-real-historical-candle",
            )
        return qualified, tuple(no_price), 0

    return _collect


def _check_hard_eligibility_inputs_well_formed(
    checkpoint_prices_by_checkpoint: dict[str, dict[str, CheckpointReferencePrice]],
) -> HardInvariantOutcome:
    malformed: list[str] = []
    checked = 0
    for checkpoint, prices in checkpoint_prices_by_checkpoint.items():
        for iid, price in prices.items():
            checked += 1
            if price.last_price <= 0:
                malformed.append(f"{checkpoint}/{iid}: non-positive checkpoint price {price.last_price}")
            if price.last_trade_time.tzinfo is None or price.checkpoint_instant.tzinfo is None:
                malformed.append(f"{checkpoint}/{iid}: naive (non-timezone-aware) checkpoint timestamp")
    if malformed:
        return HardInvariantOutcome("HARD_ELIGIBILITY_INPUTS_WELL_FORMED", False, "; ".join(malformed))
    return HardInvariantOutcome(
        "HARD_ELIGIBILITY_INPUTS_WELL_FORMED", True, f"{checked} checkpoint reference prices structurally valid",
    )


def _check_no_systemic_stale_data(candidates_by_checkpoint: dict[str, list[dict]]) -> HardInvariantOutcome:
    stale: list[str] = []
    for checkpoint, rows in candidates_by_checkpoint.items():
        stale_iids = {r["instrument_id"] for r in rows if r["freshness"] == "STALE"}
        if stale_iids:
            stale.append(f"{checkpoint}: {sorted(stale_iids)}")
    if stale:
        return HardInvariantOutcome("NO_SYSTEMIC_STALE_DATA", False, "; ".join(stale))
    return HardInvariantOutcome("NO_SYSTEMIC_STALE_DATA", True, "no STALE_DATA candidate across any canary checkpoint")


def _check_zero_provider_network_calls(quote_request_counts: dict[str, int]) -> HardInvariantOutcome:
    nonzero = {cp: n for cp, n in quote_request_counts.items() if n != 0}
    if nonzero:
        return HardInvariantOutcome("ZERO_PROVIDER_NETWORK_CALLS", False, f"nonzero quote_request_count: {nonzero}")
    return HardInvariantOutcome(
        "ZERO_PROVIDER_NETWORK_CALLS", True, f"0 quote requests across {len(quote_request_counts)} checkpoints",
    )


def _check_replay_determinism(
    rows_a_by_checkpoint: dict[str, list[dict]], rows_b_by_checkpoint: dict[str, list[dict]],
) -> HardInvariantOutcome:
    def _key(r: dict) -> tuple:
        return (r["instrument_id"], r["family"], r["threshold_percent"])

    mismatches: list[str] = []
    for checkpoint in rows_a_by_checkpoint:
        rows_a = sorted(rows_a_by_checkpoint[checkpoint], key=_key)
        rows_b = sorted(rows_b_by_checkpoint.get(checkpoint, []), key=_key)
        if len(rows_a) != len(rows_b):
            mismatches.append(f"{checkpoint}: row count {len(rows_a)} != {len(rows_b)}")
            continue
        for a, b in zip(rows_a, rows_b, strict=True):
            if (
                a["raw_logistic_estimate"] != b["raw_logistic_estimate"]
                or a["calibrated_probability"] != b["calibrated_probability"]
                or a["rank"] != b["rank"]
                or a["state"] != b["state"]
            ):
                mismatches.append(f"{checkpoint}/{_key(a)}: replay mismatch")
    if mismatches:
        return HardInvariantOutcome("REPLAY_DETERMINISM", False, "; ".join(mismatches))
    return HardInvariantOutcome(
        "REPLAY_DETERMINISM", True,
        f"byte-identical evidence/logits/probabilities/ranks across {len(rows_a_by_checkpoint)} checkpoints",
    )


def _check_checkpoint_boundary_matches_real_candle(
    *,
    market_port: EmrMarketDataPort,
    mature_instrument_ids: tuple[str, ...],
    session_date: date,
    session_open_time: time_of_day,
    checkpoint: str,
    checkpoint_instant: datetime,
    tzinfo: tzinfo_type,
    daily_bars_by_symbol: dict[str, tuple],
    regime_row: dict[str, str] | None,
) -> tuple[HardInvariantOutcome, dict[str, int], int]:
    """Reproduces `evidence_assembly.assemble_candidate_row`'s live
    synthetic-checkpoint-candle substitution using the REAL historical
    candle's own `open` as the injected price, and asserts the result is
    field-for-field identical to assembling the row directly from real
    candles that already include the real checkpoint candle (no
    substitution). Proves the substitution mechanism reproduces the frozen
    boundary formula exactly on real data -- not just the synthetic
    fixtures `test_em5_evidence_assembly.py` exercises.

    Also returns the real (non-substituted) row's per-field known-count
    tally and the number of instruments verified -- the ground-truth
    field-completeness data for the canary's diagnostic report, computed
    with the real regime assessment and real trailing REL_VOLUME history
    (unlike the boundary-equality check itself, which only needs the two
    rows to agree with each other, not with production's exact inputs)."""

    session_start_instant = datetime.combine(session_date, session_open_time, tzinfo=tzinfo)
    today_by_symbol = market_port.candles_for_instruments(
        mature_instrument_ids, Timeframe.M5, session_start_instant, checkpoint_instant,
    )
    rel_volume_start = session_date - timedelta(days=REL_VOLUME_LOOKBACK_CALENDAR_DAYS)
    rel_volume_by_symbol = market_port.candles_for_instruments(
        mature_instrument_ids, Timeframe.M5,
        datetime.combine(rel_volume_start, time_of_day(0, 0), tzinfo=tzinfo),
        datetime.combine(session_date - timedelta(days=1), time_of_day(23, 59), tzinfo=tzinfo),
    )

    mismatches: list[str] = []
    field_known_count: dict[str, int] = {}
    verified = 0
    for iid in mature_instrument_ids:
        today = today_by_symbol.get(iid, ())
        before = tuple(c for c in today if c.ts_open < checkpoint_instant)
        at_checkpoint = next((c for c in today if c.ts_open == checkpoint_instant), None)
        if not before or at_checkpoint is None:
            continue  # no real checkpoint-boundary candle to verify against for this instrument today

        rel_volume_sessions = _group_by_session_date(rel_volume_by_symbol.get(iid, ()))
        historical_volumes = historical_cumulative_volumes_through_checkpoint(
            checkpoint_time=checkpoint_instant.time(), prior_sessions_m5=rel_volume_sessions,
            lookback_sessions=REL_VOLUME_LOOKBACK_SESSIONS,
        )
        common = dict(
            instrument_id=iid, session_date=session_date, checkpoint=checkpoint,
            checkpoint_instant=checkpoint_instant, daily_bars=daily_bars_by_symbol.get(iid, ()),
            historical_checkpoint_volumes=historical_volumes, regime_row=regime_row,
        )
        live_row = assemble_candidate_row(
            today_m5_candles=before, checkpoint_reference_price=at_checkpoint.open, **common,
        )
        real_row = assemble_candidate_row(
            today_m5_candles=(*before, at_checkpoint), checkpoint_reference_price=None, **common,
        )
        verified += 1
        for name, value in real_row.items():
            if name in ("session_date", "checkpoint_ist"):
                continue
            if value is not None:
                field_known_count[name] = field_known_count.get(name, 0) + 1
        if live_row != real_row:
            diff_fields = sorted(k for k in live_row if live_row[k] != real_row.get(k))
            mismatches.append(f"{checkpoint}/{iid}: boundary mismatch on {diff_fields}")

    if verified == 0:
        outcome = HardInvariantOutcome(
            "CHECKPOINT_BOUNDARY_REGRESSION", False,
            f"{checkpoint}: no mature instrument had a real checkpoint-boundary candle to verify against",
        )
        return outcome, field_known_count, verified
    if mismatches:
        outcome = HardInvariantOutcome("CHECKPOINT_BOUNDARY_REGRESSION", False, "; ".join(mismatches))
        return outcome, field_known_count, verified
    outcome = HardInvariantOutcome(
        "CHECKPOINT_BOUNDARY_REGRESSION", True,
        f"{checkpoint}: {verified} instruments -- live substitution byte-identical to real boundary candle",
    )
    return outcome, field_known_count, verified


def run_em5_production_canary(
    *,
    market_port: EmrMarketDataPort,
    universe: str,
    session_date: date,
    calendar_context_session_type: SessionType,
    config_dir: Path,
    model_version: str,
    session_open_time: time_of_day,
    tzinfo: tzinfo_type,
    checkpoints: tuple[str, ...] = CANDIDATE_CHECKPOINTS_IST,
    families_thresholds: tuple[tuple[str, int], ...] = FAMILIES_THRESHOLDS,
    max_staleness_minutes: float = 30.0,
    completeness_floor: float = CANARY_COMPLETENESS_FLOOR,
    max_regression_percentage_points: float = MAX_COMPLETENESS_REGRESSION_PERCENTAGE_POINTS,
) -> CanaryGateResult:
    """Runs the EM-5 fail-fast operational gate (contract Section 14)
    against one already-elapsed real historical session. Refuses to
    proceed to full-universe live scanning on any numeric-floor miss or
    hard-invariant failure, naming exactly which check failed.

    Zero Kite provider calls: `session_date` must be a real, already-
    ingested past session (today's or an earlier one, at least through the
    last checkpoint being canaried) -- this is a canary over ATHENA's own
    persisted data, not a live rehearsal.

    Each of the two required determinism runs uses its own throwaway EM-5
    ledger (a fresh temp SQLite file each) so canary runs never touch, or
    duplicate rows in, the production `db/emr.db`.
    """

    failure_reasons: list[str] = []
    hard_invariants: list[HardInvariantOutcome] = []

    artifact_check = _check_frozen_artifact_integrity(
        config_dir=config_dir, model_version=model_version, families_thresholds=families_thresholds,
    )
    hard_invariants.append(artifact_check)
    if not artifact_check.passed:
        failure_reasons.append(artifact_check.name)
        return CanaryGateResult(
            passed=False, session_date=session_date, checkpoints=checkpoints, mature_instrument_ids=(),
            completeness=(), hard_invariants=tuple(hard_invariants), failure_reasons=tuple(failure_reasons),
        )

    universe_ids = tuple(market_port.resolved_universe(universe))
    mature_ids = select_mature_history_instruments(
        market_port=market_port, universe_ids=universe_ids, session_date=session_date, tzinfo=tzinfo,
    )
    if not mature_ids:
        no_mature = HardInvariantOutcome(
            "MATURE_HISTORY_UNIVERSE_NONEMPTY", False,
            f"0 of {len(universe_ids)} universe instruments meet the >= {MATURE_HISTORY_MINIMUM_SESSIONS}-session "
            f"maturity bar as of {session_date.isoformat()}",
        )
        hard_invariants.append(no_mature)
        failure_reasons.append(no_mature.name)
        return CanaryGateResult(
            passed=False, session_date=session_date, checkpoints=checkpoints, mature_instrument_ids=(),
            completeness=(), hard_invariants=tuple(hard_invariants), failure_reasons=tuple(failure_reasons),
        )
    hard_invariants.append(HardInvariantOutcome(
        "MATURE_HISTORY_UNIVERSE_NONEMPTY", True, f"{len(mature_ids)} of {len(universe_ids)} instruments mature",
    ))

    maturity_start = session_date - timedelta(days=_MATURITY_LOOKBACK_CALENDAR_DAYS)
    daily_bars_by_symbol = {
        iid: tuple(sorted((_daily_bar_from_d1_candle(c) for c in candles), key=lambda b: b.session_date))
        for iid, candles in market_port.candles_for_instruments(
            mature_ids, Timeframe.D1,
            datetime.combine(maturity_start, time_of_day(0, 0), tzinfo=tzinfo),
            datetime.combine(session_date - timedelta(days=1), time_of_day(23, 59), tzinfo=tzinfo),
        ).items()
    }

    collector = _real_candle_checkpoint_price_collector(market_port)
    regime_lookup = build_canonical_regime_lookup(market_port=market_port, config_dir=config_dir, tzinfo=tzinfo)
    #: Session-level -- RegimeEngine has no intraday concept, so every
    #: checkpoint this session shares the same real assessment.
    regime_assessment = regime_lookup(session_date)

    checkpoint_prices_by_checkpoint: dict[str, dict[str, CheckpointReferencePrice]] = {}
    quote_request_counts: dict[str, int] = {}
    candidates_a_by_checkpoint: dict[str, list[dict]] = {}
    candidates_b_by_checkpoint: dict[str, list[dict]] = {}
    boundary_checks: list[HardInvariantOutcome] = []
    field_known_count_by_checkpoint: dict[str, dict[str, int]] = {}
    field_verified_count_by_checkpoint: dict[str, int] = {}
    checkpoint_price_coverage: dict[str, dict[str, int]] = {}

    with tempfile.TemporaryDirectory(prefix="em5-canary-") as tmp:
        for checkpoint in checkpoints:
            checkpoint_instant = datetime.combine(
                session_date, time_of_day.fromisoformat(checkpoint), tzinfo=tzinfo,
            )
            scan_config = ScanCycleConfig(
                universe=universe, session_date=session_date, checkpoint=checkpoint,
                checkpoint_instant=checkpoint_instant, session_open_time=session_open_time,
                model_version=model_version, config_dir=config_dir, max_staleness_minutes=max_staleness_minutes,
                max_checkpoint_price_delay_seconds=0.0, families_thresholds=families_thresholds,
            )

            run_results = []
            for replica in ("a", "b"):
                repo = EmrRepository(Path(tmp) / f"emr-{checkpoint.replace(':', '')}-{replica}.db")
                repo.initialize()
                result = run_scan_cycle(
                    config=scan_config, market_port=market_port, emr_repo=repo,
                    calendar_context_session_type=calendar_context_session_type,
                    collect_checkpoint_prices=collector, regime_lookup=regime_lookup,
                    now=lambda ci=checkpoint_instant: ci,
                )
                rows = [r for r in repo.list_candidates(run_id=result.run_id) if r["instrument_id"] in mature_ids]
                run_results.append((result, rows))
                repo.close()

            (result_a, rows_a), (result_b, rows_b) = run_results
            candidates_a_by_checkpoint[checkpoint] = rows_a
            candidates_b_by_checkpoint[checkpoint] = rows_b
            quote_request_counts[checkpoint] = result_a.quote_request_count + result_b.quote_request_count
            qualified_prices = collector(instrument_ids=mature_ids, checkpoint_instant=checkpoint_instant)[0]
            checkpoint_prices_by_checkpoint[checkpoint] = qualified_prices
            checkpoint_price_coverage[checkpoint] = {
                "universe": len(mature_ids), "qualified": len(qualified_prices),
            }

            boundary_outcome, field_known, field_verified = _check_checkpoint_boundary_matches_real_candle(
                market_port=market_port, mature_instrument_ids=mature_ids, session_date=session_date,
                session_open_time=session_open_time, checkpoint=checkpoint, checkpoint_instant=checkpoint_instant,
                tzinfo=tzinfo, daily_bars_by_symbol=daily_bars_by_symbol, regime_row=regime_assessment,
            )
            boundary_checks.append(boundary_outcome)
            field_known_count_by_checkpoint[checkpoint] = field_known
            field_verified_count_by_checkpoint[checkpoint] = field_verified

    for check in (
        _check_hard_eligibility_inputs_well_formed(checkpoint_prices_by_checkpoint),
        _check_no_systemic_stale_data(candidates_a_by_checkpoint),
        _check_zero_provider_network_calls(quote_request_counts),
        _check_replay_determinism(candidates_a_by_checkpoint, candidates_b_by_checkpoint),
    ):
        hard_invariants.append(check)

    hard_invariants.extend(boundary_checks)
    failure_reasons.extend(h.name for h in hard_invariants if not h.passed and h.name not in failure_reasons)

    completeness: list[CheckpointCompleteness] = []
    for checkpoint in checkpoints:
        rows = candidates_a_by_checkpoint.get(checkpoint, [])
        total = len(rows)
        known = sum(1 for r in rows if r["evidence_completeness_known"] == r["evidence_completeness_total"])
        rate = (known / total) if total else 0.0
        baseline = MATURE_HISTORY_BASELINE_KNOWN_RATE.get(checkpoint)
        regression_pp = ((baseline - rate) * 100.0) if baseline is not None else None
        passes_floor = total > 0 and rate >= completeness_floor
        passes_regression = (
            baseline is not None and regression_pp is not None
            and regression_pp <= max_regression_percentage_points
        )
        completeness.append(CheckpointCompleteness(
            checkpoint=checkpoint, mature_row_count=total, all_fields_known_count=known,
            all_fields_known_rate=rate, baseline_rate=baseline, regression_percentage_points=regression_pp,
            passes_floor=passes_floor, passes_regression_bound=passes_regression,
        ))
        if not passes_floor:
            failure_reasons.append(f"COMPLETENESS_FLOOR[{checkpoint}]")
        if not passes_regression:
            failure_reasons.append(f"COMPLETENESS_REGRESSION[{checkpoint}]")

    passed = not failure_reasons
    return CanaryGateResult(
        passed=passed, session_date=session_date, checkpoints=checkpoints, mature_instrument_ids=mature_ids,
        completeness=tuple(completeness), hard_invariants=tuple(hard_invariants),
        failure_reasons=tuple(failure_reasons), regime_assessment=dict(regime_assessment),
        field_known_count=field_known_count_by_checkpoint, field_verified_count=field_verified_count_by_checkpoint,
        checkpoint_price_coverage=checkpoint_price_coverage,
    )
