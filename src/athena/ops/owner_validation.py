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
from athena.config.loader import (
    load_config,
    load_index_intelligence_config,
    load_market_health_config,
    load_sector_health_config,
    load_sector_index_mapping_config,
)
from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import DecisionType, RunStatus, RunTrigger, Timeframe
from athena.domain.market import Candle, Instrument, MarketSnapshot
from athena.market_health.aggregates import (
    compute_gap_stability,
    compute_liquidity_aggregate,
    compute_universe_breadth,
)
from athena.market_health.engine import MarketHealthEngine
from athena.market_health.score import construct_market_health_score
from athena.ops.owner_candidates import (
    DEFAULT_EXCHANGE,
    SqliteCandidateStore,
    display_symbol,
    normalize_candidate_symbol,
    to_instrument_id,
)
from athena.sector_health.engine import SectorHealthEngine
from athena.universe.engine import UniverseEngine


class _MonoClock:
    def __init__(self) -> None:
        self._t = 0.0

    def __call__(self) -> float:
        self._t += 1.0
        return self._t


class _UniverseSummaryStandIn:
    """Duck-types UniverseResult for RiskEngine._concentration_indicator,
    which only ever reads `.summary` — used to substitute the most recent
    FULL (unscoped) cycle's real eligible-instrument count when this run is
    itself symbols_filter-scoped to one/few symbols (owner-reported bug,
    2026-07-29). A scoped scan's own universe result reflects only how
    narrow that particular call was (e.g. 1 for a single-symbol re-validate,
    always triggering concentrated_risk regardless of real market breadth),
    not the true market-wide universe breadth concentration_indicator is
    meant to measure."""

    def __init__(self, summary: Mapping[str, int]) -> None:
        self.summary = summary


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
        unresolved: list[dict[str, object]] = []
        for cand in candidates:
            inst = self._resolve_instrument(cand.symbol)
            candles = self._repo.list_candles_recent(
                inst.instrument_id, Timeframe.D1, limit=500
            )
            # A candidate with neither a catalog row nor a single ingested bar was
            # never resolvable — typically a typo that the exchange does not list.
            # Judging a synthesized instrument would report it as "Excluded: failed
            # rules", implying real market data said no. Report it as unresolved.
            if not candles and self._repo.get_instrument(inst.instrument_id) is None:
                unresolved.append(
                    {
                        "symbol": display_symbol(inst.instrument_id),
                        "instrument_id": inst.instrument_id,
                        "reason": (
                            "no instrument in the catalog and no ingested market data — "
                            "the symbol may not exist on the exchange"
                        ),
                    }
                )
                continue
            instruments.append(inst)
            candles_by_id[inst.instrument_id] = candles

        if not instruments:
            return {
                "mode": "ingest_only",
                "reason": "no_resolvable_owner_candidates",
                "universe_members": {},
                "universe_source": "empty",
                "qualified_today": [],
                "unresolved_candidates": unresolved,
                "message": (
                    "None of the candidate symbols resolved to ingested market data. "
                    "Remove unresolved symbols or run an ingest cycle."
                ),
            }

        universe_engine = UniverseEngine(cfg.universe)
        result = universe_engine.build(
            instruments,
            candles_by_id,
            as_of=as_of,
            calendar=calendar,
            cycle_id=trigger.value.lower(),
        )

        health_cfg = load_market_health_config(self._config_dir)
        breadth = compute_universe_breadth(candles_by_id)
        liquidity = compute_liquidity_aggregate(
            candles_by_id,
            lookback_days=health_cfg.liquidity.lookback_days,
            method=health_cfg.liquidity.method,
        )
        index_candles_for_gap = self._index_candles_for_metrics(candles_by_id)
        gap_stability = compute_gap_stability(
            index_candles_for_gap,
            window=health_cfg.gap_stability.window,
            gap_pct_threshold=Decimal(str(health_cfg.gap_stability.gap_pct_threshold)),
        )
        metric_inputs = {
            "breadth": breadth.to_payload(),
            "liquidity": liquidity.to_payload(),
            "gap_stability": gap_stability.to_payload(),
            "institutional_flow": self._institutional_flow_payload(),
        }

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

        # Always enrich + persist universe breadth onto a snapshot row when possible
        # (even if no scan runs — MI/MH consumers read market_snapshots).
        base_snap = self._resolve_snapshot(as_of, candles_by_id)
        if base_snap is None:
            base_snap = MarketSnapshot(
                ts=as_of,
                indices={},
                breadth_advances=0,
                breadth_declines=0,
                india_vix=None,
                breadth_neutral=0,
            )
        enriched_snap = self._apply_universe_breadth(base_snap, breadth, as_of=as_of)
        self._persist_enriched_snapshot(enriched_snap)

        # MH-2: construct F-5 MarketHealthScore once per validation (shared by
        # every scanned symbol). Categorical assessment feeds trend/volatility
        # points; breadth/liquidity/institutional/gap use MH-1 aggregates.
        health_result = None
        if index_candles_for_gap:
            index_id_for_health = index_candles_for_gap[0].instrument_id
            health_result = MarketHealthEngine(health_cfg).assess(
                index_id_for_health,
                index_candles_for_gap,
                enriched_snap,
                as_of=as_of,
            )
        score_build = construct_market_health_score(
            as_of=as_of,
            config=health_cfg,
            breadth=breadth,
            liquidity=liquidity,
            gap_stability=gap_stability,
            institutional_flow=self._repo.get_latest_institutional_flow(
                prefer_final=True
            ),
            health_result=health_result,
        )

        # SD-2/DD-12: SectorHealthEngine (M2.3, approved) was built and tested
        # but never instantiated anywhere in the live pipeline — the sector
        # index candle history it needs didn't exist until DD-12's Kite
        # ingestion change. This computes and persists real per-sector
        # assessments for whichever sectors config/sector_index_mapping.json
        # explicitly maps; it does NOT touch ScoringEngine/sector_quality —
        # that remains SD-3, a separate owner-gated decision with its own
        # before/after replay-diff requirement.
        sector_health_payload: dict[str, object] = {}
        sector_candles = self._sector_candles_for_health(candles_by_id)
        if sector_candles:
            sector_cfg = load_sector_health_config(self._config_dir)
            sector_results = SectorHealthEngine(sector_cfg).assess_many(
                sector_candles, as_of=as_of, market_health=health_result,
            )
            sector_health_payload = self._sector_health_payload(sector_results)

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
            # RiskEngine accepts a calendar context and the universe result for
            # its event_risk / concentration_indicator dimensions, but this
            # pipeline never passed them — leaving both permanently UNKNOWN on
            # every decision ever scored here. Both objects already exist above;
            # they were simply out of scope inside _scan_eligible.
            scan_report, scan_regime = self._scan_eligible(
                included_ids,
                as_of=as_of,
                run_id=run_id,
                cycle_id=cycle_id,
                candles_by_id=candles_by_id,
                snapshot=enriched_snap,
                cfg=cfg,
                market_health=health_result,
                market_health_score=score_build.score,
                calendar_context=calendar.context_for(as_of.date()),
                universe_result=result,
            )
            scan_stats = {
                "total": scan_report.statistics.total,
                "successful": scan_report.statistics.successful,
                "failed": scan_report.statistics.failed,
                "skipped": scan_report.statistics.skipped,
            }
            decision_counts = dict(scan_report.summary.decision_counts)
            qualified = self._qualified_from_repo(as_of)
            decision_reports = {
                result.report.decision_id: result.report.to_dict()
                for result in scan_report.results
                if result.report is not None
            }

        # MI-2: prefer the scan's own regime payload over the earlier,
        # eager `_maybe_regime` one whenever a scan actually ran — only the
        # scan path computes market_health (reg_stage), so preferring the
        # eager one (as before) silently discarded real market_health on
        # every cycle that had eligible symbols to scan.
        if scan_regime is not None:
            regime_payload = scan_regime

        detail: dict[str, object] = {
            "mode": "owner_validation",
            "universe_members": universe_members,
            "universe_source": "owner_candidates",
            "unresolved_candidates": unresolved,
            "universe_summary": dict(result.summary),
            # Marks whether this run scanned the full active-candidate
            # universe or was symbols_filter-scoped to one/few symbols —
            # lets a later scoped run find the last real, full-universe
            # breadth for concentration_indicator instead of using its own
            # narrow (misleadingly "concentrated") scan scope.
            "universe_scope": "scoped" if self._symbols_filter else "full",
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
                "institutional_written": ingestion.institutional_written,
                "institutional_error": ingestion.institutional_error,
                "datasets_quarantined": ingestion.datasets_quarantined,
                "quarantined_dataset_ids": list(ingestion.quarantined_dataset_ids),
            },
            "market_metric_inputs": metric_inputs,
            "market_health_score": score_build.to_payload(),
            "sector_health": sector_health_payload,
        }
        if regime_payload is not None:
            detail["regime_assessment"] = regime_payload
        return detail

    def _apply_universe_breadth(
        self,
        snap: MarketSnapshot,
        breadth,
        *,
        as_of: datetime,
    ) -> MarketSnapshot:
        """Overlay universe ADV/DEC/neutral onto snapshot (F-5 §3.2 / MH-1)."""
        return MarketSnapshot(
            ts=as_of,
            indices=dict(snap.indices),
            breadth_advances=breadth.advances,
            breadth_declines=breadth.declines,
            india_vix=snap.india_vix,
            breadth_neutral=breadth.neutral,
        )

    def _persist_enriched_snapshot(self, snap: MarketSnapshot) -> None:
        latest = self._repo.get_latest_snapshot()
        if latest is not None and latest.ts == snap.ts:
            # Same timestamp — cannot UPDATE append-only table; keep in-memory only.
            return
        try:
            self._repo.add_snapshot(snap)
        except Exception:
            # Validation must not fail because a duplicate snapshot collided.
            return

    def _institutional_flow_payload(self) -> dict[str, object] | None:
        flow = self._repo.get_latest_institutional_flow(prefer_final=True)
        if flow is None:
            return None
        return {
            "session_date": flow.session_date.isoformat(),
            "fii_net": str(flow.fii_net),
            "dii_net": str(flow.dii_net),
            "combined_net": str(flow.fii_net + flow.dii_net),
            "provisional": flow.provisional,
            "source_id": flow.source_id,
            "fetched_at": flow.fetched_at.isoformat(),
        }

    def _index_candles_for_metrics(
        self, candles_by_id: Mapping[str, Sequence[Candle]]
    ) -> list[Candle]:
        candidates: list[str] = []
        try:
            from athena.config.loader import load_kite_provider_config

            kite = load_kite_provider_config(self._config_dir)
            candidates.extend(kite.index_instruments)
        except Exception:
            pass
        candidates.extend(["NSE:NIFTY 50", "NIFTY 50", "NIFTY50"])
        for iid in candidates:
            series = list(candles_by_id.get(iid, ()))
            if not series:
                series = self._repo.list_candles_recent(iid, Timeframe.D1, limit=60)
            if series:
                return series
        return []

    def _sector_candles_for_health(
        self, candles_by_id: Mapping[str, Sequence[Candle]]
    ) -> dict[str, list[Candle]]:
        """Sector name -> its mapped tracked index's candle series (SD-2/DD-12).

        Only sectors with an explicit ``config/sector_index_mapping.json``
        entry are included here — an unmapped sector simply has no series,
        so ``SectorHealthEngine`` never computes (and never fabricates) a
        result for it. Mirrors ``_index_candles_for_metrics``'s
        this-cycle-then-persisted-fallback lookup.
        """
        try:
            mapping_cfg = load_sector_index_mapping_config(self._config_dir)
            index_cfg = load_index_intelligence_config(self._config_dir)
        except Exception:
            return {}
        instrument_by_key = {
            item.key: item.instrument_id for item in index_cfg.tracked_indices
        }
        result: dict[str, list[Candle]] = {}
        for entry in mapping_cfg.mappings:
            instrument_id = instrument_by_key.get(entry.index_key)
            if not instrument_id:
                continue
            series = list(candles_by_id.get(instrument_id, ()))
            if not series:
                series = self._repo.list_candles_recent(instrument_id, Timeframe.D1, limit=60)
            if series:
                result[entry.sector] = series
        return result

    @staticmethod
    def _sector_health_payload(results: Mapping[str, Any]) -> dict[str, object]:
        """Serialize ``SectorHealthResult`` objects into run-detail JSON.

        No frozen dataclass here has a built-in serializer (unlike
        ``MarketHealthScore.to_payload()``), so this mirrors the manual
        evidence-flattening already used elsewhere in this module (e.g. the
        universe-member evidence trace above).
        """
        return {
            sector: {
                "dimensions": dict(result.assessment.dimensions),
                "explanation": result.assessment.explanation,
                "evidence": [
                    {
                        "dimension": e.dimension,
                        "outcome": e.outcome.value,
                        "explanation": e.explanation,
                        "inputs": dict(e.inputs),
                    }
                    for e in result.evidence
                ],
            }
            for sector, result in results.items()
        }

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
        # Shared with _scan_eligible via _resolve_index_candles() — always
        # the configured index's own real candle history, never a snapshot
        # label mismatch or another instrument's own candles (see that
        # method's docstring for the two owner-reported bugs this fixes).
        index_id, index_candles = self._resolve_index_candles(candles_by_id)
        if len(index_candles) >= 2:
            try:
                regime = RegimeEngine(cfg.regime).assess(
                    index_id, index_candles, snap, as_of=as_of
                )
                return self._regime_to_payload(regime)
            except Exception:
                pass

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

    def _resolve_index_candles(
        self, candles_by_id: Mapping[str, Sequence[Candle]], *, min_candles: int = 2
    ) -> tuple[str, list[Candle]]:
        """Real market-benchmark index candles for regime assessment.

        Two owner-reported bugs (2026-07-29), found together:

        1. The previous `index_id = next(iter(snapshot.indices.keys()))`
           picked whichever index happened to be first in that snapshot's
           own dict — not a configured choice, not guaranteed stable across
           snapshots — so regime (gap/trend/volatility) could silently flip
           between a NIFTY 50-based and a BANK NIFTY-based reading between
           two runs that should have been identical.
        2. Deeper: `MarketSnapshot.indices` keys are bare labels ("NIFTY
           50"), while the `candles` table stores everything under the
           full instrument_id ("NSE:NIFTY 50") — so a lookup keyed off
           `snapshot.indices` could never find real candles at all, and the
           code fell through to `candles_by_id.get(included_ids[0], ())` —
           using an ARBITRARY INDIVIDUAL STOCK's own candles as a stand-in
           for "the market index" (whichever stock happened to be first in
           this particular scan's own scope — a different one for a full
           506-symbol cycle than for a single-symbol re-validate). This
           silently fabricated a market-wide reading from single-stock
           data, the opposite of ADR-005.

        Fix: always resolve via the configured index instruments (their
        real, correctly-prefixed instrument_id — never a snapshot's own
        label, never another instrument's own candles), trying each in
        order and requiring genuine candle history before accepting one.
        Returns real, empty candles (never fabricated from an unrelated
        instrument) when no configured index has enough history yet — the
        regime engine already degrades every dimension to its own
        `*_UNKNOWN` label for that case."""
        candidates: list[str] = []
        try:
            from athena.config.loader import load_kite_provider_config

            kite = load_kite_provider_config(self._config_dir)
            candidates.extend(kite.index_instruments)
        except Exception:
            pass
        candidates.extend(["NSE:NIFTY 50", "NIFTY50"])

        seen: set[str] = set()
        for index_id in candidates:
            if not index_id or index_id in seen:
                continue
            seen.add(index_id)
            series = list(candles_by_id.get(index_id, ()))
            if len(series) < min_candles:
                series = self._repo.list_candles_recent(index_id, Timeframe.D1, limit=500)
            if len(series) >= min_candles:
                return index_id, series
        return (candidates[0] if candidates else "NIFTY50"), []

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
                breadth_neutral=0,
            )
        if snap.india_vix is None and vix is not None:
            return MarketSnapshot(
                ts=snap.ts,
                indices=dict(snap.indices),
                breadth_advances=snap.breadth_advances,
                breadth_declines=snap.breadth_declines,
                india_vix=vix,
                breadth_neutral=snap.breadth_neutral,
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

    def _last_full_universe_summary(self) -> _UniverseSummaryStandIn | None:
        """Most recent FULL (unscoped) cycle's real universe_summary, for a
        symbols_filter-scoped run's concentration_indicator — a scoped run's
        own universe result only ever has 1 (or a few) "eligible" instrument,
        which isn't the real market-wide breadth. Honestly None (→ UNKNOWN,
        never fabricated) if no prior full cycle exists yet.

        DryRunCycleOrchestrator.run_cycle() (scheduling/dry_run.py) persists
        this pipeline's own returned dict nested one level down, under a
        "pipeline" key, alongside "phase"/"duration_seconds"/"ingestion" —
        not as the top-level detail_json. A caller that invokes this
        pipeline directly (bypassing that orchestrator, e.g. a test) may
        persist the flat dict instead — check both shapes so this works
        for every real call site, not just the one under test."""
        for record in self._repo.list_runs(limit=50):
            if record.status not in (RunStatus.COMPLETED, RunStatus.DEGRADED):
                continue
            detail = self._repo.get_run_detail(record.run_id)
            pipeline_detail = detail.get("pipeline")
            if not isinstance(pipeline_detail, dict):
                pipeline_detail = detail
            if pipeline_detail.get("universe_scope") != "full":
                continue
            summary = pipeline_detail.get("universe_summary")
            if isinstance(summary, dict) and summary:
                return _UniverseSummaryStandIn(summary)
        return None

    @staticmethod
    def _regime_to_payload(
        regime, market_health=None, market_health_score=None
    ) -> dict[str, object]:
        labels = list(regime.assessment.labels)
        trend = next(
            (lb for lb in labels if "TREND" in lb or lb == "SIDEWAYS"), "UNKNOWN"
        )
        vol = next((lb for lb in labels if "VOLATILITY" in lb), "UNKNOWN")
        gap = next((lb for lb in labels if "GAP" in lb), "NO_GAP")
        explanation = regime.assessment.explanation or "; ".join(
            e.explanation for e in regime.evidence[:3]
        )
        # Categorical 4-dim labels remain for MI-2 / legacy consumers.
        # MH-2 adds the numeric F-5 score when all six components are present.
        health_dimensions = (
            dict(market_health.assessment.dimensions) if market_health is not None else {}
        )
        payload: dict[str, object] = {
            "trend": trend,
            "volatility": vol,
            "gap": gap,
            "market_health": health_dimensions,
            "explanation": explanation
            or "Regime assessed from available daily candles.",
        }
        if market_health_score is not None:
            payload["market_health_score"] = {
                "ts": market_health_score.ts.isoformat(),
                "components": dict(market_health_score.components),
                "total": market_health_score.total,
                "explanation": market_health_score.explanation,
            }
        return payload

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
        market_health=None,
        market_health_score=None,
        calendar_context=None,
        universe_result=None,
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
        from athena.indicators import IndicatorEngine, IndicatorName, IndicatorStatus
        from athena.indicators import calculations as calc
        from athena.market_health import MarketHealthEngine
        from athena.regime import RegimeEngine
        from athena.risk import RiskEngine
        from athena.runtime import WorkflowEngine, WorkflowStage, build_definition
        from athena.scanner import DailyMarketScanner, InstrumentPlan, ScanCapture
        from athena.scoring import ConfluenceInputs, ScoringEngine

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

        index_id, index_candles = self._resolve_index_candles(candles_by_id)

        captured_regime: dict[str, object] = {"payload": None}
        shared_market_health: dict[str, object] = {"value": market_health}
        shared_score: dict[str, object] = {"value": market_health_score}
        # Owner-reported bug (2026-07-29): a symbols_filter-scoped run (e.g.
        # single-symbol Re-validate) only ever has 1 "eligible" instrument in
        # its own universe_result, which always trips concentrated_risk
        # regardless of real market breadth. Substitute the last real FULL
        # cycle's universe breadth for concentration purposes in that case.
        concentration_universe = (
            self._last_full_universe_summary()
            if self._symbols_filter is not None
            else universe_result
        )

        def _intraday_direction(candles: list[Candle], period: int) -> bool | None:
            """Bool = last close at/above its trailing SMA(period); None when
            the series has fewer than `period` bars (M-X7 UNKNOWN-tolerance —
            see ind_stage's confluence note)."""
            if not candles:
                return None
            closes = [c.close for c in candles]
            sma_val = calc.sma(closes, period)
            if sma_val is None:
                return None
            return closes[-1] >= sma_val

        def builder(instrument_id: str) -> InstrumentPlan:
            cs = list(candles_by_id.get(instrument_id, ()))
            box: dict[str, Any] = {}

            def ind_stage(ctx):
                indicators = indicator_engine.compute_all(
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
                # M-X6: VWAP needs same-session intraday (5m) candles — a
                # fundamentally different series than the daily `cs` above,
                # since VWAP is cumulative from session open, not a rolling
                # window. Computed and returned separately, never merged
                # into `indicators`: ConfidenceEngine._indicator_availability/
                # _unknown_ratio measure completeness as known/len(indicators),
                # and same-session-only data is far sparser than the daily
                # series, so folding it in would silently move every symbol's
                # confidence whenever intraday history happens to be thin —
                # exactly the un-reviewed-impact risk SD-2/SD-3 treat
                # explicitly for sector_quality. `scoring_engine.score()`
                # takes `vwap` as its own parameter for the same reason.
                intraday_cs = self._repo.list_candles_recent(
                    instrument_id, Timeframe.M5, limit=100
                )
                vwap_result = (
                    indicator_engine.compute(IndicatorName.VWAP, intraday_cs, as_of=ctx.as_of)
                    if intraday_cs else None
                )
                # M-X7: multi-timeframe confluence — daily direction reuses
                # the SMA(20) already computed above; 5m reuses `intraday_cs`
                # (the same series VWAP uses); 15m needs its own fetch. Each
                # intraday direction is a plain rolling-SMA read via
                # calc.sma() with a short, timeframe-specific period, not
                # routed through IndicatorEngine — IndicatorsConfig fixes one
                # period per indicator name, and there's no way to ask it for
                # a differently-tuned SMA for 15m's much thinner real history
                # (median 14 bars/session) than the daily series' period=20.
                confluence_inputs = None
                daily_sma = indicators.get(IndicatorName.SMA)
                if daily_sma is not None and daily_sma.status is IndicatorStatus.OK:
                    daily_last_close = daily_sma.evidence.inputs.get("last_close")
                    if daily_last_close is not None:
                        confluence_cfg = scoring_cfg.confluence
                        daily_bullish = Decimal(daily_last_close) >= daily_sma.values["value"]
                        fifteen_min_cs = self._repo.list_candles_recent(
                            instrument_id, Timeframe.M15, limit=100
                        )
                        confluence_inputs = ConfluenceInputs(
                            daily_bullish=daily_bullish,
                            five_min_bullish=_intraday_direction(
                                intraday_cs, confluence_cfg.five_min_sma_period),
                            fifteen_min_bullish=_intraday_direction(
                                fifteen_min_cs, confluence_cfg.fifteen_min_sma_period),
                        )
                return {
                    "indicators": indicators,
                    "vwap": vwap_result,
                    "confluence": confluence_inputs,
                }

            def reg_stage(ctx):
                series = index_candles if index_candles else cs
                regime = regime_engine.assess(
                    index_id, series, snapshot, as_of=ctx.as_of
                )
                if shared_market_health["value"] is None:
                    shared_market_health["value"] = market_health_engine.assess(
                        index_id,
                        series,
                        snapshot,
                        as_of=ctx.as_of,
                        regime=regime,
                    )
                if captured_regime["payload"] is None:
                    captured_regime["payload"] = self._regime_to_payload(
                        regime,
                        market_health=shared_market_health["value"],
                        market_health_score=shared_score["value"],
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
                        market_health_score=shared_score["value"],
                        vwap=ctx.get("vwap"),
                        confluence=ctx.get("confluence"),
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
                        calendar_context=calendar_context,
                        universe=concentration_universe,
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
                    WorkflowStage(
                        "indicators", ind_stage,
                        produces=("indicators", "vwap", "confluence"),
                    ),
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

    def _qualified_from_repo(self, as_of: datetime) -> list[dict[str, object]]:
        day = as_of.date()
        out: list[dict[str, object]] = []
        # Every WATCH/TRADE decision made today, not just this run's own
        # symbols: validating one symbol used to rewrite the day's list down to
        # that symbol, hiding names qualified earlier the same day.
        #
        # Re-validating the same symbol several times in one day writes one
        # Decision per run, so an un-deduplicated read listed the same name
        # once per re-validate. Keep only each symbol's newest same-day
        # verdict (list_decisions is ts DESC) — and decide WATCH/TRADE from
        # that newest verdict, so a name later downgraded to NO_TRADE does
        # not keep surfacing from its earlier qualifying run.
        seen: set[str] = set()
        for decision in self._repo.list_decisions(limit=2000):
            if decision.ts.date() != day:
                continue
            if decision.instrument_id in seen:
                continue
            seen.add(decision.instrument_id)
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
