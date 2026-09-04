"""EM-5 scan orchestration -- the top-level pipeline for one scan cycle:
one (session_date, checkpoint) across the whole eligible universe,
scored against all 18 (family, threshold) combinations, using every
already-tested EM-5 component. This is the one place all of them are
wired together; every individual step (eligibility, evidence assembly,
frozen inference, explanation, ranking, the state machine, persistence)
is already independently tested against its own pure inputs.

Deterministic by construction (contract Section 11): given identical
canonical market data, checkpoint, frozen-model version, and persisted
prior-checkpoint history, re-running produces byte-identical evidence,
scores, states, and ranking -- every step here is a pure function of
its inputs plus exactly one live call (the checkpoint-price collector,
Section 2's one narrow authorized exception) and one set of DB reads
(Section 10's bulk port). No `datetime.now()`/`random` inside any
computation -- the caller supplies `now`/`session_date`/`checkpoint_instant`
explicitly.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as time_of_day
from decimal import Decimal
from pathlib import Path

from athena.domain.enums import SessionType, Timeframe
from athena.domain.market import Candle
from athena.explosive_move.contracts import EVENT_THRESHOLDS_PERCENT, EventFamily
from athena.explosive_move.event_labels import ForwardLabelOutcome, evaluate_touch_label
from athena.explosive_move.evidence_values import DailyBar
from athena.explosive_move.live.deterministic_scoring import DeterministicRuleSet, load_deterministic_rules
from athena.explosive_move.live.eligibility import (
    EligibilityResult,
    evaluate_candidate_eligibility,
    session_is_scannable,
)
from athena.explosive_move.live.evidence_assembly import (
    assemble_candidate_row,
    historical_cumulative_volumes_through_checkpoint,
)
from athena.explosive_move.live.explanation import compute_logit_contributions
from athena.explosive_move.live.frozen_inference import FrozenModel, load_frozen_model
from athena.explosive_move.live.market_data_port import EmrMarketDataPort
from athena.explosive_move.live.ranking import rank_candidates
from athena.explosive_move.live.scan_lock import EmrScanLock, default_emr_scan_lock_path
from athena.explosive_move.live.state_machine import (
    DEFAULT_RANK_CUTOFFS,
    RankCutoffs,
    ScannerState,
    determine_next_state,
)
from athena.explosive_move.store.repository import EmrRepository

#: All 18 approved (family, threshold) combinations -- re-derived from
#: the same frozen `contracts` constants `em4b_logistic_fitting.py`
#: uses, never imported from it (that module transitively imports
#: numpy/scikit-learn; Section 12 forbids that anywhere in the live path).
FAMILIES_THRESHOLDS: tuple[tuple[str, int], ...] = tuple(
    (family.value, threshold) for family in EventFamily for threshold in EVENT_THRESHOLDS_PERCENT
)

TOP_K_CONTRIBUTIONS = 5
REL_VOLUME_LOOKBACK_SESSIONS = 20
#: Wide enough to reliably find 50+ prior trading sessions (Blocker 5's
#: mature-history rule) even across weekends/holidays.
DAILY_BAR_LOOKBACK_CALENDAR_DAYS = 120
#: Wide enough for 20 prior trading sessions' comparable-time-of-day M5 data.
REL_VOLUME_LOOKBACK_CALENDAR_DAYS = 40


def _daily_bar_from_d1_candle(candle: Candle) -> DailyBar:
    return DailyBar(
        session_date=candle.ts_open.date(), open=candle.open, high=candle.high,
        low=candle.low, close=candle.close, volume=candle.volume,
    )


def _group_by_session_date(candles: tuple[Candle, ...]) -> dict[date, tuple[Candle, ...]]:
    grouped: dict[date, list[Candle]] = {}
    for c in candles:
        grouped.setdefault(c.ts_open.date(), []).append(c)
    return {d: tuple(sorted(cs, key=lambda c: c.ts_open)) for d, cs in grouped.items()}


def _already_occurred(
    *, family: str, threshold_percent: int, reference_price: Decimal | None,
    checkpoint_instant: datetime, session_candles_so_far: tuple[Candle, ...],
) -> bool:
    """CLOSE has no ALREADY_OCCURRED concept (event_labels.evaluate_close_label's
    own docstring: the qualifying close is only known at session close
    itself). TOUCH/OPEN_TO_HIGH share identical touch mechanics, differing
    only in which reference price the caller supplies -- both checked here
    via the frozen `evaluate_touch_label`, unmodified."""

    if family == EventFamily.CLOSE.value or reference_price is None:
        return False
    result = evaluate_touch_label(
        reference_price=reference_price, threshold_percent=threshold_percent,
        checkpoint_instant=checkpoint_instant, session_candles=session_candles_so_far,
    )
    return result.outcome is ForwardLabelOutcome.ALREADY_OCCURRED


@dataclass(frozen=True, slots=True)
class ScanCycleConfig:
    universe: str
    session_date: date
    checkpoint: str
    checkpoint_instant: datetime
    session_open_time: time_of_day
    model_version: str
    config_dir: Path
    max_staleness_minutes: float
    max_checkpoint_price_delay_seconds: float
    rank_cutoffs: RankCutoffs = DEFAULT_RANK_CUTOFFS
    families_thresholds: tuple[tuple[str, int], ...] = FAMILIES_THRESHOLDS
    top_k_contributions: int = TOP_K_CONTRIBUTIONS


@dataclass(frozen=True, slots=True)
class ScanCycleResult:
    run_id: str
    status: str
    eligible_count: int
    ineligible_count: int
    candidates_persisted: int
    transitions_persisted: int
    quote_request_count: int


class EmrScanAlreadyRunningError(RuntimeError):
    """EM-7A.1: raised when `run_scan_cycle` is invoked for a
    deterministic `run_id` whose persisted `emr_scan_runs` row is already
    `RUNNING`. Conservative by design (Section 10 of the owner's EM-7A.1
    authorization): an ambiguous/active RUNNING row is never assumed
    stale and never silently overwritten -- full stale-run recovery
    policy belongs to a future EM-7B/EM-7C operational milestone, not
    guessed at here."""


def _fingerprint(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_run_id(*, session_date: date, checkpoint: str, universe: str, model_version: str) -> str:
    """EM-7B: the exact deterministic `run_id` formula `run_scan_cycle`
    computes internally, extracted as a public, reusable function so a
    caller (the EM-7B worker) can look up `emr_repo.get_scan_run(...)`
    for a not-yet-attempted checkpoint without duplicating the formula
    (which would risk silent drift from this module's own definition).
    Purely additive -- `run_scan_cycle` itself now calls this instead of
    inlining the same four lines; the produced value is byte-identical to
    before, verified by the existing deterministic-run-id tests."""
    fingerprint = _fingerprint({
        "session_date": session_date.isoformat(), "checkpoint": checkpoint,
        "universe": universe, "model_version": model_version,
    })
    return f"em5-scan-{fingerprint}"


def _reconstruct_completed_result(emr_repo: EmrRepository, existing: dict, run_id: str) -> ScanCycleResult:
    """EM-7A.1 Case A: an already-`COMPLETE` run for this exact
    deterministic identity is authoritative. Reconstructed entirely from
    already-persisted state -- no recomputation, no provider call
    (in particular, no second checkpoint-reference-price request)."""
    candidates_persisted = len(emr_repo.list_candidates(run_id=run_id))
    transitions_persisted = len(emr_repo.list_transitions_for_run(run_id=run_id))
    return ScanCycleResult(
        run_id=run_id, status="COMPLETE",
        eligible_count=existing.get("eligible_count") or 0,
        ineligible_count=existing.get("ineligible_count") or 0,
        candidates_persisted=candidates_persisted, transitions_persisted=transitions_persisted,
        quote_request_count=existing.get("quote_request_count") or 0,
    )


def run_scan_cycle(
    *,
    config: ScanCycleConfig,
    market_port: EmrMarketDataPort,
    emr_repo: EmrRepository,
    calendar_context_session_type: SessionType,
    collect_checkpoint_prices: Callable[..., tuple[dict, tuple[str, ...], int]],
    regime_lookup: Callable[[date], dict | None],
    now: Callable[[], datetime] | None = None,
) -> ScanCycleResult:
    """One full scan cycle. `collect_checkpoint_prices` matches
    `checkpoint_reference_price.collect_checkpoint_reference_prices`'s
    signature (injectable for tests/replay); production callers pass
    that function directly.

    `regime_lookup` is a REQUIRED keyword argument (EM-7A, ADR-014
    Section 20) -- there is deliberately no default and no silent
    fallback. The already-accepted Section 14 production canary already
    wires the real `regime_source.build_canonical_regime_lookup`; any
    future live/operational caller MUST do the same, or regime features
    silently collapse to all-UNKNOWN (the exact defect a prior production
    canary run found and an Owner/Chief Architect ruling on 2026-08-28
    already required be fixed at every live call site). Tests/replay that
    deliberately want UNKNOWN regime remain free to pass
    `lambda _d: None` explicitly -- that stays a valid, honest choice; it
    is the *silent, unrequested* default this signature removes, not the
    UNKNOWN outcome itself."""

    started_monotonic = time.monotonic()
    started_ts = (now or datetime.now)()

    run_id = compute_run_id(
        session_date=config.session_date, checkpoint=config.checkpoint,
        universe=config.universe, model_version=config.model_version,
    )

    # EM-7A.1 Sections 8-10 / EM-7A.2 Section 3: same deterministic
    # run_id, three distinct existing-lifecycle cases -- checked BEFORE
    # evaluating session eligibility, BEFORE writing a fresh RUNNING row,
    # and BEFORE any provider call. Checking these first means an
    # already-COMPLETE run is always authoritative for this run_id
    # (never re-invokes the checkpoint-quote collector, regardless of
    # what session type the caller supplies now), an already-RUNNING row
    # is never reinterpreted as skipped just because the caller now
    # supplies a non-scannable session type, and an existing FAILED (or
    # legacy pre-EM-7A.2 SKIPPED_SESSION_TYPE, see below) row is left
    # untouched unless the session is genuinely scannable.
    existing = emr_repo.get_scan_run(run_id)
    if existing is not None:
        if existing["status"] == "COMPLETE":
            return _reconstruct_completed_result(emr_repo, existing, run_id)
        if existing["status"] == "RUNNING":
            raise EmrScanAlreadyRunningError(
                f"EMR scan run_id {run_id!r} is already RUNNING -- refusing a second, "
                "ambiguous concurrent execution for the same deterministic identity"
            )
        # else: FAILED, or a legacy pre-EM-7A.2 persisted
        # SKIPPED_SESSION_TYPE row (EM-7A.2 no longer writes this status
        # to the database -- see below -- but a database created before
        # EM-7A.2 may still contain one; treated identically to FAILED
        # here, purely for backward-compatible same-run_id lookup, never
        # written again by this function) -- fall through to the
        # eligibility check, which decides whether a fresh execution
        # attempt under the same run_id is appropriate.

    # EM-7A.2: session-scannability is a PRE-EXECUTION eligibility
    # question -- "this scan was never eligible to start" -- not a
    # scan-run lifecycle outcome. A non-scannable session must never be
    # represented as a RUNNING scan that executed and terminated in a
    # fourth persisted state. Checked here, after the existing-run
    # dispatch above (so it can never override an already-COMPLETE
    # result, reinterpret an already-RUNNING row, or mutate an existing
    # FAILED row) and before any RUNNING write, provider call, or
    # computation -- a true preflight rejection. The in-memory
    # `ScanCycleResult.status == "SKIPPED_SESSION_TYPE"` outcome is
    # retained (smallest change compatible with existing callers/types);
    # only its persistence to `emr_scan_runs` is removed.
    if not session_is_scannable(calendar_context_session_type):
        return ScanCycleResult(run_id, "SKIPPED_SESSION_TYPE", 0, 0, 0, 0, 0)

    emr_repo.save_scan_run({
        "run_id": run_id, "session_date": config.session_date.isoformat(), "checkpoint": config.checkpoint,
        "frozen_model_version": config.model_version, "status": "RUNNING", "started_ts": started_ts.isoformat(),
    })

    try:
        universe_ids = tuple(market_port.resolved_universe(config.universe))

        db_read_start = time.monotonic()
        daily_start = config.session_date - timedelta(days=DAILY_BAR_LOOKBACK_CALENDAR_DAYS)
        daily_end = config.session_date - timedelta(days=1)
        daily_candles_by_symbol = market_port.candles_for_instruments(
            universe_ids, Timeframe.D1,
            datetime.combine(daily_start, time_of_day(0, 0), tzinfo=config.checkpoint_instant.tzinfo),
            datetime.combine(daily_end, time_of_day(23, 59), tzinfo=config.checkpoint_instant.tzinfo),
        )
        daily_bars_by_symbol = {
            iid: tuple(sorted((_daily_bar_from_d1_candle(c) for c in candles), key=lambda b: b.session_date))
            for iid, candles in daily_candles_by_symbol.items()
        }

        session_start_instant = datetime.combine(
            config.session_date, config.session_open_time, tzinfo=config.checkpoint_instant.tzinfo,
        )
        today_candles_by_symbol = market_port.candles_for_instruments(
            universe_ids, Timeframe.M5, session_start_instant, config.checkpoint_instant,
        )

        rel_volume_start = config.session_date - timedelta(days=REL_VOLUME_LOOKBACK_CALENDAR_DAYS)
        rel_volume_end = config.session_date - timedelta(days=1)
        rel_volume_candles_by_symbol = market_port.candles_for_instruments(
            universe_ids, Timeframe.M5,
            datetime.combine(rel_volume_start, time_of_day(0, 0), tzinfo=config.checkpoint_instant.tzinfo),
            datetime.combine(rel_volume_end, time_of_day(23, 59), tzinfo=config.checkpoint_instant.tzinfo),
        )
        db_read_latency_ms = (time.monotonic() - db_read_start) * 1000

        quote_start = time.monotonic()
        checkpoint_prices, _no_price, quote_request_count = collect_checkpoint_prices(
            instrument_ids=universe_ids, checkpoint_instant=config.checkpoint_instant,
            max_delay_seconds=config.max_checkpoint_price_delay_seconds,
        )
        quote_capture_duration_ms = (time.monotonic() - quote_start) * 1000

        model_cache: dict[tuple[str, int], FrozenModel] = {
            (family, threshold): load_frozen_model(
                config_dir=config.config_dir, version=config.model_version, family=family, threshold_percent=threshold,
            )
            for family, threshold in config.families_thresholds
        }
        deterministic_rules: DeterministicRuleSet = load_deterministic_rules(
            config_dir=config.config_dir, version=config.model_version,
        )

        evidence_start = time.monotonic()
        candidate_rows: dict[str, dict] = {}
        base_eligibility: dict[str, EligibilityResult] = {}
        most_recent_ts: dict[str, datetime | None] = {}
        for iid in universe_ids:
            today = today_candles_by_symbol.get(iid, ())
            most_recent_ts[iid] = max((c.ts_open for c in today), default=None)
            if not today:
                continue  # no live data at all today -- cannot assemble any evidence
            base_eligibility[iid] = evaluate_candidate_eligibility(
                in_universe=True, most_recent_candle_ts=most_recent_ts[iid], as_of=config.checkpoint_instant,
                max_staleness_minutes=config.max_staleness_minutes,
                has_checkpoint_reference_price=iid in checkpoint_prices,
            )
            rel_volume_sessions = _group_by_session_date(rel_volume_candles_by_symbol.get(iid, ()))
            historical_volumes = historical_cumulative_volumes_through_checkpoint(
                checkpoint_time=config.checkpoint_instant.time(), prior_sessions_m5=rel_volume_sessions,
                lookback_sessions=REL_VOLUME_LOOKBACK_SESSIONS,
            )
            checkpoint_price = checkpoint_prices.get(iid)
            live_price = checkpoint_price.last_price if checkpoint_price else None
            candidate_rows[iid] = assemble_candidate_row(
                instrument_id=iid, session_date=config.session_date, checkpoint=config.checkpoint,
                checkpoint_instant=config.checkpoint_instant, daily_bars=daily_bars_by_symbol.get(iid, ()),
                today_m5_candles=today, checkpoint_reference_price=live_price,
                historical_checkpoint_volumes=historical_volumes, regime_row=regime_lookup(config.session_date),
            )
        evidence_generation_duration_ms = (time.monotonic() - evidence_start) * 1000

        inference_start = time.monotonic()
        eligible_count = sum(1 for e in base_eligibility.values() if e.hard_eligible)
        ineligible_count = len(universe_ids) - eligible_count

        all_candidates: list[dict] = []
        all_transitions: list[dict] = []
        prior_daily_bars_by_symbol = daily_bars_by_symbol

        for family, threshold in config.families_thresholds:
            model = model_cache[(family, threshold)]
            scores_for_ranking: dict[str, float] = {}
            per_symbol: dict[str, dict] = {}

            for iid in candidate_rows:
                row = candidate_rows[iid]
                eligibility = base_eligibility[iid]
                prior_bars = prior_daily_bars_by_symbol.get(iid, ())
                today_candles = today_candles_by_symbol.get(iid, ())
                if family == EventFamily.OPEN_TO_HIGH.value:
                    reference_price = today_candles[0].open if today_candles else None
                else:
                    reference_price = prior_bars[-1].close if prior_bars else None
                already_occurred = _already_occurred(
                    family=family, threshold_percent=threshold, reference_price=reference_price,
                    checkpoint_instant=config.checkpoint_instant, session_candles_so_far=today_candles,
                )

                scored = model.score(row, checkpoint=config.checkpoint)
                contributions = compute_logit_contributions(
                    row, feature_names=model.feature_names, coefficients=model.coefficients,
                    intercept=model.intercept, preprocessing=model.preprocessing,
                )
                deterministic = deterministic_rules.score(
                    family=family, threshold_percent=threshold, checkpoint=config.checkpoint, evidence=row,
                )
                probability_language = (
                    "calibrated_probability" if scored.calibration_level != "UNCALIBRATED_INSUFFICIENT_SUPPORT"
                    else "raw_estimate"
                )
                non_key_fields = {k: v for k, v in row.items() if k not in ("session_date", "checkpoint_ist")}
                known_count = sum(1 for v in non_key_fields.values() if v is not None)
                total_count = len(non_key_fields)

                per_symbol[iid] = {
                    "eligibility": eligibility, "already_occurred": already_occurred,
                    "scored": scored, "contributions": contributions, "deterministic": deterministic,
                    "probability_language": probability_language,
                    "known_count": known_count, "total_count": total_count,
                }
                if eligibility.hard_eligible and not already_occurred:
                    scores_for_ranking[iid] = scored.calibrated_probability

            ranks = rank_candidates(scores_for_ranking)

            for iid, info in per_symbol.items():
                history = emr_repo.list_candidates_for_symbol(
                    instrument_id=iid, family=family, threshold_percent=threshold,
                    session_date=config.session_date.isoformat(),
                )
                prior_state = ScannerState(history[-1]["state"]) if history else ScannerState.INACTIVE
                prior_rank = history[-1]["rank"] if history else None
                ever_reached = ScannerState.INACTIVE
                for h in history:
                    if _tier_rank(ScannerState(h["state"])) > _tier_rank(ever_reached):
                        ever_reached = ScannerState(h["state"])

                eligibility = info["eligibility"]
                ineligible_reason = eligibility.hard_ineligible_reason
                ineligible_reason_value = ineligible_reason.value if ineligible_reason else None
                transition = determine_next_state(
                    rank=ranks.get(iid),
                    hard_ineligible=not eligibility.hard_eligible, already_occurred=info["already_occurred"],
                    prior_state=prior_state, prior_rank=prior_rank, ever_reached=ever_reached,
                    hard_ineligible_reason=ineligible_reason_value, rank_cutoffs=config.rank_cutoffs,
                )

                checkpoint_price = checkpoint_prices.get(iid)
                snapshot_ts = checkpoint_price.snapshot_timestamp if checkpoint_price else None
                last_trade_ts = checkpoint_price.last_trade_time if checkpoint_price else None
                is_stale = ineligible_reason_value == "STALE_DATA"
                feasibility_reason = (
                    ineligible_reason_value if eligibility.feasibility.value == "PRICE_BAND_IMPOSSIBLE" else None
                )
                candidate = {
                    "run_id": run_id, "instrument_id": iid, "family": family, "threshold_percent": threshold,
                    "checkpoint": config.checkpoint, "session_date": config.session_date.isoformat(),
                    "rank": ranks.get(iid), "raw_logit": info["scored"].raw_logit,
                    "raw_logistic_estimate": info["scored"].raw_logit,
                    "deterministic_score": info["deterministic"].score,
                    "calibrated_probability": info["scored"].calibrated_probability,
                    "probability_language": info["probability_language"],
                    "em4b_model_version": config.model_version, "em4d_calibration_version": config.model_version,
                    "checkpoint_price": checkpoint_price.last_price if checkpoint_price else None,
                    "checkpoint_price_semantic": (
                        checkpoint_price.reference_price_semantic if checkpoint_price else None
                    ),
                    "checkpoint_snapshot_timestamp": snapshot_ts.isoformat() if snapshot_ts else None,
                    "checkpoint_last_trade_time": last_trade_ts.isoformat() if last_trade_ts else None,
                    "checkpoint_price_latency_seconds": (
                        checkpoint_price.latency_seconds if checkpoint_price else None
                    ),
                    "evidence_timestamp": config.checkpoint_instant.isoformat(),
                    "evidence_completeness_known": info["known_count"],
                    "evidence_completeness_total": info["total_count"],
                    "freshness": "STALE" if is_stale else "FRESH",
                    "feasibility": eligibility.feasibility.value, "feasibility_reason": feasibility_reason,
                    "state": transition.to_state.value, "state_reason": transition.reason,
                    "logit_contributions": {"terms": [
                        {"term": c.term, "coefficient": c.coefficient, "transformed_value": c.transformed_value,
                         "contribution": c.contribution, "is_missing_indicator": c.is_missing_indicator}
                        for c in info["contributions"]
                    ]},
                }
                all_candidates.append(candidate)

                if transition.to_state != prior_state:
                    all_transitions.append({
                        "run_id": run_id, "instrument_id": iid, "family": family, "threshold_percent": threshold,
                        "checkpoint": config.checkpoint, "session_date": config.session_date.isoformat(),
                        "sequence_number": len(history) + 1, "from_state": transition.from_state.value,
                        "to_state": transition.to_state.value, "reason": transition.reason,
                    })

        inference_duration_ms = (time.monotonic() - inference_start) * 1000

        finished_ts = (now or datetime.now)()
        total_duration_ms = (time.monotonic() - started_monotonic) * 1000

        # EM-7A.1 Section 2: the ONE atomic transaction -- candidates,
        # transitions, and the terminal COMPLETE status all become
        # durable together, or none of them do. Replaces the prior three
        # independently-committed calls that made a partial durable
        # result possible.
        emr_repo.commit_scan_result(
            run_id=run_id, candidates=all_candidates, transitions=all_transitions,
            run_update={
                "finished_ts": finished_ts.isoformat(),
                "eligible_count": eligible_count, "ineligible_count": ineligible_count,
                "evidence_generation_duration_ms": evidence_generation_duration_ms,
                "quote_capture_duration_ms": quote_capture_duration_ms,
                "inference_duration_ms": inference_duration_ms, "total_duration_ms": total_duration_ms,
                "quote_request_count": quote_request_count, "db_read_latency_ms": db_read_latency_ms,
            },
        )

        return ScanCycleResult(
            run_id=run_id, status="COMPLETE", eligible_count=eligible_count, ineligible_count=ineligible_count,
            candidates_persisted=len(all_candidates), transitions_persisted=len(all_transitions),
            quote_request_count=quote_request_count,
        )
    except Exception as exc:
        # EM-7A.1 Sections 4-5: every run-level exception after RUNNING
        # was established terminates the run as FAILED -- never an
        # orphaned RUNNING row. The original exception (exc) remains the
        # primary, externally-visible failure; if the FAILED write itself
        # also raises, that second exception is chained as `__cause__`
        # (diagnostic evidence only) rather than replacing exc as the
        # apparent root cause.
        failure_finished_ts = (now or datetime.now)().isoformat()
        try:
            emr_repo.mark_scan_failed(
                run_id=run_id, failure_type=type(exc).__name__,
                failure_reason=str(exc), finished_ts=failure_finished_ts,
            )
        except Exception as mark_exc:
            raise exc from mark_exc
        raise


def run_scan_cycle_with_lock(
    *, lock: EmrScanLock | None = None, **kwargs: object,
) -> ScanCycleResult:
    """EM-7A.1 Section 17: the one safe, hardened entrypoint a future
    EM-7B worker must use -- acquires the EMR-owned scan lock, runs
    `run_scan_cycle(**kwargs)`, and always releases, so a future worker
    cannot forget locking. `run_scan_cycle` itself remains lock-free
    (pure replay/test/canary usage stays unaffected -- nothing about
    single-threaded test/research invocation needs cross-process
    exclusion). `lock` defaults to `EmrScanLock(default_emr_scan_lock_path())`
    if not supplied; tests may inject their own `EmrScanLock` pointed at
    a temporary path. Raises `EmrScanLockBusyError` if another scan
    execution already holds the lock -- never silently proceeds."""
    active_lock = lock or EmrScanLock(default_emr_scan_lock_path())
    with active_lock:
        return run_scan_cycle(**kwargs)  # type: ignore[arg-type]


#: Ordinal tier for computing `ever_reached` from persisted history --
#: mirrors `state_machine._TIER_LEVEL` (TARGET_REACHED/INVALIDATED are
#: terminal, ranked above every progression tier since reaching them
#: once this session is the highest fact there is).
_EVER_REACHED_TIER: dict[ScannerState, int] = {
    ScannerState.INACTIVE: 0, ScannerState.FADING: 0, ScannerState.WATCH: 1, ScannerState.DEVELOPING: 1,
    ScannerState.CONFIRMED: 2, ScannerState.HIGH_CONVICTION: 3,
    ScannerState.TARGET_REACHED: 4, ScannerState.INVALIDATED: 4,
}


def _tier_rank(state: ScannerState) -> int:
    return _EVER_REACHED_TIER[state]
