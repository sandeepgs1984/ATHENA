"""Evidence Aggregation Engine (M3.1).

Gathers all approved intelligence into a single immutable EvidenceBundle,
preserving provenance and detecting missing required sources. It aggregates
only — no scoring, no signals, no decisions, no transformation of the
underlying evidence.

Pure and replayable: injected ``as_of``, no I/O, no clock reads, deterministic
ordering (fixed source order; sectors and items in their existing deterministic
order).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from athena.data.corporate_actions.evidence import AdjustmentEvidence
from athena.data.validation.reports import ValidationReport
from athena.evidence.models import EvidenceBundle, EvidenceItem, EvidenceSource
from athena.market_health.models import MarketHealthResult
from athena.regime.models import RegimeResult
from athena.sector_health.models import SectorHealthResult
from athena.universe.engine import UniverseResult


class EvidenceAggregationEngine:
    """Assemble approved intelligence into one provenance-preserving evidence graph."""

    def aggregate(
        self,
        *,
        as_of: datetime,
        regime: RegimeResult | None = None,
        market_health: MarketHealthResult | None = None,
        sector_health: Mapping[str, SectorHealthResult] | None = None,
        universe: UniverseResult | None = None,
        corporate_action_evidence: Sequence[AdjustmentEvidence] | None = None,
        validation_reports: Sequence[ValidationReport] | None = None,
        required_sources: Sequence[EvidenceSource] = (),
    ) -> EvidenceBundle:
        items: list[EvidenceItem] = []

        if regime is not None:
            ts = regime.assessment.ts
            for ev in regime.evidence:
                items.append(EvidenceItem(
                    source=EvidenceSource.REGIME, kind=ev.dimension,
                    reference_id=ev.evidence_id, ts=ts, explanation=ev.explanation,
                    payload=ev))

        if market_health is not None:
            ts = market_health.assessment.ts
            for ev in market_health.evidence:
                items.append(EvidenceItem(
                    source=EvidenceSource.MARKET_HEALTH, kind=ev.dimension,
                    reference_id=ev.evidence_id, ts=ts, explanation=ev.explanation,
                    payload=ev))

        if sector_health is not None:
            for sector in sorted(sector_health):
                result = sector_health[sector]
                ts = result.assessment.ts
                for ev in result.evidence:
                    items.append(EvidenceItem(
                        source=EvidenceSource.SECTOR_HEALTH, kind=f"{sector}:{ev.dimension}",
                        reference_id=ev.evidence_id, ts=ts, explanation=ev.explanation,
                        payload=ev))

        if universe is not None:
            us_ts = datetime.combine(universe.universe.universe_date, as_of.timetz())
            for assessment in universe.assessments:
                items.append(EvidenceItem(
                    source=EvidenceSource.UNIVERSE, kind=assessment.instrument_id,
                    reference_id=assessment.instrument_id, ts=us_ts,
                    explanation=assessment.eligibility_summary, payload=assessment))

        if corporate_action_evidence is not None:
            for ev in corporate_action_evidence:
                items.append(EvidenceItem(
                    source=EvidenceSource.CORPORATE_ACTION, kind=ev.action_type.value,
                    reference_id=ev.action_id, ts=as_of, explanation=ev.explanation,
                    payload=ev))

        if validation_reports is not None:
            for report in validation_reports:
                items.append(EvidenceItem(
                    source=EvidenceSource.VALIDATION, kind=report.validation_type.value,
                    reference_id=f"{report.validation_type.value}-{report.ts.isoformat()}",
                    ts=report.ts, explanation=report.explanation, payload=report))

        present = {item.source for item in items}
        missing = tuple(s.value for s in required_sources if s not in present)
        provenance = {
            source.value: sum(1 for item in items if item.source is source)
            for source in EvidenceSource if any(item.source is source for item in items)
        }
        return EvidenceBundle(
            bundle_id=f"evidence-{as_of.isoformat()}",
            as_of=as_of, items=tuple(items), missing_sources=missing,
            provenance=provenance,
        )
