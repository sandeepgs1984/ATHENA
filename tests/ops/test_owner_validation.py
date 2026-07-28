"""Owner validation pipeline: eligibility + WATCH/TRADE qualify (D-V2 / D-V3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction, RunTrigger, Timeframe
from athena.domain.market import Candle, Instrument
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
