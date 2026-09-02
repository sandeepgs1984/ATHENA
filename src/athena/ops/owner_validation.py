"""Owner validation pipeline for dry-run cycles (D-V2 / D-V3).

After ingest: UniverseEngine eligibility on ``owner_candidates``, then
DailyMarketScanner + DecisionEngine on included names. Persists decisions/
traces and returns ``universe_members`` + ``qualified_today`` for run detail.

Heavy analytical imports are deferred inside ``run`` / ``_scan_eligible`` to
avoid circular import chains through ``athena.scanner`` at package import time.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

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
        persistence_clock: Callable[[], datetime] | None = None,
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
        # ID-6D.1: the real, timezone-aware wall-clock instant a persisted
        # EntryQualification observation was actually written -- distinct
        # from `as_of` (the evaluation/market-time checkpoint). Injectable
        # for deterministic tests (mirrors this codebase's existing
        # `utc_now`/`_utc_now` module-level helpers in
        # `portfolio/sync.py`/`darvax/screening/sweep.py`, made explicitly
        # injectable here rather than a bare hardcoded call, since
        # `save_entry_qualification` requires proving `as_of != persisted_at`
        # under test). Never used by the pure EntryQualificationEngine or
        # any analytical engine -- only at this orchestration boundary.
        self._persistence_clock: Callable[[], datetime] = (
            persistence_clock or (lambda: datetime.now(tz=timezone.utc))
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
            # ID-5E: bounded by as_of -- this run's own daily candle series
            # (feeds universe eligibility, market health, D1 indicators,
            # scoring) must not see a D1 row dated after this run's own
            # `as_of` during a historical replay.
            candles = self._repo.list_candles_recent(
                inst.instrument_id, Timeframe.D1, limit=500, as_of=as_of
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
        index_candles_for_gap = self._index_candles_for_metrics(candles_by_id, as_of=as_of)
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

        # SD-2/DD-12/SD-3 (ID-P0): SectorHealthEngine (M2.3, approved) computes
        # and persists real per-sector assessments for whichever sectors
        # config/sector_index_mapping.json explicitly maps. SD-3 (ID-P0) wires
        # the result into the per-instrument workflow via `sector_results`,
        # resolved per instrument by `Instrument.sector` inside
        # `_scan_eligible` (never guessed, never substituted) and threaded
        # into ScoringEngine.score()/EvidenceAggregationEngine.aggregate()/
        # DecisionEngine.decide() — all three already accepted this parameter
        # before this change; only the call sites were missing it.
        sector_health_payload: dict[str, object] = {}
        sector_results: Mapping[str, Any] = {}
        sector_candles = self._sector_candles_for_health(candles_by_id, as_of=as_of)
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
                sector_results=sector_results,
                instruments=instruments,
                calendar=calendar,
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
        self, candles_by_id: Mapping[str, Sequence[Candle]], *, as_of: datetime
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
                # ID-5E: this fallback (only reached when the index isn't
                # already in this cycle's own resolved candles_by_id) must
                # not see a D1 row dated after this run's own as_of either.
                series = self._repo.list_candles_recent(iid, Timeframe.D1, limit=60, as_of=as_of)
            if series:
                return series
        return []

    def _sector_candles_for_health(
        self, candles_by_id: Mapping[str, Sequence[Candle]], *, as_of: datetime
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
                # ID-5E: same fallback-safety reasoning as
                # _index_candles_for_metrics above.
                series = self._repo.list_candles_recent(
                    instrument_id, Timeframe.D1, limit=60, as_of=as_of
                )
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
        index_id, index_candles = self._resolve_index_candles(candles_by_id, as_of=as_of)
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
        self, candles_by_id: Mapping[str, Sequence[Candle]], *,
        as_of: datetime, min_candles: int = 2,
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
                # ID-5E: same fallback-safety reasoning as
                # _index_candles_for_metrics/_sector_candles_for_health.
                series = self._repo.list_candles_recent(
                    index_id, Timeframe.D1, limit=500, as_of=as_of
                )
            if len(series) >= min_candles:
                return index_id, series
        return (candidates[0] if candidates else "NIFTY50"), []

    def _resolve_snapshot(
        self,
        as_of: datetime,
        candles_by_id: Mapping[str, Sequence[Candle]],
    ) -> MarketSnapshot | None:
        """Prefer persisted snapshot; fill India VIX from VIX candles when missing."""
        # ID-5G: bounded by as_of -- this feeds MarketHealthEngine.assess()
        # (via run()'s own enriched_snap) and RegimeEngine (via
        # _maybe_regime), both genuinely analytical, so a historical
        # replay must not receive a snapshot dated after its own as_of.
        snap = self._repo.get_latest_snapshot_as_of(as_of)
        vix = snap.india_vix if snap is not None else None
        if vix is None:
            vix = self._vix_from_candles(candles_by_id, as_of=as_of)
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
        self, candles_by_id: Mapping[str, Sequence[Candle]], *, as_of: datetime
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
                # ID-5E: same fallback-safety reasoning as
                # _index_candles_for_metrics/_resolve_index_candles.
                series = self._repo.list_candles_recent(iid, Timeframe.D1, limit=5, as_of=as_of)
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
        sector_results: Mapping[str, Any] | None = None,
        instruments: Sequence[Instrument] | None = None,
        calendar: CalendarEngine | None = None,
    ):
        from zoneinfo import ZoneInfo

        from athena.confidence import ConfidenceEngine
        from athena.config.loader import (
            load_confidence_config,
            load_decision_config,
            load_index_intelligence_config,
            load_market_health_config,
            load_risk_assessment_config,
            load_scoring_config,
            load_sector_index_mapping_config,
        )
        from athena.data.validation.calendar_expectations import latest_trading_day_on_or_before
        from athena.decision import DecisionEngine
        from athena.evidence import EvidenceAggregationEngine, EvidenceSource
        from athena.indicators import IndicatorEngine, IndicatorName, IndicatorStatus
        from athena.indicators import calculations as calc
        from athena.intraday import (
            EntryQualificationEngine,
            GapEngine,
            IntradayAnalyticsEngine,
            OpeningRangeEngine,
            OpeningRangeWindow,
            RelativeStrengthEngine,
            RelativeVolumeEngine,
            resolve_evidence_finality,
        )
        from athena.market_health import MarketHealthEngine
        from athena.regime import RegimeEngine
        from athena.risk import RiskEngine
        from athena.runtime import WorkflowEngine, WorkflowStage, build_definition
        from athena.scanner import DailyMarketScanner, InstrumentPlan, ScanCapture
        from athena.scoring import ConfluenceInputs, ScoringEngine
        from athena.session import SessionContextEngine, completed_candles, session_day_start

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
        session_engine = SessionContextEngine()
        session_tzinfo = ZoneInfo(cfg.market.timezone)
        intraday_analytics_engine = IntradayAnalyticsEngine()
        opening_range_engine = OpeningRangeEngine()
        relative_strength_engine = RelativeStrengthEngine()
        relative_volume_engine = RelativeVolumeEngine()
        entry_qualification_engine = EntryQualificationEngine()
        gap_engine = GapEngine()
        risk_engine = RiskEngine(risk_cfg)
        evidence_engine = EvidenceAggregationEngine()
        decision_engine = DecisionEngine(decision_cfg)
        scanner = DailyMarketScanner(WorkflowEngine(clock=_MonoClock()))

        index_id, index_candles = self._resolve_index_candles(candles_by_id, as_of=as_of)

        # SD-3 (ID-P0): Instrument.sector is the sole authoritative stock ->
        # sector relationship (never ADR-011's symbol_group/resolve_universe,
        # which models universe/scan eligibility, not sector taxonomy — see
        # docs/research/ID-0-RUNTIME-AUDIT-ARCHITECTURE-REPORT.md §6). A
        # symbol with no `.sector`, a `.sector` with no
        # config/sector_index_mapping.json entry, or a mapped sector with no
        # resolvable SectorHealthResult this cycle all resolve to the same
        # honest `None` below — never fabricated, never guessed.
        sector_results = sector_results or {}
        sector_by_instrument: dict[str, str] = {
            inst.instrument_id: inst.sector for inst in (instruments or ()) if inst.sector
        }

        # ID-4: RelativeStrengthContext's market/sector sides, computed
        # ONCE per run (not once per stock) -- reuses the exact same
        # authorities SD-2/SD-3 (ID-P0) already established, never a
        # second benchmark config or a second sector mapping:
        #   - `index_id` (just resolved above) is the SAME market-benchmark
        #     identity already authoritative for regime this cycle.
        #   - sector -> index_key -> instrument_id is the SAME
        #     config/sector_index_mapping.json + config/index_intelligence.json
        #     chain `_sector_candles_for_health` already uses for
        #     SectorHealthEngine, applied here to resolve each mapped
        #     sector's OWN M5 series instead of its D1 series.
        # Each series is a single session-bounded `get_candles` read (ID-3.1
        # semantics, never `list_candles_recent(limit=N)`), fetched once and
        # shared by every instrument in that sector/the whole universe.
        day_start_run = session_day_start(as_of, session_tzinfo)
        market_five_min = self._repo.get_candles(index_id, Timeframe.M5, day_start_run, as_of)
        sector_to_index_id: dict[str, str] = {}
        try:
            sector_mapping_cfg = load_sector_index_mapping_config(self._config_dir)
            index_intel_cfg = load_index_intelligence_config(self._config_dir)
            instrument_by_key = {t.key: t.instrument_id for t in index_intel_cfg.tracked_indices}
            sector_to_index_id = {
                m.sector: instrument_by_key[m.index_key]
                for m in sector_mapping_cfg.mappings
                if m.index_key in instrument_by_key
            }
        except Exception:
            sector_to_index_id = {}
        sector_five_min_by_sector: dict[str, list[Candle]] = {
            sector_name: self._repo.get_candles(sector_index_id, Timeframe.M5, day_start_run, as_of)
            for sector_name, sector_index_id in sector_to_index_id.items()
        }

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
            sector_name = sector_by_instrument.get(instrument_id)
            sector_health_result = sector_results.get(sector_name) if sector_name else None

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
                #
                # ID-2.1: filtered through the canonical completed-candle
                # primitive (`athena.session.completed_candles`, ID-1's own
                # `ts_open + duration <= as_of` rule) before ANY analytical
                # use — a still-forming last bar must never move VWAP,
                # confluence, or (transitively) IntradaySignalSet. This is
                # the one authoritative completed-candle filter; nothing
                # downstream re-derives its own copy of the formula.
                #
                # ID-3.1 §2/§5: VWAP is cumulative from session open, so it
                # needs the FULL current session's 5m bars — a fixed
                # `limit=100` fetch was proven (ID-3's real-data sanity
                # check) to silently drop the session's own earliest bars on
                # a day where persisted row density for one session exceeds
                # 100. Bounded by calendar day instead (`session_day_start`
                # -> `as_of`), via the existing PK-indexed `get_candles` —
                # no arbitrary row-count limit.
                vwap_raw = self._repo.get_candles(
                    instrument_id, Timeframe.M5,
                    session_day_start(ctx.as_of, session_tzinfo), ctx.as_of,
                )
                intraday_cs = completed_candles(vwap_raw, Timeframe.M5, as_of=ctx.as_of)
                vwap_result = (
                    indicator_engine.compute(IndicatorName.VWAP, intraday_cs, as_of=ctx.as_of)
                    if intraday_cs else None
                )
                # M-X7: multi-timeframe confluence — daily direction reuses
                # the SMA(20) already computed above. 5m/15m each get their
                # OWN `list_candles_recent(limit=100)` fetch here (ID-3.1
                # §5: audited and deliberately NOT switched to the
                # session-bounded fetch above) — confluence's rolling
                # SMA(9)/SMA(5) genuinely reads across a session boundary
                # early in the day today (e.g. at 09:20, SMA(9) draws on
                # yesterday's trailing bars, per `_intraday_direction`'s
                # "None only below `period` bars available" contract, never
                # a session-only one). Whether that cross-session reach is
                # actually intentional is unresolved from the code alone —
                # flagged as an open methodology question for the owner
                # rather than silently redefined either way. Each intraday
                # direction is a plain rolling-SMA read via calc.sma() with a
                # short, timeframe-specific period, not routed through
                # IndicatorEngine — IndicatorsConfig fixes one period per
                # indicator name, and there's no way to ask it for a
                # differently-tuned SMA for 15m's much thinner real history
                # (median 14 bars/session) than the daily series' period=20.
                confluence_inputs = None
                daily_sma = indicators.get(IndicatorName.SMA)
                if daily_sma is not None and daily_sma.status is IndicatorStatus.OK:
                    daily_last_close = daily_sma.evidence.inputs.get("last_close")
                    if daily_last_close is not None:
                        confluence_cfg = scoring_cfg.confluence
                        daily_bullish = Decimal(daily_last_close) >= daily_sma.values["value"]
                        # ID-5E: the retrieval cutoff (`as_of=ctx.as_of`
                        # below) and the analytical completed-candle filter
                        # (`completed_candles(..., as_of=ctx.as_of)`) are
                        # two separate concerns -- the retrieval cutoff
                        # stops a future-dated row from stealing one of the
                        # 100 LIMIT slots a genuinely earlier row should
                        # have had (repository boundary); completed_candles
                        # separately still excludes a still-forming tail
                        # bar (analytical boundary). Both were already
                        # correct for LIVE runs (no future rows exist in a
                        # live database); this closes the gap for a
                        # historical replay `ctx.as_of`. The deliberate
                        # cross-session-boundary reach (ID-3.1 §5, see
                        # above) is unchanged -- only genuinely future-dated
                        # rows are now excluded, never a prior session's own
                        # trailing bars.
                        confluence_five_min_cs = completed_candles(
                            self._repo.list_candles_recent(
                                instrument_id, Timeframe.M5, limit=100, as_of=ctx.as_of
                            ),
                            Timeframe.M5, as_of=ctx.as_of,
                        )
                        fifteen_min_cs = completed_candles(
                            self._repo.list_candles_recent(
                                instrument_id, Timeframe.M15, limit=100, as_of=ctx.as_of
                            ),
                            Timeframe.M15, as_of=ctx.as_of,
                        )
                        confluence_inputs = ConfluenceInputs(
                            daily_bullish=daily_bullish,
                            five_min_bullish=_intraday_direction(
                                confluence_five_min_cs, confluence_cfg.five_min_sma_period),
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
                        sector_health=sector_health_result,
                        vwap=ctx.get("vwap"),
                        confluence=ctx.get("confluence"),
                    )
                }

            def conf_stage(ctx):
                evidence_bundle = evidence_engine.aggregate(
                    as_of=ctx.as_of,
                    regime=ctx.get("regime"),
                    market_health=ctx.get("market_health"),
                    sector_health=(
                        {sector_name: sector_health_result}
                        if sector_health_result is not None
                        else None
                    ),
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
                    sector_health=sector_health_result,
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

            def session_stage(ctx):
                # ID-1 foundation only: nothing downstream declares a
                # dependency on "session_context" yet (no EntryQualification
                # exists). Independent of every other stage by design — its
                # own reads (5m/15m candles, latest quote), never touching
                # ind_stage's closure-local intraday series, so it cannot
                # perturb existing VWAP/confluence/scoring/decision behavior.
                #
                # ID-5C: this stage also produces "gap_context" (previous-
                # trading-session close -> current-session-open) — placed
                # here rather than a new stage because it needs nothing
                # this stage doesn't already have (session_date, `cs`'s
                # already-fetched D1 history) and adding a stage "because
                # RelativeStrength has one" was explicitly not wanted.
                # Reuses `cs` (this instrument's D1 candle history,
                # already fetched once per cycle for ind_stage) directly —
                # zero new repository reads, and independent of ID-5B's
                # still-open current-session M5 question by construction
                # (only D1 candles are read here, never M5).
                #
                # ID-3.1 §2/§4: session-scoped, so bounded by calendar day
                # (`session_day_start` -> `as_of`) rather than a fixed
                # `limit=100` — the same real-data truncation risk applies
                # here as to VWAP/ORB (this data feeds SessionContext's own
                # bar-count/latest-completed-bar/missing-bar provenance).
                day_start = session_day_start(ctx.as_of, session_tzinfo)
                five_min_candles = self._repo.get_candles(
                    instrument_id, Timeframe.M5, day_start, ctx.as_of
                )
                fifteen_min_candles = self._repo.get_candles(
                    instrument_id, Timeframe.M15, day_start, ctx.as_of
                )
                # ID-5F: bounded by ctx.as_of -- a historical replay must
                # not receive a quote timestamped after its own analytical
                # instant (the same market-time point-in-time gap ID-5E
                # closed for candles).
                latest_quote = self._repo.get_latest_quote(instrument_id, as_of=ctx.as_of)
                session_context = session_engine.assess(
                    instrument_id,
                    as_of=ctx.as_of,
                    exchange=self._exchange,
                    calendar=calendar,
                    sessions=cfg.market.sessions,
                    tzinfo=session_tzinfo,
                    five_min_candles=five_min_candles,
                    fifteen_min_candles=fifteen_min_candles,
                    latest_quote_ts=latest_quote.ts if latest_quote is not None else None,
                )

                # ID-5C: previous-trading-session-close -> current-session-
                # open transition. Zero new I/O -- `cs` (this instrument's
                # D1 history) is already fetched once per cycle by
                # OwnerValidationPipeline.run(), the same series ind_stage
                # already reuses for its own daily indicators. Deliberately
                # independent of ID-5B's still-open current-session M5
                # question: only D1 candles are read, never M5.
                session_date = session_context.session_date
                previous_session_date = latest_trading_day_on_or_before(
                    calendar, session_date - timedelta(days=1)
                )
                previous_session_close = next(
                    (c.close for c in cs if c.ts_open.date() == previous_session_date),
                    None,
                ) if previous_session_date is not None else None
                current_session_open = next(
                    (c.open for c in cs if c.ts_open.date() == session_date), None
                )
                gap_context = gap_engine.assess(
                    instrument_id,
                    as_of=ctx.as_of,
                    session_date=session_date,
                    previous_session_date=previous_session_date,
                    previous_session_close=previous_session_close,
                    current_session_open=current_session_open,
                )
                return {"session_context": session_context, "gap_context": gap_context}

            def relative_strength_stage(ctx):
                # ID-4: stock's own session-bounded M5 read (same pattern
                # as VWAP/ORB/session_stage — a fourth independent,
                # identically-shaped bounded read, same rationale as
                # intraday_analytics_stage's own §15 note above).
                # `market_five_min`/`sector_five_min_by_sector` are the
                # run-level shared reads resolved once above — never
                # refetched per instrument, per §22/§23's "do not recompute
                # identical market/sector series per stock" instruction.
                stock_five_min = self._repo.get_candles(
                    instrument_id, Timeframe.M5,
                    session_day_start(ctx.as_of, session_tzinfo), ctx.as_of,
                )
                sector_index_id = sector_to_index_id.get(sector_name) if sector_name else None
                rs_context = relative_strength_engine.assess(
                    instrument_id,
                    as_of=ctx.as_of,
                    session_context=ctx.get("session_context"),
                    sector=sector_name,
                    market_benchmark_id=index_id,
                    sector_benchmark_id=sector_index_id,
                    stock_five_min_candles=stock_five_min,
                    market_five_min_candles=market_five_min,
                    sector_five_min_candles=(
                        sector_five_min_by_sector.get(sector_name, []) if sector_name else []
                    ),
                    calendar=calendar,
                    tzinfo=session_tzinfo,
                )
                return {"relative_strength": rs_context}

            def relative_volume_stage(ctx):
                # ID-5D.1 Issue B fix: retrieve ALL of this instrument's
                # persisted M5 history, not a hardcoded lookback-day count.
                # A hardcoded bound (the original ID-5D 120-day window)
                # would silently become an undisclosed rolling-baseline-cap
                # POLICY the moment M5 history exceeds it -- resolving the
                # still-OWNER_PENDING rolling-cap question without owner
                # approval. `earliest_candle_ts` is a single indexed MIN()
                # seek on the existing (instrument_id, timeframe, ts_open)
                # index (`idx_candles_range`), not a table scan, and not a
                # new repository capability beyond that one lookup. No
                # instrument history at all falls back to today's own
                # session start, matching every other stage's bounded-read
                # shape (an empty read, handled by the engine's existing
                # honest-unavailable path).
                earliest_ts = self._repo.earliest_candle_ts(instrument_id, Timeframe.M5)
                lookback_start = earliest_ts or session_day_start(ctx.as_of, session_tzinfo)
                wide_five_min = self._repo.get_candles(
                    instrument_id, Timeframe.M5, lookback_start, ctx.as_of,
                )
                rv_context = relative_volume_engine.assess(
                    instrument_id,
                    as_of=ctx.as_of,
                    session_context=ctx.get("session_context"),
                    five_min_candles=wide_five_min,
                    calendar=cast(CalendarEngine, calendar),
                    tzinfo=session_tzinfo,
                )
                return {"relative_volume": rv_context}

            def intraday_analytics_stage(ctx):
                # ID-2 foundation: formalizes the existing "vwap"/
                # "confluence" outputs `ind_stage` already produced this
                # cycle (declared dependency: "indicators") into typed
                # evidence — computes nothing new, so it cannot diverge
                # from what ScoringEngine already saw.
                #
                # ID-3 adds genuinely new evidence (OR15/OR30) computed
                # here rather than as a separate WorkflowStage — this
                # stage already IS "produce IntradaySignalSet", and ORB
                # needs only its own raw 5m candle read (same repo call
                # pattern `session_stage` already uses) plus the already-
                # declared "session" dependency's SessionContext, so no new
                # stage/dependency is justified. Nothing downstream
                # (scoring/confidence/risk/decision) declares a dependency
                # on "intraday_signal_set" yet.
                #
                # ID-3.1 §2/§4: session-scoped like VWAP/session_stage, so
                # bounded by calendar day rather than a fixed `limit=100` —
                # this is the exact fetch the ID-3 real-data sanity check
                # proved could silently drop the opening range's own bars.
                #
                # ID-3.1 §15: this is the third independent, identically-
                # shaped (`session_day_start` -> `as_of`, M5) bounded read
                # per instrument per cycle — session_stage and ind_stage's
                # VWAP fetch each read the same window. Deliberately NOT
                # deduplicated through a shared workflow-produced artifact:
                # doing so would require `session`/`indicators` to gain a
                # declared dependency on each other (they are currently
                # independent, order-preserving stages — see their own
                # comments), risking the existing Kahn-ordering regression
                # proof for a single-digit-millisecond, PK-indexed query
                # (verified via EXPLAIN QUERY PLAN in the repository test
                # suite) that costs far less than the restructuring risk.
                five_min_raw = self._repo.get_candles(
                    instrument_id, Timeframe.M5,
                    session_day_start(ctx.as_of, session_tzinfo), ctx.as_of,
                )
                orb_by_window = opening_range_engine.assess(
                    instrument_id,
                    as_of=ctx.as_of,
                    session_context=ctx.get("session_context"),
                    five_min_candles=five_min_raw,
                    calendar=calendar,
                    tzinfo=session_tzinfo,
                )
                signal_set = intraday_analytics_engine.assess(
                    instrument_id,
                    as_of=ctx.as_of,
                    session_date=ctx.get("session_context").session_date,
                    session_context=ctx.get("session_context"),
                    vwap=ctx.get("vwap"),
                    confluence=ctx.get("confluence"),
                    five_min_sma_period=scoring_cfg.confluence.five_min_sma_period,
                    fifteen_min_sma_period=scoring_cfg.confluence.fifteen_min_sma_period,
                    or15=orb_by_window[OpeningRangeWindow.OR15],
                    or30=orb_by_window[OpeningRangeWindow.OR30],
                    relative_strength=ctx.get("relative_strength"),
                    gap=ctx.get("gap_context"),
                    relative_volume=ctx.get("relative_volume"),
                )
                return {"intraday_signal_set": signal_set}

            def entry_qualification_stage(ctx):
                # ID-6D: wires the owner-closed ID-6A/ID-6B.2/ID-6B.2A/
                # ID-6C/ID-6C.1 Entry Qualification chain into the canonical
                # runtime for the first time. No methodology change here —
                # the frozen v0 expression (VWAP positive AND aggregate
                # trend BULLISH AND (RS support OR RVOL support)) lives
                # entirely inside EntryQualificationEngine, untouched.
                #
                # "decision" dependency: reads the canonical Decision
                # dec_stage just captured into `box["cap"]` THIS cycle —
                # not a repository re-query. Within one synchronous,
                # single-threaded per-instrument pipeline execution, the
                # Decision `dec_stage` just produced (and already
                # persisted) is provably the freshest possible artifact
                # for this instrument — no staleness/supersession is
                # structurally reachable, so no TTL/age heuristic or
                # extra "latest decision" query is needed (see the ID-6D
                # design note §"Current Decision source of truth").
                #
                # "intraday_analytics" dependency: SessionContext and
                # IntradaySignalSet already share the same as_of/
                # session_date by construction (both stages read
                # `ctx.as_of`) — ID-6B.2A's own input-coherence checks
                # remain a defensive backstop here, never normal control
                # flow.
                #
                # The engine is called unconditionally — it already emits
                # OUT_OF_SCOPE for non-WATCH/TRADE Decision types itself,
                # so no special-casing is needed to invoke it safely — but
                # persistence is scoped to WATCH/TRADE only, per the
                # owner's explicit instruction not to flood
                # `entry_qualifications` with structurally irrelevant
                # observations for Decision types that were never in the
                # Entry Qualification funnel to begin with.
                decision = box["cap"].outcome.decision
                session_context = ctx.get("session_context")
                signal_set = ctx.get("intraday_signal_set")
                evidence_finality = resolve_evidence_finality(decision, session_context)
                eq = entry_qualification_engine.evaluate(
                    decision=decision,
                    session_context=session_context,
                    signal_set=signal_set,
                    evidence_finality=evidence_finality,
                )
                if decision.decision_type in (DecisionType.WATCH, DecisionType.TRADE):
                    # ID-6D.1: as_of (above, from SessionContext) is the
                    # evaluation/market-time checkpoint; persisted_at is the
                    # actual durable-write instant -- intentionally
                    # independent dimensions, never conflated. Sourced from
                    # the injected `self._persistence_clock`, never
                    # `ctx.as_of` and never a bare `datetime.now()` here.
                    self._repo.save_entry_qualification(
                        eq, persisted_at=self._persistence_clock()
                    )
                return {"entry_qualification": eq}

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
                    # ID-1 foundation stage. Declared LAST and with no
                    # dependencies/dependents so it cannot change the
                    # existing six stages' relative execution order (Kahn's
                    # sort batches same-round-ready stages by declaration
                    # index — see tests/market_intel/test_session_context.py
                    # / tests/ops/test_owner_validation.py's ordering proof).
                    WorkflowStage(
                        "session",
                        session_stage,
                        produces=("session_context", "gap_context"),
                    ),
                    # ID-4 foundation stage. Depends only on "session" (for
                    # SessionContext's session_open_ts/close_ts/date, which
                    # also govern the market-benchmark/sector-index
                    # canonical filtering here). No dependency on
                    # "indicators" — RelativeStrengthContext doesn't reuse
                    # anything ind_stage produced, it fetches its own bounded
                    # stock M5 series. Nothing among scoring/confidence/risk/
                    # decision depends on it.
                    WorkflowStage(
                        "relative_strength",
                        relative_strength_stage,
                        depends_on=("session",),
                        produces=("relative_strength",),
                    ),
                    # ID-5D foundation stage. Depends only on "session"
                    # (SessionContext's session_open_ts/close_ts/date govern
                    # its own canonical-slot alignment) — same dependency
                    # shape as "relative_strength", independent of
                    # "indicators". Nothing among scoring/confidence/risk/
                    # decision depends on it.
                    WorkflowStage(
                        "relative_volume",
                        relative_volume_stage,
                        depends_on=("session",),
                        produces=("relative_volume",),
                    ),
                    # ID-2 foundation stage. Depends on "session" (for
                    # SessionContext/data-quality), "indicators" (to reuse
                    # the existing vwap/confluence outputs, not recompute
                    # them), (ID-4) "relative_strength" and (ID-5D)
                    # "relative_volume" (to compose them onto
                    # IntradaySignalSet, not recompute them) — all four
                    # already resolved by the time this runs. Nothing among
                    # scoring/confidence/risk/decision depends on it, so it
                    # cannot perturb their existing relative order (see
                    # test_id2_intraday_analytics_stage_does_not_perturb_existing_stage_order).
                    WorkflowStage(
                        "intraday_analytics",
                        intraday_analytics_stage,
                        depends_on=("session", "indicators", "relative_strength", "relative_volume"),
                        produces=("intraday_signal_set",),
                    ),
                    # ID-6D: the first stage to join the previously-
                    # independent "decision" and "intraday_analytics"
                    # branches — Entry Qualification structurally needs
                    # both. Declared last: nothing else depends on it, so
                    # it cannot perturb the existing ten stages' relative
                    # execution order.
                    WorkflowStage(
                        "entry_qualification",
                        entry_qualification_stage,
                        depends_on=("decision", "intraday_analytics"),
                        produces=("entry_qualification",),
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
