"""ID-7F1: Entry Actionability historical replay adapter (Mode A only).

Read-only, research-only. Reuses ID-6B.1's own `ReadOnlyStore` (SQLite
URI `mode=ro` + `PRAGMA query_only=ON`) and its exact bounded-candle-read
pattern, but replays the PERSISTED `entry_qualifications` population
directly (every WATCH/TRADE row), not a fixed checkpoint grid over
`decisions` -- ID-7A already gives replay its own authoritative, exact
identity source (unlike ID-6E, which predates EntryQualification
persistence and had to derive checkpoints from raw Decision candidates).

Calls the real, unmodified `EntryActionabilityEngine.evaluate()` (ID-7C)
for every observation with `policy=None`. No methodology is re-derived
here, `save_entry_actionability` is never called, and no schema/
repository/workflow object is touched or changed.

This is Mode A ONLY from the frozen ID-7F0 contract
(`docs/research/ID-7F0-ENTRY-ACTIONABILITY-REPLAY-SHADOW-VALIDATION-CONTRACT.md`):
settled historical MARKET-TIME-BOUNDED reconstruction. Conclusions
describe how the frozen V0 methodology behaves at historical checkpoints
using the data representation this replay reads now -- never a claim
about what ATHENA knew live at that historical instant (no bitemporal
knowledge-time replay is supported or claimed). Mode B (production
shadow equivalence against real persisted `EntryActionability` rows) is
explicitly NOT implemented here -- ID-7F0 §36 found the live database
has neither the schema-v18 migration nor any real `EntryActionability`
rows yet.

Failure classification (ID-7F0 §35, frozen): a Decision missing or
disagreeing with its bound EntryQualification on identity fields is
`UPSTREAM_BINDING_DEFECT`; a `ValueError` raised while constructing
`EntryActionabilityMarketEvidence` or while calling
`EntryActionabilityEngine.evaluate()` (given an already-validated
binding) is `PIT_EVIDENCE_DEFECT` -- ID-7F0's own frozen taxonomy has no
separate "replay implementation defect" category, and a bug in this
module's own reconstruction is, definitionally, a defect in the
point-in-time evidence it produced, so it is deliberately mapped there
rather than inventing a new category (documented here, not casually
expanded); a duplicate persisted EQ identity is `PERSISTENCE_DEFECT`; two
deterministic re-evaluations of the identical inputs producing different
results is `REPLAY_EQUIVALENCE_DEFECT`. Legitimate missing M5/VWAP/OR15
evidence is never a defect of any kind -- it is ordinary `DATA_AVAILABILITY`,
tracked purely descriptively.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.id6b1_entry_qualification_baseline import ReadOnlyStore
from athena.data.store import serialization as ser
from athena.domain.decision import Decision
from athena.domain.enums import Timeframe
from athena.indicators import IndicatorEngine, IndicatorName, IndicatorStatus
from athena.intraday import (
    EntryActionability,
    EntryActionabilityEngine,
    EntryActionabilityMarketEvidence,
    EntryQualification,
    OpeningRangeEngine,
    OpeningRangeWindow,
)
from athena.session import (
    SessionContextEngine,
    completed_candles,
    latest_completed_candle,
    session_day_start,
)

#: Frozen, deterministic replay-compute metadata -- NEVER a claim that the
#: engine actually executed at this instant historically (ID-7F0 §21/§29).
#: Any fixed, timezone-aware value works for determinism purposes; this one
#: is simply memorable and clearly outside the real historical data range.
DEFAULT_REPLAY_EVALUATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)

_ENTRY_QUALIFICATION_COLUMNS = (
    "instrument_id, session_date, as_of, decision_id, methodology_version, "
    "run_id, cycle_id, decision_type, state, evidence_finality, confirmation, "
    "reason_codes_json, evidence_refs_json, config_snapshot_id, explanation"
)
_DECISION_COLUMNS = (
    "decision_id, ts, run_id, cycle_id, decision_type, explanation, "
    "instrument_id, direction, score_ref, confidence_ref, risk_ref, "
    "gate_results_json, trade_plan_json"
)


@dataclass(frozen=True, slots=True)
class ReplayDefect:
    """A replay-classified failure -- never silently folded into a
    methodology outcome. ``kind`` is one of ID-7F0's own frozen
    taxonomy: ``UPSTREAM_BINDING_DEFECT`` / ``PIT_EVIDENCE_DEFECT`` /
    ``PERSISTENCE_DEFECT`` / ``REPLAY_EQUIVALENCE_DEFECT``."""

    instrument_id: str
    session_date: str
    decision_id: str
    entry_qualification_as_of: str
    kind: str
    detail: str


@dataclass(frozen=True, slots=True)
class UnexpectedReplayException:
    """ID-7F1.1: a per-observation reconstruction/evaluation failure that
    is NOT a `ValueError` (which the frozen `PIT_EVIDENCE_DEFECT` rule
    already covers) -- i.e. a genuine, unanticipated programming failure
    for this one observation. Deliberately kept as its own diagnostic
    category, separate from ID-7F0's frozen defect taxonomy (never
    silently mapped to `DATA_AVAILABILITY`/`UNKNOWN`/`PIT_EVIDENCE_DEFECT`,
    and never expanding that taxonomy either) -- a bug in this module's
    own reconstruction is neither legitimate missing evidence nor a
    point-in-time coherence defect; it is its own thing, reported
    honestly. The observation still counts as *attempted* (it was
    selected and processing began) but NOT as *reconstructed
    successfully*, and it makes the run's own acceptance verdict
    ``False`` (§ replay acceptance criteria) -- never a silent
    "PASS with hidden exceptions"."""

    instrument_id: str
    session_date: str
    decision_id: str
    entry_qualification_as_of: str
    exception_type: str
    detail: str


def _get_decision(store: ReadOnlyStore, decision_id: str) -> Decision | None:
    """Exact-by-id lookup -- never "latest Decision"."""
    row = store.conn.execute(
        f"SELECT {_DECISION_COLUMNS} FROM decisions WHERE decision_id=?", (decision_id,)
    ).fetchone()
    return ser.row_to_decision(tuple(row)) if row is not None else None


def _load_eq_population(store: ReadOnlyStore) -> list[EntryQualification]:
    """Every persisted WATCH/TRADE EntryQualification row -- the frozen
    ID-7F0 replay population (§6/§10 of this milestone's authorization).
    Deterministic ordering (never relied upon for correctness, only for
    reproducible artifact/log ordering)."""
    rows = store.conn.execute(
        f"SELECT {_ENTRY_QUALIFICATION_COLUMNS} FROM entry_qualifications "
        "WHERE decision_type IN ('WATCH','TRADE') "
        "ORDER BY instrument_id, session_date, as_of, decision_id"
    ).fetchall()
    return [ser.row_to_entry_qualification(tuple(row)) for row in rows]


def eq_identity(eq: EntryQualification) -> tuple:
    """The frozen EQ composite-identity key -- the same tuple
    ``save_entry_actionability`` uses to look up the exact upstream
    EntryQualification (`repository.py`). Exposed as a pure function so
    duplicate-detection is independently testable without a database."""
    return (
        eq.instrument_id, eq.session_date.isoformat(), eq.as_of.isoformat(),
        eq.decision_id, eq.methodology_version,
    )


def partition_duplicates(
    eqs: list[EntryQualification],
) -> tuple[list[EntryQualification], list[EntryQualification]]:
    """Split ``eqs`` into (first-seen-per-identity, duplicates) using the
    frozen EQ composite identity (`eq_identity`). A real persisted
    duplicate should be structurally unreachable -- the table's own
    composite `PRIMARY KEY` (`schema.py`) already prevents it -- but this
    is defense-in-depth, tested independently of that DB constraint."""
    seen: set[tuple] = set()
    unique: list[EntryQualification] = []
    duplicates: list[EntryQualification] = []
    for eq in eqs:
        identity = eq_identity(eq)
        if identity in seen:
            duplicates.append(eq)
            continue
        seen.add(identity)
        unique.append(eq)
    return unique, duplicates


def _validate_binding(eq: EntryQualification, decision: Decision | None) -> str | None:
    """Mirrors `EntryActionabilityEngine._validate_binding`'s own checks,
    performed here FIRST so a genuine binding mismatch is classified
    `UPSTREAM_BINDING_DEFECT` rather than surfacing as an undifferentiated
    engine `ValueError`. Returns an explanation string, or `None` if the
    binding is coherent."""
    if decision is None:
        return f"no Decision row found for decision_id={eq.decision_id!r}"
    if eq.decision_id != decision.decision_id:
        return f"decision_id mismatch: eq={eq.decision_id!r} decision={decision.decision_id!r}"
    if eq.decision_type != decision.decision_type:
        return (
            f"decision_type mismatch: eq={eq.decision_type.value!r} "
            f"decision={decision.decision_type.value!r}"
        )
    if eq.run_id != decision.run_id:
        return f"run_id mismatch: eq={eq.run_id!r} decision={decision.run_id!r}"
    if eq.cycle_id != decision.cycle_id:
        return f"cycle_id mismatch: eq={eq.cycle_id!r} decision={decision.cycle_id!r}"
    if decision.instrument_id is not None and decision.instrument_id != eq.instrument_id:
        return (
            f"instrument_id mismatch: eq={eq.instrument_id!r} "
            f"decision={decision.instrument_id!r}"
        )
    return None


def _reconstruct_market_evidence(
    eq: EntryQualification,
    *,
    store: ReadOnlyStore,
    session_engine: SessionContextEngine,
    opening_range_engine: OpeningRangeEngine,
    indicator_engine: IndicatorEngine,
    calendar: CalendarEngine,
    tzinfo: ZoneInfo,
    exchange: str,
    sessions_cfg,
) -> tuple[EntryActionabilityMarketEvidence, dict[str, Any]]:
    """Bounded, point-in-time reconstruction of exactly the evidence
    ID-7E's own production `entry_actionability_stage` would have
    supplied live for this exact checkpoint -- same canonical helpers,
    same bounds, never a second independent formula. Returns the market
    evidence object plus a small descriptive dict (never methodology-
    consumed) for the replay artifact.

    May raise ``ValueError`` -- from `EntryActionabilityMarketEvidence`'s
    own structural invariants, from `SessionContextEngine`/
    `OpeningRangeEngine`'s own `as_of` checks, or (later, at the caller)
    from `EntryActionabilityEngine.evaluate()`'s own PIT/coherence
    checks. The caller classifies any such raise as `PIT_EVIDENCE_DEFECT`
    -- never silently re-labeled as a methodology outcome.
    """
    day_start = session_day_start(eq.as_of, tzinfo)
    five_min = store.candles(eq.instrument_id, Timeframe.M5, day_start, eq.as_of)
    fifteen_min = store.candles(eq.instrument_id, Timeframe.M15, day_start, eq.as_of)
    latest_quote_ts = store.latest_quote_ts(eq.instrument_id, eq.as_of)

    session_context = session_engine.assess(
        eq.instrument_id, as_of=eq.as_of, exchange=exchange, calendar=calendar,
        sessions=sessions_cfg, tzinfo=tzinfo,
        five_min_candles=five_min, fifteen_min_candles=fifteen_min,
        latest_quote_ts=latest_quote_ts,
    )

    completed_m5 = completed_candles(five_min, Timeframe.M5, as_of=eq.as_of)
    latest_completed_m5 = latest_completed_candle(five_min, Timeframe.M5, as_of=eq.as_of)
    vwap_result = (
        indicator_engine.compute(IndicatorName.VWAP, completed_m5, as_of=eq.as_of)
        if completed_m5 else None
    )
    session_vwap = (
        vwap_result.values["vwap"]
        if vwap_result is not None and vwap_result.status is IndicatorStatus.OK
        else None
    )
    session_vwap_as_of = (
        latest_completed_m5.ts_open + timedelta(minutes=5)
        if session_vwap is not None
        else None
    )

    orb = opening_range_engine.assess(
        eq.instrument_id, as_of=eq.as_of, session_context=session_context,
        five_min_candles=five_min, calendar=calendar, tzinfo=tzinfo,
    )
    or15 = orb[OpeningRangeWindow.OR15]

    market_evidence = EntryActionabilityMarketEvidence(
        completed_m5_close=latest_completed_m5,
        session_vwap=session_vwap,
        session_vwap_as_of=session_vwap_as_of,
        opening_range_15=or15,
    )

    descriptive = {
        "session_context_session_date": session_context.session_date.isoformat(),
        "completed_m5_ts": (
            latest_completed_m5.ts_open.isoformat() if latest_completed_m5 else None
        ),
        "session_vwap": str(session_vwap) if session_vwap is not None else None,
        "session_vwap_as_of": (
            session_vwap_as_of.isoformat() if session_vwap_as_of is not None else None
        ),
        "or15_status": or15.formation.status.value,
        "or15_as_of": or15.as_of.isoformat(),
    }
    return market_evidence, descriptive


def _observation_dict(
    eq: EntryQualification, decision: Decision, ea: EntryActionability,
    descriptive_evidence: dict[str, Any], *, deterministic_match: bool,
) -> dict[str, Any]:
    return {
        "instrument_id": eq.instrument_id,
        "session_date": eq.session_date.isoformat(),
        "decision_id": eq.decision_id,
        "decision_type": eq.decision_type.value,
        "direction": decision.direction.value,
        "run_id": eq.run_id,
        "cycle_id": eq.cycle_id,
        "eq_as_of": eq.as_of.isoformat(),
        "eq_methodology_version": eq.methodology_version,
        "eq_state": eq.state.value,
        **{f"reconstructed_{k}": v for k, v in descriptive_evidence.items()},
        "ea_state": ea.state.value,
        "ea_reason_codes": [c.value for c in ea.reason_codes],
        "entry_actionability_as_of": ea.entry_actionability_as_of.isoformat(),
        "entry_actionability_methodology_version": ea.entry_actionability_methodology_version,
        "evidence_as_of": ea.evidence_as_of.isoformat() if ea.evidence_as_of else None,
        "evidence_finality": ea.evidence_finality.value,
        "entry_reference_price": (
            str(ea.entry_reference.price) if ea.entry_reference else None
        ),
        "operative_invalidation_level": (
            str(ea.operative_invalidation.level) if ea.operative_invalidation else None
        ),
        "reward_t1_price": str(ea.reward.t1_price) if ea.reward else None,
        "reward_t2_price": str(ea.reward.t2_price) if ea.reward else None,
        "opening_range_context_level": (
            str(ea.opening_range_context.level) if ea.opening_range_context else None
        ),
        "classification": "METHODOLOGY_RESULT",
        "deterministic_match": deterministic_match,
    }


def run_replay(
    *,
    db_path: Path,
    config_dir: Path,
    output_dir: Path,
    evaluated_at: datetime = DEFAULT_REPLAY_EVALUATED_AT,
) -> dict[str, Any]:
    """Historical, market-time-bounded replay of the real
    `EntryActionabilityEngine` over every persisted WATCH/TRADE
    `EntryQualification` row in ``db_path`` (opened strictly read-only).
    Never writes to ``db_path``; never calls `save_entry_actionability`;
    output goes only to disposable JSONL/JSON under ``output_dir``.

    ``evaluated_at`` is a single fixed, timezone-aware replay-compute
    timestamp reused for every observation -- diagnostic metadata only,
    never a historical knowledge-time claim (module docstring).
    """
    if evaluated_at.tzinfo is None:
        raise ValueError("run_replay evaluated_at must be timezone-aware")

    started = time.perf_counter()
    cfg = load_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, cfg.market)
    tzinfo = ZoneInfo(cfg.market.timezone)
    indicator_engine = IndicatorEngine(cfg.indicators)
    session_engine = SessionContextEngine()
    opening_range_engine = OpeningRangeEngine()
    engine = EntryActionabilityEngine()

    store = ReadOnlyStore(db_path)
    schema_version_start = store.conn.execute("SELECT version FROM schema_version").fetchone()
    schema_version_start = int(schema_version_start[0]) if schema_version_start else None

    rows: list[dict[str, Any]] = []
    defects: list[ReplayDefect] = []
    unexpected_exceptions: list[UnexpectedReplayException] = []
    m5_vwap_checkpoint_violations = 0

    try:
        population = _load_eq_population(store)
        population_total = len(population)
        unique_population, duplicate_population = partition_duplicates(population)
        duplicate_identity_count = len(duplicate_population)
        unique_population_total = len(unique_population)
        # ID-7F1.1: `rows_attempted` is exactly the unique population
        # size -- every unique EQ enters the per-observation loop below
        # exactly once and is "attempted" regardless of whether it ends
        # in a binding defect, a PIT-evidence defect, an unexpected
        # exception, or a successful (possibly determinism-mismatched)
        # reconstruction. It is deliberately NOT derived from
        # len(rows) + len(defects) -- a determinism mismatch appends to
        # BOTH `rows` (the reconstruction did succeed) AND `defects`
        # (flagging the mismatch), so that sum double-counts exactly the
        # observations this milestone exists to stop double-counting.
        rows_attempted = unique_population_total
        for dup in duplicate_population:
            defects.append(ReplayDefect(
                instrument_id=dup.instrument_id, session_date=dup.session_date.isoformat(),
                decision_id=dup.decision_id, entry_qualification_as_of=dup.as_of.isoformat(),
                kind="PERSISTENCE_DEFECT",
                detail="duplicate persisted EntryQualification logical identity",
            ))
        for eq in unique_population:
            decision = _get_decision(store, eq.decision_id)
            binding_error = _validate_binding(eq, decision)
            if binding_error is not None:
                defects.append(ReplayDefect(
                    instrument_id=eq.instrument_id, session_date=eq.session_date.isoformat(),
                    decision_id=eq.decision_id, entry_qualification_as_of=eq.as_of.isoformat(),
                    kind="UPSTREAM_BINDING_DEFECT", detail=binding_error,
                ))
                continue
            assert decision is not None  # binding_error is None => decision exists

            try:
                try:
                    market_evidence, descriptive = _reconstruct_market_evidence(
                        eq, store=store, session_engine=session_engine,
                        opening_range_engine=opening_range_engine,
                        indicator_engine=indicator_engine, calendar=calendar, tzinfo=tzinfo,
                        exchange=cfg.market.exchange, sessions_cfg=cfg.market.sessions,
                    )
                    ea_first = engine.evaluate(
                        decision=decision, entry_qualification=eq,
                        market_evidence=market_evidence, evaluated_at=evaluated_at, policy=None,
                    )
                    # Determinism (ID-7F0 §27 / ID-7F1 §20): full
                    # independent re-reconstruction + re-evaluation of the
                    # identical historical checkpoint must be byte-for-byte
                    # equal -- never merely re-calling evaluate() on cached
                    # objects, which would only prove the engine's own
                    # purity, not the whole replay pipeline's.
                    market_evidence_2, _ = _reconstruct_market_evidence(
                        eq, store=store, session_engine=session_engine,
                        opening_range_engine=opening_range_engine,
                        indicator_engine=indicator_engine, calendar=calendar, tzinfo=tzinfo,
                        exchange=cfg.market.exchange, sessions_cfg=cfg.market.sessions,
                    )
                    ea_second = engine.evaluate(
                        decision=decision, entry_qualification=eq,
                        market_evidence=market_evidence_2, evaluated_at=evaluated_at, policy=None,
                    )
                except ValueError as exc:
                    # PIT_EVIDENCE_DEFECT: binding was already independently
                    # proven above, so any ValueError past this point is a
                    # point-in-time evidence/coherence defect (candle
                    # coherence, VWAP-provenance, OR15 coherence, or this
                    # module's own malformed reconstruction) -- never
                    # silently relabeled as a legitimate methodology UNKNOWN.
                    defects.append(ReplayDefect(
                        instrument_id=eq.instrument_id, session_date=eq.session_date.isoformat(),
                        decision_id=eq.decision_id, entry_qualification_as_of=eq.as_of.isoformat(),
                        kind="PIT_EVIDENCE_DEFECT", detail=f"{type(exc).__name__}: {exc}",
                    ))
                    continue
            except Exception as exc:  # noqa: BLE001 -- deliberate, narrow, documented (§6/§7)
                # ID-7F1.1: a genuinely unexpected (non-ValueError)
                # failure reconstructing/evaluating THIS ONE observation
                # -- never BaseException/KeyboardInterrupt/SystemExit
                # (not subclasses of Exception, so never caught here),
                # never silently relabeled as legitimate methodology
                # evidence, never expanding ID-7F0's own frozen defect
                # taxonomy. Recorded as its own diagnostic, the run
                # continues to the next independent observation (so one
                # bad row cannot hide whether the issue is isolated or
                # systemic), and the run's own acceptance verdict is
                # forced to False by any non-zero count of these
                # (§ replay acceptance criteria) -- never a silent
                # "PASS with hidden exceptions."
                unexpected_exceptions.append(UnexpectedReplayException(
                    instrument_id=eq.instrument_id, session_date=eq.session_date.isoformat(),
                    decision_id=eq.decision_id, entry_qualification_as_of=eq.as_of.isoformat(),
                    exception_type=type(exc).__name__, detail=str(exc),
                ))
                continue

            deterministic_match = ea_first == ea_second
            if not deterministic_match:
                defects.append(ReplayDefect(
                    instrument_id=eq.instrument_id, session_date=eq.session_date.isoformat(),
                    decision_id=eq.decision_id, entry_qualification_as_of=eq.as_of.isoformat(),
                    kind="REPLAY_EQUIVALENCE_DEFECT",
                    detail="two independent reconstructions of the identical checkpoint "
                           "produced different EntryActionability results",
                ))

            if (
                market_evidence.completed_m5_close is not None
                and market_evidence.session_vwap_as_of is not None
                and market_evidence.session_vwap_as_of
                != market_evidence.completed_m5_close.ts_open + timedelta(minutes=5)
            ):
                m5_vwap_checkpoint_violations += 1  # structurally unreachable; counted anyway

            rows.append(_observation_dict(
                eq, decision, ea_first, descriptive, deterministic_match=deterministic_match,
            ))
    finally:
        schema_version_end = store.conn.execute("SELECT version FROM schema_version").fetchone()
        schema_version_end = int(schema_version_end[0]) if schema_version_end else None
        store.close()

    return _summarize(
        rows=rows, defects=defects, unexpected_exceptions=unexpected_exceptions,
        population_total=population_total, unique_population_total=unique_population_total,
        duplicate_identity_count=duplicate_identity_count, rows_attempted=rows_attempted,
        m5_vwap_checkpoint_violations=m5_vwap_checkpoint_violations,
        db_path=db_path, schema_version_start=schema_version_start,
        schema_version_end=schema_version_end, evaluated_at=evaluated_at,
        started=started, output_dir=output_dir,
    )


# --------------------------------------------------------------------------- #
# Analysis / summary
# --------------------------------------------------------------------------- #


def pct(part: int, whole: int) -> float:
    return round((part / whole * 100.0), 2) if whole else 0.0


def _counter_payload(counter: Counter[str], total: int) -> dict[str, dict[str, float | int]]:
    return {key: {"count": value, "pct": pct(value, total)} for key, value in sorted(counter.items())}


def _population_inventory(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_observations": len(rows),
        "decision_type_counts": _counter_payload(
            Counter(r["decision_type"] for r in rows), len(rows)
        ),
        "direction_counts": _counter_payload(Counter(r["direction"] for r in rows), len(rows)),
        "eq_state_counts": _counter_payload(Counter(r["eq_state"] for r in rows), len(rows)),
        "eq_methodology_version_counts": _counter_payload(
            Counter(r["eq_methodology_version"] for r in rows), len(rows)
        ),
        "distinct_sessions": len({r["session_date"] for r in rows}),
        "distinct_instruments": len({r["instrument_id"] for r in rows}),
    }


def _ea_result_distribution(rows: list[dict[str, Any]], decision_type: str) -> dict[str, Any]:
    subset = [r for r in rows if r["decision_type"] == decision_type]
    total = len(subset)
    state_counts = Counter(r["ea_state"] for r in subset)
    reason_counts: Counter[str] = Counter()
    for r in subset:
        for reason in r["ea_reason_codes"]:
            reason_counts[reason] += 1
    return {
        "observations": total,
        "state_distribution": _counter_payload(state_counts, total),
        "reason_code_counts": dict(sorted(reason_counts.items())),
    }


def _evidence_availability(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    m5_present = sum(1 for r in rows if r["reconstructed_completed_m5_ts"] is not None)
    vwap_present = sum(1 for r in rows if r["reconstructed_session_vwap"] is not None)
    or15_status_counts = Counter(r["reconstructed_or15_status"] for r in rows)
    return {
        "completed_m5_present": m5_present,
        "completed_m5_absent": total - m5_present,
        "completed_m5_present_pct": pct(m5_present, total),
        "session_vwap_present": vwap_present,
        "session_vwap_absent": total - vwap_present,
        "session_vwap_present_pct": pct(vwap_present, total),
        "or15_status_counts": _counter_payload(or15_status_counts, total),
    }


def _empirical_availability(rows: list[dict[str, Any]]) -> dict[str, str]:
    trade_rows = [r for r in rows if r["decision_type"] == "TRADE"]
    actionable_rows = [r for r in rows if r["ea_state"] == "ACTIONABLE"]
    unknown_rows = [r for r in rows if r["ea_state"] == "UNKNOWN"]
    short_rows = [r for r in rows if r["direction"] == "SHORT"]
    return {
        "trade_empirical_validation": (
            "TRADE_EMPIRICAL_VALIDATION_NOT_AVAILABLE" if not trade_rows
            else "TRADE_EMPIRICAL_VALIDATION_AVAILABLE"
        ),
        "actionable_empirical_validation": (
            "ACTIONABLE_EMPIRICAL_VALIDATION_NOT_AVAILABLE" if not actionable_rows
            else "ACTIONABLE_EMPIRICAL_VALIDATION_AVAILABLE"
        ),
        "unknown_empirical_validation": (
            "UNKNOWN_EMPIRICAL_VALIDATION_NOT_AVAILABLE" if not unknown_rows
            else "UNKNOWN_EMPIRICAL_VALIDATION_AVAILABLE"
        ),
        "short_empirical_validation": (
            "SHORT_EMPIRICAL_VALIDATION_NOT_AVAILABLE" if not short_rows
            else "SHORT_EMPIRICAL_VALIDATION_AVAILABLE"
        ),
    }


def _watch_invariant_check(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """ID-7F0 §17: every real, coherent WATCH observation must be
    NOT_ACTIONABLE / UPSTREAM_DECISION_NOT_TRADE. Any deviation is a
    replay/methodology-equivalence defect to investigate, never silently
    accepted."""
    watch_rows = [r for r in rows if r["decision_type"] == "WATCH"]
    violations = [
        r for r in watch_rows
        if r["ea_state"] != "NOT_ACTIONABLE"
        or "UPSTREAM_DECISION_NOT_TRADE" not in r["ea_reason_codes"]
    ]
    return {
        "watch_observations": len(watch_rows),
        "watch_invariant_violations": len(violations),
        "watch_invariant_holds": len(violations) == 0,
        "violation_decision_ids": [r["decision_id"] for r in violations][:50],
    }


def _analysis_digest(summary: dict[str, Any]) -> str:
    stable = json.loads(json.dumps(summary, sort_keys=True))
    stable["metadata"].pop("runtime_seconds", None)
    stable.pop("artifacts", None)
    payload = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _replay_acceptance(
    *,
    defect_kind_counts: Counter[str],
    unexpected_exception_count: int,
    determinism_mismatches: int,
    m5_vwap_checkpoint_violations: int,
    watch_invariant_violations: int,
) -> bool:
    """ID-7F1.1 §9: the smallest explicit clean-replay acceptance
    verdict. Deliberately excludes TRADE/ACTIONABLE/UNKNOWN/SHORT
    empirical availability -- those populations remain honestly absent
    from real data (§27 elsewhere) and are never an acceptance
    criterion. Any non-zero unexpected-exception count forces this
    False -- never a silent "PASS with hidden exceptions"."""
    return (
        defect_kind_counts.get("UPSTREAM_BINDING_DEFECT", 0) == 0
        and defect_kind_counts.get("PIT_EVIDENCE_DEFECT", 0) == 0
        and defect_kind_counts.get("PERSISTENCE_DEFECT", 0) == 0
        and defect_kind_counts.get("REPLAY_EQUIVALENCE_DEFECT", 0) == 0
        and unexpected_exception_count == 0
        and determinism_mismatches == 0
        and m5_vwap_checkpoint_violations == 0
        and watch_invariant_violations == 0
    )


def _summarize(
    *,
    rows: list[dict[str, Any]],
    defects: list[ReplayDefect],
    unexpected_exceptions: list[UnexpectedReplayException],
    population_total: int,
    unique_population_total: int,
    duplicate_identity_count: int,
    rows_attempted: int,
    m5_vwap_checkpoint_violations: int,
    db_path: Path,
    schema_version_start: int | None,
    schema_version_end: int | None,
    evaluated_at: datetime,
    started: float,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / "id7f1_observations.jsonl"
    with rows_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    defects_path = output_dir / "id7f1_defects.jsonl"
    with defects_path.open("w", encoding="utf-8") as fh:
        for defect in defects:
            fh.write(json.dumps({
                "instrument_id": defect.instrument_id, "session_date": defect.session_date,
                "decision_id": defect.decision_id,
                "entry_qualification_as_of": defect.entry_qualification_as_of,
                "kind": defect.kind, "detail": defect.detail,
            }, sort_keys=True) + "\n")
    unexpected_path = output_dir / "id7f1_unexpected_exceptions.jsonl"
    with unexpected_path.open("w", encoding="utf-8") as fh:
        for exc in unexpected_exceptions:
            fh.write(json.dumps({
                "instrument_id": exc.instrument_id, "session_date": exc.session_date,
                "decision_id": exc.decision_id,
                "entry_qualification_as_of": exc.entry_qualification_as_of,
                "exception_type": exc.exception_type, "detail": exc.detail,
            }, sort_keys=True) + "\n")

    defect_kind_counts = Counter(d.kind for d in defects)
    determinism_mismatches = sum(1 for r in rows if not r["deterministic_match"])
    # ID-7F1.1 §3: defect-bearing OBSERVATIONS, keyed by exact replay
    # identity -- orthogonal to len(defects), since one observation
    # could in principle carry more than one defect record (it does
    # not today, but this count is correct either way).
    observations_with_defects = len({
        (d.instrument_id, d.session_date, d.decision_id, d.entry_qualification_as_of)
        for d in defects
    })
    watch_invariant = _watch_invariant_check(rows)

    summary: dict[str, Any] = {
        "metadata": {
            "milestone": "ID-7F1",
            "label": "historical market-time-bounded replay via the real "
                      "EntryActionabilityEngine (Mode A only, no shadow comparison)",
            "source_db_path": str(db_path),
            "schema_version_observed_at_start": schema_version_start,
            "schema_version_observed_at_end": schema_version_end,
            "schema_version_unchanged": schema_version_start == schema_version_end,
            "read_only": "SQLite URI mode=ro with PRAGMA query_only=ON",
            "fixed_evaluated_at": evaluated_at.isoformat(),
            "evaluated_at_semantics": "replay compute metadata only -- NOT a historical "
                                      "knowledge-time claim",
            "replay_semantics": "market-time bounded deterministic reconstruction -- "
                                "not bitemporal knowledge-time replay",
            "runtime_seconds": round(time.perf_counter() - started, 3),
        },
        "population_inventory": _population_inventory(rows),
        # ID-7F1.1: explicit, independently-derived population counters
        # (never rows_attempted = len(rows) + len(defects), which
        # double-counts any observation that both reconstructed
        # successfully AND carries a REPLAY_EQUIVALENCE_DEFECT).
        "population_total": population_total,
        "duplicate_population_total": duplicate_identity_count,
        "unique_population_total": unique_population_total,
        "rows_attempted": rows_attempted,
        "rows_reconstructed_successfully": len(rows),
        "defect_counts": {
            "total": len(defects),
            "by_kind": dict(sorted(defect_kind_counts.items())),
            "upstream_binding_defects": defect_kind_counts.get("UPSTREAM_BINDING_DEFECT", 0),
            "pit_evidence_defects": defect_kind_counts.get("PIT_EVIDENCE_DEFECT", 0),
            "persistence_defects": defect_kind_counts.get("PERSISTENCE_DEFECT", 0),
            "replay_equivalence_defects": defect_kind_counts.get("REPLAY_EQUIVALENCE_DEFECT", 0),
        },
        "observations_with_defects": observations_with_defects,
        "duplicate_identity_count": duplicate_identity_count,
        "unexpected_replay_exceptions": {
            "total": len(unexpected_exceptions),
            "by_exception_type": dict(sorted(
                Counter(e.exception_type for e in unexpected_exceptions).items()
            )),
        },
        "determinism": {
            "checked_observations": len(rows),
            "mismatches": determinism_mismatches,
            "determinism_holds": determinism_mismatches == 0,
        },
        "m5_vwap_checkpoint_violations": m5_vwap_checkpoint_violations,
        "watch_result_distribution": _ea_result_distribution(rows, "WATCH"),
        "trade_result_distribution": _ea_result_distribution(rows, "TRADE"),
        "watch_invariant_check": watch_invariant,
        "evidence_availability": _evidence_availability(rows),
        "empirical_availability": _empirical_availability(rows),
        "replay_acceptance": _replay_acceptance(
            defect_kind_counts=defect_kind_counts,
            unexpected_exception_count=len(unexpected_exceptions),
            determinism_mismatches=determinism_mismatches,
            m5_vwap_checkpoint_violations=m5_vwap_checkpoint_violations,
            watch_invariant_violations=watch_invariant["watch_invariant_violations"],
        ),
    }
    summary_path = output_dir / "id7f1_summary.json"
    analysis_digest = _analysis_digest(summary)
    summary["artifacts"] = {
        "summary_path": str(summary_path),
        "observations_path": str(rows_path),
        "defects_path": str(defects_path),
        "unexpected_exceptions_path": str(unexpected_path),
        "analysis_sha256": analysis_digest,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
