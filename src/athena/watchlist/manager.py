"""Watchlist Manager (M4.3).

Answers one question: "Which instruments deserve ongoing attention based on
ATHENA's completed decisions?" It consumes an immutable ``DailyScanReport``
(M4.2) and maintains deterministic, explainable named watchlists.

It COORDINATES STATE ONLY: it never executes analytical engines, never
recalculates a decision, and never invents a conclusion — it organises and
preserves outputs already produced by the analytical pipeline and scanner.

Purity and replayability: :meth:`apply` is a pure function of
``(config, previous, scan_report, as_of)``. There is no hidden state and no
clock read (``as_of`` is injected), so identical inputs always produce identical
watchlist state. History is append-only — past state is never overwritten.
"""

from __future__ import annotations

from datetime import datetime

from athena.config.models import (
    WatchlistConfig,
    WatchlistDecisionRuleCfg,
    WatchlistDefCfg,
    WatchlistTrendRuleCfg,
)
from athena.runtime.models import ExecutionStatus
from athena.scanner.models import DailyScanReport, InstrumentScanResult
from athena.watchlist.models import (
    WatchlistChange,
    WatchlistChangeType,
    WatchlistEntry,
    WatchlistSnapshot,
    WatchlistSummary,
)

# Per-instrument decision facts observed in one scan.
_Observed = dict[str, "_DecisionFacts"]


class _DecisionFacts:
    __slots__ = ("decision_id", "decision_ts", "decision_type", "explanation")

    def __init__(self, decision_type: str, decision_id: str,
                 explanation: str, decision_ts: datetime) -> None:
        self.decision_type = decision_type
        self.decision_id = decision_id
        self.explanation = explanation
        self.decision_ts = decision_ts


class WatchlistManager:
    """Deterministic, config-driven organiser of completed decision outcomes."""

    def __init__(self, config: WatchlistConfig) -> None:
        self._config = config

    def apply(
        self,
        scan_report: DailyScanReport,
        *,
        as_of: datetime,
        previous: WatchlistSnapshot | None = None,
    ) -> WatchlistSnapshot:
        """Fold one scan report into a new immutable watchlist snapshot.

        ``previous`` supplies prior membership (for retention and removal) and
        the prior scan's decisions (for trend rules). Omit it for the first scan.
        """
        if as_of.tzinfo is None:
            raise ValueError("WatchlistManager.apply requires timezone-aware as_of")

        observed = self._observe(scan_report)
        prev_entries = {(e.watchlist, e.instrument_id): e
                        for e in (previous.entries if previous else ())}
        prev_decisions = dict(previous.observed_decisions) if previous else {}

        entries: list[WatchlistEntry] = []
        changes: list[WatchlistChange] = []
        counts: dict[str, int] = {}
        added = retained = removed = 0

        for wl in self._config.watchlists:
            current: dict[str, str] = {}  # instrument_id -> match detail
            for instrument_id in sorted(observed):
                member, detail = self._evaluate(wl, instrument_id,
                                                observed[instrument_id].decision_type,
                                                prev_decisions)
                if member:
                    current[instrument_id] = detail

            for instrument_id in sorted(current):
                facts = observed[instrument_id]
                detail = current[instrument_id]
                prev_entry = prev_entries.get((wl.name, instrument_id))
                if prev_entry is None:
                    entered_as_of = as_of
                    added += 1
                    changes.append(WatchlistChange(
                        change_type=WatchlistChangeType.ADDED, watchlist=wl.name,
                        instrument_id=instrument_id, reason=f"entered {wl.name}: {detail}",
                        as_of=as_of, scan_id=scan_report.scan_id,
                        decision_type=facts.decision_type))
                else:
                    entered_as_of = prev_entry.entered_as_of
                    retained += 1
                    changes.append(WatchlistChange(
                        change_type=WatchlistChangeType.RETAINED, watchlist=wl.name,
                        instrument_id=instrument_id, reason=f"remained in {wl.name}: {detail}",
                        as_of=as_of, scan_id=scan_report.scan_id,
                        decision_type=facts.decision_type))
                entries.append(WatchlistEntry(
                    watchlist=wl.name, instrument_id=instrument_id,
                    decision_type=facts.decision_type, decision_id=facts.decision_id,
                    explanation=facts.explanation, decision_ts=facts.decision_ts,
                    scan_id=scan_report.scan_id, entered_as_of=entered_as_of,
                    last_seen_as_of=as_of))
            counts[wl.name] = len(current)

            # Removals: prior members of THIS watchlist no longer satisfying the rule.
            for instrument_id in sorted(
                inst for (name, inst) in prev_entries if name == wl.name
            ):
                if instrument_id in current:
                    continue
                if instrument_id in observed:
                    reason = (f"exited {wl.name}: rule no longer satisfied "
                              f"(decision {observed[instrument_id].decision_type})")
                else:
                    reason = f"exited {wl.name}: not present in current scan"
                removed += 1
                changes.append(WatchlistChange(
                    change_type=WatchlistChangeType.REMOVED, watchlist=wl.name,
                    instrument_id=instrument_id, reason=reason, as_of=as_of,
                    scan_id=scan_report.scan_id,
                    decision_type=(observed[instrument_id].decision_type
                                   if instrument_id in observed else None)))

        summary = WatchlistSummary(counts=counts, added=added,
                                   retained=retained, removed=removed)
        observed_decisions = {inst: facts.decision_type
                              for inst, facts in observed.items()}
        return WatchlistSnapshot(
            snapshot_id=f"watchlist-{as_of.isoformat()}", as_of=as_of,
            scan_id=scan_report.scan_id, entries=tuple(entries),
            changes=tuple(changes), observed_decisions=observed_decisions,
            summary=summary)

    # ------------------------------------------------------------- internals

    @staticmethod
    def _observe(scan_report: DailyScanReport) -> _Observed:
        """Extract completed decision facts, one per instrument. Fails loudly on
        duplicate instruments — a scan report must classify each instrument once."""
        observed: _Observed = {}
        for result in scan_report.results:
            if not _has_decision(result):
                continue
            if result.instrument_id in observed:
                raise ValueError(
                    f"duplicate instrument in scan report: {result.instrument_id}")
            report = result.report
            observed[result.instrument_id] = _DecisionFacts(
                decision_type=result.decision_type or "",
                decision_id=report.decision_id,
                explanation=_explanation(report),
                decision_ts=report.ts)
        return observed

    def _evaluate(
        self,
        wl: WatchlistDefCfg,
        instrument_id: str,
        decision_type: str,
        prev_decisions: dict[str, str],
    ) -> tuple[bool, str]:
        """Return (is_member, human match detail) for one instrument and rule."""
        rule = wl.rule
        if isinstance(rule, WatchlistDecisionRuleCfg):
            if decision_type in rule.decisions:
                return True, f"decision {decision_type}"
            return False, ""
        if isinstance(rule, WatchlistTrendRuleCfg):
            prev = prev_decisions.get(instrument_id)
            if prev is None:
                return False, ""
            ranks = self._config.decision_rank
            cur_rank = ranks.get(decision_type)
            prev_rank = ranks.get(prev)
            if cur_rank is None or prev_rank is None:
                return False, ""
            improving = cur_rank > prev_rank
            weakening = cur_rank < prev_rank
            if rule.direction == "improving" and improving:
                return True, (f"decision improved {prev}({prev_rank})"
                              f"→{decision_type}({cur_rank})")
            if rule.direction == "weakening" and weakening:
                return True, (f"decision weakened {prev}({prev_rank})"
                              f"→{decision_type}({cur_rank})")
            return False, ""
        raise ValueError(f"unsupported watchlist rule: {type(rule).__name__}")


def _has_decision(result: InstrumentScanResult) -> bool:
    return (result.status is ExecutionStatus.COMPLETED
            and result.report is not None
            and result.decision_type is not None)


def _explanation(report) -> str:
    """Faithfully lift the decision's own explanation from its report."""
    decision = report.machine.get("decision")
    if isinstance(decision, dict) and decision.get("explanation"):
        return str(decision["explanation"])
    return f"decision {report.decision_type}"
