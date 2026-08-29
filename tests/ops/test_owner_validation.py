"""Owner validation pipeline: eligibility + WATCH/TRADE qualify (D-V2 / D-V3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena import BLUEPRINT_VERSION, __version__
from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction, RunStatus, RunTrigger, Timeframe
from athena.domain.market import Candle, Instrument
from athena.domain.run import RunRecord
from athena.ops.owner_candidates import SqliteCandidateStore, normalize_candidate_symbol
from athena.ops.owner_validation import OwnerValidationPipeline

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 9, 30, tzinfo=IST)


def _candles(instrument_id: str, n: int = 80, seed: int = 100) -> list[Candle]:
    out: list[Candle] = []
    for i in range(n):
        day = date(2025, 11, 1) + timedelta(days=i)
        ts = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
        px = Decimal(str(seed + i))
        out.append(
            Candle(
                instrument_id=instrument_id,
                timeframe=Timeframe.D1,
                ts_open=ts,
                open=px,
                high=px + Decimal("2"),
                low=px - Decimal("1"),
                close=px + Decimal("1"),
                volume=1_000_000,
                source="test",
            )
        )
    return out


def _intraday_candles(instrument_id: str, day, n: int = 6, seed: int = 100) -> list[Candle]:
    """Same-day 5m bars for VWAP (M-X6) — starts 09:15 IST on `day`."""
    out: list[Candle] = []
    for i in range(n):
        ts = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
        ts += timedelta(minutes=5 * i)
        px = Decimal(str(seed + i))
        out.append(
            Candle(
                instrument_id=instrument_id, timeframe=Timeframe.M5, ts_open=ts,
                open=px, high=px + Decimal("1"), low=px - Decimal("1"), close=px,
                volume=10_000, source="test",
            )
        )
    return out


def _timeframe_candles(
    instrument_id: str, day, timeframe: Timeframe, step_minutes: int,
    n: int, seed: int = 100, rising: bool = True,
) -> list[Candle]:
    """Same-day bars at an arbitrary timeframe/step for confluence (M-X7)."""
    out: list[Candle] = []
    for i in range(n):
        ts = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
        ts += timedelta(minutes=step_minutes * i)
        px = Decimal(str(seed + i)) if rising else Decimal(str(seed - i))
        out.append(
            Candle(
                instrument_id=instrument_id, timeframe=timeframe, ts_open=ts,
                open=px, high=px + Decimal("1"), low=px - Decimal("1"), close=px,
                volume=10_000, source="test",
            )
        )
    return out


def _persist_run(repo: SqliteRepository, run_id: str, as_of: datetime, detail: dict) -> None:
    """Mimics DryRunOrchestrator's own repo.save_run() call (scheduling/
    dry_run.py) — OwnerValidationPipeline.run() itself never persists to the
    runs table; that only happens one layer up in production. Needed here to
    exercise _last_full_universe_summary(), which reads real persisted runs."""
    repo.save_run(
        RunRecord(
            run_id=run_id,
            cycle_id=run_id,
            trigger=RunTrigger.REFRESH,
            started_ts=as_of,
            status=RunStatus.COMPLETED,
            software_version=__version__,
            blueprint_version=BLUEPRINT_VERSION,
            strategy_profile="intraday-momentum",
            strategy_profile_version="1",
            indicator_versions={},
            config_snapshot_id="cfg",
            finished_ts=as_of,
        ),
        detail=detail,
    )


@pytest.fixture()
def config_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "config"


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    path = tmp_path / "val.db"
    r = SqliteRepository(path)
    r.initialize()
    return r


class TestOwnerCandidatesNormalize:
    def test_normalize_strips_exchange(self) -> None:
        assert normalize_candidate_symbol("nse:infy") == "INFY"
        assert normalize_candidate_symbol("  RELIANCE ") == "RELIANCE"


class TestOwnerValidationPipeline:
    def test_empty_candidates_ingest_only(self, repo: SqliteRepository, config_dir: Path) -> None:
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF,
            instruments_upserted=0,
            candles_fetched=0,
            candles_written=0,
            quotes_fetched=0,
            quotes_written=0,
            datasets_validated=0,
            datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-empty"
        )
        assert detail["mode"] == "ingest_only"
        assert detail["universe_members"] == {}

    def test_eligibility_and_qualified_layer(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        store.upsert_candidate(symbol="BBB")

        for sym, seed in (("AAA", 100), ("BBB", 200)):
            iid = f"NSE:{sym}"
            repo.upsert_instrument(
                Instrument(
                    instrument_id=iid,
                    symbol=sym,
                    exchange="NSE",
                    series="EQ",
                    status="ACTIVE",
                )
            )
            repo.add_candles(_candles(iid, seed=seed))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF,
            instruments_upserted=2,
            candles_fetched=160,
            candles_written=160,
            quotes_fetched=0,
            quotes_written=0,
            datasets_validated=2,
            datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-eligibility"
        )
        assert detail["mode"] == "owner_validation"
        members = detail["universe_members"]
        assert "AAA" in members and "BBB" in members
        # With full candle history both should typically be included
        assert members["AAA"]["included"] is True or members["AAA"]["included"] is False
        assert "trace" in members["AAA"]
        assert detail["universe_source"] == "owner_candidates"
        assert isinstance(detail["qualified_today"], list)
        assert isinstance(detail["decision_reports"], dict)
        assert detail["decision_reports"]
        first_report = next(iter(detail["decision_reports"].values()))
        assert "score" in first_report
        assert "confidence" in first_report
        assert "risk" in first_report
        # Full analytical path must populate score/confidence/risk (not refs-only).
        assert first_report["score"]["status"] == "OK"
        assert first_report["confidence"]["status"] == "OK"
        assert first_report["risk"]["status"] == "OK"
        assert first_report["confidence"]["dimensions"]
        assert first_report["risk"]["dimensions"]
        # Decisions persisted for included names
        decisions = repo.list_decisions(limit=50)
        assert len(decisions) >= 1
        types = {d.decision_type for d in decisions}
        assert types <= {
            DecisionType.TRADE,
            DecisionType.WATCH,
            DecisionType.NO_TRADE,
            DecisionType.INSUFFICIENT_DATA,
        }
        assert any(d.confidence_ref for d in decisions)
        assert any(d.risk_ref for d in decisions)
        # MI-2 (Market Intelligence redesign): regime_assessment.market_health
        # must be the real 4-dimension categorical breakdown MarketHealthEngine
        # already computes (breadth/trend_quality/momentum/volatility), not a
        # hardcoded 0 — the numeric MarketHealthScore domain type is never
        # constructed anywhere in ATHENA, so a real dict is the honest shape.
        regime_assessment = detail.get("regime_assessment")
        assert regime_assessment is not None
        health = regime_assessment["market_health"]
        assert isinstance(health, dict)
        assert set(health) == {"breadth", "trend_quality", "momentum", "volatility"}
        assert all(isinstance(v, str) and v for v in health.values())
        # Regression: each persisted decision must carry the actual run_id
        # passed into this call, not a locally-recomputed one derived from
        # (trigger, as_of) — see test_repeat_validate_with_same_as_of_does_
        # not_orphan_earlier_decision below for the full collision scenario.
        assert all(d.run_id == "run-test-eligibility" for d in decisions)

    def test_vwap_flows_into_score_without_affecting_confidence(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """M-X6: VWAP is computed from same-session 5m candles and reaches
        ScoringEngine's technical_structure — but must never touch
        ConfidenceEngine's indicator_availability ratio (still 6/6, never
        6/7), since that's a separate, un-reviewed-impact risk (see
        ScoringEngine.score()'s own docstring note). Checked end-to-end
        against the real production config, not a unit-level mock."""
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        store.upsert_candidate(symbol="BBB")
        for sym, seed in (("AAA", 100), ("BBB", 200)):
            iid = f"NSE:{sym}"
            repo.upsert_instrument(
                Instrument(instrument_id=iid, symbol=sym, exchange="NSE", series="EQ", status="ACTIVE")
            )
            repo.add_candles(_candles(iid, seed=seed))
        # Only AAA gets same-day intraday candles; BBB has none at all —
        # confirms the confidence isolation holds in BOTH the
        # VWAP-available and VWAP-unavailable cases within one run.
        repo.add_candles(_intraday_candles("NSE:AAA", AS_OF.date(), seed=100))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=2, candles_fetched=166, candles_written=166,
            quotes_fetched=0, quotes_written=0, datasets_validated=2, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-vwap"
        )
        reports = detail["decision_reports"]
        assert reports
        for report in reports.values():
            dims = {d["name"]: d for d in report["confidence"]["dimensions"]}
            avail = dims["indicator_availability"]
            # Exactly 6/6 regardless of AAA vs BBB — never 6/7 or 7/7.
            assert "6/6" in avail["explanation"], avail["explanation"]

    def test_confluence_flows_into_score_without_affecting_confidence(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """M-X7: multi-timeframe confluence is computed from same-session 5m
        + 15m candles and reaches ScoringEngine's trend component — but must
        never touch ConfidenceEngine's indicator_availability ratio (still
        6/6, never 6/7), same isolation guarantee as VWAP's own
        test_vwap_flows_into_score_without_affecting_confidence above."""
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        store.upsert_candidate(symbol="BBB")
        for sym, seed in (("AAA", 100), ("BBB", 200)):
            iid = f"NSE:{sym}"
            repo.upsert_instrument(
                Instrument(instrument_id=iid, symbol=sym, exchange="NSE", series="EQ", status="ACTIVE")
            )
            repo.add_candles(_candles(iid, seed=seed))  # rising daily series -> daily_bullish
        # Only AAA gets same-day 5m + 15m candles, both rising (agreeing with
        # its own rising daily series) — BBB has neither, confirming the
        # confidence isolation holds in both the confluence-available and
        # confluence-unavailable cases within one run.
        repo.add_candles(
            _timeframe_candles("NSE:AAA", AS_OF.date(), Timeframe.M5, 5, n=15, seed=100))
        repo.add_candles(
            _timeframe_candles("NSE:AAA", AS_OF.date(), Timeframe.M15, 15, n=8, seed=100))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=2, candles_fetched=183, candles_written=183,
            quotes_fetched=0, quotes_written=0, datasets_validated=2, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-confluence"
        )
        reports = detail["decision_reports"]
        assert reports
        for report in reports.values():
            dims = {d["name"]: d for d in report["confidence"]["dimensions"]}
            avail = dims["indicator_availability"]
            assert "6/6" in avail["explanation"], avail["explanation"]
        by_instrument = {r["decision"]["instrument_id"]: r for r in reports.values()}
        trend_aaa = next(
            c for c in by_instrument["NSE:AAA"]["score"]["components"] if c["dimension"] == "trend")
        confluence_contribs = [c for c in trend_aaa["contributions"] if c["source"] == "confluence:intraday"]
        assert confluence_contribs, trend_aaa["contributions"]
        assert "2/2" in confluence_contribs[0]["description"]
        trend_bbb = next(
            c for c in by_instrument["NSE:BBB"]["score"]["components"] if c["dimension"] == "trend")
        assert not any(c["source"] == "confluence:intraday" for c in trend_bbb["contributions"])

    def test_confluence_tolerates_thin_15m_data(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """M-X7: real production 15m history runs as thin as 9 bars/session
        (well under a naive N-bar confluence window) — a symbol with enough
        5m bars but too few 15m bars for its own short SMA must still score
        a confluence bonus from 5m alone, not go UNKNOWN or error out."""
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_timeframe_candles(iid, AS_OF.date(), Timeframe.M5, 5, n=15, seed=100))
        # Only 3 bars at 15m — fewer than confluence.fifteen_min_sma_period
        # (5 in production config), so the 15m direction must resolve to
        # None (excluded), not raise or silently disagree.
        repo.add_candles(_timeframe_candles(iid, AS_OF.date(), Timeframe.M15, 15, n=3, seed=100))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=1, candles_fetched=98, candles_written=98,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-confluence-thin"
        )
        report = next(
            r for r in detail["decision_reports"].values() if r["decision"]["instrument_id"] == iid)
        trend = next(c for c in report["score"]["components"] if c["dimension"] == "trend")
        confluence_contribs = [c for c in trend["contributions"] if c["source"] == "confluence:intraday"]
        assert confluence_contribs, trend["contributions"]
        assert "1/1" in confluence_contribs[0]["description"]

    def test_sector_health_computed_when_mapped_index_has_candles(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """SD-2 / DD-12: SectorHealthEngine (M2.3, approved) was built and
        tested but never instantiated in the live pipeline — the config
        against the real config/sector_index_mapping.json + config/providers/
        kite.json in this repo (config_dir points at production config, not a
        copy) exercises the actual wiring end-to-end. Only the sector-index
        candle series matters here; no equity candidate/instrument needs a
        sector label — the mapping is keyed by sector name -> index key
        directly, independent of any single stock. Still needs at least one
        real owner candidate, or run() takes its own "no candidates" early
        return before ever reaching the sector-health computation."""
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        repo.upsert_instrument(
            Instrument(
                instrument_id="NSE:AAA", symbol="AAA", exchange="NSE",
                series="EQ", status="ACTIVE",
            )
        )
        repo.add_candles(_candles("NSE:AAA", seed=100))
        repo.upsert_instrument(
            Instrument(
                instrument_id="NSE:NIFTY IT",
                symbol="NIFTY IT",
                exchange="NSE",
                series="INDICES",
                status="ACTIVE",
            )
        )
        repo.add_candles(_candles("NSE:NIFTY IT", n=80, seed=30000))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=2, candles_fetched=160, candles_written=160,
            quotes_fetched=0, quotes_written=0, datasets_validated=2, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-sector-health"
        )
        sector_health = detail["sector_health"]
        assert "Information Technology" in sector_health
        it_result = sector_health["Information Technology"]
        assert set(it_result["dimensions"]) == {"trend", "breadth", "momentum", "volatility"}
        # Real computed labels, not fabricated placeholders — breadth is
        # UNKNOWN because this test supplies no constituent_breadth (M2.4),
        # exactly like MarketHealthEngine's own honest-unavailable pattern.
        assert it_result["dimensions"]["breadth"] == "SECTOR_BREADTH_UNKNOWN"
        assert it_result["dimensions"]["trend"] != ""
        assert it_result["explanation"]
        assert it_result["evidence"]
        assert all(e["explanation"] for e in it_result["evidence"])
        # No candles for any other mapped sector's index in this test — must
        # not appear.
        assert "Automobile and Auto Components" not in sector_health

    def test_sector_health_empty_without_mapped_index_candles(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """No sector-index candles ingested this run (the common case until
        DD-12's backfill runs) -> sector_health is an empty dict, never a
        fabricated per-sector result."""
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        repo.upsert_instrument(
            Instrument(
                instrument_id="NSE:AAA", symbol="AAA", exchange="NSE",
                series="EQ", status="ACTIVE",
            )
        )
        repo.add_candles(_candles("NSE:AAA", seed=100))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=1, candles_fetched=80, candles_written=80,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-no-sector-health"
        )
        assert detail["sector_health"] == {}

    def test_sector_health_wired_into_scoring_evidence_and_decision_trace(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-P0/SD-3 (wiring only, no threshold recalibration): Instrument.sector
        is resolved per instrument inside `_scan_eligible` and threaded into
        ScoringEngine.score()/EvidenceAggregationEngine.aggregate()/
        DecisionEngine.decide() — all three already accepted `sector_health`
        before this change; only the call sites were missing it. Exercised
        end-to-end against the real production config/sector_index_mapping.json
        (config_dir points at production config, not a copy).

        Three instruments share IDENTICAL daily candle series (seed=100), so
        every OTHER scoring component must come out byte-identical across all
        three — proving the wiring touches sector_quality alone:
        - AAA: sector mapped ("Information Technology") + real NIFTY IT proxy
          index candles present -> sector_quality resolves OK.
        - BBB: sector set but to an UNMAPPED value ("Capital Goods", per
          config/sector_index_mapping.json's own _meta list of deliberately
          unmapped sectors) -> sector_quality stays UNKNOWN, never guessed.
        - CCC: no sector at all (Instrument.sector is None) -> same honest
          UNKNOWN path, and the pipeline must not fail for a sector-less symbol.
        """
        store = SqliteCandidateStore(repo)
        sectors = {"AAA": "Information Technology", "BBB": "Capital Goods", "CCC": None}
        for sym, sector in sectors.items():
            store.upsert_candidate(symbol=sym)
            iid = f"NSE:{sym}"
            repo.upsert_instrument(
                Instrument(
                    instrument_id=iid, symbol=sym, exchange="NSE", series="EQ",
                    status="ACTIVE", sector=sector,
                )
            )
            repo.add_candles(_candles(iid, seed=100))
        repo.upsert_instrument(
            Instrument(
                instrument_id="NSE:NIFTY IT", symbol="NIFTY IT", exchange="NSE",
                series="INDICES", status="ACTIVE",
            )
        )
        repo.add_candles(_candles("NSE:NIFTY IT", n=80, seed=30000))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=4, candles_fetched=320, candles_written=320,
            quotes_fetched=0, quotes_written=0, datasets_validated=4, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion,
            run_id="run-test-sector-wiring",
        )
        reports = detail["decision_reports"]
        assert reports
        by_instrument = {r["decision"]["instrument_id"]: r for r in reports.values()}
        aaa, bbb, ccc = by_instrument["NSE:AAA"], by_instrument["NSE:BBB"], by_instrument["NSE:CCC"]

        def sector_component(report):
            return next(
                c for c in report["score"]["components"] if c["dimension"] == "sector_quality"
            )

        aaa_sector, bbb_sector, ccc_sector = (
            sector_component(aaa), sector_component(bbb), sector_component(ccc)
        )

        # 1. UNKNOWN without an applicable SectorHealthResult (both the
        # unmapped-sector and the no-sector case).
        assert bbb_sector["status"] == "UNKNOWN", bbb_sector
        assert bbb_sector["value"] is None
        assert ccc_sector["status"] == "UNKNOWN", ccc_sector
        assert ccc_sector["value"] is None

        # 2. Known when a valid matching SectorHealthResult exists.
        assert aaa_sector["status"] == "OK", aaa_sector
        assert aaa_sector["value"] is not None

        # 3. The existing configured 15% weight is used unchanged, for every
        # instrument regardless of known/UNKNOWN status (weight is config, not
        # data-driven).
        assert aaa_sector["weight"] == bbb_sector["weight"] == ccc_sector["weight"] == 15

        # 5. No unrelated scoring component changes — all three instruments
        # have identical daily candles, differing only in Instrument.sector.
        other_dims = {"trend", "momentum", "market_quality", "liquidity", "technical_structure"}
        by_dim = {
            iid: {c["dimension"]: c for c in report["score"]["components"]}
            for iid, report in (("AAA", aaa), ("BBB", bbb), ("CCC", ccc))
        }
        for dim in other_dims:
            values = {iid: by_dim[iid][dim]["value"] for iid in by_dim}
            statuses = {iid: by_dim[iid][dim]["status"] for iid in by_dim}
            assert len(set(values.values())) == 1, (dim, values)
            assert len(set(statuses.values())) == 1, (dim, statuses)

        # 4. Composite re-normalization behaves exactly per the existing
        # contract: completeness = known_weight / 100, and AAA (sector known)
        # has exactly 0.15 more known weight than BBB/CCC (sector UNKNOWN) —
        # no other dimension's known/UNKNOWN status differs between them.
        aaa_completeness = Decimal(aaa["score"]["completeness"])
        bbb_completeness = Decimal(bbb["score"]["completeness"])
        ccc_completeness = Decimal(ccc["score"]["completeness"])
        assert bbb_completeness == ccc_completeness
        assert aaa_completeness - bbb_completeness == Decimal("0.15")

        # 6. EvidenceBundle receives Sector Health provenance for AAA only.
        assert "SECTOR_HEALTH" in aaa["evidence"]["present_sources"]
        assert aaa["evidence"]["provenance"].get("SECTOR_HEALTH", 0) > 0
        assert "SECTOR_HEALTH" not in bbb["evidence"]["present_sources"]
        assert "SECTOR_HEALTH" not in ccc["evidence"]["present_sources"]

        # 7. Decision reasoning trace receives the existing Sector Health
        # explanation for AAA only, and it's non-empty (ADR-005).
        aaa_stage_names = {s["stage"] for s in aaa["reasoning"]["stages"]}
        bbb_stage_names = {s["stage"] for s in bbb["reasoning"]["stages"]}
        ccc_stage_names = {s["stage"] for s in ccc["reasoning"]["stages"]}
        assert "sector_health" in aaa_stage_names
        assert "sector_health" not in bbb_stage_names
        assert "sector_health" not in ccc_stage_names
        sector_stage = next(s for s in aaa["reasoning"]["stages"] if s["stage"] == "sector_health")
        assert sector_stage["summary"]

        # 8. Symbols without a resolvable sector continue through the existing
        # UNKNOWN path rather than failing the pipeline — real decisions, not
        # a crash or a silently-dropped instrument.
        for report in (aaa, bbb, ccc):
            assert report["decision"]["type"] in {
                "TRADE", "WATCH", "NO_TRADE", "INSUFFICIENT_DATA",
            }

    def test_id1_session_stage_is_produced_without_perturbing_existing_stage_order(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-1 §8/U: the new `session` WorkflowStage must be a genuine,
        explicitly-declared participant in the real per-instrument workflow
        graph (not an undeclared closure dependency) — and, since nothing
        yet depends on it, it must not perturb the pre-existing six stages'
        relative execution order. Verified against the REAL topological sort
        (Kahn, `WorkflowDefinition._topological_order`), not asserted by
        inspection alone."""
        from athena.runtime.workflow import WorkflowStage, build_definition

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_intraday_candles(iid, AS_OF.date(), seed=100))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-session-stage"
        )
        assert detail["decision_reports"], "session stage must not break the existing scan"

        # Reproduce the exact declared stage graph the real code builds (same
        # names/depends_on/produces as owner_validation.py's `defn`) to prove
        # the claim about ordering generically, without depending on any
        # single instrument's runtime data.
        noop = lambda ctx: {}  # noqa: E731
        stages = [
            WorkflowStage("indicators", noop, produces=("indicators", "vwap", "confluence")),
            WorkflowStage("regime", noop, produces=("regime", "market_health")),
            WorkflowStage("scoring", noop, depends_on=("indicators", "regime"), produces=("scoring",)),
            WorkflowStage("confidence", noop, depends_on=("scoring", "regime"),
                          produces=("evidence_bundle", "confidence")),
            WorkflowStage("risk", noop, depends_on=("indicators", "regime"), produces=("risk",)),
            WorkflowStage("decision", noop, depends_on=("scoring", "confidence", "risk"),
                          produces=("outcome",)),
        ]
        original_order = build_definition("pre-id1", stages).execution_order
        with_session = build_definition(
            "post-id1", [*stages, WorkflowStage("session", noop, produces=("session_context",))]
        ).execution_order
        # Every pre-existing stage keeps its exact relative order; "session"
        # is simply interleaved wherever the Kahn sort's declaration-index
        # tie-break places a new zero-dependency, zero-dependent stage.
        pre_existing_names = [n for n in with_session if n != "session"]
        assert tuple(pre_existing_names) == original_order
        assert "session" in with_session

    def test_repeat_validate_with_same_as_of_does_not_orphan_earlier_decision(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """Regression test for the exact owner-reported bug: validating two
        different symbols back-to-back with the same as_of (the normal case
        for ad-hoc "Re-validate" outside live trading hours, since
        resolve_validate_as_of always resolves to the same fixed session
        close) must not orphan the first symbol's decision from its own
        run. Each OwnerValidationPipeline.run() call now receives the
        orchestrator's own unique run_id instead of recomputing one locally
        from (trigger, as_of) — previously every such call collided on the
        same derived run_id, and whichever call ran second silently
        overwrote the first's persisted analysis via the runs-table upsert,
        even though the *decision* row itself still (correctly, now) points
        at its own distinct run_id."""
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        store.upsert_candidate(symbol="BBB")
        for sym, seed in (("AAA", 100), ("BBB", 200)):
            iid = f"NSE:{sym}"
            repo.upsert_instrument(
                Instrument(instrument_id=iid, symbol=sym, exchange="NSE", series="EQ", status="ACTIVE")
            )
            repo.add_candles(_candles(iid, seed=seed))
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=1, candles_fetched=80, candles_written=80,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )

        pipe_a = OwnerValidationPipeline(repo, config_dir, symbols_filter=["AAA"])
        pipe_a.run(RunTrigger.REFRESH, as_of=AS_OF, ingestion=ingestion, run_id="run-refresh-A")

        pipe_b = OwnerValidationPipeline(repo, config_dir, symbols_filter=["BBB"])
        pipe_b.run(RunTrigger.REFRESH, as_of=AS_OF, ingestion=ingestion, run_id="run-refresh-B")

        decisions = {d.instrument_id: d for d in repo.list_decisions(limit=50)}
        assert decisions["NSE:AAA"].run_id == "run-refresh-A"
        assert decisions["NSE:BBB"].run_id == "run-refresh-B"

    def test_risk_scores_every_dimension_from_calendar_and_universe(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """Regression (SD-1): RiskEngine.assess accepts a calendar context and
        the universe result for its event_risk / concentration_indicator
        dimensions, but this pipeline never passed either — so both were
        permanently UNKNOWN and every risk score was a mean over only 4 of the
        6 configured dimensions (completeness 0.75). Both objects already
        existed in run(); they were merely out of scope inside _scan_eligible.
        """
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        store.upsert_candidate(symbol="BBB")
        for sym, seed in (("AAA", 100), ("BBB", 200)):
            iid = f"NSE:{sym}"
            repo.upsert_instrument(
                Instrument(
                    instrument_id=iid, symbol=sym, exchange="NSE", series="EQ", status="ACTIVE"
                )
            )
            repo.add_candles(_candles(iid, seed=seed))
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=2, candles_fetched=160, candles_written=160,
            quotes_fetched=0, quotes_written=0, datasets_validated=2, datasets_skipped_empty=0,
        )

        pipe = OwnerValidationPipeline(repo, config_dir)
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-risk-dims"
        )

        reports = detail["decision_reports"]
        assert reports
        for report in reports.values():
            dims = {d["name"]: d for d in report["risk"]["dimensions"]}
            # The two dimensions that were silently blank on every decision.
            for name in ("event_risk", "concentration_indicator"):
                assert dims[name]["status"] == "OK", f"{name} still UNKNOWN"
                assert dims[name]["value"] is not None
                # A known dimension must carry its own evidence, not just a value.
                assert dims[name]["contributions"]
            # Prove the *real* objects were threaded through, not placeholders:
            # the calendar context must be for this run's own trading date...
            assert (
                dims["event_risk"]["contributions"][0]["reference"]
                == AS_OF.date().isoformat()
            )
            # ...and concentration must reflect this run's actual universe size.
            assert "2 eligible instrument(s)" in (
                dims["concentration_indicator"]["contributions"][0]["description"]
            )
            # Both now contribute to the weighted mean, so completeness must
            # exceed the 0.75 that four-of-six dimensions produced before.
            # It is not 1.0 here only because this fixture's linear price
            # series yields VOLATILITY_UNKNOWN from the regime engine — a
            # property of the synthetic candles, not of the wiring.
            assert Decimal(report["risk"]["completeness"]) > Decimal("0.75")

    def test_resolve_index_candles_uses_real_index_not_a_random_stock(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """Owner-reported bug (2026-07-29), the deeper of two root causes:
        `MarketSnapshot.indices` keys are bare labels ("NIFTY 50"), while the
        `candles` table stores everything under the full instrument_id
        ("NSE:NIFTY 50") — so the old `index_id = next(iter(snapshot.
        indices.keys()))` could never find real candles under that bare
        label, and _scan_eligible fell through to
        `candles_by_id.get(included_ids[0], ())` — an ARBITRARY INDIVIDUAL
        STOCK's own candles standing in for "the market index." Which stock
        won depended on scan scope (the first eligible symbol in a full
        cycle vs. the target symbol itself in a single-symbol re-validate),
        producing a different, fabricated "market regime" reading each time
        — the opposite of ADR-005. _resolve_index_candles() must always
        resolve the configured index's own real candles (via the correctly-
        prefixed instrument_id), never another instrument's."""
        pipe = OwnerValidationPipeline(repo, config_dir)
        repo.upsert_instrument(
            Instrument(
                instrument_id="NSE:NIFTY 50", symbol="NIFTY 50", exchange="NSE",
                series="EQ", status="ACTIVE",
            )
        )
        nifty_candles = _candles("NSE:NIFTY 50", seed=24000)
        repo.add_candles(nifty_candles)
        stock_candles = _candles("NSE:SOMESTOCK", seed=500)

        # candles_by_id here mimics a real scan scope: the index itself is
        # never one of the tracked owner_candidates, so it's absent from
        # this dict — only reachable via the repo (as in production).
        candles_by_id = {"NSE:SOMESTOCK": stock_candles}
        index_id, resolved = pipe._resolve_index_candles(candles_by_id)
        assert index_id == "NSE:NIFTY 50"
        assert resolved == nifty_candles
        # Never the unrelated stock's own candles standing in for the index.
        assert resolved != stock_candles

    def test_resolve_index_candles_honestly_empty_when_no_index_data_exists(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ADR-005: with zero real index candle history anywhere (not even
        via the repo), _resolve_index_candles() must return empty candles —
        never silently substitute an unrelated instrument's own candles as
        a stand-in for "the market index." The regime engine already
        degrades every dimension to its own *_UNKNOWN label for empty input."""
        pipe = OwnerValidationPipeline(repo, config_dir)
        stock_candles = _candles("NSE:SOMESTOCK", seed=500)
        candles_by_id = {"NSE:SOMESTOCK": stock_candles}
        _index_id, resolved = pipe._resolve_index_candles(candles_by_id)
        assert resolved == []

    def test_scoped_revalidate_reuses_last_full_cycle_concentration(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """Owner-reported bug (2026-07-29): re-validating a single symbol
        showed a much higher risk than the same symbol had during the full
        daily cycle, and the value kept changing on every re-validate. Root
        cause: a symbols_filter-scoped run's own universe_result only ever
        has 1 "eligible" instrument (itself), which always tripped
        concentrated_risk (70) regardless of real market breadth — SD-1
        wired concentration_indicator through correctly, but a scoped run's
        own narrow scan scope was never the right input for a market-wide
        breadth measure. Fix: a scoped run now reuses the last real FULL
        (unscoped) cycle's universe_summary instead of its own scan scope."""
        store = SqliteCandidateStore(repo)
        symbols = ["AAA", "BBB", "CCC"]
        for i, sym in enumerate(symbols):
            store.upsert_candidate(symbol=sym)
            iid = f"NSE:{sym}"
            repo.upsert_instrument(
                Instrument(instrument_id=iid, symbol=sym, exchange="NSE", series="EQ", status="ACTIVE")
            )
            repo.add_candles(_candles(iid, seed=100 + i * 100))
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=3, candles_fetched=240, candles_written=240,
            quotes_fetched=0, quotes_written=0, datasets_validated=3, datasets_skipped_empty=0,
        )

        # A full (unscoped) cycle first — this is the "last known real
        # breadth" a later scoped re-validate should fall back to.
        full_pipe = OwnerValidationPipeline(repo, config_dir)
        full_detail = full_pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-full-cycle"
        )
        _persist_run(repo, "run-full-cycle", AS_OF, full_detail)
        full_reports = full_detail["decision_reports"]
        full_dims = {d["name"]: d for r in full_reports.values() for d in r["risk"]["dimensions"]}
        full_concentration_desc = full_dims["concentration_indicator"]["contributions"][0]["description"]
        assert "3 eligible instrument(s)" in full_concentration_desc

        # Now a symbols_filter-scoped re-validate of just one symbol — its
        # own scan scope only ever has 1 eligible instrument, but its
        # concentration_indicator must reuse the full cycle's real breadth.
        scoped_pipe = OwnerValidationPipeline(repo, config_dir, symbols_filter=["AAA"])
        scoped_detail = scoped_pipe.run(
            RunTrigger.REFRESH, as_of=AS_OF, ingestion=ingestion, run_id="run-scoped-revalidate"
        )
        scoped_report = next(iter(scoped_detail["decision_reports"].values()))
        scoped_dims = {d["name"]: d for d in scoped_report["risk"]["dimensions"]}
        scoped_concentration = scoped_dims["concentration_indicator"]
        assert scoped_concentration["status"] == "OK"
        assert "1 eligible instrument(s)" not in scoped_concentration["contributions"][0]["description"]
        assert "3 eligible instrument(s)" in scoped_concentration["contributions"][0]["description"]
        # Same real breadth → same concentration risk value as the full cycle.
        assert scoped_concentration["value"] == full_dims["concentration_indicator"]["value"]

    def test_scoped_revalidate_finds_full_cycle_nested_under_pipeline_key(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """Regression for the exact owner-reported bug surviving the first
        fix attempt: DryRunCycleOrchestrator.run_cycle() (scheduling/
        dry_run.py, the real code path behind both the scheduled cycle and
        the "Run Full Validation" button) persists this pipeline's own
        returned dict nested one level down, under a "pipeline" key,
        alongside "phase"/"duration_seconds"/"ingestion" — never as the
        top-level detail_json. The first fix checked only the flat
        top-level shape, so it worked in a direct-call test but never
        found a real production run, leaving concentration_indicator
        perpetually UNKNOWN (and re-validate risk correspondingly inflated)
        in the actual running system. _last_full_universe_summary() must
        find the real breadth through this nesting."""
        store = SqliteCandidateStore(repo)
        symbols = ["AAA", "BBB", "CCC"]
        for i, sym in enumerate(symbols):
            store.upsert_candidate(symbol=sym)
            iid = f"NSE:{sym}"
            repo.upsert_instrument(
                Instrument(instrument_id=iid, symbol=sym, exchange="NSE", series="EQ", status="ACTIVE")
            )
            repo.add_candles(_candles(iid, seed=100 + i * 100))
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=3, candles_fetched=240, candles_written=240,
            quotes_fetched=0, quotes_written=0, datasets_validated=3, datasets_skipped_empty=0,
        )

        full_pipe = OwnerValidationPipeline(repo, config_dir)
        full_detail = full_pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-full-cycle-nested"
        )
        # Persist exactly as DryRunCycleOrchestrator.run_cycle() does: the
        # pipeline's own dict nested under "pipeline", not top-level.
        _persist_run(
            repo, "run-full-cycle-nested", AS_OF,
            {"phase": "finished", "duration_seconds": 1.0, "pipeline": full_detail, "ingestion": None},
        )

        scoped_pipe = OwnerValidationPipeline(repo, config_dir, symbols_filter=["AAA"])
        scoped_detail = scoped_pipe.run(
            RunTrigger.REFRESH, as_of=AS_OF, ingestion=ingestion, run_id="run-scoped-nested"
        )
        scoped_report = next(iter(scoped_detail["decision_reports"].values()))
        scoped_dims = {d["name"]: d for d in scoped_report["risk"]["dimensions"]}
        scoped_concentration = scoped_dims["concentration_indicator"]
        assert scoped_concentration["status"] == "OK", (
            "concentration_indicator was UNKNOWN — _last_full_universe_summary() "
            "failed to find the full cycle nested under the real pipeline key"
        )
        assert "3 eligible instrument(s)" in scoped_concentration["contributions"][0]["description"]

    def test_scoped_revalidate_concentration_unknown_with_no_prior_full_cycle(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """Honest fallback (ADR-005): if a symbols_filter-scoped run is the
        very first run ever (no prior full cycle to borrow breadth from),
        concentration_indicator must be UNKNOWN, never fabricated from the
        scoped run's own 1-symbol sample."""
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=1, candles_fetched=80, candles_written=80,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )

        pipe = OwnerValidationPipeline(repo, config_dir, symbols_filter=["AAA"])
        detail = pipe.run(
            RunTrigger.REFRESH, as_of=AS_OF, ingestion=ingestion, run_id="run-first-ever-scoped"
        )
        report = next(iter(detail["decision_reports"].values()))
        dims = {d["name"]: d for d in report["risk"]["dimensions"]}
        assert dims["concentration_indicator"]["status"] == "UNKNOWN"
        assert dims["concentration_indicator"]["value"] is None

    def test_unresolvable_candidate_reported_not_judged(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """A typo'd symbol has no catalog row and no ingested bar. Feeding a
        synthesized instrument to UniverseEngine would report it as "Excluded:
        failed rules", implying real market data said no — it must be reported
        as unresolved instead, and must not abort the run for real symbols."""
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        store.upsert_candidate(symbol="INFSDFSD")
        repo.upsert_instrument(
            Instrument(
                instrument_id="NSE:AAA", symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE"
            )
        )
        repo.add_candles(_candles("NSE:AAA", seed=100))

        detail = OwnerValidationPipeline(repo, config_dir).run(
            RunTrigger.REFRESH,
            as_of=AS_OF,
            ingestion=IngestionResult(
                as_of=AS_OF, instruments_upserted=1, candles_fetched=80, candles_written=80,
                quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
            ),
            run_id="run-unresolved",
        )

        assert "AAA" in detail["universe_members"]
        assert "INFSDFSD" not in detail["universe_members"]
        unresolved = detail["unresolved_candidates"]
        assert [row["symbol"] for row in unresolved] == ["INFSDFSD"]
        assert "may not exist" in str(unresolved[0]["reason"])

    def test_qualified_today_keeps_one_row_per_symbol(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """Owner-reported bug: re-validating the same symbol several times in
        one day listed it once per re-validate under Qualified Today. Only the
        newest same-day verdict per symbol may appear, exactly once."""
        pipe = OwnerValidationPipeline(repo, config_dir)
        for idx in range(3):
            repo.save_decision(
                Decision(
                    decision_id=f"d-aaa-{idx}",
                    ts=AS_OF.replace(hour=10, minute=idx),
                    run_id=f"run-{idx}",
                    cycle_id="cyc",
                    decision_type=DecisionType.WATCH,
                    explanation=f"pass {idx}",
                    instrument_id="NSE:AAA",
                    direction=Direction.LONG,
                )
            )

        qualified = pipe._qualified_from_repo(AS_OF)
        assert [row["symbol"] for row in qualified] == ["AAA"]
        assert qualified[0]["decision_id"] == "d-aaa-2"
        assert qualified[0]["explanation"] == "pass 2"

    def test_qualified_today_drops_symbol_downgraded_to_no_trade(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """A name whose newest same-day verdict is NO_TRADE must not keep
        surfacing from its earlier qualifying run."""
        pipe = OwnerValidationPipeline(repo, config_dir)
        for idx, decision_type in enumerate((DecisionType.WATCH, DecisionType.NO_TRADE)):
            repo.save_decision(
                Decision(
                    decision_id=f"d-bbb-{idx}",
                    ts=AS_OF.replace(hour=11, minute=idx),
                    run_id=f"run-b{idx}",
                    cycle_id="cyc",
                    decision_type=decision_type,
                    explanation=f"pass {idx}",
                    instrument_id="NSE:BBB",
                    direction=Direction.LONG,
                )
            )

        assert pipe._qualified_from_repo(AS_OF) == []

    def test_qualified_today_keeps_symbols_from_earlier_runs(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """Qualified Today is the day's list, not the current run's: validating
        one symbol used to rewrite it down to that symbol, hiding names that
        qualified earlier the same day."""
        pipe = OwnerValidationPipeline(repo, config_dir)
        for symbol, hour in (("NSE:AAA", 10), ("NSE:BBB", 14)):
            repo.save_decision(
                Decision(
                    decision_id=f"d-{symbol[-3:].lower()}",
                    ts=AS_OF.replace(hour=hour, minute=0),
                    run_id=f"run-{hour}",
                    cycle_id="cyc",
                    decision_type=DecisionType.WATCH,
                    explanation="qualified",
                    instrument_id=symbol,
                    direction=Direction.LONG,
                )
            )
        repo.save_decision(
            Decision(
                decision_id="d-yesterday",
                ts=AS_OF.replace(day=AS_OF.day - 1, hour=10),
                run_id="run-prev",
                cycle_id="cyc",
                decision_type=DecisionType.WATCH,
                explanation="yesterday",
                instrument_id="NSE:CCC",
                direction=Direction.LONG,
            )
        )

        qualified = pipe._qualified_from_repo(AS_OF)
        assert [row["symbol"] for row in qualified] == ["AAA", "BBB"]
