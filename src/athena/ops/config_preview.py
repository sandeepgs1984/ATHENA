"""Config-change impact preview (M-X9).

Deterministic replay-based diff of a candidate config change (a scoring-
weight edit, in particular) against recent real decisions, before the
change goes live. Read-only against the real repository — only ever calls
``list_decisions``/``get_instrument``/``get_candles``/``get_latest_snapshot_before``,
never a write method — and replays each decision through the real,
unmodified ``OwnerValidationPipeline`` against a fresh, throwaway in-memory
repository per replay, seeded only with that instrument's real candle
history and market snapshot bounded strictly before/at the decision's own
timestamp (no look-ahead). This mirrors M-X8's canary pattern (reuse the
real pipeline against a throwaway store) rather than reconstructing typed
engine inputs from the lossy, presentation-only JSON `DecisionReportingEngine`
persists (which discards indicator evidence needed to re-score faithfully).

Caveat found via real-data validation, not assumed: each replay is scoped
to exactly one instrument (`symbols_filter`), so `RiskEngine`'s
concentration read sees a single-instrument universe with no prior-run
history to fall back on — a materially different context than the
original multi-instrument scan that actually produced the persisted
decision. `ConfigPreviewRow.original_decision_type` can therefore
legitimately differ from `current.decision_type` even with the *current*
config replayed — that mismatch is a replay-methodology artifact, not a
regression. It is NOT the comparison this module makes. The valid,
apples-to-apples signal is `current` vs `candidate`: both are computed
under the exact same single-instrument context, so the concentration-risk
effect is held constant on both sides and only the config difference can
move the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import RunTrigger, Timeframe
from athena.ops.owner_candidates import SqliteCandidateStore
from athena.ops.owner_validation import OwnerValidationPipeline

_EARLIEST = datetime(2000, 1, 1)


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    """One instrument's re-scored outcome under one config. `None` fields
    mean the pipeline didn't produce a report for this instrument at all
    (e.g. insufficient replayed history) — distinct from a known UNKNOWN
    decision_type/composite, which are real string values."""

    decision_type: str | None
    composite: str | None


@dataclass(frozen=True, slots=True)
class ConfigPreviewRow:
    """One recent real decision, replayed under both configs."""

    decision_id: str
    instrument_id: str
    original_decision_type: str
    current: ReplayOutcome
    candidate: ReplayOutcome

    @property
    def changed(self) -> bool:
        return self.current.decision_type != self.candidate.decision_type


@dataclass(frozen=True, slots=True)
class ConfigPreviewReport:
    """Aggregate impact of a candidate config change over recently
    replayed real decisions. Never persisted — transient, computed on
    demand and returned/printed."""

    rows: tuple[ConfigPreviewRow, ...]
    skipped: tuple[str, ...]  # decision_ids that couldn't be replayed (reason in message)

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def changed_count(self) -> int:
        return sum(1 for r in self.rows if r.changed)

    @property
    def changed_pct(self) -> float:
        return (self.changed_count / self.total * 100.0) if self.total else 0.0


def replay_decision_under_config(
    repo: SqliteRepository, decision: Decision, config_dir: Path
) -> ReplayOutcome:
    """Re-score one real, already-persisted decision under `config_dir`.

    Builds a fresh in-memory repo seeded only with that instrument's real
    daily candle history up to (and including) the decision's own `ts`, and
    the real market snapshot in effect strictly before that `ts` — bounding
    both so the replay only ever sees what was actually knowable at the
    time, never future data. Runs the real, unmodified
    `OwnerValidationPipeline` against that throwaway store; never touches
    `repo` (the real one) beyond the read-only lookups below.
    """
    instrument_id = decision.instrument_id
    if instrument_id is None:
        return ReplayOutcome(decision_type=None, composite=None)
    instrument = repo.get_instrument(instrument_id)
    if instrument is None:
        return ReplayOutcome(decision_type=None, composite=None)
    candles = repo.get_candles(instrument_id, Timeframe.D1, _EARLIEST, decision.ts)
    if not candles:
        return ReplayOutcome(decision_type=None, composite=None)
    snapshot = repo.get_latest_snapshot_before(decision.ts)

    shadow = SqliteRepository(":memory:")
    try:
        shadow.initialize()
        shadow.upsert_instrument(instrument)
        shadow.add_candles(candles)
        if snapshot is not None:
            shadow.add_snapshot(snapshot)
        SqliteCandidateStore(shadow).upsert_candidate(symbol=instrument.symbol)

        pipe = OwnerValidationPipeline(shadow, config_dir, symbols_filter=[instrument.symbol])
        ingestion = IngestionResult(
            as_of=decision.ts, instruments_upserted=1, candles_fetched=len(candles),
            candles_written=len(candles), quotes_fetched=0, quotes_written=0,
            datasets_validated=1, datasets_skipped_empty=0,
        )
        try:
            detail = pipe.run(
                RunTrigger.REFRESH, as_of=decision.ts, ingestion=ingestion,
                run_id=f"preview-{decision.decision_id}",
            )
        except Exception:
            return ReplayOutcome(decision_type=None, composite=None)
    finally:
        shadow.close()

    reports = detail.get("decision_reports") if isinstance(detail, dict) else None
    if not reports:
        return ReplayOutcome(decision_type=None, composite=None)
    report = next(iter(reports.values()))
    return ReplayOutcome(
        decision_type=report.get("decision", {}).get("type"),
        composite=report.get("score", {}).get("composite"),
    )


def preview_config_change(
    repo: SqliteRepository,
    *,
    current_config_dir: Path,
    candidate_config_dir: Path,
    limit: int = 20,
) -> ConfigPreviewReport:
    """Replay the `limit` most recent real decisions under both the current
    and candidate config, and diff the resulting decision types."""
    rows: list[ConfigPreviewRow] = []
    skipped: list[str] = []
    for decision in repo.list_decisions(limit=limit):
        if decision.instrument_id is None:
            skipped.append(decision.decision_id)
            continue
        current = replay_decision_under_config(repo, decision, current_config_dir)
        candidate = replay_decision_under_config(repo, decision, candidate_config_dir)
        if current.decision_type is None:
            skipped.append(decision.decision_id)
            continue
        rows.append(
            ConfigPreviewRow(
                decision_id=decision.decision_id,
                instrument_id=decision.instrument_id,
                original_decision_type=decision.decision_type.value,
                current=current,
                candidate=candidate,
            )
        )
    return ConfigPreviewReport(rows=tuple(rows), skipped=tuple(skipped))
