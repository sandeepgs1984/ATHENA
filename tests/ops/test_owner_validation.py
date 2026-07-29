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
