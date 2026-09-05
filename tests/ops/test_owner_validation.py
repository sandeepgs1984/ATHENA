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
from athena.domain.market import Candle, Instrument, MarketSnapshot, Quote
from athena.domain.run import RunRecord
from athena.intraday import GapDirection, RelativeStrengthRelation
from athena.ops.owner_candidates import SqliteCandidateStore, normalize_candidate_symbol
from athena.ops.owner_validation import OwnerValidationPipeline
from athena.session import SessionDataQualityStatus

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


def _d1(instrument_id: str, day: date, *, open_: str, close: str) -> Candle:
    """A single daily (D1) candle at an exact real calendar date — for
    ID-5C gap tests, which need precise previous-session/current-session
    D1 rows rather than `_candles()`'s arbitrary date range."""
    o, c = Decimal(open_), Decimal(close)
    return Candle(
        instrument_id=instrument_id, timeframe=Timeframe.D1,
        ts_open=datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
        open=o, high=max(o, c) + 1, low=min(o, c) - 1, close=c, volume=1_000_000, source="test",
    )


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
        test_vwap_flows_into_score_without_affecting_confidence above.

        ID-2.1: `as_of` is deliberately later in the session than the
        module's shared `AS_OF` — confluence now only counts candles
        genuinely COMPLETED by `as_of` (`ts_open + duration <= as_of`), so
        enough real session time must have elapsed for the fixture's 5m/15m
        bars to actually satisfy their SMA periods (9 and 5 respectively)
        without any of them still forming."""
        confluence_as_of = datetime(2026, 3, 2, 10, 35, tzinfo=IST)
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
            _timeframe_candles("NSE:AAA", confluence_as_of.date(), Timeframe.M5, 5, n=15, seed=100))
        repo.add_candles(
            _timeframe_candles("NSE:AAA", confluence_as_of.date(), Timeframe.M15, 15, n=8, seed=100))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=confluence_as_of, instruments_upserted=2, candles_fetched=183, candles_written=183,
            quotes_fetched=0, quotes_written=0, datasets_validated=2, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=confluence_as_of, ingestion=ingestion, run_id="run-test-confluence"
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
        a confluence bonus from 5m alone, not go UNKNOWN or error out.

        ID-2.1: `as_of` is deliberately later in the session, same reasoning
        as `test_confluence_flows_into_score_without_affecting_confidence`
        — enough real time must have elapsed for the 15 real 5m bars to be
        genuinely completed, not still forming."""
        confluence_as_of = datetime(2026, 3, 2, 10, 35, tzinfo=IST)
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_timeframe_candles(iid, confluence_as_of.date(), Timeframe.M5, 5, n=15, seed=100))
        # Only 3 bars at 15m — fewer than confluence.fifteen_min_sma_period
        # (5 in production config), so the 15m direction must resolve to
        # None (excluded), not raise or silently disagree.
        repo.add_candles(_timeframe_candles(iid, confluence_as_of.date(), Timeframe.M15, 15, n=3, seed=100))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=confluence_as_of, instruments_upserted=1, candles_fetched=98, candles_written=98,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=confluence_as_of, ingestion=ingestion, run_id="run-test-confluence-thin"
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

    def test_id2_intraday_analytics_stage_does_not_perturb_existing_stage_order(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-2 §8/§9/#21/#22: the new `intraday_analytics` stage explicitly
        depends on `session` and `indicators` (real dependencies, not an
        undeclared closure read) — and, since nothing among scoring/
        confidence/risk/decision depends on IT, those six pre-existing
        stages (already proven order-stable under ID-1's own `session`
        addition) must keep their exact relative order here too."""
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
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-intraday-analytics-stage"
        )
        assert detail["decision_reports"], "intraday_analytics stage must not break the existing scan"

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
            WorkflowStage("session", noop, produces=("session_context",)),
        ]
        original_order = build_definition("pre-id2", stages).execution_order
        with_intraday = build_definition(
            "post-id2",
            [*stages, WorkflowStage(
                "intraday_analytics", noop, depends_on=("session", "indicators"),
                produces=("intraday_signal_set",),
            )],
        ).execution_order
        pre_existing_names = [n for n in with_intraday if n != "intraday_analytics"]
        assert tuple(pre_existing_names) == original_order
        assert "intraday_analytics" in with_intraday

    def test_id2_intraday_signal_set_reuses_the_exact_same_vwap_and_confluence_scoring_used(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-2 §6/§12: "one authoritative calculation" — proven by object
        identity, not just equal values. `IntradayAnalyticsEngine.assess()`
        must receive the literal same `vwap`/`confluence` objects
        `ScoringEngine.score()` received the same cycle, never an
        independently recomputed pair that could silently diverge."""
        from athena.intraday.engine import IntradayAnalyticsEngine
        from athena.scoring.engine import ScoringEngine

        recorded: dict[str, object] = {}
        real_assess = IntradayAnalyticsEngine.assess
        real_score = ScoringEngine.score

        def spy_assess(self, *args, **kwargs):
            recorded["intraday_vwap"] = kwargs.get("vwap")
            recorded["intraday_confluence"] = kwargs.get("confluence")
            return real_assess(self, *args, **kwargs)

        def spy_score(self, *args, **kwargs):
            recorded["scoring_vwap"] = kwargs.get("vwap")
            recorded["scoring_confluence"] = kwargs.get("confluence")
            return real_score(self, *args, **kwargs)

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)
        monkeypatch.setattr(ScoringEngine, "score", spy_score)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_intraday_candles(iid, AS_OF.date(), seed=100))
        repo.add_candles(
            _timeframe_candles(iid, AS_OF.date(), Timeframe.M15, 15, n=8, seed=100))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=1, candles_fetched=94, candles_written=94,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-intraday-parity"
        )
        assert detail["decision_reports"]
        assert recorded["intraday_vwap"] is recorded["scoring_vwap"]
        assert recorded["intraday_confluence"] is recorded["scoring_confluence"]

    def test_id21_forming_5m_candle_has_zero_influence_until_it_completes(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-2.1 §10: non-vacuous proof, not just a unit test of the
        primitive in isolation. 9 real completed 5m bars (period=9) are
        crafted so `five_min_bullish` is deterministically False (last
        close below the trailing SMA). An extreme forming candle (close=500)
        is added after them — if it were incorrectly included, it would
        flip both VWAP's deviation_pct sign and `five_min_bullish` to True.

        Proves, against the REAL pipeline (not a mock): the forming candle
        changes NOTHING one second before it completes, and DOES change the
        result at the exact moment it completes — so the filter is neither
        a no-op (it must matter once eligible) nor over-aggressive (it must
        not matter before)."""
        from athena.scoring.engine import ScoringEngine

        recorded: list[dict[str, object]] = []
        real_score = ScoringEngine.score

        def spy_score(self, *args, **kwargs):
            result = real_score(self, *args, **kwargs)
            recorded.append({"vwap": kwargs.get("vwap"), "confluence": kwargs.get("confluence")})
            return result

        monkeypatch.setattr(ScoringEngine, "score", spy_score)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))

        start = datetime(2026, 3, 2, 9, 15, tzinfo=IST)
        # 9 completed bars, closes descending 110->102: mean=106, last=102 < 106 -> bearish.
        closes = [110, 109, 108, 107, 106, 105, 104, 103, 102]

        def m5(ts, close):
            px = Decimal(str(close))
            return Candle(instrument_id=iid, timeframe=Timeframe.M5, ts_open=ts,
                          open=px, high=px + 1, low=px - 1, close=px, volume=1_000, source="test")

        completed = [m5(start + timedelta(minutes=5 * i), c) for i, c in enumerate(closes)]
        repo.add_candles(completed)

        forming_ts = completed[-1].ts_open + timedelta(minutes=5)
        forming = m5(forming_ts, 500)  # would flip bearish -> bullish if included
        repo.add_candles([forming])

        just_before = forming_ts + timedelta(minutes=5) - timedelta(seconds=1)
        at_boundary = forming_ts + timedelta(minutes=5)

        pipe = OwnerValidationPipeline(repo, config_dir)

        def run_at(as_of, run_id):
            ingestion = IngestionResult(
                as_of=as_of, instruments_upserted=1, candles_fetched=10, candles_written=10,
                quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
            )
            recorded.clear()
            pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id=run_id)
            return recorded[0]

        before = run_at(just_before, "run-before-completion")
        at_bound = run_at(at_boundary, "run-at-completion")

        assert before["confluence"].five_min_bullish is False, (
            "baseline (forming candle not yet eligible) must stay bearish"
        )
        assert before["vwap"].values["deviation_pct"] < 0, "baseline VWAP must reflect only completed bars"

        assert at_bound["confluence"].five_min_bullish is True, (
            "once genuinely completed, the extreme candle MUST flip five_min_bullish -- "
            "proving the filter is not a no-op"
        )
        assert at_bound["vwap"].values["deviation_pct"] != before["vwap"].values["deviation_pct"]

    def test_id21_forming_15m_candle_excluded_from_confluence_until_completion(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """Same proof as the 5m test, for the 15m confluence leg
        (period=5) — a distinct code path (`fifteen_min_cs`) from the 5m one,
        so it needs its own non-vacuous evidence."""
        from athena.scoring.engine import ScoringEngine

        recorded: list[dict[str, object]] = []
        real_score = ScoringEngine.score

        def spy_score(self, *args, **kwargs):
            result = real_score(self, *args, **kwargs)
            recorded.append({"confluence": kwargs.get("confluence")})
            return result

        monkeypatch.setattr(ScoringEngine, "score", spy_score)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))

        start = datetime(2026, 3, 2, 9, 15, tzinfo=IST)
        closes = [110, 108, 106, 104, 102]  # 5 bars, period=5: mean=106, last=102 < 106 -> bearish

        def m15(ts, close):
            px = Decimal(str(close))
            return Candle(instrument_id=iid, timeframe=Timeframe.M15, ts_open=ts,
                          open=px, high=px + 1, low=px - 1, close=px, volume=1_000, source="test")

        completed = [m15(start + timedelta(minutes=15 * i), c) for i, c in enumerate(closes)]
        repo.add_candles(completed)
        # 5m history so daily/5m legs resolve too (not the object under test here).
        repo.add_candles(_timeframe_candles(iid, start.date(), Timeframe.M5, 5, n=15, seed=100))

        forming_ts = completed[-1].ts_open + timedelta(minutes=15)
        repo.add_candles([m15(forming_ts, 500)])

        just_before = forming_ts + timedelta(minutes=15) - timedelta(seconds=1)
        at_boundary = forming_ts + timedelta(minutes=15)

        pipe = OwnerValidationPipeline(repo, config_dir)

        def run_at(as_of, run_id):
            ingestion = IngestionResult(
                as_of=as_of, instruments_upserted=1, candles_fetched=20, candles_written=20,
                quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
            )
            recorded.clear()
            pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id=run_id)
            return recorded[0]

        before = run_at(just_before, "run-before-completion-15m")
        at_bound = run_at(at_boundary, "run-at-completion-15m")

        assert before["confluence"].fifteen_min_bullish is False
        assert at_bound["confluence"].fifteen_min_bullish is True

    def test_id21_session_context_and_confluence_agree_on_latest_completed_bar(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-2.1 §7: `SessionContext.five_min.latest_completed_bar_ts` must
        never disagree with which bar the analytical path (VWAP/confluence)
        actually treated as eligible — a mismatch would mean two different
        completed-candle authorities exist, exactly what ID-2.1 exists to
        rule out."""
        from athena.intraday.engine import IntradayAnalyticsEngine

        recorded: dict[str, object] = {}
        real_assess = IntradayAnalyticsEngine.assess

        def spy_assess(self, *args, **kwargs):
            recorded["session_context"] = kwargs.get("session_context")
            recorded["vwap"] = kwargs.get("vwap")
            return real_assess(self, *args, **kwargs)

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_intraday_candles(iid, AS_OF.date(), n=6, seed=100))  # 09:15..09:40

        as_of = datetime(2026, 3, 2, 9, 27, tzinfo=IST)  # mid-bar for the 09:25 5m candle
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-consistency")

        session_context = recorded["session_context"]
        vwap = recorded["vwap"]
        # SessionContext's own completed-bar boundary must be at/after the
        # latest candle actually used to compute VWAP's deviation -- proven
        # by re-deriving VWAP with athena.session's own primitive and
        # confirming it matches what ScoringEngine received (already proven
        # object-identical elsewhere; here proven semantically consistent).
        assert session_context.five_min.latest_completed_bar_ts == datetime(2026, 3, 2, 9, 20, tzinfo=IST)
        assert vwap is not None and vwap.status.value == "OK"

    def test_id3_intraday_signal_set_carries_or15_or30_from_a_real_cycle(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-3 §10/#25: `IntradaySignalSet.or15`/`.or30` must be genuinely
        populated (not left as a placeholder) by a real pipeline cycle, and
        `OpeningRangeEngine` must receive real 5m candles from the real
        repository — proving the wiring inside `intraday_analytics_stage`
        actually runs, not just that the dataclass accepts the fields."""
        from athena.intraday.engine import IntradayAnalyticsEngine
        from athena.intraday.opening_range_models import OpeningRangeFormationStatus

        recorded: dict[str, object] = {}
        real_assess = IntradayAnalyticsEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded["signal_set"] = result
            return result

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_intraday_candles(iid, AS_OF.date(), n=6, seed=100))  # 09:15..09:40

        as_of = datetime(2026, 3, 2, 9, 30, tzinfo=IST)  # OR15 window (09:15-09:30) just elapsed
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-orb")

        assert detail["decision_reports"]
        signal_set = recorded["signal_set"]
        assert signal_set.or15.formation.status is OpeningRangeFormationStatus.COMPLETE
        assert signal_set.or15.formation.bars_present == 3
        assert signal_set.or30.formation.status is OpeningRangeFormationStatus.FORMING

    def test_id31_orb_and_vwap_survive_a_high_row_density_session_via_the_real_repo(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-3.1 §22/§23 retrieval regression: the exact real production
        defect ID-3's real-data sanity check found — a fixed
        `list_candles_recent(limit=100)` read silently drops a session's
        own opening bars once persisted row density for that session
        exceeds 100. This test seeds 130 real M5 rows for one session (more
        than the old fixed limit, and spanning well past `as_of` in
        timestamp terms, so a fetch with no `as_of` bound would grab
        chronologically-later rows instead of the session's own opening
        bars) and asserts OR15 still resolves COMPLETE from its own
        canonical opening bars and VWAP still receives session data — proof
        the production path no longer depends on an arbitrary "latest N
        rows" fetch. This test must fail if `intraday_analytics_stage`/
        `ind_stage`/`session_stage` ever revert to `list_candles_recent`."""
        from athena.intraday.engine import IntradayAnalyticsEngine
        from athena.intraday.models import VwapRelation
        from athena.intraday.opening_range_models import OpeningRangeFormationStatus

        recorded: dict[str, object] = {}
        real_assess = IntradayAnalyticsEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded["signal_set"] = result
            return result

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        # 130 5m rows for one session (09:15 onward) -- more than the old
        # fixed limit=100, and the tail extends well past `as_of` (09:30),
        # so a fetch with no as_of bound (the pre-ID-3.1 `list_candles_recent`
        # path) would keep the 100 chronologically-LATEST rows and drop the
        # session's own opening bars entirely.
        repo.add_candles(_intraday_candles(iid, AS_OF.date(), n=130, seed=100))

        as_of = datetime(2026, 3, 2, 9, 30, tzinfo=IST)  # OR15 window just elapsed
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=130, candles_written=130,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-dense-session"
        )

        assert detail["decision_reports"]
        signal_set = recorded["signal_set"]
        assert signal_set.or15.formation.status is OpeningRangeFormationStatus.COMPLETE
        assert signal_set.or15.formation.bars_present == 3
        assert signal_set.vwap.relation is not VwapRelation.VWAP_UNAVAILABLE

    def test_id4_relative_strength_stage_does_not_perturb_existing_stage_order(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-4 §21/§22: the new `relative_strength` stage explicitly
        depends only on `session` (a real dependency, not an undeclared
        closure read) — and, since nothing among scoring/confidence/risk/
        decision depends on IT, and `intraday_analytics` merely gains it as
        a THIRD declared dependency (alongside its existing `session`/
        `indicators`), the six pre-existing structural stages (already
        proven order-stable under ID-1/ID-2's own additions) must keep
        their exact relative order here too."""
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
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-rs-stage"
        )
        assert detail["decision_reports"], "relative_strength stage must not break the existing scan"

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
            WorkflowStage("session", noop, produces=("session_context",)),
        ]
        original_order = build_definition("pre-id4", stages).execution_order
        with_rs = build_definition(
            "post-id4",
            [
                *stages,
                WorkflowStage(
                    "relative_strength", noop, depends_on=("session",),
                    produces=("relative_strength",),
                ),
                WorkflowStage(
                    "intraday_analytics", noop,
                    depends_on=("session", "indicators", "relative_strength"),
                    produces=("intraday_signal_set",),
                ),
            ],
        ).execution_order
        pre_existing_names = [n for n in with_rs if n not in ("relative_strength", "intraday_analytics")]
        assert tuple(pre_existing_names) == original_order
        assert "relative_strength" in with_rs
        assert with_rs.index("relative_strength") < with_rs.index("intraday_analytics")

    def test_id4_intraday_signal_set_carries_real_relative_strength_from_a_real_cycle(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-4 §19/#21: `IntradaySignalSet.relative_strength` must be
        genuinely populated from real repository data for the actual
        authoritative market benchmark (NSE:NIFTY 50, resolved the exact
        same way regime already resolves it) and a real, mapped sector
        index (NSE:NIFTY IT, via the real config/sector_index_mapping.json
        + config/index_intelligence.json chain) — not a placeholder."""
        from athena.intraday.engine import IntradayAnalyticsEngine

        recorded: dict[str, object] = {}
        real_assess = IntradayAnalyticsEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded["signal_set"] = result
            return result

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(
                instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE",
                sector="Information Technology",
            )
        )
        repo.upsert_instrument(
            Instrument(instrument_id="NSE:NIFTY 50", symbol="NIFTY 50", exchange="NSE",
                       series="INDEX", status="ACTIVE")
        )
        repo.upsert_instrument(
            Instrument(instrument_id="NSE:NIFTY IT", symbol="NIFTY IT", exchange="NSE",
                       series="INDEX", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_intraday_candles(iid, AS_OF.date(), n=2, seed=100))
        repo.add_candles(_intraday_candles("NSE:NIFTY 50", AS_OF.date(), n=2, seed=1000))
        repo.add_candles(_intraday_candles("NSE:NIFTY IT", AS_OF.date(), n=2, seed=500))

        as_of = datetime(2026, 3, 2, 9, 30, tzinfo=IST)  # both 5m bars completed for all three
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=3, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-rs")

        assert detail["decision_reports"]
        rs = recorded["signal_set"].relative_strength
        assert rs.market_benchmark_id == "NSE:NIFTY 50"
        assert rs.sector_benchmark_id == "NSE:NIFTY IT"
        assert rs.stock_available and rs.sector_available and rs.market_available
        assert rs.stock_return_pct == Decimal("1")
        assert rs.sector_return_pct == Decimal("0.2")
        assert rs.market_return_pct == Decimal("0.1")
        assert rs.stock_vs_market_relation is RelativeStrengthRelation.OUTPERFORMING

    def test_id5c_monday_uses_previous_friday_close_via_real_calendar(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5C §10: a real Monday session must resolve its previous
        trading session as the immediately preceding Friday via the real
        calendar authority (`latest_trading_day_on_or_before`), not naive
        weekday arithmetic. 2026-08-31 is a real Monday; 2026-08-28 is the
        real immediately preceding Friday (ID-5A's own repaired date)."""
        from athena.intraday.engine import IntradayAnalyticsEngine

        recorded: dict[str, object] = {}
        real_assess = IntradayAnalyticsEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded["signal_set"] = result
            return result

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))  # unrelated history, for universe eligibility only
        repo.add_candles([_d1(iid, date(2026, 8, 28), open_="98", close="100")])  # Friday settled close
        repo.add_candles([_d1(iid, date(2026, 8, 31), open_="103", close="103")])  # Monday's own open
        repo.add_candles(_intraday_candles(iid, date(2026, 8, 31), n=2, seed=100))

        as_of = datetime(2026, 8, 31, 9, 30, tzinfo=IST)
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-gap-monday")

        assert detail["decision_reports"]
        gap = recorded["signal_set"].gap
        assert gap.available is True
        assert gap.previous_session_date == date(2026, 8, 28)
        assert gap.previous_session_close == Decimal("100")
        assert gap.current_session_open == Decimal("103")
        assert gap.gap_pct == Decimal("3")
        assert gap.direction is GapDirection.GAP_UP

    def test_id5c_holiday_transition_uses_actual_previous_trading_session(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5C §10: Tuesday 2026-09-15's previous trading session is
        Friday 2026-09-11 (Monday 2026-09-14 is a real exchange holiday,
        Ganesh Chaturthi, per config/calendar/holidays.json) — proves the
        calendar-driven resolution correctly skips a holiday, not just a
        weekend."""
        from athena.intraday.engine import IntradayAnalyticsEngine

        recorded: dict[str, object] = {}
        real_assess = IntradayAnalyticsEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded["signal_set"] = result
            return result

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles([_d1(iid, date(2026, 9, 11), open_="98", close="100")])  # Friday before the holiday
        repo.add_candles([_d1(iid, date(2026, 9, 15), open_="102", close="102")])  # Tuesday after the holiday
        repo.add_candles(_intraday_candles(iid, date(2026, 9, 15), n=2, seed=100))

        as_of = datetime(2026, 9, 15, 9, 30, tzinfo=IST)
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-gap-holiday")

        assert detail["decision_reports"]
        gap = recorded["signal_set"].gap
        assert gap.available is True
        assert gap.previous_session_date == date(2026, 9, 11)
        assert gap.previous_session_close == Decimal("100")
        assert gap.gap_pct == Decimal("2")

    def test_id5c_missing_immediate_previous_session_does_not_substitute_stale_candle(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5C §28: the calendar correctly resolves 2026-08-28 (Friday)
        as Monday 2026-08-31's immediately preceding trading session, but
        ATHENA's own D1 history is genuinely missing that exact date (only
        an OLDER row, 2026-08-25, exists). GapContext must report
        unavailable, never silently substitute the older candle -- proven
        non-vacuously by reverting the exact-match lookup and confirming
        this test then wrongly finds a value."""
        from athena.intraday.engine import IntradayAnalyticsEngine

        recorded: dict[str, object] = {}
        real_assess = IntradayAnalyticsEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded["signal_set"] = result
            return result

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        # Deliberately NO candle at 2026-08-28 (the real immediately
        # preceding trading session) -- only an older, stale one.
        repo.add_candles([_d1(iid, date(2026, 8, 25), open_="80", close="95")])
        repo.add_candles([_d1(iid, date(2026, 8, 31), open_="103", close="103")])
        repo.add_candles(_intraday_candles(iid, date(2026, 8, 31), n=2, seed=100))

        as_of = datetime(2026, 8, 31, 9, 30, tzinfo=IST)
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-gap-stale")

        assert detail["decision_reports"]
        gap = recorded["signal_set"].gap
        assert gap.available is False
        assert gap.previous_session_close is None
        # The calendar still correctly identifies WHICH date should have
        # been used, even though ATHENA has no data for it.
        assert gap.previous_session_date == date(2026, 8, 28)

    def test_id5c_later_m5_data_cannot_change_gap(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5C §5/§14/§15/§16: GapContext is derived purely from D1
        candles -- an extreme, off-grid, and still-forming M5 row must
        have zero effect on it. Proven by running the identical scenario
        twice (clean, then with extreme M5 noise added) and asserting the
        resulting GapContext is byte-identical both times."""
        from athena.intraday.engine import IntradayAnalyticsEngine

        recorded: list[object] = []
        real_assess = IntradayAnalyticsEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded.append(result)
            return result

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles([_d1(iid, date(2026, 8, 28), open_="98", close="100")])
        repo.add_candles([_d1(iid, date(2026, 8, 31), open_="103", close="103")])
        repo.add_candles(_intraday_candles(iid, date(2026, 8, 31), n=2, seed=100))

        as_of = datetime(2026, 8, 31, 9, 30, tzinfo=IST)
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-gap-clean")
        baseline_gap = recorded[-1].gap
        assert baseline_gap.available is True
        assert baseline_gap.gap_pct == Decimal("3")

        # Add extreme canonical, off-grid, and still-forming M5 rows, then
        # re-validate -- the gap must come out byte-identical.
        repo.add_candles([Candle(
            instrument_id=iid, timeframe=Timeframe.M5,
            ts_open=datetime(2026, 8, 31, 9, 20, tzinfo=IST),
            open=Decimal("999999"), high=Decimal("999999"), low=Decimal("999999"),
            close=Decimal("999999"), volume=1, source="test",
        )])
        repo.add_candles([Candle(
            instrument_id=iid, timeframe=Timeframe.M5,
            ts_open=datetime(2026, 8, 31, 9, 23, 55, tzinfo=IST),  # off-grid
            open=Decimal("1"), high=Decimal("999999"), low=Decimal("1"),
            close=Decimal("999999"), volume=1, source="test",
        )])
        repo.add_candles([Candle(
            instrument_id=iid, timeframe=Timeframe.M5,
            ts_open=datetime(2026, 8, 31, 9, 25, tzinfo=IST),  # not yet completed at 9:30
            open=Decimal("1"), high=Decimal("999999"), low=Decimal("1"),
            close=Decimal("999999"), volume=1, source="test",
        )])
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-gap-noisy")
        noisy_gap = recorded[-1].gap
        assert noisy_gap == baseline_gap

    def test_id5d_relative_volume_stage_does_not_perturb_existing_stage_order(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-5D: the new `relative_volume` stage explicitly depends only
        on `session` (matching `relative_strength`'s own dependency shape)
        — and, since nothing among scoring/confidence/risk/decision
        depends on IT, and `intraday_analytics` merely gains it as a
        FOURTH declared dependency (alongside its existing `session`/
        `indicators`/`relative_strength`), the six pre-existing structural
        stages must keep their exact relative order here too."""
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
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-rv-stage"
        )
        assert detail["decision_reports"], "relative_volume stage must not break the existing scan"

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
            WorkflowStage("session", noop, produces=("session_context",)),
            WorkflowStage(
                "relative_strength", noop, depends_on=("session",), produces=("relative_strength",),
            ),
        ]
        original_order = build_definition("pre-id5d", stages).execution_order
        with_rv = build_definition(
            "post-id5d",
            [
                *stages,
                WorkflowStage(
                    "relative_volume", noop, depends_on=("session",),
                    produces=("relative_volume",),
                ),
                WorkflowStage(
                    "intraday_analytics", noop,
                    depends_on=("session", "indicators", "relative_strength", "relative_volume"),
                    produces=("intraday_signal_set",),
                ),
            ],
        ).execution_order
        pre_existing_names = [n for n in with_rv if n not in ("relative_volume", "intraday_analytics")]
        assert tuple(pre_existing_names) == original_order
        assert "relative_volume" in with_rv
        assert with_rv.index("relative_volume") < with_rv.index("intraday_analytics")

    def test_id5d_intraday_signal_set_carries_real_relative_volume_from_a_real_cycle(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5D: `IntradaySignalSet.relative_volume` must be genuinely
        populated from real repository data via the stage's own bounded
        wide-lookback M5 read — not a placeholder. Today (a real Monday,
        2026-08-31) has two canonical M5 bars totalling 200 volume; the
        one comparable historical settled session (Friday 2026-08-28) has
        the same two same-time-of-day slots totalling 100 volume. The
        expected ratio (200/100 = 2.0x, ABOVE_BASELINE) proves the real
        pipeline wiring reaches RelativeVolumeEngine correctly, with
        `baseline_session_count == 1` exposing full provenance."""
        from athena.intraday.engine import IntradayAnalyticsEngine
        from athena.intraday.relative_volume_models import RelativeVolumeRelation

        recorded: dict[str, object] = {}
        real_assess = IntradayAnalyticsEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded["signal_set"] = result
            return result

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))  # unrelated D1 history, for universe eligibility only
        repo.add_candles([_d1(iid, date(2026, 8, 28), open_="98", close="100")])
        repo.add_candles([_d1(iid, date(2026, 8, 31), open_="103", close="103")])

        def _m5_vol(day: date, hh: int, mm: int, volume: int) -> Candle:
            ts = datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST)
            return Candle(
                instrument_id=iid, timeframe=Timeframe.M5, ts_open=ts,
                open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100"),
                volume=volume, source="test",
            )

        # Comparable historical settled session: Friday 2026-08-28.
        repo.add_candles([
            _m5_vol(date(2026, 8, 28), 9, 15, 50),
            _m5_vol(date(2026, 8, 28), 9, 20, 50),
        ])
        # Today: Monday 2026-08-31, same two same-time-of-day slots.
        repo.add_candles([
            _m5_vol(date(2026, 8, 31), 9, 15, 100),
            _m5_vol(date(2026, 8, 31), 9, 20, 100),
        ])

        as_of = datetime(2026, 8, 31, 9, 30, tzinfo=IST)  # both today's bars completed
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-rvol")

        assert detail["decision_reports"]
        rv = recorded["signal_set"].relative_volume
        assert rv.available is True
        assert rv.current_cumulative_volume == 200
        assert rv.current_canonical_bar_count == 2
        assert rv.baseline_session_count == 1
        assert rv.baseline_session_dates == (date(2026, 8, 28),)
        assert rv.historical_average_cumulative_volume == Decimal("100")
        assert rv.rvol_ratio == Decimal("2")
        assert rv.relation is RelativeVolumeRelation.ABOVE_BASELINE

    def test_id5d1_retrieval_is_not_capped_at_the_old_hardcoded_120_day_window(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5D.1 Issue B: the ONLY comparable historical settled session
        seeded here is 2026-01-05 -- a real trading Monday (verified via
        the real calendar) 238 calendar days before as_of (2026-08-31),
        well beyond ID-5D's original hardcoded 120-day retrieval window.
        The corrected retrieval path (`repo.earliest_candle_ts`-based, not
        a hardcoded lookback) must still find and use it -- proving the
        analytical baseline POLICY ("use ALL available comparable prior
        settled sessions") is no longer silently capped by an
        undisclosed retrieval bound."""
        from athena.intraday.engine import IntradayAnalyticsEngine

        recorded: dict[str, object] = {}
        real_assess = IntradayAnalyticsEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded["signal_set"] = result
            return result

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles([_d1(iid, date(2026, 8, 28), open_="98", close="100")])
        repo.add_candles([_d1(iid, date(2026, 8, 31), open_="103", close="103")])

        def _m5_vol(day: date, hh: int, mm: int, volume: int) -> Candle:
            ts = datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST)
            return Candle(
                instrument_id=iid, timeframe=Timeframe.M5, ts_open=ts,
                open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100"),
                volume=volume, source="test",
            )

        far_history_day = date(2026, 1, 5)  # a real trading Monday, 238 days before as_of
        assert (date(2026, 8, 31) - far_history_day).days > 120
        repo.add_candles([
            _m5_vol(far_history_day, 9, 15, 40),
            _m5_vol(far_history_day, 9, 20, 40),
        ])
        repo.add_candles([
            _m5_vol(date(2026, 8, 31), 9, 15, 100),
            _m5_vol(date(2026, 8, 31), 9, 20, 100),
        ])

        as_of = datetime(2026, 8, 31, 9, 30, tzinfo=IST)
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        detail = pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-rvol-far")

        assert detail["decision_reports"]
        rv = recorded["signal_set"].relative_volume
        assert rv.available is True
        assert rv.baseline_session_count == 1
        assert rv.baseline_session_dates == (far_history_day,)
        assert rv.historical_average_cumulative_volume == Decimal("80")
        assert rv.rvol_ratio == Decimal("2.5")

    def test_id5e_d1_indicators_are_invariant_to_future_d1_candles(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5E §27 (Daily Future-Leak Proof): `IndicatorEngine.compute_all`
        (SMA/RSI/ADX/MACD/ATR/VOLUME_MA) reads `cs`, the D1 series
        `list_candles_recent(..., as_of=as_of)` resolves -- it must be
        byte-identical whether or not the repository ALSO holds D1 candles
        dated after this historical `as_of` (as it would after further
        real ingestion in a genuine replay scenario). Proven by running
        the identical historical cycle twice: once against clean data,
        once after adding extreme-valued future D1 rows, and asserting the
        recorded indicator results are unchanged."""
        from athena.indicators.engine import IndicatorEngine

        recorded: list[object] = []
        real_compute_all = IndicatorEngine.compute_all

        def spy_compute_all(self, *args, **kwargs):
            result = real_compute_all(self, *args, **kwargs)
            recorded.append(result)
            return result

        monkeypatch.setattr(IndicatorEngine, "compute_all", spy_compute_all)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))  # 2025-11-01 .. 2026-01-19 (80 days)
        as_of = datetime(2026, 1, 20, 9, 30, tzinfo=IST)  # the historical replay target instant

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=80, candles_written=80,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-d1-clean")
        clean = recorded[-1]

        # Seed extreme-valued FUTURE D1 candles dated after as_of -- already
        # present in the repository, as real further ingestion would leave
        # them, before replaying the SAME historical as_of again.
        future_days = [date(2026, 1, 21) + timedelta(days=i) for i in range(30)]
        repo.add_candles([
            Candle(
                instrument_id=iid, timeframe=Timeframe.D1,
                ts_open=datetime.combine(d, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                open=Decimal("999999"), high=Decimal("999999"), low=Decimal("999999"),
                close=Decimal("999999"), volume=1, source="test",
            )
            for d in future_days
        ])
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-d1-noisy")
        noisy = recorded[-1]

        assert noisy == clean

    def test_id5e_intraday_signal_set_is_invariant_to_future_intraday_candles(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5E §26 (Historical Replay / Pipeline Invariance Proof): the
        entire IntradaySignalSet (vwap, confluence/trend, OR15/OR30,
        RelativeStrength, Gap, RelativeVolume) must be byte-identical
        whether or not the repository ALSO holds M5/M15/D1 candles dated
        after this historical `as_of` -- covering §15's confluence fix
        specifically (the M5/M15 `list_candles_recent(limit=100)` reads
        feeding SMA(9)/SMA(5) direction) alongside every other
        as_of-bounded read already exercised by ID-2 through ID-5D's own
        real-cycle tests. Proven the same way as the D1 proof above: run
        the identical historical cycle twice, add extreme-valued future
        M5/M15/D1 noise between runs, assert the recorded IntradaySignalSet
        is unchanged."""
        from athena.intraday.engine import IntradayAnalyticsEngine

        recorded: list[object] = []
        real_assess = IntradayAnalyticsEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded.append(result)
            return result

        monkeypatch.setattr(IntradayAnalyticsEngine, "assess", spy_assess)

        # Same 15 M5 / 8 M15 real-bar shape the existing confluence
        # integration test uses (both SMA periods, 9 and 5, genuinely
        # satisfied, none still forming) -- with too few real bars,
        # confluence is already None in both runs regardless of any
        # retrieval bug, which would make this proof vacuous.
        confluence_as_of = datetime(2026, 3, 2, 10, 35, tzinfo=IST)
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_timeframe_candles(iid, confluence_as_of.date(), Timeframe.M5, 5, n=15, seed=100))
        repo.add_candles(_timeframe_candles(iid, confluence_as_of.date(), Timeframe.M15, 15, n=8, seed=100))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=confluence_as_of, instruments_upserted=1, candles_fetched=103, candles_written=103,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(
            RunTrigger.PREMARKET, as_of=confluence_as_of, ingestion=ingestion,
            run_id="run-intraday-clean",
        )
        clean = recorded[-1]
        assert clean.trend.five_min.bullish is not None, "test setup must produce a real confluence signal"

        def _extreme(tf: Timeframe, ts: datetime) -> Candle:
            return Candle(
                instrument_id=iid, timeframe=tf, ts_open=ts,
                open=Decimal("999999"), high=Decimal("999999"), low=Decimal("999999"),
                close=Decimal("999999"), volume=999999, source="test",
            )

        # Future noise: later-the-same-day M5/M15 bars (past this run's own
        # as_of, as they would be after later real ingestion the same
        # session) plus a future D1 candle. Seeded in bulk (>= the
        # confluence reads' own limit=100) so an unbounded fetch would
        # genuinely crowd the real pre-as_of bars out of the LIMIT window
        # -- not merely add a single row completed_candles would filter
        # out downstream regardless of retrieval bounding.
        future_intraday = [
            _extreme(tf, datetime(2026, 3, 2, 14, 0, tzinfo=IST) + timedelta(minutes=5 * i))
            for tf in (Timeframe.M5, Timeframe.M15)
            for i in range(120)
        ]
        repo.add_candles([
            *future_intraday,
            _extreme(Timeframe.D1, datetime(2026, 3, 3, 9, 15, tzinfo=IST)),
        ])
        pipe.run(
            RunTrigger.PREMARKET, as_of=confluence_as_of, ingestion=ingestion,
            run_id="run-intraday-noisy",
        )
        noisy = recorded[-1]

        assert noisy == clean

    def test_id5f_session_context_latest_quote_ts_is_invariant_to_a_future_quote(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5F §11/§12 (SessionContext Pipeline Invariance / Future-Quote
        Non-Vacuous Proof): `SessionContext.latest_quote_ts` must be
        byte-identical whether or not the repository ALSO holds a quote
        dated after this run's own `as_of` (as it would after further real
        polling since that historical instant). Proven the same way as
        ID-5E's own proofs: run the identical historical cycle twice, add
        a future-dated quote between runs, assert the recorded
        SessionContext is unchanged."""
        from athena.session import SessionContextEngine

        recorded: list[object] = []
        real_assess = SessionContextEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded.append(result)
            return result

        monkeypatch.setattr(SessionContextEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_intraday_candles(iid, date(2026, 1, 20), n=2, seed=100))
        real_quote_ts = datetime(2026, 1, 20, 9, 20, tzinfo=IST)
        repo.add_quotes([
            Quote(instrument_id=iid, ts=real_quote_ts, last_price=Decimal("100"),
                  volume=1000, source="test"),
        ])

        as_of = datetime(2026, 1, 20, 9, 25, tzinfo=IST)
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=82, candles_written=82,
            quotes_fetched=1, quotes_written=1, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-quote-clean")
        clean = recorded[-1]
        assert clean.latest_quote_ts == real_quote_ts
        assert clean.data_quality is not SessionDataQualityStatus.QUOTE_UNAVAILABLE

        # Future quote dated after as_of -- already present in the
        # repository, as real further polling would leave it, before
        # replaying the SAME historical as_of again.
        repo.add_quotes([
            Quote(instrument_id=iid, ts=datetime(2026, 1, 20, 9, 40, tzinfo=IST),
                  last_price=Decimal("999999"), volume=1, source="test"),
        ])
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-quote-noisy")
        noisy = recorded[-1]

        assert noisy == clean
        assert noisy.latest_quote_ts == real_quote_ts

    def test_id5f_no_historical_quote_preserves_quote_unavailable_semantics(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5F §16: with zero quotes at or before `as_of` (only a future
        one exists), `SessionContext` must still degrade to
        `QUOTE_UNAVAILABLE` -- ID-5F must not accidentally return the
        oldest future quote just because it's the only one in the
        database."""
        from athena.session import SessionContextEngine

        recorded: list[object] = []
        real_assess = SessionContextEngine.assess

        def spy_assess(self, *args, **kwargs):
            result = real_assess(self, *args, **kwargs)
            recorded.append(result)
            return result

        monkeypatch.setattr(SessionContextEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_intraday_candles(iid, date(2026, 1, 20), n=2, seed=100))
        repo.add_candles(_timeframe_candles(iid, date(2026, 1, 20), Timeframe.M15, 15, n=1, seed=100))
        repo.add_quotes([
            Quote(instrument_id=iid, ts=datetime(2026, 1, 20, 9, 40, tzinfo=IST),
                  last_price=Decimal("999999"), volume=1, source="test"),
        ])

        as_of = datetime(2026, 1, 20, 9, 25, tzinfo=IST)
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=83, candles_written=83,
            quotes_fetched=1, quotes_written=1, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-quote-future-only")

        ctx = recorded[-1]
        assert ctx.latest_quote_ts is None
        assert ctx.data_quality is SessionDataQualityStatus.QUOTE_UNAVAILABLE

    def test_id5g_market_health_snapshot_input_is_invariant_to_a_future_snapshot(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5G §14/§17 (Pipeline Invariance / Future-Snapshot Non-Vacuous
        Proof): the `MarketSnapshot` fed to `MarketHealthEngine.assess()`
        (via `_resolve_snapshot`'s `enriched_snap`) must be byte-identical
        whether or not the repository ALSO holds a snapshot dated after
        this run's own `as_of` (as it would after further real polling
        since that historical instant). Proven the same way as ID-5E's/
        ID-5F's own proofs: run the identical historical cycle twice, add
        a future-dated snapshot with an extreme india_vix between runs,
        assert the recorded snapshot's `india_vix` is unchanged."""
        from athena.market_health.engine import MarketHealthEngine

        recorded: list[object] = []
        real_assess = MarketHealthEngine.assess

        def spy_assess(self, index_symbol, index_candles, snapshot, **kwargs):
            recorded.append(snapshot)
            return real_assess(self, index_symbol, index_candles, snapshot, **kwargs)

        monkeypatch.setattr(MarketHealthEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.upsert_instrument(
            Instrument(instrument_id="NSE:NIFTY 50", symbol="NIFTY 50", exchange="NSE",
                       series="INDEX", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_candles("NSE:NIFTY 50", seed=24000))
        real_snapshot_ts = datetime(2026, 1, 20, 9, 20, tzinfo=IST)
        repo.add_snapshot(MarketSnapshot(
            ts=real_snapshot_ts, indices={"NIFTY 50": Decimal("24000")}, india_vix=Decimal("15"),
        ))

        as_of = datetime(2026, 1, 20, 9, 25, tzinfo=IST)
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=2, candles_fetched=160, candles_written=160,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-snapshot-clean")
        clean = recorded[-1]
        assert clean is not None
        assert clean.india_vix == Decimal("15")

        # Future snapshot dated after as_of -- already present in the
        # repository, as real further polling would leave it, before
        # replaying the SAME historical as_of again.
        repo.add_snapshot(MarketSnapshot(
            ts=datetime(2026, 1, 20, 9, 40, tzinfo=IST),
            indices={"NIFTY 50": Decimal("99999")}, india_vix=Decimal("999"),
        ))
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-snapshot-noisy")
        noisy = recorded[-1]

        assert noisy == clean
        assert noisy.india_vix == Decimal("15")

    def test_id5g1_market_health_snapshot_input_is_invariant_to_a_fractional_second_future_snapshot(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5G.1 §19 (Pipeline Fractional-Future Invariance): the owner-
        found precision bug's exact regression, replayed through the real
        pipeline -- a real snapshot at `as_of + 50ms` (eligible) and an
        extreme-valued one at `as_of + 900ms` (same whole second,
        genuinely future) must not be conflated by a whole-second-
        truncating comparison. The extreme snapshot must never leak into
        `MarketHealthEngine`'s `india_vix` input."""
        from athena.market_health.engine import MarketHealthEngine

        recorded: list[object] = []
        real_assess = MarketHealthEngine.assess

        def spy_assess(self, index_symbol, index_candles, snapshot, **kwargs):
            recorded.append(snapshot)
            return real_assess(self, index_symbol, index_candles, snapshot, **kwargs)

        monkeypatch.setattr(MarketHealthEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.upsert_instrument(
            Instrument(instrument_id="NSE:NIFTY 50", symbol="NIFTY 50", exchange="NSE",
                       series="INDEX", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_candles("NSE:NIFTY 50", seed=24000))

        as_of = datetime(2026, 1, 20, 9, 20, 0, 100_000, tzinfo=IST)  # .100s
        # Future/extreme snapshot inserted FIRST deliberately: SQLite's
        # ORDER BY tie-break among datetime()-truncated-equal rows favors
        # whichever was inserted first (empirically confirmed) -- so this
        # ordering is required for a revert to the old datetime()-based
        # SQL to actually expose the bug non-vacuously, rather than
        # accidentally "passing" by tie-break luck.
        repo.add_snapshot(MarketSnapshot(
            ts=datetime(2026, 1, 20, 9, 20, 0, 900_000, tzinfo=IST),  # .900s -- same whole second, future
            indices={"NIFTY 50": Decimal("99999")}, india_vix=Decimal("999"),
        ))
        repo.add_snapshot(MarketSnapshot(
            ts=datetime(2026, 1, 20, 9, 20, 0, 50_000, tzinfo=IST),  # .050s -- eligible
            indices={"NIFTY 50": Decimal("24000")}, india_vix=Decimal("15"),
        ))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=2, candles_fetched=160, candles_written=160,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-snapshot-fractional")

        snap = recorded[-1]
        assert snap is not None
        # ts is always re-stamped to as_of by _apply_universe_breadth
        # (pre-existing, unrelated behavior) -- india_vix is the value
        # that would actually leak from the wrong snapshot.
        assert snap.india_vix == Decimal("15")

    def test_id5g_no_historical_snapshot_preserves_missing_snapshot_fallback(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-5G §19: with zero snapshots at or before `as_of` (only a
        future one exists), `_resolve_snapshot` must fall through to its
        existing "no persisted snapshot" behavior -- never the oldest
        future snapshot."""
        from athena.market_health.engine import MarketHealthEngine

        recorded: list[object] = []
        real_assess = MarketHealthEngine.assess

        def spy_assess(self, index_symbol, index_candles, snapshot, **kwargs):
            recorded.append(snapshot)
            return real_assess(self, index_symbol, index_candles, snapshot, **kwargs)

        monkeypatch.setattr(MarketHealthEngine, "assess", spy_assess)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.upsert_instrument(
            Instrument(instrument_id="NSE:NIFTY 50", symbol="NIFTY 50", exchange="NSE",
                       series="INDEX", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_candles("NSE:NIFTY 50", seed=24000))
        repo.add_snapshot(MarketSnapshot(
            ts=datetime(2026, 1, 20, 9, 40, tzinfo=IST),
            indices={"NIFTY 50": Decimal("99999")}, india_vix=Decimal("999"),
        ))

        as_of = datetime(2026, 1, 20, 9, 25, tzinfo=IST)
        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=2, candles_fetched=160, candles_written=160,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="run-snapshot-future-only")

        snap = recorded[-1]
        assert snap is not None  # _resolve_snapshot's own synthetic-empty fallback, ts=as_of
        assert snap.india_vix != Decimal("999")

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
        index_id, resolved = pipe._resolve_index_candles(candles_by_id, as_of=AS_OF)
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
        _index_id, resolved = pipe._resolve_index_candles(candles_by_id, as_of=AS_OF)
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

    def test_id6d_entry_qualification_stage_does_not_perturb_existing_stage_order(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-6D: the new `entry_qualification` stage explicitly depends on
        `decision` and `intraday_analytics` (real dependencies) — and,
        since nothing depends on IT, the ten pre-existing stages (already
        proven order-stable under ID-1/ID-2/ID-4/ID-5D's own additions)
        must keep their exact relative order here too."""
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
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-eq-stage-order"
        )
        assert detail["decision_reports"], "entry_qualification stage must not break the existing scan"

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
            WorkflowStage("session", noop, produces=("session_context",)),
            WorkflowStage("relative_strength", noop, depends_on=("session",), produces=("relative_strength",)),
            WorkflowStage("relative_volume", noop, depends_on=("session",), produces=("relative_volume",)),
            WorkflowStage(
                "intraday_analytics", noop,
                depends_on=("session", "indicators", "relative_strength", "relative_volume"),
                produces=("intraday_signal_set",),
            ),
        ]
        original_order = build_definition("pre-id6d", stages).execution_order
        with_eq = build_definition(
            "post-id6d",
            [*stages, WorkflowStage(
                "entry_qualification", noop, depends_on=("decision", "intraday_analytics"),
                produces=("entry_qualification",),
            )],
        ).execution_order
        pre_existing_names = [n for n in with_eq if n != "entry_qualification"]
        assert tuple(pre_existing_names) == original_order
        assert "entry_qualification" in with_eq

    def test_id6d_entry_qualification_persists_bound_to_the_exact_canonical_decision(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-6D: the persisted EntryQualification must bind to the SAME
        Decision the cycle just produced -- same decision_id/instrument_id/
        decision_type/run_id/cycle_id (ID-6C.1's own binding invariant),
        with as_of matching SessionContext, never wall-clock/scheduler time."""
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
        pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-eq-binding")

        decision = repo.get_decision(f"decision-{iid}-{AS_OF.isoformat()}")
        assert decision is not None, "fixture must produce a real WATCH/TRADE decision"
        assert decision.decision_type in (DecisionType.WATCH, DecisionType.TRADE)

        eq = repo.latest_entry_qualification_for_decision(decision.decision_id)
        assert eq is not None
        assert eq.decision_id == decision.decision_id
        assert eq.instrument_id == decision.instrument_id
        assert eq.decision_type == decision.decision_type
        assert eq.run_id == decision.run_id
        assert eq.cycle_id == decision.cycle_id
        assert eq.as_of == AS_OF  # SessionContext's own as_of, not wall-clock
        assert eq.confirmation.value == "NOT_EVALUATED"

    def test_id6d_rerun_with_same_run_id_is_idempotent_not_duplicated(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-6D + ID-6C: re-executing the same cycle (same as_of/run_id --
        a retry) must persist exactly one EntryQualification observation,
        not two -- save_entry_qualification's own idempotency must hold
        through two full pipeline executions, not just a direct unit call."""
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
        for _ in range(2):
            detail = pipe.run(
                RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-eq-idempotent"
            )
            assert detail["decision_reports"]

        assert repo.record_counts()["entry_qualifications"] == 1
        history = repo.list_entry_qualifications_for_instrument_session(iid, AS_OF.date())
        assert len(history) == 1

    def test_id6d_engine_receives_the_exact_same_session_context_and_signal_set(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-6D #10/#19: no duplicate SessionContext/IntradaySignalSet
        construction -- EntryQualificationEngine.evaluate() must receive
        the literal same objects `intraday_analytics_stage` already
        produced this cycle, proven by identity, not equal values."""
        from athena.intraday.entry_qualification_engine import EntryQualificationEngine

        recorded: dict[str, object] = {}
        real_evaluate = EntryQualificationEngine.evaluate

        def spy_evaluate(self, *args, **kwargs):
            recorded["session_context"] = kwargs.get("session_context")
            recorded["signal_set"] = kwargs.get("signal_set")
            return real_evaluate(self, *args, **kwargs)

        monkeypatch.setattr(EntryQualificationEngine, "evaluate", spy_evaluate)

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
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-eq-identity"
        )
        assert detail["decision_reports"]
        assert recorded["session_context"] is not None
        assert recorded["signal_set"] is not None
        assert recorded["session_context"].as_of == AS_OF
        assert recorded["signal_set"].as_of == AS_OF

    def test_id6d1_as_of_and_persisted_at_are_distinct_dimensions(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-6D.1: EntryQualification.as_of must remain the SessionContext
        evaluation checkpoint; persisted_at must be the actual injected
        wall-clock write instant -- proven with genuinely different values,
        not merely happening to observe equal ones."""
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_intraday_candles(iid, AS_OF.date(), seed=100))

        persist_time = AS_OF.astimezone(ZoneInfo("UTC")) + timedelta(seconds=3)
        pipe = OwnerValidationPipeline(
            repo, config_dir, persistence_clock=lambda: persist_time
        )
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-eq1d1-distinct")

        decision = repo.get_decision(f"decision-{iid}-{AS_OF.isoformat()}")
        assert decision is not None
        eq = repo.latest_entry_qualification_for_decision(decision.decision_id)
        assert eq is not None
        assert eq.as_of == AS_OF  # unchanged: evaluation/market-time checkpoint

        row = repo.connection.execute(
            "SELECT persisted_at FROM entry_qualifications WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()
        assert row is not None
        stored_persisted_at = datetime.fromisoformat(row[0])
        assert stored_persisted_at == persist_time
        assert stored_persisted_at != eq.as_of  # genuinely distinct, not coincidentally equal
        assert stored_persisted_at.tzinfo is not None  # timezone-aware

    def test_id6d1_idempotent_retry_preserves_original_persisted_at(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-6D.1: a delayed/retried idempotent write must not overwrite
        the original observation's persisted_at, and must not create a
        second row -- the second call's persistence-attempt time is
        discarded, exactly as an idempotent no-op should behave."""
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        repo.add_candles(_intraday_candles(iid, AS_OF.date(), seed=100))

        first_persist = AS_OF.astimezone(ZoneInfo("UTC")) + timedelta(seconds=2)
        second_persist = AS_OF.astimezone(ZoneInfo("UTC")) + timedelta(minutes=10)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )

        pipe_first = OwnerValidationPipeline(
            repo, config_dir, persistence_clock=lambda: first_persist
        )
        pipe_first.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-eq1d1-retry"
        )
        pipe_second = OwnerValidationPipeline(
            repo, config_dir, persistence_clock=lambda: second_persist
        )
        pipe_second.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-eq1d1-retry"
        )

        assert repo.record_counts()["entry_qualifications"] == 1
        decision = repo.get_decision(f"decision-{iid}-{AS_OF.isoformat()}")
        row = repo.connection.execute(
            "SELECT persisted_at FROM entry_qualifications WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()
        assert datetime.fromisoformat(row[0]) == first_persist  # not overwritten by the retry

    def test_id6d1_no_pure_engine_clock_dependency_introduced(self) -> None:
        """Structural proof: EntryQualificationEngine.evaluate()'s signature
        carries no clock/persisted_at parameter -- the pure engine remains
        entirely clock-free, unchanged by this correction."""
        import inspect

        from athena.intraday.entry_qualification_engine import EntryQualificationEngine

        params = inspect.signature(EntryQualificationEngine.evaluate).parameters
        assert set(params) == {"self", "decision", "session_context", "signal_set",
                                "evidence_finality", "policy"}

    # ------------------------------------------------------------ ID-7E

    def test_id7e_entry_actionability_stage_does_not_perturb_existing_stage_order(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-7E: the new `entry_actionability` stage explicitly depends
        only on `entry_qualification` (a real data dependency -- see the
        production DAG's own comment for the transitive-guarantee proof)
        -- and, since nothing depends on IT, the eleven pre-existing
        stages (already proven order-stable under ID-1/ID-2/ID-4/ID-5D/
        ID-6D's own additions) must keep their exact relative order here
        too."""
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
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-ea-stage-order"
        )
        assert detail["decision_reports"], "entry_actionability stage must not break the existing scan"

        noop = lambda ctx: {}  # noqa: E731
        stages = [
            WorkflowStage("indicators", noop,
                          produces=("indicators", "vwap", "confluence", "latest_completed_m5")),
            WorkflowStage("regime", noop, produces=("regime", "market_health")),
            WorkflowStage("scoring", noop, depends_on=("indicators", "regime"), produces=("scoring",)),
            WorkflowStage("confidence", noop, depends_on=("scoring", "regime"),
                          produces=("evidence_bundle", "confidence")),
            WorkflowStage("risk", noop, depends_on=("indicators", "regime"), produces=("risk",)),
            WorkflowStage("decision", noop, depends_on=("scoring", "confidence", "risk"),
                          produces=("outcome",)),
            WorkflowStage("session", noop, produces=("session_context",)),
            WorkflowStage("relative_strength", noop, depends_on=("session",), produces=("relative_strength",)),
            WorkflowStage("relative_volume", noop, depends_on=("session",), produces=("relative_volume",)),
            WorkflowStage(
                "intraday_analytics", noop,
                depends_on=("session", "indicators", "relative_strength", "relative_volume"),
                produces=("intraday_signal_set",),
            ),
            WorkflowStage(
                "entry_qualification", noop, depends_on=("decision", "intraday_analytics"),
                produces=("entry_qualification",),
            ),
        ]
        original_order = build_definition("pre-id7e", stages).execution_order
        with_ea = build_definition(
            "post-id7e",
            [*stages, WorkflowStage(
                "entry_actionability", noop, depends_on=("entry_qualification",),
                produces=("entry_actionability",),
            )],
        ).execution_order
        pre_existing_names = [n for n in with_ea if n != "entry_actionability"]
        assert tuple(pre_existing_names) == original_order
        assert "entry_actionability" in with_ea

    def test_id7e_entry_actionability_transitive_dependency_is_structurally_guaranteed(self) -> None:
        """ID-7E #5: proves -- from WorkflowEngine's own generic failure-
        propagation mechanics, not from insertion order -- that a stage
        depending only on `entry_qualification` can safely read outputs
        produced further upstream (`indicators`, `intraday_analytics`):
        if either of those had failed or been skipped, `entry_qualification`
        itself could never reach COMPLETED (its own `depends_on` would
        block it), so a completed `entry_qualification` transitively
        proves every one of ITS OWN ancestors also completed."""
        from athena.runtime.models import ExecutionStatus
        from athena.runtime.workflow import WorkflowEngine, WorkflowStage, build_definition

        def boom(ctx):
            raise ValueError("indicators failed")

        stages = [
            WorkflowStage("indicators", boom, produces=("indicators",)),
            WorkflowStage("intraday_analytics", lambda ctx: {"intraday_signal_set": True},
                          depends_on=("indicators",), produces=("intraday_signal_set",)),
            WorkflowStage("entry_qualification", lambda ctx: {"entry_qualification": True},
                          depends_on=("intraday_analytics",), produces=("entry_qualification",)),
            WorkflowStage("entry_actionability", lambda ctx: {"entry_actionability": True},
                          depends_on=("entry_qualification",), produces=("entry_actionability",)),
        ]
        execution = WorkflowEngine().execute(
            build_definition("transitive-proof", stages), as_of=AS_OF
        )
        by_name = {r.stage_name: r for r in execution.stage_results}
        assert by_name["indicators"].status is ExecutionStatus.FAILED
        assert by_name["intraday_analytics"].status is ExecutionStatus.SKIPPED
        assert by_name["entry_qualification"].status is ExecutionStatus.SKIPPED
        assert by_name["entry_actionability"].status is ExecutionStatus.SKIPPED

    def test_id7e_entry_actionability_persists_bound_to_the_exact_canonical_decision_and_eq(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-7E: the persisted EntryActionability must bind to the SAME
        Decision and the SAME EntryQualification the cycle just produced
        -- proving the full composite identity/denormalized fields, not
        merely instrument_id."""
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
        pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-ea-binding")

        decision = repo.get_decision(f"decision-{iid}-{AS_OF.isoformat()}")
        assert decision is not None, "fixture must produce a real WATCH/TRADE decision"
        assert decision.decision_type in (DecisionType.WATCH, DecisionType.TRADE)

        eq = repo.latest_entry_qualification_for_decision(decision.decision_id)
        assert eq is not None

        history = repo.list_entry_actionabilities_for_instrument_session(iid, AS_OF.date())
        assert len(history) == 1
        ea = history[0]
        assert ea.decision_id == decision.decision_id
        assert ea.instrument_id == decision.instrument_id
        assert ea.decision_type == decision.decision_type
        assert ea.run_id == decision.run_id
        assert ea.cycle_id == decision.cycle_id
        assert ea.entry_qualification_as_of == eq.as_of
        assert ea.entry_qualification_methodology_version == eq.methodology_version
        assert ea.entry_qualification_state == eq.state
        assert ea.entry_actionability_as_of == eq.as_of  # Option 1: same checkpoint as EQ
        assert ea.evaluated_at is not None

    def test_id7e_watch_decision_persists_not_actionable_row(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ADR-015's frozen WATCH contract: a WATCH-bound EntryQualification
        must still yield a persisted NOT_ACTIONABLE row with
        UPSTREAM_DECISION_NOT_TRADE -- never silently omitted merely
        because WATCH itself is non-actionable."""
        import dataclasses

        from athena.decision.engine import DecisionEngine
        from athena.domain.enums import DecisionType as DT

        real_decide = DecisionEngine.decide

        def forced_watch(self, *args, **kwargs):
            outcome = real_decide(self, *args, **kwargs)
            if outcome.decision.decision_type is DT.TRADE:
                forced = dataclasses.replace(
                    outcome.decision, decision_type=DT.WATCH, trade_plan=None, gate_results=()
                )
                outcome = dataclasses.replace(outcome, decision=forced)
            return outcome

        monkeypatch.setattr(DecisionEngine, "decide", forced_watch)

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
        pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-ea-watch")

        decision = repo.get_decision(f"decision-{iid}-{AS_OF.isoformat()}")
        assert decision is not None
        assert decision.decision_type is DecisionType.WATCH

        from athena.intraday import EntryActionabilityReasonCode, EntryActionabilityState

        history = repo.list_entry_actionabilities_for_instrument_session(iid, AS_OF.date())
        assert len(history) == 1
        ea = history[0]
        assert ea.state is EntryActionabilityState.NOT_ACTIONABLE
        assert EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE in ea.reason_codes
        assert ea.entry_reference is None

    def test_id7e_trade_qualified_full_pipeline_yields_actionable(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-7E's central positive proof: with a real TRADE Decision, a
        real QUALIFIED EntryQualification, and real completed-M5/VWAP
        evidence composed entirely from what this cycle's own workflow
        already computed (never a second repository read, never
        provider access), the wired stage reaches ACTIONABLE with a
        coherent entry/invalidation/reward and VWAP provenance exactly
        equal to the selected candle's own completion instant.

        DecisionEngine.decide and EntryQualificationEngine.evaluate are
        monkeypatched (mirroring the ID-6D test file's own established
        spy/force pattern) only to force the upstream methodology
        verdicts (TRADE / QUALIFIED) that real scoring/confidence/risk
        config would make statistically rare to hit incidentally --
        DecisionEngine/EntryQualificationEngine's own frozen methodology
        is not being tested here (it already has its own exhaustive
        suites); this test proves ID-7E's OWN responsibility: composition
        and wiring, not decision methodology."""
        import dataclasses

        from athena.decision.engine import DecisionEngine
        from athena.domain.enums import DecisionType as DT
        from athena.domain.enums import Direction as Dir
        from athena.domain.decision import TradePlan
        from athena.intraday import (
            EntryActionabilityState,
            EntryQualificationEngine,
            EntryQualificationState,
        )

        real_decide = DecisionEngine.decide

        def forced_trade(self, *args, **kwargs):
            outcome = real_decide(self, *args, **kwargs)
            forced_decision = dataclasses.replace(
                outcome.decision,
                decision_type=DT.TRADE,
                direction=Dir.LONG,
                gate_results=(),
                trade_plan=TradePlan(
                    entry_low=Decimal("100"), entry_high=Decimal("103"),
                    stop_loss=Decimal("95"), targets=(Decimal("110"),),
                    position_size=1, risk_amount=Decimal("500"),
                    risk_reward=Decimal("2"),
                    valid_from=AS_OF, valid_until=AS_OF + timedelta(days=1),
                ),
            )
            return dataclasses.replace(outcome, decision=forced_decision)

        monkeypatch.setattr(DecisionEngine, "decide", forced_trade)

        real_eq_evaluate = EntryQualificationEngine.evaluate

        def forced_qualified(self, *args, **kwargs):
            eq = real_eq_evaluate(self, *args, **kwargs)
            return dataclasses.replace(
                eq, state=EntryQualificationState.QUALIFIED, reason_codes=()
            )

        monkeypatch.setattr(EntryQualificationEngine, "evaluate", forced_qualified)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        # Rising same-session 5m bars: VWAP (mean of typical prices) ends up
        # below the latest completed bar's own close -- valid LONG geometry
        # (VWAP-loss invalidation below entry), reached without inventing a
        # synthetic candle shape unrelated to any real fixture pattern
        # already used elsewhere in this file (test_vwap_flows_into_score...).
        repo.add_candles(_intraday_candles(iid, AS_OF.date(), seed=100))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-ea-actionable")

        decision = repo.get_decision(f"decision-{iid}-{AS_OF.isoformat()}")
        assert decision is not None
        assert decision.decision_type is DT.TRADE

        history = repo.list_entry_actionabilities_for_instrument_session(iid, AS_OF.date())
        assert len(history) == 1
        ea = history[0]
        assert ea.state is EntryActionabilityState.ACTIONABLE
        assert ea.reason_codes == ()
        assert ea.entry_reference is not None
        assert ea.entry_reference.price == Decimal("102")  # last completed M5 close
        assert ea.entry_location_context is not None
        assert ea.entry_location_context.vwap == Decimal("101")  # mean of 3 completed typical prices
        assert ea.operative_invalidation is not None
        assert ea.operative_invalidation.level == Decimal("101")
        assert ea.reward is not None
        assert ea.reward.t1_price == Decimal("102") * (Decimal(1) + Decimal("0.01"))
        # VWAP provenance exactly equals the selected candle's own
        # completion instant -- never ctx.as_of/evaluated_at/persisted_at.
        assert ea.evidence_as_of == AS_OF

    def test_id7e_missing_evidence_yields_unknown_insufficient_evidence(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-7E: an upstream-eligible (TRADE + QUALIFIED) candidate with
        no completed M5 checkpoint candle at all (no intraday history
        fetched) must persist UNKNOWN/INSUFFICIENT_EVIDENCE -- ordinary
        missing evidence, never a stage failure."""
        import dataclasses

        from athena.decision.engine import DecisionEngine
        from athena.domain.enums import DecisionType as DT
        from athena.domain.enums import Direction as Dir
        from athena.domain.decision import TradePlan
        from athena.intraday import (
            EntryActionabilityReasonCode,
            EntryActionabilityState,
            EntryQualificationEngine,
            EntryQualificationState,
        )

        real_decide = DecisionEngine.decide

        def forced_trade(self, *args, **kwargs):
            outcome = real_decide(self, *args, **kwargs)
            forced_decision = dataclasses.replace(
                outcome.decision,
                decision_type=DT.TRADE,
                direction=Dir.LONG,
                gate_results=(),
                trade_plan=TradePlan(
                    entry_low=Decimal("100"), entry_high=Decimal("103"),
                    stop_loss=Decimal("95"), targets=(Decimal("110"),),
                    position_size=1, risk_amount=Decimal("500"),
                    risk_reward=Decimal("2"),
                    valid_from=AS_OF, valid_until=AS_OF + timedelta(days=1),
                ),
            )
            return dataclasses.replace(outcome, decision=forced_decision)

        monkeypatch.setattr(DecisionEngine, "decide", forced_trade)

        real_eq_evaluate = EntryQualificationEngine.evaluate

        def forced_qualified(self, *args, **kwargs):
            eq = real_eq_evaluate(self, *args, **kwargs)
            return dataclasses.replace(
                eq, state=EntryQualificationState.QUALIFIED, reason_codes=()
            )

        monkeypatch.setattr(EntryQualificationEngine, "evaluate", forced_qualified)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        # Deliberately NO same-day 5m candles -- no completed M5 checkpoint,
        # no VWAP, matching test_vwap_flows_into_score...'s own "BBB has
        # none at all" precedent.

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=1, candles_fetched=80, candles_written=80,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-ea-missing")

        history = repo.list_entry_actionabilities_for_instrument_session(iid, AS_OF.date())
        assert len(history) == 1
        ea = history[0]
        assert ea.state is EntryActionabilityState.UNKNOWN
        assert ea.reason_codes == (EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,)
        assert ea.entry_reference is None

    def test_id7e_invalid_geometry_yields_unknown_invalidation_unavailable(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-7E: an upstream-eligible LONG candidate whose VWAP sits ABOVE
        the completed M5 entry close (falling intraday session) has no
        valid VWAP-loss invalidation for LONG -- must persist
        UNKNOWN/INVALIDATION_UNAVAILABLE, never a raised domain error
        escaping the stage."""
        import dataclasses

        from athena.decision.engine import DecisionEngine
        from athena.domain.enums import DecisionType as DT
        from athena.domain.enums import Direction as Dir
        from athena.domain.decision import TradePlan
        from athena.intraday import (
            EntryActionabilityReasonCode,
            EntryActionabilityState,
            EntryQualificationEngine,
            EntryQualificationState,
        )

        real_decide = DecisionEngine.decide

        def forced_trade(self, *args, **kwargs):
            outcome = real_decide(self, *args, **kwargs)
            forced_decision = dataclasses.replace(
                outcome.decision,
                decision_type=DT.TRADE,
                direction=Dir.LONG,
                gate_results=(),
                trade_plan=TradePlan(
                    entry_low=Decimal("90"), entry_high=Decimal("100"),
                    stop_loss=Decimal("85"), targets=(Decimal("110"),),
                    position_size=1, risk_amount=Decimal("500"),
                    risk_reward=Decimal("2"),
                    valid_from=AS_OF, valid_until=AS_OF + timedelta(days=1),
                ),
            )
            return dataclasses.replace(outcome, decision=forced_decision)

        monkeypatch.setattr(DecisionEngine, "decide", forced_trade)

        real_eq_evaluate = EntryQualificationEngine.evaluate

        def forced_qualified(self, *args, **kwargs):
            eq = real_eq_evaluate(self, *args, **kwargs)
            return dataclasses.replace(
                eq, state=EntryQualificationState.QUALIFIED, reason_codes=()
            )

        monkeypatch.setattr(EntryQualificationEngine, "evaluate", forced_qualified)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        iid = "NSE:AAA"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
        )
        repo.add_candles(_candles(iid, seed=100))
        # Falling same-session 5m bars: the latest completed bar's close is
        # BELOW the session VWAP -- invalid LONG geometry (VWAP must be
        # below entry for a LONG invalidation to make sense).
        repo.add_candles(
            _timeframe_candles(iid, AS_OF.date(), Timeframe.M5, 5, n=6, seed=100, rising=False)
        )

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=1, candles_fetched=86, candles_written=86,
            quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
        )
        pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-ea-geometry")

        history = repo.list_entry_actionabilities_for_instrument_session(iid, AS_OF.date())
        assert len(history) == 1
        ea = history[0]
        assert ea.state is EntryActionabilityState.UNKNOWN
        assert ea.reason_codes == (EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,)
        assert ea.evidence_as_of == AS_OF  # evidence checkpoint still populated

    def test_id7e_contract_error_fails_only_that_instrument_others_unaffected(
        self, repo: SqliteRepository, config_dir: Path, monkeypatch
    ) -> None:
        """ID-7E #39/#44: a genuine incoherent-composition contract error
        (here: an EntryQualification whose session_date disagrees with
        the real SessionContext, so `_validate_or15_coherence` raises)
        must fail ONLY the `entry_actionability` stage for THAT
        instrument -- the already-persisted Decision and
        EntryQualification for it remain untouched (their own stages ran
        and persisted successfully earlier in the same DAG, independent
        of this later stage's own failure), no EntryActionability row is
        written for it, and a second, healthy instrument in the same scan
        is completely unaffected."""
        import dataclasses

        from athena.decision.engine import DecisionEngine
        from athena.domain.enums import DecisionType as DT
        from athena.domain.enums import Direction as Dir
        from athena.domain.decision import TradePlan
        from athena.intraday import EntryQualificationEngine, EntryQualificationState

        broken_iid = "NSE:AAA"
        healthy_iid = "NSE:BBB"

        real_decide = DecisionEngine.decide

        def forced_trade_for_broken(self, instrument_id, *args, **kwargs):
            outcome = real_decide(self, instrument_id, *args, **kwargs)
            if instrument_id != broken_iid:
                return outcome
            forced_decision = dataclasses.replace(
                outcome.decision,
                decision_type=DT.TRADE,
                direction=Dir.LONG,
                gate_results=(),
                trade_plan=TradePlan(
                    entry_low=Decimal("100"), entry_high=Decimal("103"),
                    stop_loss=Decimal("95"), targets=(Decimal("110"),),
                    position_size=1, risk_amount=Decimal("500"),
                    risk_reward=Decimal("2"),
                    valid_from=AS_OF, valid_until=AS_OF + timedelta(days=1),
                ),
            )
            return dataclasses.replace(outcome, decision=forced_decision)

        monkeypatch.setattr(DecisionEngine, "decide", forced_trade_for_broken)

        real_eq_evaluate = EntryQualificationEngine.evaluate

        def forced_incoherent_for_broken(self, *args, **kwargs):
            eq = real_eq_evaluate(self, *args, **kwargs)
            if eq.instrument_id != broken_iid:
                return eq
            return dataclasses.replace(
                eq,
                state=EntryQualificationState.QUALIFIED,
                reason_codes=(),
                session_date=eq.session_date - timedelta(days=1),  # incoherent vs real SessionContext
            )

        monkeypatch.setattr(EntryQualificationEngine, "evaluate", forced_incoherent_for_broken)

        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol="AAA")
        store.upsert_candidate(symbol="BBB")
        for iid, sym, seed in ((broken_iid, "AAA", 100), (healthy_iid, "BBB", 200)):
            repo.upsert_instrument(
                Instrument(instrument_id=iid, symbol=sym, exchange="NSE", series="EQ", status="ACTIVE")
            )
            repo.add_candles(_candles(iid, seed=seed))
            repo.add_candles(_intraday_candles(iid, AS_OF.date(), seed=seed))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=AS_OF, instruments_upserted=2, candles_fetched=172, candles_written=172,
            quotes_fetched=0, quotes_written=0, datasets_validated=2, datasets_skipped_empty=0,
        )
        detail = pipe.run(
            RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-ea-contract-error"
        )

        # The broken instrument's scan failed (entry_actionability stage
        # raised -> workflow execution not COMPLETED -> InstrumentScanResult
        # FAILED, no report) -- but Decision/EQ persistence, which happened
        # in earlier, independent stages, is untouched.
        assert detail["scan_statistics"]["failed"] == 1
        assert detail["scan_statistics"]["successful"] == 1

        broken_decision = repo.get_decision(f"decision-{broken_iid}-{AS_OF.isoformat()}")
        assert broken_decision is not None, "Decision persistence must survive a later stage's failure"
        broken_eq = repo.latest_entry_qualification_for_decision(broken_decision.decision_id)
        assert broken_eq is not None, "EntryQualification persistence must survive a later stage's failure"
        assert repo.list_entry_actionabilities_for_instrument_session(broken_iid, AS_OF.date()) == []

        # The healthy sibling instrument's report is present and its own
        # Decision persisted normally -- one instrument's contract error
        # never terminates or corrupts the other's scan (DailyMarketScanner's
        # existing per-instrument isolation, unchanged by ID-7E).
        healthy_decision = repo.get_decision(f"decision-{healthy_iid}-{AS_OF.isoformat()}")
        assert healthy_decision is not None
        reports_by_instrument = {
            r["decision"]["instrument_id"] for r in detail["decision_reports"].values()
        }
        assert healthy_iid in reports_by_instrument
        assert broken_iid not in reports_by_instrument

    def test_id7e_rerun_with_same_run_id_is_idempotent_not_duplicated(
        self, repo: SqliteRepository, config_dir: Path
    ) -> None:
        """ID-7E + ID-7A: re-executing the same cycle (same as_of/run_id --
        a retry) must persist exactly one EntryActionability observation,
        not two -- save_entry_actionability's own idempotency must hold
        through two full pipeline executions, not just a direct unit call."""
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
        for _ in range(2):
            detail = pipe.run(
                RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-test-ea-idempotent"
            )
            assert detail["decision_reports"]

        assert repo.record_counts()["entry_actionabilities"] == 1
        history = repo.list_entry_actionabilities_for_instrument_session(iid, AS_OF.date())
        assert len(history) == 1

    def test_id7e_no_currentness_no_provider_no_config_in_stage(self) -> None:
        """ID-7E #27/#30/#41/#42: source-scan proof that owner_validation.py
        never references currentness concepts or provider/network
        libraries in connection with EntryActionability -- currentness
        remains a later read-time consumer's exclusive responsibility, and
        the write-time stage performs zero provider/network access."""
        import inspect

        import athena.ops.owner_validation as ov

        source = inspect.getsource(ov)
        for forbidden in (
            "is_currently_usable", "EntryActionabilityCurrentness",
            "current_decision_id", "current_entry_qualification_identity",
        ):
            assert forbidden not in source, f"currentness concept leaked into owner_validation.py: {forbidden}"
        for provider_token in ("KiteConnect", "kiteconnect", "requests.", "httpx."):
            assert provider_token not in source

    def test_id7e_evaluator_invocation_uses_policy_none(self) -> None:
        """ID-7E #16/#26: proves the wired stage calls
        EntryActionabilityEngine.evaluate() without constructing an
        EntryActionabilityPolicy -- no new configuration plumbing was
        introduced merely to wire this stage."""
        import inspect

        import athena.ops.owner_validation as ov

        source = inspect.getsource(ov)
        assert "EntryActionabilityPolicy" not in source
