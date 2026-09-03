"""PS-P7B Portfolio Confidence adapter tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from athena.confidence.models import ConfidenceLevel
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction, RunStatus, RunTrigger
from athena.domain.run import RunRecord
from athena.portfolio.confidence_adapter import (
    PortfolioConfidenceAdapter,
    PortfolioConfidenceReason,
)

AS_OF = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)


def _decision(
    *,
    decision_id: str = "decision-1",
    run_id: str = "run-1",
    instrument_id: str = "NSE:INFY",
) -> Decision:
    return Decision(
        decision_id=decision_id,
        ts=AS_OF,
        run_id=run_id,
        cycle_id="cycle-1",
        decision_type=DecisionType.TRADE,
        explanation="test decision",
        instrument_id=instrument_id,
        direction=Direction.LONG,
        trade_plan=TradePlan(
            entry_low=Decimal("1500"),
            entry_high=Decimal("1510"),
            stop_loss=Decimal("1450"),
            targets=(Decimal("1700"),),
            position_size=1,
            risk_amount=Decimal("50"),
            risk_reward=Decimal("4"),
            valid_from=AS_OF,
            valid_until=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
        ),
    )


def _run(run_id: str) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        cycle_id="cycle-1",
        trigger=RunTrigger.REFRESH,
        started_ts=AS_OF,
        status=RunStatus.COMPLETED,
        software_version="test",
        blueprint_version="test",
        strategy_profile="test",
        strategy_profile_version="test",
        indicator_versions={},
        config_snapshot_id="cfg-1",
        input_digest="digest",
        finished_ts=AS_OF,
    )


def _repo(tmp_path, *, level: str | None = "HIGH", decision_id: str = "decision-1") -> SqliteRepository:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    confidence = (
        {"status": "OK", "level": level, "overall": 80}
        if level is not None
        else {"status": "UNKNOWN"}
    )
    repo.save_run(
        _run("run-1"),
        detail={"pipeline": {"decision_reports": {decision_id: {"confidence": confidence}}}},
    )
    return repo


@pytest.mark.parametrize("level", list(ConfidenceLevel))
def test_adapter_maps_coherent_confidence_levels(tmp_path, level: ConfidenceLevel) -> None:
    repo = _repo(tmp_path, level=level.value)
    decision = _decision()

    result = PortfolioConfidenceAdapter(repo).resolve(
        decision=decision,
        instrument_id="NSE:INFY",
        decision_is_coherent=True,
    )

    assert result.level is level
    assert result.is_coherent is True
    assert result.reason is PortfolioConfidenceReason.FROM_CONFIDENCE
    assert result.decision_id == "decision-1"
    assert result.run_id == "run-1"


def test_adapter_returns_null_for_missing_confidence(tmp_path) -> None:
    repo = _repo(tmp_path, level=None)
    result = PortfolioConfidenceAdapter(repo).resolve(
        decision=_decision(),
        instrument_id="NSE:INFY",
        decision_is_coherent=True,
    )

    assert result.level is None
    assert result.reason is PortfolioConfidenceReason.UNAVAILABLE


def test_adapter_rejects_stale_or_wrong_instrument_decision(tmp_path) -> None:
    repo = _repo(tmp_path, level="HIGH")
    stale = PortfolioConfidenceAdapter(repo).resolve(
        decision=_decision(),
        instrument_id="NSE:INFY",
        decision_is_coherent=False,
    )
    wrong_instrument = PortfolioConfidenceAdapter(repo).resolve(
        decision=_decision(instrument_id="NSE:TCS"),
        instrument_id="NSE:INFY",
        decision_is_coherent=True,
    )

    assert stale.level is None
    assert stale.reason is PortfolioConfidenceReason.INCOHERENT
    assert wrong_instrument.level is None
    assert wrong_instrument.reason is PortfolioConfidenceReason.INCOHERENT


def test_adapter_does_not_fallback_to_wrong_run_or_decision_report(tmp_path) -> None:
    repo = _repo(tmp_path, level="HIGH", decision_id="other-decision")
    result = PortfolioConfidenceAdapter(repo).resolve(
        decision=_decision(decision_id="decision-1"),
        instrument_id="NSE:INFY",
        decision_is_coherent=True,
    )

    assert result.level is None
    assert result.reason is PortfolioConfidenceReason.UNAVAILABLE


def test_adapter_degrades_malformed_legacy_payload_to_null(tmp_path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    repo.save_run(_run("run-1"), detail={"pipeline": {"decision_reports": {"decision-1": {"confidence": "bad"}}}})

    result = PortfolioConfidenceAdapter(repo).resolve(
        decision=_decision(),
        instrument_id="NSE:INFY",
        decision_is_coherent=True,
    )

    assert result.level is None
    assert result.reason is PortfolioConfidenceReason.UNAVAILABLE
