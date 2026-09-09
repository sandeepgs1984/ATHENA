"""EntryQualification read-time coherence (ID-11).

Proves `resolve_entry_qualification_coherence` is a pure, deterministic
function that performs exactly the identity/session/point-in-time checks
frozen by the ID-11 design contract (semantics-extracted from
`portfolio/sync.py::_latest_coherent_entry_qualification`, minus its
Portfolio-specific `_decision_matches_price_session` precondition), and
that it invents no age-based staleness threshold.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from athena.domain.decision import Decision
from athena.domain.enums import DecisionType
from athena.intraday.entry_qualification_coherence import (
    EntryQualificationCoherence,
    resolve_entry_qualification_coherence,
)
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationState,
)

IST = ZoneInfo("Asia/Kolkata")
DAY = date(2026, 9, 9)
EQ_AS_OF = datetime(2026, 9, 9, 9, 45, tzinfo=IST)
CHECKPOINT = datetime(2026, 9, 9, 9, 50, tzinfo=IST)


def _decision(**overrides: object) -> Decision:
    fields: dict[str, object] = dict(
        decision_id="decision-1",
        ts=EQ_AS_OF,
        run_id="run-1",
        cycle_id="cycle-1",
        decision_type=DecisionType.WATCH,
        explanation="test decision",
        instrument_id="NSE:TEST",
    )
    fields.update(overrides)
    return Decision(**fields)  # type: ignore[arg-type]


def _eq(**overrides: object) -> EntryQualification:
    fields: dict[str, object] = dict(
        instrument_id="NSE:TEST",
        session_date=DAY,
        as_of=EQ_AS_OF,
        run_id="run-1",
        cycle_id="cycle-1",
        decision_id="decision-1",
        decision_type=DecisionType.WATCH,
        state=EntryQualificationState.QUALIFIED,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        confirmation=EntryQualificationConfirmation.CONFIRMED_BY_POLICY,
        reason_codes=(),
        evidence_refs=(),
        methodology_version="entry-qualification-v0",
        config_snapshot_id=None,
        explanation="test eq",
    )
    fields.update(overrides)
    return EntryQualification(**fields)  # type: ignore[arg-type]


def test_coherent_when_everything_matches() -> None:
    result = resolve_entry_qualification_coherence(
        _eq(), _decision(), read_checkpoint=CHECKPOINT, market_timezone=IST
    )
    assert result.status is EntryQualificationCoherence.COHERENT


def test_incoherent_when_eq_is_none() -> None:
    result = resolve_entry_qualification_coherence(
        None, _decision(), read_checkpoint=CHECKPOINT, market_timezone=IST
    )
    assert result.status is EntryQualificationCoherence.INCOHERENT
    assert "no EntryQualification" in result.explanation


def test_incoherent_on_instrument_mismatch() -> None:
    result = resolve_entry_qualification_coherence(
        _eq(instrument_id="NSE:OTHER"),
        _decision(),
        read_checkpoint=CHECKPOINT,
        market_timezone=IST,
    )
    assert result.status is EntryQualificationCoherence.INCOHERENT
    assert "instrument mismatch" in result.explanation


def test_incoherent_on_decision_id_mismatch() -> None:
    result = resolve_entry_qualification_coherence(
        _eq(decision_id="decision-2"),
        _decision(),
        read_checkpoint=CHECKPOINT,
        market_timezone=IST,
    )
    assert result.status is EntryQualificationCoherence.INCOHERENT
    assert "decision_id mismatch" in result.explanation


def test_incoherent_on_run_id_mismatch() -> None:
    result = resolve_entry_qualification_coherence(
        _eq(run_id="run-2"), _decision(), read_checkpoint=CHECKPOINT, market_timezone=IST
    )
    assert result.status is EntryQualificationCoherence.INCOHERENT
    assert "run_id/cycle_id mismatch" in result.explanation


def test_incoherent_on_cycle_id_mismatch() -> None:
    result = resolve_entry_qualification_coherence(
        _eq(cycle_id="cycle-2"), _decision(), read_checkpoint=CHECKPOINT, market_timezone=IST
    )
    assert result.status is EntryQualificationCoherence.INCOHERENT
    assert "run_id/cycle_id mismatch" in result.explanation


def test_incoherent_on_decision_type_mismatch() -> None:
    result = resolve_entry_qualification_coherence(
        _eq(decision_type=DecisionType.TRADE),
        _decision(decision_type=DecisionType.WATCH),
        read_checkpoint=CHECKPOINT,
        market_timezone=IST,
    )
    assert result.status is EntryQualificationCoherence.INCOHERENT
    assert "decision_type mismatch" in result.explanation


def test_incoherent_on_session_date_mismatch() -> None:
    result = resolve_entry_qualification_coherence(
        _eq(session_date=date(2026, 9, 8)),
        _decision(),
        read_checkpoint=CHECKPOINT,
        market_timezone=IST,
    )
    assert result.status is EntryQualificationCoherence.INCOHERENT
    assert "session_date" in result.explanation


def test_incoherent_on_as_of_date_mismatch() -> None:
    # as_of's own market-local date disagrees with session_date, even
    # though session_date itself happens to equal the checkpoint's date.
    result = resolve_entry_qualification_coherence(
        _eq(as_of=datetime(2026, 9, 8, 23, 55, tzinfo=IST), session_date=DAY),
        _decision(),
        read_checkpoint=CHECKPOINT,
        market_timezone=IST,
    )
    assert result.status is EntryQualificationCoherence.INCOHERENT
    assert "as_of's own market-local date" in result.explanation


def test_incoherent_on_future_as_of() -> None:
    result = resolve_entry_qualification_coherence(
        _eq(as_of=CHECKPOINT + timedelta(minutes=5)),
        _decision(),
        read_checkpoint=CHECKPOINT,
        market_timezone=IST,
    )
    assert result.status is EntryQualificationCoherence.INCOHERENT
    assert "temporally impossible" in result.explanation


def test_equal_as_of_and_checkpoint_is_coherent() -> None:
    """Equality is explicitly allowed -- only a strictly-future as_of is
    rejected (mirrors is_currently_usable's own PIT convention)."""
    result = resolve_entry_qualification_coherence(
        _eq(as_of=CHECKPOINT), _decision(), read_checkpoint=CHECKPOINT, market_timezone=IST
    )
    assert result.status is EntryQualificationCoherence.COHERENT


def test_rejects_naive_read_checkpoint() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        resolve_entry_qualification_coherence(
            _eq(),
            _decision(),
            read_checkpoint=datetime(2026, 9, 9, 9, 50),
            market_timezone=IST,
        )


def test_no_age_based_staleness_is_ever_applied() -> None:
    """An EQ whose as_of is hours old within the SAME session must still be
    COHERENT -- there is no frozen age-based staleness threshold for
    EntryQualification, and none may be invented here."""
    old_as_of = datetime(2026, 9, 9, 9, 16, tzinfo=IST)
    late_checkpoint = datetime(2026, 9, 9, 15, 0, tzinfo=IST)
    result = resolve_entry_qualification_coherence(
        _eq(as_of=old_as_of),
        _decision(),
        read_checkpoint=late_checkpoint,
        market_timezone=IST,
    )
    assert result.status is EntryQualificationCoherence.COHERENT
