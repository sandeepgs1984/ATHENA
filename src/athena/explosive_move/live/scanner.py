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


def _fingerprint(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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

    run_id_fingerprint = _fingerprint({
        "session_date": config.session_date.isoformat(), "checkpoint": config.checkpoint,
        "universe": config.universe, "model_version": config.model_version,
    })
    run_id = f"em5-scan-{run_id_fingerprint}"
    emr_repo.save_scan_run({
        "run_id": run_id, "session_date": config.session_date.isoformat(), "checkpoint": config.checkpoint,
        "frozen_model_version": config.model_version, "status": "RUNNING", "started_ts": started_ts.isoformat(),
    })

    if not session_is_scannable(calendar_context_session_type):
        emr_repo.save_scan_run({
            "run_id": run_id, "session_date": config.session_date.isoformat(), "checkpoint": config.checkpoint,
            "frozen_model_version": config.model_version, "status": "SKIPPED_SESSION_TYPE",
            "started_ts": started_ts.isoformat(), "finished_ts": (now or datetime.now)().isoformat(),
            "eligible_count": 0, "ineligible_count": 0,
        })
        return ScanCycleResult(run_id, "SKIPPED_SESSION_TYPE", 0, 0, 0, 0, 0)

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
                "raw_logistic_estimate": info["scored"].raw_logit, "deterministic_score": info["deterministic"].score,
                "calibrated_probability": info["scored"].calibrated_probability,
                "probability_language": info["probability_language"],
                "em4b_model_version": config.model_version, "em4d_calibration_version": config.model_version,
                "checkpoint_price": checkpoint_price.last_price if checkpoint_price else None,
                "checkpoint_price_semantic": checkpoint_price.reference_price_semantic if checkpoint_price else None,
                "checkpoint_snapshot_timestamp": snapshot_ts.isoformat() if snapshot_ts else None,
                "checkpoint_last_trade_time": last_trade_ts.isoformat() if last_trade_ts else None,
                "checkpoint_price_latency_seconds": checkpoint_price.latency_seconds if checkpoint_price else None,
                "evidence_timestamp": config.checkpoint_instant.isoformat(),
                "evidence_completeness_known": info["known_count"], "evidence_completeness_total": info["total_count"],
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

    emr_repo.save_candidates(all_candidates)
    emr_repo.save_transitions(all_transitions)

    finished_ts = (now or datetime.now)()
    total_duration_ms = (time.monotonic() - started_monotonic) * 1000
    emr_repo.save_scan_run({
        "run_id": run_id, "session_date": config.session_date.isoformat(), "checkpoint": config.checkpoint,
        "frozen_model_version": config.model_version, "status": "COMPLETE",
        "started_ts": started_ts.isoformat(), "finished_ts": finished_ts.isoformat(),
        "eligible_count": eligible_count, "ineligible_count": ineligible_count,
        "evidence_generation_duration_ms": evidence_generation_duration_ms,
        "quote_capture_duration_ms": quote_capture_duration_ms,
        "inference_duration_ms": inference_duration_ms, "total_duration_ms": total_duration_ms,
        "quote_request_count": quote_request_count, "db_read_latency_ms": db_read_latency_ms,
    })

    return ScanCycleResult(
        run_id=run_id, status="COMPLETE", eligible_count=eligible_count, ineligible_count=ineligible_count,
        candidates_persisted=len(all_candidates), transitions_persisted=len(all_transitions),
        quote_request_count=quote_request_count,
    )


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
