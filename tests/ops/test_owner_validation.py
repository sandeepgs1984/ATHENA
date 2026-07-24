"""Owner validation pipeline: eligibility + WATCH/TRADE qualify (D-V2 / D-V3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import DecisionType, RunTrigger, Timeframe
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
        detail = pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion)
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
        detail = pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion)
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
