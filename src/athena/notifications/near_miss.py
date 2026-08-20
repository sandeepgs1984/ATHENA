"""Near-miss detection for the daily briefing (AUX-4a).

**Not a new analytical computation.** ATHENA persists no entry-price level for
anything short of a TRADE decision (``Decision.trade_plan`` is ``None`` unless
``decision_type is TRADE`` -- see ``domain/decision.py``), so "how close is
price to an entry band" has no persisted quantity to read for a WATCH
decision. What *is* already computed and persisted is the composite score a
WATCH decision fell short with, and the trade threshold it fell short of
(``decision/engine.py``'s own classification: WATCH vs TRADE is exactly this
comparison). The gap between them is the same arithmetic already shipped for
the decision counterfactual endpoint (M-X2,
``api/v1/services/decisions_service.py``'s ``get_decision_counterfactual``) --
read here a second time from the same persisted report, never re-derived.

A WATCH decision only counts as a near-miss when every quality gate already
passed. One blocked purely on a failed gate (liquidity, risk, etc.) is not
"close" in any honest sense -- it is blocked by something score proximity
does not describe, and folding it into this digest would misrepresent why it
isn't a TRADE.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from athena.config.models import DecisionThresholdsCfg
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType


@dataclass(frozen=True, slots=True)
class NearMissReading:
    """The composite score and its gap to the trade threshold, or ``None``
    fields when the underlying report cannot be read -- absence, not zero."""

    composite: Decimal | None
    score_gap: Decimal | None


def _fetch_score_block(repo: SqliteRepository, decision: Decision) -> Mapping[str, Any]:
    """Same navigation as decisions_service.py's _fetch_report: run detail ->
    pipeline -> decision_reports[decision_id] -> score. Duplicated rather than
    imported across the api/notifications layer boundary, same formula, kept
    honest by test parity rather than a shared private helper."""
    detail = repo.get_run_detail(decision.run_id)
    pipeline = detail.get("pipeline", detail)
    if not isinstance(pipeline, Mapping):
        return {}
    reports = pipeline.get("decision_reports")
    if not isinstance(reports, Mapping):
        return {}
    report = reports.get(decision.decision_id)
    if not isinstance(report, Mapping):
        return {}
    score = report.get("score")
    return score if isinstance(score, Mapping) else {}


def near_miss_reading(
    repo: SqliteRepository, decision: Decision, thresholds: DecisionThresholdsCfg,
) -> NearMissReading:
    """The composite score and its gap to the trade threshold for one
    decision, or absent fields if the persisted report cannot supply one."""
    score_block = _fetch_score_block(repo, decision)
    if score_block.get("status") != "OK":
        return NearMissReading(composite=None, score_gap=None)
    try:
        composite = Decimal(str(score_block.get("composite")))
    except (TypeError, ArithmeticError, ValueError):
        return NearMissReading(composite=None, score_gap=None)
    required = Decimal(thresholds.min_composite_for_trade)
    gap = max(Decimal(0), required - composite)
    return NearMissReading(composite=composite, score_gap=gap)


def is_near_miss(
    decision: Decision, reading: NearMissReading, *, max_gap: Decimal,
) -> bool:
    """A WATCH decision that passed every gate and sits within ``max_gap``
    composite points of the trade threshold.

    Excludes anything blocked by a failed gate: that decision's distance to
    TRADE is a safety check, not a score margin, and reporting it here would
    read as "almost tradeable" when the real blocker is unrelated to score.
    """
    if decision.decision_type is not DecisionType.WATCH:
        return False
    if any(not g.passed for g in decision.gate_results):
        return False
    if reading.score_gap is None:
        return False
    return reading.score_gap <= max_gap
