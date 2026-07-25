"""Confidence Engine (M3.4).

Answers one question: "How trustworthy is the current evaluation?" It measures
the reliability and completeness of the accumulated artifacts — never market
direction, attractiveness, or risk.

Six independently explainable dimensions, each degrading to explicit UNKNOWN
when it cannot be determined:
- Evidence Completeness : required sources present in the EvidenceBundle
- Data Freshness        : validation reports passed vs total
- Indicator Availability: indicators OK vs total requested
- Cross-Engine Agreement: dispersion of known component scores (tight = agree)
- Unknown Ratio         : share of known artifacts across scores/indicators/evidence
- Consistency           : absence of contradictory signals among known scores

Pure and replayable: injected ``as_of``, Decimal math, config-driven weights and
thresholds. Consumes approved artifacts only — never raw providers/repositories.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from athena.confidence.models import (
    ConfidenceAssessment,
    ConfidenceContribution,
    ConfidenceDimension,
    ConfidenceLevel,
    ConfidenceStatus,
)
from athena.config.models import ConfidenceConfig
from athena.data.validation.reports import ValidationResult
from athena.evidence.models import EvidenceBundle, EvidenceSource
from athena.indicators.models import IndicatorName, IndicatorResult, IndicatorStatus
from athena.scoring.models import ScoringResult

_ZERO, _HUNDRED = Decimal(0), Decimal(100)
_TWO_DP = Decimal("0.01")


def _fmt2(value: Decimal) -> str:
    """Compact 2dp rendering for owner-facing explanations (avoids long Decimal tails)."""
    return format(value.quantize(_TWO_DP), "f")


def _clamp(value: Decimal) -> Decimal:
    return max(_ZERO, min(_HUNDRED, value))


class ConfidenceEngine:
    """Deterministic, artifact-driven reliability assessment."""

    def __init__(self, config: ConfidenceConfig) -> None:
        self._config = config

    def _level(self, value: Decimal) -> ConfidenceLevel:
        if value < Decimal(self._config.levels.low_below):
            return ConfidenceLevel.LOW
        if value >= Decimal(self._config.levels.high_at_or_above):
            return ConfidenceLevel.HIGH
        return ConfidenceLevel.MEDIUM

    def _ok(self, name, value, contributions, explanation) -> ConfidenceDimension:
        v = _clamp(value)
        return ConfidenceDimension(name=name, status=ConfidenceStatus.OK, value=v,
                                   level=self._level(v), contributions=tuple(contributions),
                                   explanation=explanation)

    @staticmethod
    def _unknown(name, explanation) -> ConfidenceDimension:
        return ConfidenceDimension(name=name, status=ConfidenceStatus.UNKNOWN, value=None,
                                   level=None, contributions=(), explanation=explanation)

    def assess(
        self,
        *,
        as_of: datetime,
        evidence_bundle: EvidenceBundle | None = None,
        scoring: ScoringResult | None = None,
        indicators: Mapping[IndicatorName, IndicatorResult] | None = None,
    ) -> ConfidenceAssessment:
        indicators = dict(indicators or {})
        dims = {
            "evidence_completeness": self._evidence_completeness(evidence_bundle),
            "data_freshness": self._data_freshness(evidence_bundle),
            "indicator_availability": self._indicator_availability(indicators),
            "cross_engine_agreement": self._cross_engine_agreement(scoring),
            "unknown_ratio": self._unknown_ratio(scoring, indicators, evidence_bundle),
            "consistency": self._consistency(scoring),
        }
        unknown_stats = self._unknown_stats(scoring, indicators, evidence_bundle)
        overall = self._overall(dims)
        return ConfidenceAssessment(
            assessment_id=f"confidence-{as_of.isoformat()}", ts=as_of, dimensions=dims,
            unknown_stats=unknown_stats, **overall)

    # ------------------------------------------------------------- dimensions

    def _evidence_completeness(self, bundle) -> ConfidenceDimension:
        if bundle is None:
            return self._unknown("evidence_completeness", "no evidence bundle available")
        present = len(bundle.present_sources)
        missing = len(bundle.missing_sources)
        total = present + missing
        if total == 0:
            return self._unknown("evidence_completeness", "evidence bundle has no sources")
        value = _HUNDRED * Decimal(present) / Decimal(total)
        contribs = [ConfidenceContribution("evidence_bundle", bundle.bundle_id,
                                           f"{present} present, {missing} missing required sources")]
        return self._ok("evidence_completeness", value, contribs,
                        f"evidence completeness {value:.1f}% ({present}/{total} sources)")

    def _data_freshness(self, bundle) -> ConfidenceDimension:
        if bundle is None:
            return self._unknown("data_freshness", "no evidence bundle available")
        validation_items = bundle.by_source(EvidenceSource.VALIDATION)
        if not validation_items:
            return self._unknown("data_freshness", "no validation evidence to assess freshness")
        passed = sum(1 for item in validation_items
                     if getattr(item.payload, "result", None) is ValidationResult.PASSED)
        total = len(validation_items)
        value = _HUNDRED * Decimal(passed) / Decimal(total)
        contribs = [ConfidenceContribution("evidence_bundle:validation", bundle.bundle_id,
                                           f"{passed}/{total} validation report(s) passed")]
        return self._ok("data_freshness", value, contribs,
                        f"data freshness {value:.1f}% ({passed}/{total} validations passed)")

    def _indicator_availability(self, indicators) -> ConfidenceDimension:
        if not indicators:
            return self._unknown("indicator_availability", "no indicators provided")
        known = sum(1 for r in indicators.values() if r.status is IndicatorStatus.OK)
        total = len(indicators)
        value = _HUNDRED * Decimal(known) / Decimal(total)
        contribs = [ConfidenceContribution("indicators", "indicator_set",
                                           f"{known}/{total} indicators available (OK)")]
        return self._ok("indicator_availability", value, contribs,
                        f"indicator availability {value:.1f}% ({known}/{total} OK)")

    def _cross_engine_agreement(self, scoring) -> ConfidenceDimension:
        if scoring is None:
            return self._unknown("cross_engine_agreement", "no scoring result available")
        known = [(dim, c.value) for dim, c in scoring.components.items()
                 if c.is_known and c.value is not None]
        if len(known) < 2:
            return self._unknown("cross_engine_agreement",
                                 "need at least two known component scores to compare")
        values = [v for _, v in known]
        spread = max(values) - min(values)
        value = _HUNDRED - spread  # tight cluster → high agreement
        contribs = [ConfidenceContribution("scoring", "components",
                                           f"score spread {_fmt2(spread)} across {len(known)} components "
                                           f"({', '.join(d for d, _ in known)})")]
        return self._ok("cross_engine_agreement", value, contribs,
                        f"cross-engine agreement {_fmt2(_clamp(value))} (score spread {_fmt2(spread)})")

    def _unknown_ratio(self, scoring, indicators, bundle) -> ConfidenceDimension:
        total = 0
        unknown = 0
        parts: list[str] = []
        if scoring is not None:
            comps = list(scoring.components.values())
            total += len(comps)
            u = sum(1 for c in comps if not c.is_known)
            unknown += u
            parts.append(f"{u}/{len(comps)} components unknown")
        if indicators:
            total += len(indicators)
            u = sum(1 for r in indicators.values() if r.status is not IndicatorStatus.OK)
            unknown += u
            parts.append(f"{u}/{len(indicators)} indicators unknown")
        if bundle is not None:
            present = len(bundle.present_sources)
            missing = len(bundle.missing_sources)
            total += present + missing
            unknown += missing
            parts.append(f"{missing} evidence source(s) missing")
        if total == 0:
            return self._unknown("unknown_ratio", "no artifacts to measure unknown ratio")
        ratio = Decimal(unknown) / Decimal(total)
        value = _HUNDRED * (Decimal(1) - ratio)
        contribs = [ConfidenceContribution("artifacts", "aggregate", "; ".join(parts))]
        return self._ok("unknown_ratio", value, contribs,
                        f"known-artifact ratio {value:.1f}% ({unknown}/{total} unknown)")

    def _consistency(self, scoring) -> ConfidenceDimension:
        if scoring is None:
            return self._unknown("consistency", "no scoring result available")
        known = {dim: c.value for dim, c in scoring.components.items()
                 if c.is_known and c.value is not None}
        if len(known) < 2:
            return self._unknown("consistency", "need at least two known scores to check consistency")
        gap = Decimal(self._config.consistency.divergence_gap)
        penalty = Decimal(self._config.consistency.contradiction_penalty)
        checks = [("trend", "momentum"), ("market_quality", "sector_quality")]
        contradictions = []
        for a, b in checks:
            if a in known and b in known and abs(known[a] - known[b]) >= gap:
                contradictions.append(f"{a} vs {b} diverge by {_fmt2(abs(known[a] - known[b]))}")
        value = _HUNDRED - penalty * Decimal(len(contradictions))
        detail = ("; ".join(contradictions) if contradictions
                  else "no contradictory signals among known scores")
        contribs = [ConfidenceContribution("scoring", "components", detail)]
        return self._ok("consistency", value, contribs,
                        f"consistency {_fmt2(_clamp(value))} ({len(contradictions)} contradiction(s))")

    # ------------------------------------------------------------- aggregate

    def _unknown_stats(self, scoring, indicators, bundle) -> dict[str, int]:
        stats = {"unknown_components": 0, "unknown_indicators": 0, "missing_evidence_sources": 0}
        if scoring is not None:
            stats["unknown_components"] = sum(1 for c in scoring.components.values() if not c.is_known)
        if indicators:
            stats["unknown_indicators"] = sum(
                1 for r in indicators.values() if r.status is not IndicatorStatus.OK)
        if bundle is not None:
            stats["missing_evidence_sources"] = len(bundle.missing_sources)
        return stats

    def _overall(self, dims) -> dict:
        weights = self._config.weights.model_dump()
        weighted_sum = _ZERO
        known_weight = 0
        total_weight = sum(int(w) for w in weights.values())
        for name, dim in dims.items():
            if dim.is_known and dim.value is not None:
                w = int(weights[name])
                weighted_sum += dim.value * Decimal(w)
                known_weight += w
        if known_weight == 0:
            return dict(overall_status=ConfidenceStatus.UNKNOWN, overall_value=None,
                        overall_level=None, completeness=_ZERO,
                        explanation="overall confidence UNKNOWN: no dimension could be determined")
        value = _clamp(weighted_sum / Decimal(known_weight))
        completeness = Decimal(known_weight) / Decimal(total_weight)
        return dict(overall_status=ConfidenceStatus.OK, overall_value=value,
                    overall_level=self._level(value), completeness=completeness,
                    explanation=(f"overall confidence {_fmt2(value)} ({self._level(value).value}), "
                                 f"completeness {completeness:.2f}"))
