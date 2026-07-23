"""Rules-based playbook diagnostics analyzer (M10.4).

Deterministic, propose-only. Never mutates configuration files.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

from athena.config.models import DecisionConfig, DiagnosticsConfig, ScoringConfig
from athena.domain.decision import Decision, DecisionJournalEntry
from athena.domain.enums import DecisionType, QualityGate, RunStatus, UserAction
from athena.domain.run import RunRecord
from athena.diagnostics.models import (
    DiagnosticFinding,
    DiagnosticReport,
    DiagnosticStatus,
    TuningProposal,
)


class PlaybookDiagnosticsAnalyzer:
    """Analyze runs + optional decisions/journal → immutable DiagnosticReport."""

    def __init__(
        self,
        config: DiagnosticsConfig,
        *,
        scoring: ScoringConfig | None = None,
        decision: DecisionConfig | None = None,
        tzinfo: ZoneInfo,
    ) -> None:
        self._config = config
        self._scoring = scoring
        self._decision = decision
        self._tzinfo = tzinfo

    def analyze(
        self,
        *,
        as_of: datetime,
        runs: Sequence[RunRecord],
        decisions: Sequence[Decision] = (),
        journal: Sequence[DecisionJournalEntry] = (),
    ) -> DiagnosticReport:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        day = as_of.astimezone(self._tzinfo).date()
        report_id = f"diag-{day.isoformat()}"
        findings: list[DiagnosticFinding] = []
        proposals: list[TuningProposal] = []
        reasons: list[str] = []

        if not runs and not decisions and not journal:
            reasons.append("no_runs_decisions_or_journal")
            return DiagnosticReport(
                report_id=report_id,
                as_of=as_of,
                status=DiagnosticStatus.INSUFFICIENT_DATA,
                findings=(),
                proposals=(),
                input_digest=_digest([], [], []),
                degradation_reasons=tuple(reasons),
            )

        if not decisions:
            reasons.append("no_decision_inputs")
        if not journal:
            reasons.append("no_journal_inputs")

        findings.extend(self._ops_findings(runs))
        findings.extend(self._decision_mix_findings(decisions))
        findings.extend(self._gate_findings(decisions))
        proposals.extend(self._adherence_proposals(journal, decisions))
        proposals.extend(self._gate_weight_proposals(decisions))

        if not findings and not proposals and reasons:
            status = DiagnosticStatus.DEGRADED
        elif reasons:
            status = DiagnosticStatus.DEGRADED
        else:
            status = DiagnosticStatus.OK

        # INSUFFICIENT_DATA only when truly empty (handled above).
        # If we have runs-only, DEGRADED is correct.
        if not runs and not decisions and not journal:
            status = DiagnosticStatus.INSUFFICIENT_DATA

        findings_t = tuple(sorted(findings, key=lambda f: f.finding_id))
        proposals_t = tuple(sorted(proposals, key=lambda p: p.proposal_id))
        return DiagnosticReport(
            report_id=report_id,
            as_of=as_of,
            status=status,
            findings=findings_t,
            proposals=proposals_t,
            input_digest=_digest(runs, decisions, journal),
            degradation_reasons=tuple(reasons),
        )

    def _ops_findings(self, runs: Sequence[RunRecord]) -> list[DiagnosticFinding]:
        if not runs:
            return []
        failed = sum(1 for r in runs if r.status is RunStatus.FAILED)
        rate = failed / len(runs)
        if rate < self._config.failed_run_rate_watch:
            return []
        return [DiagnosticFinding(
            finding_id="ops-failed-run-rate",
            category="ops",
            severity="watch",
            summary=(
                f"failed run rate {rate:.0%} ({failed}/{len(runs)}) "
                f"exceeds watch threshold {self._config.failed_run_rate_watch:.0%}"
            ),
            evidence={"failed": failed, "total": len(runs), "rate": round(rate, 4)},
        )]

    def _decision_mix_findings(self, decisions: Sequence[Decision]) -> list[DiagnosticFinding]:
        if not decisions:
            return []
        weak = {
            DecisionType.INSUFFICIENT_DATA,
            DecisionType.DATA_VALIDATION_FAILED,
        }
        weak_n = sum(1 for d in decisions if d.decision_type in weak)
        share = weak_n / len(decisions)
        if share < self._config.insufficient_data_share_watch:
            return []
        return [DiagnosticFinding(
            finding_id="calibration-insufficient-data-share",
            category="calibration",
            severity="watch",
            summary=(
                f"insufficient/validation decision share {share:.0%} "
                f"({weak_n}/{len(decisions)}) — data quality, not weight tuning"
            ),
            evidence={"weak": weak_n, "total": len(decisions), "share": round(share, 4)},
        )]

    def _gate_findings(self, decisions: Sequence[Decision]) -> list[DiagnosticFinding]:
        failed_gates: Counter[str] = Counter()
        for d in decisions:
            for g in d.gate_results:
                if not g.passed:
                    failed_gates[g.gate.value] += 1
        if not failed_gates:
            return []
        top_gate, top_n = failed_gates.most_common(1)[0]
        return [DiagnosticFinding(
            finding_id="gates-top-failure",
            category="gates",
            severity="watch",
            summary=f"most frequent failed gate is {top_gate} ({top_n} failures)",
            evidence={"gate_counts": dict(sorted(failed_gates.items())), "top": top_gate},
        )]

    def _adherence_proposals(
        self,
        journal: Sequence[DecisionJournalEntry],
        decisions: Sequence[Decision],
    ) -> list[TuningProposal]:
        if not journal or self._decision is None:
            return []
        n = len(journal)
        rejectedish = sum(
            1 for j in journal
            if j.user_action in (UserAction.REJECTED, UserAction.IGNORED)
        )
        rate = rejectedish / n
        if rate < self._config.rejection_rate_actionable:
            return []

        current = self._decision.thresholds.min_composite_for_trade
        step = min(self._config.max_weight_step, 5)
        proposed = min(100, current + step)
        blocked = n < self._config.min_sample_size
        return [TuningProposal(
            proposal_id="prop-decision-min-composite",
            target_config="decision.json",
            parameter_path="thresholds.min_composite_for_trade",
            current_value=current,
            proposed_value=proposed,
            delta=proposed - current,
            rationale=(
                f"owner rejected/ignored {rejectedish}/{n} ({rate:.0%}) journaled "
                f"recommendations; raise trade composite threshold to be more selective"
            ),
            sample_size=n,
            metric_name="rejection_or_ignore_rate",
            metric_value=f"{rate:.4f}",
            blocked=blocked,
            block_reason="sample_below_minimum" if blocked else "",
        )]

    def _gate_weight_proposals(self, decisions: Sequence[Decision]) -> list[TuningProposal]:
        if not decisions or self._scoring is None:
            return []
        failed_gates: Counter[str] = Counter()
        for d in decisions:
            for g in d.gate_results:
                if not g.passed:
                    failed_gates[g.gate.value] += 1
        if not failed_gates:
            return []
        top_gate, top_n = failed_gates.most_common(1)[0]
        n = len(decisions)
        # RISK gate dominance → propose slight bump to market_quality weight (attention)
        # and a note — only RISK maps to a scoring-adjacent proposal in v1.
        if top_gate != QualityGate.RISK.value:
            return []

        current = self._scoring.weights.market_quality
        donor = self._scoring.weights.momentum
        step = min(self._config.max_weight_step, 5, donor)
        if step <= 0:
            return []
        proposed_mq = current + step
        proposed_mom = donor - step
        blocked = n < self._config.min_sample_size
        # Emit two linked proposals that keep sum 100.
        return [
            TuningProposal(
                proposal_id="prop-scoring-market-quality-up",
                target_config="scoring.json",
                parameter_path="weights.market_quality",
                current_value=current,
                proposed_value=proposed_mq,
                delta=step,
                rationale=(
                    f"RISK gate failed most often ({top_n}); shift +{step} to "
                    f"market_quality from momentum (paired proposal keeps sum 100)"
                ),
                sample_size=n,
                metric_name="risk_gate_failures",
                metric_value=str(top_n),
                blocked=blocked,
                block_reason="sample_below_minimum" if blocked else "",
            ),
            TuningProposal(
                proposal_id="prop-scoring-momentum-down",
                target_config="scoring.json",
                parameter_path="weights.momentum",
                current_value=donor,
                proposed_value=proposed_mom,
                delta=-step,
                rationale=(
                    f"paired with market_quality +{step} so scoring weights still sum to 100"
                ),
                sample_size=n,
                metric_name="risk_gate_failures",
                metric_value=str(top_n),
                blocked=blocked,
                block_reason="sample_below_minimum" if blocked else "",
            ),
        ]


def _digest(
    runs: Sequence[RunRecord],
    decisions: Sequence[Decision],
    journal: Sequence[DecisionJournalEntry],
) -> str:
    payload = {
        "runs": sorted(r.run_id for r in runs),
        "decisions": sorted(d.decision_id for d in decisions),
        "journal": sorted(f"{j.decision_ref}:{j.user_action.value}" for j in journal),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]
