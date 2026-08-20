"""Unit tests for DecisionsService.get_track_record (AUX-5 "My track record").

Pure aggregation over persisted DecisionJournalEntry + TradeOutcome data —
no new tracking, no new domain computation. Every rate/average field must be
None (never a fabricated 0) whenever its underlying sample is empty.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from athena.api.v1.providers.in_memory import InMemoryDecisionProvider
from athena.api.v1.services.decisions_service import DecisionsService
from athena.domain.decision import DecisionJournalEntry, TradeOutcome
from athena.domain.enums import UserAction


def _journal(decision_ref: str, action: UserAction, *, ts: datetime) -> DecisionJournalEntry:
    return DecisionJournalEntry(decision_ref=decision_ref, user_action=action, action_ts=ts, notes="")


def _outcome(
    decision_ref: str,
    *,
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: int = 10,
    holding_seconds: int = 86_400,
    adherence: dict | None = None,
    closed_ts: datetime = datetime(2026, 8, 1, tzinfo=timezone.utc),
) -> TradeOutcome:
    pnl = (exit_price - entry_price) * quantity
    return TradeOutcome(
        outcome_id=f"out-{decision_ref}",
        decision_ref=decision_ref,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        pnl=pnl,
        holding_seconds=holding_seconds,
        adherence=adherence or {},
        closed_ts=closed_ts,
    )


@pytest.fixture()
def provider() -> InMemoryDecisionProvider:
    return InMemoryDecisionProvider()


def test_empty_history_yields_none_rates_not_fabricated_zeros(config_dir, provider):
    service = DecisionsService(provider, config_dir=config_dir)
    record = service.get_track_record()

    assert record.journal_entry_count == 0
    assert record.accept_rate_pct is None
    assert record.closed_trade_count == 0
    assert record.win_rate_pct is None
    assert record.avg_return_pct is None
    assert record.avg_holding_days is None
    assert record.plan_adherence_rate_pct is None
    assert record.total_pnl == Decimal("0")


def test_journal_action_breakdown_and_accept_rate(config_dir, provider):
    ts = datetime(2026, 8, 1, tzinfo=timezone.utc)
    provider.journal_entries["d1"] = _journal("d1", UserAction.ACCEPTED, ts=ts)
    provider.journal_entries["d2"] = _journal("d2", UserAction.ACCEPTED, ts=ts)
    provider.journal_entries["d3"] = _journal("d3", UserAction.REJECTED, ts=ts)
    provider.journal_entries["d4"] = _journal("d4", UserAction.IGNORED, ts=ts)

    service = DecisionsService(provider, config_dir=config_dir)
    record = service.get_track_record()

    assert record.journal_entry_count == 4
    assert record.accepted_count == 2
    assert record.rejected_count == 1
    assert record.ignored_count == 1
    assert record.accept_rate_pct == Decimal("50")


def test_win_loss_breakeven_counts_and_total_pnl(config_dir, provider):
    provider.trade_outcomes["d1"] = _outcome("d1", entry_price=Decimal("100"), exit_price=Decimal("110"))
    provider.trade_outcomes["d2"] = _outcome("d2", entry_price=Decimal("100"), exit_price=Decimal("90"))
    provider.trade_outcomes["d3"] = _outcome("d3", entry_price=Decimal("100"), exit_price=Decimal("100"))

    service = DecisionsService(provider, config_dir=config_dir)
    record = service.get_track_record()

    assert record.closed_trade_count == 3
    assert record.win_count == 1
    assert record.loss_count == 1
    assert record.breakeven_count == 1
    assert record.win_rate_pct == Decimal("100") / Decimal("3")
    assert record.total_pnl == Decimal("0")  # +100 -100 +0


def test_avg_return_and_holding_days_over_real_outcomes(config_dir, provider):
    # d1: +10% return over 1 day; d2: +20% return over 2 days.
    provider.trade_outcomes["d1"] = _outcome(
        "d1", entry_price=Decimal("100"), exit_price=Decimal("110"), holding_seconds=86_400
    )
    provider.trade_outcomes["d2"] = _outcome(
        "d2", entry_price=Decimal("100"), exit_price=Decimal("120"), holding_seconds=172_800
    )

    service = DecisionsService(provider, config_dir=config_dir)
    record = service.get_track_record()

    assert record.avg_return_pct == Decimal("15")
    assert record.avg_holding_days == Decimal("1.5")


def test_plan_adherence_rate_flattens_checks_across_outcomes(config_dir, provider):
    provider.trade_outcomes["d1"] = _outcome(
        "d1",
        entry_price=Decimal("100"),
        exit_price=Decimal("110"),
        adherence={"entered_within_zone": True, "hit_stop": False, "hit_target": True},
    )
    provider.trade_outcomes["d2"] = _outcome(
        "d2",
        entry_price=Decimal("100"),
        exit_price=Decimal("90"),
        adherence={"entered_within_zone": True, "hit_stop": True, "hit_target": False},
    )

    service = DecisionsService(provider, config_dir=config_dir)
    record = service.get_track_record()

    # 4 True out of 6 checks total.
    assert record.adherence_check_count == 6
    assert record.adherence_pass_count == 4
    assert record.plan_adherence_rate_pct == (Decimal("4") / Decimal("6")) * 100


def test_outcomes_with_no_trade_plan_have_empty_adherence_and_do_not_skew_rate(config_dir, provider):
    """A WATCH-side outcome (no TradePlan) yields an empty adherence dict —
    it must not be counted as failed checks, only excluded from the sample."""
    provider.trade_outcomes["d1"] = _outcome(
        "d1", entry_price=Decimal("100"), exit_price=Decimal("110"), adherence={}
    )
    provider.trade_outcomes["d2"] = _outcome(
        "d2",
        entry_price=Decimal("100"),
        exit_price=Decimal("90"),
        adherence={"entered_within_zone": True},
    )

    service = DecisionsService(provider, config_dir=config_dir)
    record = service.get_track_record()

    assert record.adherence_check_count == 1
    assert record.adherence_pass_count == 1
    assert record.plan_adherence_rate_pct == Decimal("100")
