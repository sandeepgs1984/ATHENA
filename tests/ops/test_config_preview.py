"""Config-change impact preview tests (M-X9): replay-based diff, read-only
against the real repo, never touching production state."""

from __future__ import annotations

import json
import shutil
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
from athena.ops.config_preview import preview_config_change, replay_decision_under_config
from athena.ops.owner_candidates import SqliteCandidateStore
from athena.ops.owner_validation import OwnerValidationPipeline

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 9, 30, tzinfo=IST)
REAL_CONFIG = Path(__file__).resolve().parents[2] / "config"


def _candles(instrument_id: str, n: int = 80, seed: int = 100) -> list[Candle]:
    out = []
    for i in range(n):
        day = date(2025, 11, 1) + timedelta(days=i)
        ts = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
        px = Decimal(str(seed + i))
        out.append(
            Candle(
                instrument_id=instrument_id, timeframe=Timeframe.D1, ts_open=ts,
                open=px, high=px + Decimal("2"), low=px - Decimal("1"), close=px + Decimal("1"),
                volume=1_000_000, source="test",
            )
        )
    return out


@pytest.fixture()
def repo_with_one_real_decision(tmp_path: Path) -> SqliteRepository:
    """A repo with exactly one real decision, produced the normal way via
    the real OwnerValidationPipeline — not a hand-built Decision object."""
    repo = SqliteRepository(tmp_path / "preview.db")
    repo.initialize()
    store = SqliteCandidateStore(repo)
    store.upsert_candidate(symbol="AAA")
    iid = "NSE:AAA"
    repo.upsert_instrument(
        Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
    )
    repo.add_candles(_candles(iid, seed=100))
    pipe = OwnerValidationPipeline(repo, REAL_CONFIG)
    ingestion = IngestionResult(
        as_of=AS_OF, instruments_upserted=1, candles_fetched=80, candles_written=80,
        quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
    )
    pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="seed-run")
    assert repo.list_decisions(limit=1)
    return repo


class TestReplayDecisionUnderConfig:
    def test_deterministic_when_config_unchanged(self, repo_with_one_real_decision):
        repo = repo_with_one_real_decision
        decision = repo.list_decisions(limit=1)[0]
        a = replay_decision_under_config(repo, decision, REAL_CONFIG)
        b = replay_decision_under_config(repo, decision, REAL_CONFIG)
        assert a.decision_type is not None
        assert a == b

    def test_never_writes_to_the_real_repo(self, repo_with_one_real_decision):
        repo = repo_with_one_real_decision
        decision = repo.list_decisions(limit=1)[0]
        before = [d.decision_id for d in repo.list_decisions(limit=50)]
        replay_decision_under_config(repo, decision, REAL_CONFIG)
        after = [d.decision_id for d in repo.list_decisions(limit=50)]
        assert before == after

    def test_unresolvable_instrument_returns_none_outcome(self, tmp_path):
        repo = SqliteRepository(tmp_path / "empty.db")
        repo.initialize()
        fake = Decision(
            decision_id="d-1", ts=AS_OF, run_id="r", cycle_id="c",
            decision_type=DecisionType.NO_TRADE, explanation="x",
            instrument_id="NSE:NOPE", direction=Direction.NONE,
        )
        outcome = replay_decision_under_config(repo, fake, REAL_CONFIG)
        assert outcome.decision_type is None
        assert outcome.composite is None

    def test_no_instrument_id_returns_none_outcome(self, tmp_path):
        repo = SqliteRepository(tmp_path / "empty3.db")
        repo.initialize()
        fake = Decision(
            decision_id="d-2", ts=AS_OF, run_id="r", cycle_id="c",
            decision_type=DecisionType.NO_TRADE, explanation="x",
            instrument_id=None, direction=Direction.NONE,
        )
        outcome = replay_decision_under_config(repo, fake, REAL_CONFIG)
        assert outcome.decision_type is None


class TestPreviewConfigChange:
    def test_zero_changes_when_configs_identical(self, repo_with_one_real_decision):
        report = preview_config_change(
            repo_with_one_real_decision,
            current_config_dir=REAL_CONFIG, candidate_config_dir=REAL_CONFIG, limit=5,
        )
        assert report.total == 1
        assert report.changed_count == 0
        assert report.changed_pct == 0.0

    def test_detects_a_real_change_from_a_candidate_weight_edit(
        self, repo_with_one_real_decision, tmp_path
    ):
        candidate_dir = tmp_path / "candidate_config"
        shutil.copytree(REAL_CONFIG, candidate_dir)
        scoring_path = candidate_dir / "scoring.json"
        data = json.loads(scoring_path.read_text())
        # A maximally disruptive, still-valid (sums to 100) weight change —
        # all weight onto one previously-minor dimension — guaranteed to
        # move the composite enough to be a meaningful mechanism check.
        data["weights"] = {
            "trend": 0, "momentum": 0, "market_quality": 0,
            "sector_quality": 0, "liquidity": 100, "technical_structure": 0,
        }
        scoring_path.write_text(json.dumps(data))

        report = preview_config_change(
            repo_with_one_real_decision,
            current_config_dir=REAL_CONFIG, candidate_config_dir=candidate_dir, limit=5,
        )
        assert report.total == 1
        row = report.rows[0]
        assert row.candidate.decision_type is not None
        assert row.candidate.composite != row.current.composite

    def test_report_never_writes_to_the_real_repo(self, repo_with_one_real_decision):
        repo = repo_with_one_real_decision
        before = [d.decision_id for d in repo.list_decisions(limit=50)]
        preview_config_change(
            repo, current_config_dir=REAL_CONFIG, candidate_config_dir=REAL_CONFIG, limit=5,
        )
        after = [d.decision_id for d in repo.list_decisions(limit=50)]
        assert before == after

    def test_skips_decision_without_an_instrument_id(self, tmp_path):
        repo = SqliteRepository(tmp_path / "noiid.db")
        repo.initialize()
        repo.save_decision(
            Decision(
                decision_id="d-no-iid", ts=AS_OF, run_id="r", cycle_id="c",
                decision_type=DecisionType.NO_TRADE, explanation="x",
                instrument_id=None, direction=Direction.NONE,
            )
        )
        report = preview_config_change(
            repo, current_config_dir=REAL_CONFIG, candidate_config_dir=REAL_CONFIG, limit=5,
        )
        assert report.total == 0
        assert report.skipped == ("d-no-iid",)

    def test_empty_repo_produces_empty_report(self, tmp_path):
        repo = SqliteRepository(tmp_path / "empty4.db")
        repo.initialize()
        report = preview_config_change(
            repo, current_config_dir=REAL_CONFIG, candidate_config_dir=REAL_CONFIG, limit=5,
        )
        assert report.total == 0
        assert report.skipped == ()
        assert report.changed_pct == 0.0
