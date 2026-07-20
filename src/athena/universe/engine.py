"""Universe Engine (M2.4, R-4).

Answers one question: "Which instruments are eligible for further analysis?" —
by applying deterministic, configuration-driven eligibility rules to each
instrument independently. It never ranks, scores, or selects what to trade.

Also publishes constituent advances/declines per sector as a canonical output
(completing the data dependency anticipated by Sector Health, M2.3) — without
ever calling the Sector Health Engine.

Pure and replayable: injected ``as_of``, Decimal math, thresholds from
universe.json. Regime/Market-Health/Sector-Health-aware but dependent on none.

Note: ``max_universe_size`` is advisory only. Dropping eligible instruments to
meet a size cap would require ranking, which is out of scope here — so all
eligible instruments are included and the cap is reported in the summary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from athena.calendar.engine import CalendarEngine
from athena.config.models import UniverseConfig
from athena.data.validation.calendar_expectations import trading_days_between
from athena.domain.market import Candle, Instrument, Universe, UniverseMember
from athena.universe.models import RuleEvidence, UniverseAssessment


@dataclass(frozen=True, slots=True)
class UniverseResult:
    """The canonical universe plus per-instrument assessments and breadth export."""

    universe: Universe
    assessments: tuple[UniverseAssessment, ...]
    constituent_breadth: Mapping[str, tuple[int, int]]
    summary: Mapping[str, int]


class UniverseEngine:
    """Deterministic, explainable investable-universe construction."""

    def __init__(self, config: UniverseConfig) -> None:
        self._config = config

    def build(
        self,
        instruments: Sequence[Instrument],
        candles_by_instrument: Mapping[str, Sequence[Candle]],
        *,
        as_of: datetime,
        sector_by_instrument: Mapping[str, str] | None = None,
        calendar: CalendarEngine | None = None,
        history_window_days: int | None = None,
        cycle_id: str = "premarket",
    ) -> UniverseResult:
        assessments: list[UniverseAssessment] = []
        members: list[UniverseMember] = []

        for instrument in sorted(instruments, key=lambda i: i.instrument_id):
            candles = sorted(candles_by_instrument.get(instrument.instrument_id, ()),
                             key=lambda c: c.ts_open)
            evidence = self._evaluate(instrument, candles, as_of, calendar, history_window_days)
            failed = [e for e in evidence if not e.passed]
            included = not failed
            if included:
                trace = tuple(e.explanation for e in evidence)
                members.append(UniverseMember(instrument_id=instrument.instrument_id,
                                              inclusion_trace=trace))
                summary = f"included: passed all {len(evidence)} eligibility rules"
                assessments.append(UniverseAssessment(
                    instrument_id=instrument.instrument_id, included=True,
                    exclusion_reasons=(), evidence=evidence, eligibility_summary=summary))
            else:
                reasons = tuple(f"{e.rule}: {e.explanation}" for e in failed)
                summary = f"excluded: failed {len(failed)}/{len(evidence)} rule(s)"
                assessments.append(UniverseAssessment(
                    instrument_id=instrument.instrument_id, included=False,
                    exclusion_reasons=reasons, evidence=evidence, eligibility_summary=summary))

        universe = Universe(
            universe_id=f"universe-{as_of.date().isoformat()}",
            universe_date=as_of.date(), cycle_id=cycle_id, members=tuple(members))
        breadth = self._constituent_breadth(members, candles_by_instrument, sector_by_instrument)
        summary = {
            "evaluated": len(assessments),
            "included": len(members),
            "excluded": len(assessments) - len(members),
            "configured_max": self._config.max_universe_size,
        }
        return UniverseResult(universe=universe, assessments=tuple(assessments),
                              constituent_breadth=breadth, summary=summary)

    # ------------------------------------------------------------------ rules

    def _evaluate(
        self, instrument: Instrument, candles: Sequence[Candle], as_of: datetime,
        calendar: CalendarEngine | None, history_window_days: int | None,
    ) -> tuple[RuleEvidence, ...]:
        cfg = self._config
        rules: list[RuleEvidence] = []

        # Independent instrument-metadata rules.
        rules.append(RuleEvidence(
            "active_status", instrument.status == "ACTIVE",
            f"status={instrument.status} (required ACTIVE)",
            {"status": instrument.status}))
        rules.append(RuleEvidence(
            "supported_series", instrument.series in cfg.supported_series,
            f"series={instrument.series} (supported {cfg.supported_series})",
            {"series": instrument.series}))
        rules.append(RuleEvidence(
            "eligible_exchange", instrument.exchange in cfg.eligible_exchanges,
            f"exchange={instrument.exchange} (eligible {cfg.eligible_exchanges})",
            {"exchange": instrument.exchange}))

        # Data-presence rule.
        has_data = len(candles) > 0
        rules.append(RuleEvidence(
            "data_present", has_data,
            f"{len(candles)} candle(s) available" if has_data else "no candle data (missing dataset)",
            {"candle_count": str(len(candles))}))

        if not has_data:
            # Data-dependent rules cannot be evaluated → fail with a clear reason.
            for rule in ("min_history", "min_liquidity"):
                rules.append(RuleEvidence(rule, False, "not evaluable: no candle data", {}))
            return tuple(rules)

        rules.append(RuleEvidence(
            "min_history", len(candles) >= cfg.min_trading_history_days,
            f"{len(candles)} candle(s) vs minimum {cfg.min_trading_history_days}",
            {"candle_count": str(len(candles)), "min_required": str(cfg.min_trading_history_days)}))

        avg_volume = Decimal(sum(c.volume for c in candles)) / Decimal(len(candles))
        rules.append(RuleEvidence(
            "min_liquidity", avg_volume >= Decimal(cfg.min_avg_daily_volume),
            f"avg volume {avg_volume:.0f} vs minimum {cfg.min_avg_daily_volume}",
            {"avg_volume": f"{avg_volume:.2f}", "min_required": str(cfg.min_avg_daily_volume)}))

        # Optional data-completeness rule (needs a calendar + window to define expectations).
        if calendar is not None and history_window_days is not None:
            rules.append(self._completeness_rule(candles, as_of, calendar, history_window_days))

        return tuple(rules)

    def _completeness_rule(
        self, candles: Sequence[Candle], as_of: datetime,
        calendar: CalendarEngine, window_days: int,
    ) -> RuleEvidence:
        start = as_of.date() - timedelta(days=window_days)
        expected = trading_days_between(calendar, start, as_of.date())
        present = {c.ts_open.date() for c in candles}
        have = sum(1 for d in expected if d in present)
        completeness = Decimal(have) / Decimal(len(expected)) if expected else Decimal(0)
        threshold = Decimal(str(self._config.min_history_completeness))
        return RuleEvidence(
            "data_completeness", completeness >= threshold,
            f"completeness {completeness:.3f} ({have}/{len(expected)} expected sessions) "
            f"vs minimum {threshold}",
            {"present": str(have), "expected": str(len(expected)),
             "completeness": f"{completeness:.4f}", "min_required": str(threshold)})

    # ------------------------------------------------------- constituent breadth

    @staticmethod
    def _constituent_breadth(
        members: Sequence[UniverseMember],
        candles_by_instrument: Mapping[str, Sequence[Candle]],
        sector_by_instrument: Mapping[str, str] | None,
    ) -> dict[str, tuple[int, int]]:
        """Advances/declines per sector across included instruments (canonical export
        for Sector Health, M2.3). Latest close vs prior close decides up/down."""
        if not sector_by_instrument:
            return {}
        tally: dict[str, list[int]] = {}
        for member in members:
            sector = sector_by_instrument.get(member.instrument_id)
            if sector is None:
                continue
            candles = sorted(candles_by_instrument.get(member.instrument_id, ()),
                             key=lambda c: c.ts_open)
            if len(candles) < 2:
                continue
            adv_dec = tally.setdefault(sector, [0, 0])
            if candles[-1].close > candles[-2].close:
                adv_dec[0] += 1
            elif candles[-1].close < candles[-2].close:
                adv_dec[1] += 1
        return {sector: (a, d) for sector, (a, d) in sorted(tally.items())}
