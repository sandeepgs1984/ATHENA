"""Daily briefing assembly from the run ledger (M10.3 + R6 day summary).

Renders only — does not re-run the decision pipeline. Optional decisions are
injected via ``DecisionSummarySource``; missing decisions degrade explicitly.
R6 adds day roll-up + journal prompts for decisions lacking journal rows.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from athena.config.models import NotificationsConfig
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision, DecisionTrace
from athena.domain.enums import RunStatus
from athena.domain.run import RunRecord
from athena.errors import BriefingError
from athena.notifications.models import (
    BriefingDecisionSummary,
    BriefingJournalPrompt,
    BriefingRunSummary,
    BriefingStatus,
    DailyBriefing,
)


class DecisionSummarySource(Protocol):
    """Optional provider of decisions for the briefing day."""

    def list_for_day(self, as_of: datetime) -> Sequence[Decision | tuple[Decision, DecisionTrace | None]]:
        ...


class DailyBriefingBuilder:
    """Assemble an immutable ``DailyBriefing`` from SQLite runs + optional decisions."""

    def __init__(
        self,
        repo: SqliteRepository,
        config: NotificationsConfig,
        *,
        tzinfo: ZoneInfo,
        decision_source: DecisionSummarySource | None = None,
    ) -> None:
        self._repo = repo
        self._config = config
        self._tzinfo = tzinfo
        self._decision_source = decision_source

    def build(self, *, as_of: datetime) -> DailyBriefing:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        day = as_of.astimezone(self._tzinfo).date()
        briefing_id = f"brief-{day.isoformat()}"
        runs = self._runs_for_day(as_of)
        reasons: list[str] = []

        if not runs and self._config.require_runs:
            raise BriefingError(
                f"no runs found for {day.isoformat()} — cannot assemble daily briefing"
            )

        run_summaries = tuple(self._summarize_run(r) for r in runs)
        if any(r.status == RunStatus.FAILED.value for r in run_summaries):
            reasons.append("one_or_more_runs_failed")

        decisions = self._decision_summaries(as_of)
        if not decisions and self._config.degrade_without_decisions:
            reasons.append("no_decision_summaries")

        journal_prompts = self._journal_prompts(decisions)
        day_summary = _build_day_summary(run_summaries, decisions, journal_prompts)

        if not runs:
            status = BriefingStatus.FAILED
            reasons = ["no_runs"]
        elif reasons:
            status = BriefingStatus.DEGRADED
        else:
            status = BriefingStatus.OK

        text = _render_text(
            briefing_id, as_of, status, run_summaries, decisions,
            day_summary, journal_prompts, tuple(reasons),
        )
        machine = {
            "briefing_id": briefing_id,
            "as_of": as_of.isoformat(),
            "status": status.value,
            "run_count": len(run_summaries),
            "decision_count": len(decisions),
            "runs": [r.to_dict() for r in run_summaries],
            "decisions": [d.to_dict() for d in decisions],
            "day_summary": dict(day_summary),
            "journal_prompts": [p.to_dict() for p in journal_prompts],
            "degradation_reasons": list(reasons),
        }
        return DailyBriefing(
            briefing_id=briefing_id,
            as_of=as_of,
            status=status,
            runs=run_summaries,
            decisions=decisions,
            text_summary=text,
            machine=machine,
            degradation_reasons=tuple(reasons),
            day_summary=day_summary,
            journal_prompts=journal_prompts,
        )

    def _runs_for_day(self, as_of: datetime) -> list[RunRecord]:
        day = as_of.astimezone(self._tzinfo).date()
        scanned = self._repo.list_runs(limit=self._config.max_runs_scanned)
        matched = [
            r for r in scanned
            if r.started_ts.astimezone(self._tzinfo).date() == day
        ]
        matched.sort(key=lambda r: (r.started_ts, r.run_id))
        return matched

    def _summarize_run(self, run: RunRecord) -> BriefingRunSummary:
        detail = self._repo.get_run_detail(run.run_id)
        ingest = detail.get("ingestion") if isinstance(detail.get("ingestion"), dict) else {}
        return BriefingRunSummary(
            run_id=run.run_id,
            trigger=run.trigger.value,
            status=run.status.value,
            started_ts=run.started_ts,
            candles_written=int(ingest.get("candles_written", 0) or 0),
            quotes_written=int(ingest.get("quotes_written", 0) or 0),
        )

    def _decision_summaries(self, as_of: datetime) -> tuple[BriefingDecisionSummary, ...]:
        if self._decision_source is None:
            return ()
        day = as_of.astimezone(self._tzinfo).date()
        items = self._decision_source.list_for_day(as_of)
        out: list[BriefingDecisionSummary] = []
        for item in items:
            if isinstance(item, tuple):
                decision, trace = item
            else:
                decision, trace = item, None
            if decision.ts.astimezone(self._tzinfo).date() != day:
                continue
            out.append(BriefingDecisionSummary(
                decision_id=decision.decision_id,
                decision_type=decision.decision_type.value,
                instrument_id=decision.instrument_id,
                direction=decision.direction.value,
                explanation=decision.explanation,
                trace_stage_count=len(trace.stages) if trace is not None else 0,
            ))
        out.sort(key=lambda d: d.decision_id)
        return tuple(out)

    def _journal_prompts(
        self, decisions: Sequence[BriefingDecisionSummary],
    ) -> tuple[BriefingJournalPrompt, ...]:
        """Prompt for decisions that have no journal row yet (user action/outcome)."""
        journaled = {
            e.decision_ref
            for e in self._repo.list_journal(limit=self._config.max_runs_scanned)
        }
        prompts: list[BriefingJournalPrompt] = []
        for d in decisions:
            if d.decision_id in journaled:
                continue
            inst = d.instrument_id or "-"
            prompts.append(BriefingJournalPrompt(
                decision_id=d.decision_id,
                instrument_id=d.instrument_id,
                decision_type=d.decision_type,
                prompt=(
                    f"Record journal action for {d.decision_id} ({inst} {d.decision_type}): "
                    "ACCEPTED / REJECTED / IGNORED + optional outcome notes"
                ),
            ))
        return tuple(prompts)


def _build_day_summary(
    runs: Sequence[BriefingRunSummary],
    decisions: Sequence[BriefingDecisionSummary],
    prompts: Sequence[BriefingJournalPrompt],
) -> dict[str, object]:
    by_trigger = Counter(r.trigger for r in runs)
    by_status = Counter(r.status for r in runs)
    by_decision_type = Counter(d.decision_type for d in decisions)
    return {
        "run_count": len(runs),
        "runs_by_trigger": dict(sorted(by_trigger.items())),
        "runs_by_status": dict(sorted(by_status.items())),
        "decision_count": len(decisions),
        "decisions_by_type": dict(sorted(by_decision_type.items())),
        "journal_prompts_pending": len(prompts),
        "closing_run_present": any(r.trigger == "CLOSING" for r in runs),
    }


def _render_text(
    briefing_id: str,
    as_of: datetime,
    status: BriefingStatus,
    runs: Sequence[BriefingRunSummary],
    decisions: Sequence[BriefingDecisionSummary],
    day_summary: Mapping[str, object],
    journal_prompts: Sequence[BriefingJournalPrompt],
    reasons: Sequence[str],
) -> str:
    lines = [
        f"ATHENA Daily Briefing {briefing_id}",
        f"as_of: {as_of.isoformat()}",
        f"status: {status.value}",
        "",
        "Day summary:",
        f"  runs={day_summary.get('run_count', 0)} "
        f"by_trigger={day_summary.get('runs_by_trigger', {})} "
        f"by_status={day_summary.get('runs_by_status', {})}",
        f"  decisions={day_summary.get('decision_count', 0)} "
        f"by_type={day_summary.get('decisions_by_type', {})}",
        f"  journal_prompts_pending={day_summary.get('journal_prompts_pending', 0)} "
        f"closing_run_present={day_summary.get('closing_run_present', False)}",
        "",
        f"Runs ({len(runs)}):",
    ]
    if not runs:
        lines.append("  (none)")
    else:
        for r in runs:
            lines.append(
                f"  - {r.run_id} [{r.trigger}] {r.status} "
                f"candles={r.candles_written} quotes={r.quotes_written}"
            )
    lines.append("")
    lines.append(f"Decisions ({len(decisions)}):")
    if not decisions:
        lines.append("  (none)")
    else:
        for d in decisions:
            inst = d.instrument_id or "-"
            lines.append(
                f"  - {d.decision_id} {d.decision_type} {inst} {d.direction} "
                f"stages={d.trace_stage_count}: {d.explanation}"
            )
    lines.append("")
    lines.append(f"Journal prompts ({len(journal_prompts)}):")
    if not journal_prompts:
        lines.append("  (none — all decisions journaled, or no decisions)")
    else:
        for p in journal_prompts:
            lines.append(f"  - {p.prompt}")
    if reasons:
        lines.append("")
        lines.append("Degradation:")
        for reason in reasons:
            lines.append(f"  - {reason}")
    return "\n".join(lines) + "\n"
