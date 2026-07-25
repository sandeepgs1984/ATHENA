"""Decision Engine (M3.6).

Combines the completed analytical pipeline (evidence, scores, confidence, risk,
regime, indicators) into the first deterministic, explainable trading decisions.
Produces the frozen-domain ``Decision`` + ``DecisionTrace`` and honors every
frozen invariant (a TRADE carries a plan, a direction, and zero failed gates).

Answers only: "Given the approved artifacts, what deterministic decision
follows?" It never executes, sizes, or allocates capital. Trade plans use
analytical price levels (last close + ATR) — position_size is a provisional
unit, NOT a capital-based size (that belongs to a later capital layer).

Pure and replayable: injected ``as_of``, Decimal math, config-driven gates and
policy. Consumes approved artifacts only; never recalculates lower layers.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from decimal import Decimal

from athena.confidence.models import ConfidenceAssessment
from athena.config.models import DecisionConfig
from athena.decision.models import DecisionOutcome
from athena.domain.decision import (
    Decision,
    DecisionTrace,
    GateResult,
    TraceStage,
    TradePlan,
)
from athena.domain.enums import DecisionType, Direction, QualityGate
from athena.evidence.models import EvidenceBundle
from athena.indicators.models import IndicatorName, IndicatorResult, IndicatorStatus
from athena.regime.models import RegimeResult
from athena.risk.models import RiskAssessment
from athena.scoring.models import ScoringResult

_ZERO = Decimal(0)
_SCORE_QUANT = Decimal("0.01")

_TREND_DIRECTION = {"BULL_TREND": Direction.LONG, "BEAR_TREND": Direction.SHORT}

_GATE_PHRASE = {
    QualityGate.DATA: "data quality",
    QualityGate.EVIDENCE: "evidence coverage",
    QualityGate.RISK: "risk limits",
    QualityGate.EXPLAINABILITY: "explainability",
    QualityGate.CONFIDENCE: "confidence",
    QualityGate.MARKET: "market conditions",
}


def _fmt_score(value: Decimal) -> str:
    """Compact score for owner-facing explanations (avoids long Decimal tails)."""
    return format(value.quantize(_SCORE_QUANT), "f")


class DecisionEngine:
    """Deterministic combination of approved artifacts into auditable decisions."""

    def __init__(self, config: DecisionConfig) -> None:
        self._config = config

    def decide(
        self,
        instrument_id: str,
        *,
        as_of: datetime,
        run_id: str = "manual",
        cycle_id: str = "manual",
        scoring: ScoringResult | None = None,
        confidence: ConfidenceAssessment | None = None,
        risk: RiskAssessment | None = None,
        evidence_bundle: EvidenceBundle | None = None,
        regime: RegimeResult | None = None,
        indicators: Mapping[IndicatorName, IndicatorResult] | None = None,
        market_health=None,
        sector_health=None,
    ) -> DecisionOutcome:
        indicators = dict(indicators or {})
        decision_id = f"decision-{instrument_id}-{as_of.isoformat()}"
        score_ref = f"score-{instrument_id}-{as_of.isoformat()}" if scoring else None
        confidence_ref = confidence.assessment_id if confidence else None
        risk_ref = risk.assessment_id if risk else None

        gates = self._evaluate_gates(scoring, confidence, risk, evidence_bundle)

        # Non-actionable when scoring/composite is unavailable — never fabricate a decision.
        if scoring is None or scoring.composite.value is None:
            decision = Decision(
                decision_id=decision_id, ts=as_of, run_id=run_id, cycle_id=cycle_id,
                decision_type=DecisionType.INSUFFICIENT_DATA, instrument_id=instrument_id,
                score_ref=score_ref, confidence_ref=confidence_ref, risk_ref=risk_ref,
                gate_results=gates,
                explanation=(
                    "Needs more data — ATHENA could not compute a score for this symbol yet."
                ),
            )
            return DecisionOutcome(decision=decision,
                                   trace=self._trace(decision_id, regime, market_health,
                                                     sector_health, scoring, confidence, risk,
                                                     evidence_bundle, None))

        composite = scoring.composite.value
        thresholds = self._config.thresholds
        all_gates_pass = all(g.passed for g in gates)
        direction = self._direction(regime)
        plan = self._build_plan(direction, indicators, as_of)
        score_txt = _fmt_score(composite)
        watch_txt = _fmt_score(Decimal(thresholds.watch_composite))
        trade_txt = _fmt_score(Decimal(thresholds.min_composite_for_trade))

        if (all_gates_pass and composite >= Decimal(thresholds.min_composite_for_trade)
                and direction is not Direction.NONE and plan is not None):
            stance = "Buy setup" if direction is Direction.LONG else "Sell setup"
            decision = Decision(
                decision_id=decision_id, ts=as_of, run_id=run_id, cycle_id=cycle_id,
                decision_type=DecisionType.TRADE, instrument_id=instrument_id,
                direction=direction, score_ref=score_ref, confidence_ref=confidence_ref,
                risk_ref=risk_ref, gate_results=gates, trade_plan=plan,
                explanation=(
                    f"{stance} — score {score_txt}/100 clears the trade level ({trade_txt}) "
                    f"and all safety checks passed."
                ),
            )
        elif composite >= Decimal(thresholds.watch_composite):
            failed = [g for g in gates if not g.passed]
            if failed:
                needs = ", ".join(_GATE_PHRASE.get(g.gate, g.gate.value.lower()) for g in failed)
                explanation = (
                    f"Hold / watch — score {score_txt}/100 is interesting, but not ready "
                    f"to trade yet. Still blocked on: {needs}."
                )
            else:
                explanation = (
                    f"Hold / watch — score {score_txt}/100 is above watch ({watch_txt}) "
                    f"but below the trade level ({trade_txt})."
                )
            decision = Decision(
                decision_id=decision_id, ts=as_of, run_id=run_id, cycle_id=cycle_id,
                decision_type=DecisionType.WATCH, instrument_id=instrument_id,
                score_ref=score_ref, confidence_ref=confidence_ref, risk_ref=risk_ref,
                gate_results=gates,
                explanation=explanation,
            )
        else:
            decision = Decision(
                decision_id=decision_id, ts=as_of, run_id=run_id, cycle_id=cycle_id,
                decision_type=DecisionType.NO_TRADE, instrument_id=instrument_id,
                score_ref=score_ref, confidence_ref=confidence_ref, risk_ref=risk_ref,
                gate_results=gates,
                explanation=(
                    f"Pass — score {score_txt}/100 is below the watch level ({watch_txt}). "
                    f"No action suggested."
                ),
            )

        return DecisionOutcome(
            decision=decision,
            trace=self._trace(decision_id, regime, market_health, sector_health, scoring,
                              confidence, risk, evidence_bundle, decision.trade_plan))

    # ------------------------------------------------------------------ gates

    def _evaluate_gates(self, scoring, confidence, risk, bundle) -> tuple[GateResult, ...]:
        t = self._config.thresholds
        results: list[GateResult] = []

        # DATA: an evidence bundle exists and is complete.
        if bundle is None:
            results.append(GateResult(QualityGate.DATA, False, "no evidence bundle available"))
        else:
            results.append(GateResult(QualityGate.DATA, bundle.is_complete,
                                      f"evidence bundle complete={bundle.is_complete} "
                                      f"(missing {list(bundle.missing_sources)})"))

        # EVIDENCE: composite is known and completeness meets the minimum.
        if scoring is None or scoring.composite.value is None:
            results.append(GateResult(QualityGate.EVIDENCE, False, "no composite score"))
        else:
            ok = scoring.composite.completeness >= Decimal(str(t.min_evidence_completeness))
            results.append(GateResult(QualityGate.EVIDENCE, ok,
                                      f"score completeness {scoring.composite.completeness:.2f} "
                                      f"vs min {t.min_evidence_completeness}"))

        # RISK: overall risk known and within the maximum.
        if risk is None or risk.overall_value is None:
            results.append(GateResult(QualityGate.RISK, False, "no risk assessment"))
        else:
            ok = risk.overall_value <= Decimal(t.max_risk_for_trade)
            results.append(GateResult(QualityGate.RISK, ok,
                                      f"risk {risk.overall_value:.1f} vs max {t.max_risk_for_trade}"))

        # EXPLAINABILITY: composite known ⇒ every known component carries a trace (by construction).
        if scoring is None or scoring.composite.value is None:
            results.append(GateResult(QualityGate.EXPLAINABILITY, False, "no composite score"))
        else:
            results.append(GateResult(QualityGate.EXPLAINABILITY, True,
                                      "all known component scores carry contribution traces"))

        # CONFIDENCE: overall confidence known and at/above minimum.
        if confidence is None or confidence.overall_value is None:
            results.append(GateResult(QualityGate.CONFIDENCE, False, "no confidence assessment"))
        else:
            ok = confidence.overall_value >= Decimal(t.min_confidence_for_trade)
            results.append(GateResult(QualityGate.CONFIDENCE, ok,
                                      f"confidence {confidence.overall_value:.1f} vs min "
                                      f"{t.min_confidence_for_trade}"))

        # MARKET: market-quality score known and at/above the floor.
        mq = scoring.components.get("market_quality") if scoring else None
        if mq is None or not mq.is_known or mq.value is None:
            results.append(GateResult(QualityGate.MARKET, False, "market quality score unavailable"))
        else:
            ok = mq.value >= Decimal(t.market_floor)
            results.append(GateResult(QualityGate.MARKET, ok,
                                      f"market quality {mq.value:.1f} vs floor {t.market_floor}"))

        return tuple(results)

    # ------------------------------------------------------------- direction/plan

    @staticmethod
    def _direction(regime: RegimeResult | None) -> Direction:
        if regime is None:
            return Direction.NONE
        label = next((e.outcome.value for e in regime.evidence if e.dimension == "trend"), None)
        return _TREND_DIRECTION.get(label, Direction.NONE)

    def _build_plan(
        self, direction: Direction, indicators: Mapping[IndicatorName, IndicatorResult],
        as_of: datetime,
    ) -> TradePlan | None:
        if direction is Direction.NONE:
            return None
        atr = indicators.get(IndicatorName.ATR)
        sma = indicators.get(IndicatorName.SMA)
        if atr is None or atr.status is not IndicatorStatus.OK:
            return None
        if sma is None or sma.status is not IndicatorStatus.OK:
            return None
        last_close_raw = sma.evidence.inputs.get("last_close")
        if last_close_raw is None:
            return None
        atr_val = atr.values["value"]
        if atr_val <= _ZERO:
            return None  # no meaningful stop distance → no plan → not a TRADE

        cfg = self._config.plan
        last_close = Decimal(last_close_raw)
        stop_dist = atr_val * Decimal(str(cfg.atr_stop_multiple))
        target_dist = atr_val * Decimal(str(cfg.atr_target_multiple))
        if direction is Direction.LONG:
            stop = last_close - stop_dist
            target = last_close + target_dist
        else:
            stop = last_close + stop_dist
            target = last_close - target_dist
        risk_reward = target_dist / stop_dist  # constant analytical ratio
        return TradePlan(
            entry_low=last_close, entry_high=last_close, stop_loss=stop, targets=(target,),
            position_size=cfg.default_units,
            risk_amount=stop_dist * Decimal(cfg.default_units), risk_reward=risk_reward,
            valid_from=as_of, valid_until=as_of + timedelta(hours=cfg.validity_hours))

    # ------------------------------------------------------------------ trace

    def _trace(self, decision_id, regime, market_health, sector_health, scoring, confidence,
               risk, bundle, plan) -> DecisionTrace:
        stages: list[TraceStage] = []
        if regime is not None:
            stages.append(TraceStage("regime", (regime.assessment.assessment_id,),
                                     regime.assessment.explanation))
        if market_health is not None:
            stages.append(TraceStage("market_health", (market_health.assessment.assessment_id,),
                                     market_health.assessment.explanation))
        if sector_health is not None:
            stages.append(TraceStage("sector_health", (sector_health.assessment.assessment_id,),
                                     sector_health.assessment.explanation))
        if bundle is not None:
            stages.append(TraceStage("evidence", (bundle.bundle_id,),
                                     f"{len(bundle.items)} evidence item(s), "
                                     f"complete={bundle.is_complete}"))
        if scoring is not None:
            stages.append(TraceStage("score", (f"score-{scoring.instrument_id}",),
                                     scoring.composite.explanation))
        if confidence is not None:
            stages.append(TraceStage("confidence", (confidence.assessment_id,),
                                     confidence.explanation))
        if risk is not None:
            stages.append(TraceStage("risk", (risk.assessment_id,), risk.explanation))
        stages.append(TraceStage("decision", (decision_id,), "decision composed from the above"))
        if plan is not None:
            stages.append(TraceStage("trade_plan", (decision_id,),
                                     f"entry {_fmt_score(plan.entry_low)}, "
                                     f"stop {_fmt_score(plan.stop_loss)}, "
                                     f"target {_fmt_score(plan.targets[0])}, "
                                     f"RR {_fmt_score(plan.risk_reward)}"))
        return DecisionTrace(decision_ref=decision_id, stages=tuple(stages))
