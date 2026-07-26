"""Owner validation pipeline for dry-run cycles (D-V2 / D-V3).

After ingest: UniverseEngine eligibility on ``owner_candidates``, then
DailyMarketScanner + DecisionEngine on included names. Persists decisions/
traces and returns ``universe_members`` + ``qualified_today`` for run detail.

Heavy analytical imports are deferred inside ``run`` / ``_scan_eligible`` to
avoid circular import chains through ``athena.scanner`` at package import time.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import DecisionType, RunTrigger, Timeframe
from athena.domain.market import Candle, Instrument, MarketSnapshot
from athena.ops.owner_candidates import (
    DEFAULT_EXCHANGE,
    SqliteCandidateStore,
    display_symbol,
    normalize_candidate_symbol,
    to_instrument_id,
)
from athena.universe.engine import UniverseEngine


class _MonoClock:
    def __init__(self) -> None:
        self._t = 0.0

    def __call__(self) -> float:
        self._t += 1.0
        return self._t


class OwnerValidationPipeline:
    """DryRunPipeline: eligibility + WATCH/TRADE qualify for owner candidates."""

    def __init__(
        self,
        repo: SqliteRepository,
        config_dir: Path,
        *,
        exchange: str = DEFAULT_EXCHANGE,
        enable_scan: bool = True,
        symbols_filter: Sequence[str] | None = None,
    ) -> None:
        self._repo = repo
        self._config_dir = Path(config_dir)
        self._exchange = exchange.strip().upper()
        self._enable_scan = enable_scan
        self._store = SqliteCandidateStore(repo)
        self._symbols_filter = (
            tuple(normalize_candidate_symbol(s) for s in symbols_filter)
            if symbols_filter
            else None
        )

    def run(
        self,
        trigger: RunTrigger,
        *,
        as_of: datetime,
        ingestion: IngestionResult,
        run_id: str,
    ) -> Mapping[str, object]:
        candidates = self._store.list_candidates(active_only=True)
        if self._symbols_filter:
            wanted = set(self._symbols_filter)
            candidates = [c for c in candidates if c.symbol in wanted]
        max_raw = os.environ.get("ATHENA_MAX_CANDIDATES", "").strip()
        if max_raw and self._symbols_filter is None:
            cap = int(max_raw)
            if cap < 1:
                raise ValueError("ATHENA_MAX_CANDIDATES must be >= 1")
            candidates = candidates[:cap]
        if not candidates:
            return {
                "mode": "ingest_only",
                "reason": "no_owner_candidates",
                "universe_members": {},
                "universe_source": "empty",
                "qualified_today": [],
                "message": "Add symbols on Market Intelligence to validate.",
            }

        cfg = load_config(self._config_dir)
        calendar = CalendarEngine.from_config_dir(self._config_dir, cfg.market)

        instruments: list[Instrument] = []
        candles_by_id: dict[str, list[Candle]] = {}
        for cand in candidates:
            inst = self._resolve_instrument(cand.symbol)
            instruments.append(inst)
            candles_by_id[inst.instrument_id] = self._repo.list_candles_recent(
                inst.instrument_id, Timeframe.D1, limit=500
            )

        universe_engine = UniverseEngine(cfg.universe)
        result = universe_engine.build(
            instruments,
            candles_by_id,
            as_of=as_of,
            calendar=calendar,
            cycle_id=trigger.value.lower(),
        )

        universe_members: dict[str, dict[str, object]] = {}
        included_ids: list[str] = []
        for assessment in result.assessments:
            sym = display_symbol(assessment.instrument_id)
            evidence_trace = [e.explanation for e in assessment.evidence]
            universe_members[sym] = {
                "symbol": sym,
                "instrument_id": assessment.instrument_id,
                "included": assessment.included,
                "trace": evidence_trace,
                "exclusion_reasons": list(assessment.exclusion_reasons),
                "eligibility_summary": assessment.eligibility_summary,
                "evidence": [
                    {
                        "rule": e.rule,
                        "passed": e.passed,
                        "explanation": e.explanation,
                        "inputs": dict(e.inputs),
                    }
                    for e in assessment.evidence
                ],
            }
            if assessment.included:
                included_ids.append(assessment.instrument_id)

        regime_payload = self._maybe_regime(
            cfg, as_of=as_of, candles_by_id=candles_by_id
        )

        qualified: list[dict[str, object]] = []
        scan_stats: dict[str, object] = {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
        }
        decision_counts: dict[str, int] = {}
        scan_regime: dict[str, object] | None = None
        decision_reports: dict[str, dict[str, object]] = {}

        if self._enable_scan and included_ids:
            # Use the orchestrator's own run_id (passed in) rather than
            # recomputing one locally from (trigger, as_of) — that used to
            # silently diverge from DryRunCycleOrchestrator's actual
            # persisted run_id whenever as_of collapsed to the same value
            # across separate invocations (e.g. every off-hours REFRESH),
            # causing each Decision saved here to keep pointing at a run
            # whose own detail_json had since been overwritten by a
            # different symbol's validation — the real cause behind
            # Score/Confidence/Risk still showing "Unknown" even after a
            # freshly-succeeded re-validate.
            cycle_id = f"{as_of.date().isoformat()}-{trigger.value.lower()}"
            snap = self._resolve_snapshot(as_of, candles_by_id)
            if snap is None:
                snap = MarketSnapshot(
                    ts=as_of,
                    indices={},
                    breadth_advances=0,
                    breadth_declines=0,
                    india_vix=None,
                )
            scan_report, scan_regime = self._scan_eligible(
                included_ids,
                as_of=as_of,
                run_id=run_id,
                cycle_id=cycle_id,
                candles_by_id=candles_by_id,
                snapshot=snap,
                cfg=cfg,
            )
            scan_stats = {
                "total": scan_report.statistics.total,
                "successful": scan_report.statistics.successful,
                "failed": scan_report.statistics.failed,
                "skipped": scan_report.statistics.skipped,
            }
            decision_counts = dict(scan_report.summary.decision_counts)
            qualified = self._qualified_from_repo(as_of, included_ids)
            decision_reports = {
                result.report.decision_id: result.report.to_dict()
                for result in scan_report.results
                if result.report is not None
            }

        if regime_payload is None and scan_regime is not None:
            regime_payload = scan_regime

        detail: dict[str, object] = {
            "mode": "owner_validation",
            "universe_members": universe_members,
            "universe_source": "owner_candidates",
            "universe_summary": dict(result.summary),
            "validation_summary": {
                "candidates": len(candidates),
                "evaluated": int(result.summary.get("evaluated", 0)),
                "eligible": int(result.summary.get("included", 0)),
                "excluded": int(result.summary.get("excluded", 0)),
                "qualified_watch_trade": len(qualified),
                "decision_counts": decision_counts,
            },
            "qualified_today": qualified,
            "scan_statistics": scan_stats,
            "decision_counts": decision_counts,
            "decision_reports": decision_reports,
            "candidates_evaluated": len(candidates),
            "ingestion": {
                "candles_written": ingestion.candles_written,
                "quotes_written": ingestion.quotes_written,
            },
        }
        if regime_payload is not None:
            detail["regime_assessment"] = regime_payload
        return detail

    def _resolve_instrument(self, symbol: str) -> Instrument:
        iid = to_instrument_id(symbol, exchange=self._exchange)
        for candidate_id in (iid, symbol.upper(), f"BSE:{symbol.upper()}"):
            found = self._repo.get_instrument(candidate_id)
            if found is not None:
                return found
        bare = symbol.upper()
        for inst in self._repo.list_instruments():
            if inst.symbol.upper() == bare:
                return inst
        return Instrument(
            instrument_id=iid,
            symbol=bare,
            exchange=self._exchange,
            series="EQ",
            status="ACTIVE",
        )

    def _maybe_regime(
        self,
        cfg,
        *,
        as_of: datetime,
        candles_by_id: Mapping[str, Sequence[Candle]],
    ) -> dict[str, object] | None:
        from athena.regime import RegimeEngine

        snap = self._resolve_snapshot(as_of, candles_by_id)
        index_candidates: list[str] = []
        if snap is not None and snap.indices:
            index_candidates.extend(snap.indices.keys())
        try:
            from athena.config.loader import load_kite_provider_config

            kite = load_kite_provider_config(self._config_dir)
            index_candidates.extend(kite.index_instruments)
        except Exception:
            pass
        index_candidates.extend(["NSE:NIFTY 50", "NIFTY50"])

        seen: set[str] = set()
        for index_id in index_candidates:
            if not index_id or index_id in seen:
                continue
            seen.add(index_id)
            index_candles = list(candles_by_id.get(index_id, ()))
            if len(index_candles) < 2:
                index_candles = self._repo.list_candles_recent(
                    index_id, Timeframe.D1, limit=500
                )
            if len(index_candles) < 2:
                continue
            try:
                regime = RegimeEngine(cfg.regime).assess(
                    index_id, index_candles, snap, as_of=as_of
                )
            except Exception:
                continue
            return self._regime_to_payload(regime)

        # Fall back: any equity series with enough bars (trend/gap still useful)
        for iid, series in candles_by_id.items():
            if len(series) < 2:
                continue
            try:
                regime = RegimeEngine(cfg.regime).assess(
                    iid, series, snap, as_of=as_of
                )
            except Exception:
                continue
            return self._regime_to_payload(regime)
        return None

    def _resolve_snapshot(
        self,
        as_of: datetime,
        candles_by_id: Mapping[str, Sequence[Candle]],
    ) -> MarketSnapshot | None:
        """Prefer persisted snapshot; fill India VIX from VIX candles when missing."""
        snap = self._repo.get_latest_snapshot()
        vix = snap.india_vix if snap is not None else None
        if vix is None:
            vix = self._vix_from_candles(candles_by_id)
        if snap is None:
            if vix is None:
                return None
            return MarketSnapshot(
                ts=as_of,
                indices={},
                breadth_advances=0,
                breadth_declines=0,
                india_vix=vix,
            )
        if snap.india_vix is None and vix is not None:
            return MarketSnapshot(
                ts=snap.ts,
                indices=dict(snap.indices),
                breadth_advances=snap.breadth_advances,
                breadth_declines=snap.breadth_declines,
                india_vix=vix,
            )
        return snap

    def _vix_from_candles(
        self, candles_by_id: Mapping[str, Sequence[Candle]]
    ) -> Decimal | None:
        vix_ids: list[str] = []
        try:
            from athena.config.loader import load_kite_provider_config

            kite = load_kite_provider_config(self._config_dir)
            if kite.india_vix_instrument:
                vix_ids.append(kite.india_vix_instrument)
        except Exception:
            pass
        vix_ids.extend(["NSE:INDIA VIX", "INDIA VIX"])
        seen: set[str] = set()
        for iid in vix_ids:
            if not iid or iid in seen:
                continue
            seen.add(iid)
            series = list(candles_by_id.get(iid, ()))
            if not series:
                series = self._repo.list_candles_recent(iid, Timeframe.D1, limit=5)
            if not series:
                continue
            last = max(series, key=lambda c: c.ts_open)
            try:
                return Decimal(str(last.close))
            except Exception:
                continue
        return None

    @staticmethod
    def _regime_to_payload(regime) -> dict[str, object]:
        labels = list(regime.assessment.labels)
        trend = next(
            (lb for lb in labels if "TREND" in lb or lb == "SIDEWAYS"), "UNKNOWN"
        )
        vol = next((lb for lb in labels if "VOLATILITY" in lb), "UNKNOWN")
        gap = next((lb for lb in labels if "GAP" in lb), "NO_GAP")
        explanation = regime.assessment.explanation or "; ".join(
            e.explanation for e in regime.evidence[:3]
        )
        return {
            "trend": trend,
            "volatility": vol,
            "gap": gap,
            "market_health": 0,
            "explanation": explanation
            or "Regime assessed from available daily candles.",
        }

    def _scan_eligible(
        self,
        included_ids: Sequence[str],
        *,
        as_of: datetime,
        run_id: str,
        cycle_id: str,
        candles_by_id: Mapping[str, Sequence[Candle]],
        snapshot: MarketSnapshot,
        cfg,
    ):
        from athena.confidence import ConfidenceEngine
        from athena.config.loader import (
            load_confidence_config,
            load_decision_config,
            load_market_health_config,
            load_risk_assessment_config,
            load_scoring_config,
        )
        from athena.decision import DecisionEngine
        from athena.evidence import EvidenceAggregationEngine, EvidenceSource
        from athena.indicators import IndicatorEngine, IndicatorName
        from athena.market_health import MarketHealthEngine
        from athena.regime import RegimeEngine
        from athena.risk import RiskEngine
        from athena.runtime import WorkflowEngine, WorkflowStage, build_definition
        from athena.scanner import DailyMarketScanner, InstrumentPlan, ScanCapture
        from athena.scoring import ScoringEngine

        scoring_cfg = load_scoring_config(self._config_dir)
        decision_cfg = load_decision_config(self._config_dir)
        confidence_cfg = load_confidence_config(self._config_dir)
        risk_cfg = load_risk_assessment_config(self._config_dir)
        market_health_cfg = load_market_health_config(self._config_dir)
        indicator_engine = IndicatorEngine(cfg.indicators)
        regime_engine = RegimeEngine(cfg.regime)
        market_health_engine = MarketHealthEngine(market_health_cfg)
        scoring_engine = ScoringEngine(scoring_cfg)
        confidence_engine = ConfidenceEngine(confidence_cfg)
        risk_engine = RiskEngine(risk_cfg)
        evidence_engine = EvidenceAggregationEngine()
        decision_engine = DecisionEngine(decision_cfg)
        scanner = DailyMarketScanner(WorkflowEngine(clock=_MonoClock()))

        index_id = next(iter(snapshot.indices.keys()), "NIFTY50")
        index_candles = list(candles_by_id.get(index_id, ()))
        if not index_candles:
            index_candles = self._repo.list_candles_recent(index_id, Timeframe.D1, limit=500)
        if not index_candles and included_ids:
            index_candles = list(candles_by_id.get(included_ids[0], ()))

        captured_regime: dict[str, object] = {"payload": None}
        shared_market_health: dict[str, object] = {"value": None}

        def builder(instrument_id: str) -> InstrumentPlan:
            cs = list(candles_by_id.get(instrument_id, ()))
            box: dict[str, Any] = {}

            def ind_stage(ctx):
                return {
                    "indicators": indicator_engine.compute_all(
                        [
                            IndicatorName.SMA,
                            IndicatorName.RSI,
                            IndicatorName.ADX,
                            IndicatorName.MACD,
                            IndicatorName.ATR,
                            IndicatorName.VOLUME_MA,
                        ],
                        cs,
                        as_of=ctx.as_of,
                    )
                }

            def reg_stage(ctx):
                series = index_candles if index_candles else cs
                regime = regime_engine.assess(
                    index_id, series, snapshot, as_of=ctx.as_of
                )
                if captured_regime["payload"] is None:
                    captured_regime["payload"] = self._regime_to_payload(regime)
                if shared_market_health["value"] is None:
                    shared_market_health["value"] = market_health_engine.assess(
                        index_id,
                        series,
                        snapshot,
                        as_of=ctx.as_of,
                        regime=regime,
                    )
                return {
                    "regime": regime,
                    "market_health": shared_market_health["value"],
                }

            def sco_stage(ctx):
                return {
                    "scoring": scoring_engine.score(
                        instrument_id,
                        as_of=ctx.as_of,
                        indicators=ctx.get("indicators"),
                        regime=ctx.get("regime"),
                        market_health=ctx.get("market_health"),
                    )
                }

            def conf_stage(ctx):
                evidence_bundle = evidence_engine.aggregate(
                    as_of=ctx.as_of,
                    regime=ctx.get("regime"),
                    market_health=ctx.get("market_health"),
                    required_sources=(EvidenceSource.REGIME,),
                )
                confidence = confidence_engine.assess(
                    as_of=ctx.as_of,
                    evidence_bundle=evidence_bundle,
                    scoring=ctx.get("scoring"),
                    indicators=ctx.get("indicators"),
                )
                return {
                    "evidence_bundle": evidence_bundle,
                    "confidence": confidence,
                }

            def risk_stage(ctx):
                return {
                    "risk": risk_engine.assess(
                        instrument_id,
                        as_of=ctx.as_of,
                        regime=ctx.get("regime"),
                        market_health=ctx.get("market_health"),
                        indicators=ctx.get("indicators"),
                    )
                }

            def dec_stage(ctx):
                outcome = decision_engine.decide(
                    instrument_id,
                    as_of=ctx.as_of,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    scoring=ctx.get("scoring"),
                    confidence=ctx.get("confidence"),
                    risk=ctx.get("risk"),
                    evidence_bundle=ctx.get("evidence_bundle"),
                    regime=ctx.get("regime"),
                    indicators=ctx.get("indicators"),
                    market_health=ctx.get("market_health"),
                )
                self._repo.save_decision(outcome.decision, trace=outcome.trace)
                box["cap"] = ScanCapture(
                    outcome=outcome,
                    scoring=ctx.get("scoring"),
                    confidence=ctx.get("confidence"),
                    risk=ctx.get("risk"),
                    evidence_bundle=ctx.get("evidence_bundle"),
                    indicators=ctx.get("indicators"),
                    regime=ctx.get("regime"),
                    market_health=ctx.get("market_health"),
                )
                return {"outcome": True}

            defn = build_definition(
                f"owner-val-{instrument_id}",
                [
                    WorkflowStage("indicators", ind_stage, produces=("indicators",)),
                    WorkflowStage(
                        "regime",
                        reg_stage,
                        produces=("regime", "market_health"),
                    ),
                    WorkflowStage(
                        "scoring",
                        sco_stage,
                        depends_on=("indicators", "regime"),
                        produces=("scoring",),
                    ),
                    WorkflowStage(
                        "confidence",
                        conf_stage,
                        depends_on=("scoring", "regime"),
                        produces=("evidence_bundle", "confidence"),
                    ),
                    WorkflowStage(
                        "risk",
                        risk_stage,
                        depends_on=("indicators", "regime"),
                        produces=("risk",),
                    ),
                    WorkflowStage(
                        "decision",
                        dec_stage,
                        depends_on=("scoring", "confidence", "risk"),
                        produces=("outcome",),
                    ),
                ],
            )
            return InstrumentPlan(definition=defn, collect=lambda: box.get("cap"))

        report = scanner.scan(list(included_ids), as_of=as_of, pipeline_builder=builder)
        return report, captured_regime["payload"]

    def _qualified_from_repo(
        self, as_of: datetime, included_ids: Sequence[str]
    ) -> list[dict[str, object]]:
        included = set(included_ids)
        day = as_of.date()
        out: list[dict[str, object]] = []
        for decision in self._repo.list_decisions(limit=2000):
            if decision.instrument_id not in included:
                continue
            if decision.ts.date() != day:
                continue
            if decision.decision_type not in (DecisionType.WATCH, DecisionType.TRADE):
                continue
            out.append(
                {
                    "symbol": display_symbol(decision.instrument_id),
                    "instrument_id": decision.instrument_id,
                    "decision_id": decision.decision_id,
                    "decision_type": decision.decision_type.value,
                    "explanation": decision.explanation,
                }
            )
        out.sort(key=lambda r: str(r["symbol"]))
        return out
