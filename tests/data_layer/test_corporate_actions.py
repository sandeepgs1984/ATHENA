"""Corporate Actions Engine tests (M1.4): splits, bonuses, dividends, renames,
sequential actions, strategies, replay determinism, immutability, invalid defs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.data.corporate_actions import (
    AdjustmentStrategy,
    CorporateActionsEngine,
    CorporateActionType,
    parse_action,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, CorporateAction
from athena.errors import CorporateActionError

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 1, 18, 0, tzinfo=IST)
INST = "INE-TEST-0001"


def _candle(day: date, close: str, *, vol: int = 1000) -> Candle:
    c = Decimal(close)
    return Candle(instrument_id=INST, timeframe=Timeframe.D1,
                  ts_open=datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                  open=c, high=c + 1, low=c - 1, close=c, volume=vol, source="test")


def _series() -> list[Candle]:
    # Five trading days in Feb 2026, close climbing 100..104
    return [_candle(date(2026, 2, d), str(100 + i)) for i, d in enumerate([2, 3, 4, 5, 6])]


def _action(action_id, kind, ex_date, details) -> CorporateAction:
    return CorporateAction(action_id=action_id, instrument_id=INST,
                           action_type=kind, ex_date=ex_date, details=details)


@pytest.fixture()
def engine() -> CorporateActionsEngine:
    return CorporateActionsEngine()


class TestParsing:
    def test_parse_all_types(self):
        assert parse_action(_action("s", "SPLIT", date(2026, 2, 4),
                                    {"from_shares": 1, "to_shares": 5})).action_type is CorporateActionType.SPLIT
        assert parse_action(_action("b", "BONUS", date(2026, 2, 4),
                                    {"bonus_shares": 1, "held_shares": 1})).action_type is CorporateActionType.BONUS
        assert parse_action(_action("d", "DIVIDEND", date(2026, 2, 4),
                                    {"amount": "10"})).action_type is CorporateActionType.DIVIDEND
        assert parse_action(_action("r", "RENAME", date(2026, 2, 4),
                                    {"old_symbol": "A", "new_symbol": "B"})).action_type is CorporateActionType.RENAME

    def test_unknown_type_fails(self):
        with pytest.raises(CorporateActionError, match="unknown action type"):
            parse_action(_action("x", "MERGER", date(2026, 2, 4), {}))

    def test_missing_parameter_fails(self):
        with pytest.raises(CorporateActionError, match="missing 'to_shares'"):
            parse_action(_action("s", "SPLIT", date(2026, 2, 4), {"from_shares": 1}))

    def test_non_positive_split_fails(self):
        with pytest.raises(CorporateActionError, match="must be > 0"):
            parse_action(_action("s", "SPLIT", date(2026, 2, 4), {"from_shares": 0, "to_shares": 5}))


class TestSplit:
    def test_split_adjusts_prices_and_volume_before_ex_date(self, engine):
        actions = [_action("s1", "SPLIT", date(2026, 2, 4), {"from_shares": 1, "to_shares": 5})]
        result = engine.adjust(INST, _series(), actions,
                               strategy=AdjustmentStrategy.SPLIT_ADJUSTED, as_of=AS_OF)
        by_date = {c.ts_open.date(): c for c in result.adjusted_candles}
        # Before ex-date (Feb 2, close 100): price /5 = 20, volume *5 = 5000
        assert by_date[date(2026, 2, 2)].close == Decimal("20")
        assert by_date[date(2026, 2, 2)].volume == 5000
        assert by_date[date(2026, 2, 2)].adjusted is True
        # On/after ex-date (Feb 4): untouched
        assert by_date[date(2026, 2, 4)].close == Decimal("102")
        assert by_date[date(2026, 2, 4)].adjusted is False

    def test_raw_strategy_makes_no_change(self, engine):
        actions = [_action("s1", "SPLIT", date(2026, 2, 4), {"from_shares": 1, "to_shares": 5})]
        result = engine.adjust(INST, _series(), actions,
                               strategy=AdjustmentStrategy.RAW, as_of=AS_OF)
        assert all(not c.adjusted for c in result.adjusted_candles)
        assert result.evidence == ()


class TestBonus:
    def test_bonus_1_1_halves_prior_price_doubles_volume(self, engine):
        actions = [_action("b1", "BONUS", date(2026, 2, 4), {"bonus_shares": 1, "held_shares": 1})]
        result = engine.adjust(INST, _series(), actions,
                               strategy=AdjustmentStrategy.SPLIT_BONUS_ADJUSTED, as_of=AS_OF)
        by_date = {c.ts_open.date(): c for c in result.adjusted_candles}
        assert by_date[date(2026, 2, 2)].close == Decimal("50")   # 100 * 1/2
        assert by_date[date(2026, 2, 2)].volume == 2000

    def test_bonus_ignored_under_split_only_strategy(self, engine):
        actions = [_action("b1", "BONUS", date(2026, 2, 4), {"bonus_shares": 1, "held_shares": 1})]
        result = engine.adjust(INST, _series(), actions,
                               strategy=AdjustmentStrategy.SPLIT_ADJUSTED, as_of=AS_OF)
        assert all(not c.adjusted for c in result.adjusted_candles)


class TestDividend:
    def test_dividend_factor_uses_prior_close(self, engine):
        # ex-date Feb 5; prior close is Feb 4 = 102; amount 2 → factor 100/102
        actions = [_action("d1", "DIVIDEND", date(2026, 2, 5), {"amount": "2"})]
        result = engine.adjust(INST, _series(), actions,
                               strategy=AdjustmentStrategy.FULLY_ADJUSTED, as_of=AS_OF)
        by_date = {c.ts_open.date(): c for c in result.adjusted_candles}
        factor = (Decimal("102") - Decimal("2")) / Decimal("102")
        assert by_date[date(2026, 2, 2)].close == Decimal("100") * factor
        assert by_date[date(2026, 2, 4)].volume == 1000  # volume unchanged by dividends

    def test_dividend_ignored_unless_fully_adjusted(self, engine):
        actions = [_action("d1", "DIVIDEND", date(2026, 2, 5), {"amount": "2"})]
        result = engine.adjust(INST, _series(), actions,
                               strategy=AdjustmentStrategy.SPLIT_BONUS_ADJUSTED, as_of=AS_OF)
        assert all(not c.adjusted for c in result.adjusted_candles)

    def test_implausible_dividend_fails(self, engine):
        actions = [_action("d1", "DIVIDEND", date(2026, 2, 5), {"amount": "9999"})]
        with pytest.raises(CorporateActionError, match="implausible"):
            engine.adjust(INST, _series(), actions,
                          strategy=AdjustmentStrategy.FULLY_ADJUSTED, as_of=AS_OF)


class TestRenames:
    def test_symbol_map_and_chain(self, engine):
        actions = [
            _action("r1", "RENAME", date(2026, 2, 3), {"old_symbol": "AAA", "new_symbol": "BBB"}),
            _action("r2", "RENAME", date(2026, 2, 5), {"old_symbol": "BBB", "new_symbol": "CCC"}),
        ]
        assert engine.build_symbol_map(actions) == {"AAA": "BBB", "BBB": "CCC"}
        assert engine.resolve_symbol(actions, "AAA") == "CCC"

    def test_rename_does_not_change_candles_but_is_evidenced(self, engine):
        actions = [_action("r1", "RENAME", date(2026, 2, 3), {"old_symbol": "AAA", "new_symbol": "BBB"})]
        result = engine.adjust(INST, _series(), actions,
                               strategy=AdjustmentStrategy.FULLY_ADJUSTED, as_of=AS_OF)
        assert all(not c.adjusted for c in result.adjusted_candles)
        rename_ev = [e for e in result.evidence if e.action_type is CorporateActionType.RENAME]
        assert len(rename_ev) == 1
        assert rename_ev[0].metadata["new_symbol"] == "BBB"


class TestSequentialAndReplay:
    def test_sequential_split_then_bonus_are_cumulative(self, engine):
        actions = [
            _action("s1", "SPLIT", date(2026, 2, 4), {"from_shares": 1, "to_shares": 2}),
            _action("b1", "BONUS", date(2026, 2, 6), {"bonus_shares": 1, "held_shares": 1}),
        ]
        result = engine.adjust(INST, _series(), actions,
                               strategy=AdjustmentStrategy.SPLIT_BONUS_ADJUSTED, as_of=AS_OF)
        by_date = {c.ts_open.date(): c for c in result.adjusted_candles}
        # Feb 2 is before both: factor = (1/2) * (1/2) = 1/4 → 100 * 1/4 = 25
        assert by_date[date(2026, 2, 2)].close == Decimal("25")
        # Feb 5 is after split, before bonus: factor = 1/2 → 103 * 1/2 = 51.5
        assert by_date[date(2026, 2, 5)].close == Decimal("51.5")

    def test_replay_is_deterministic(self, engine):
        actions = [_action("s1", "SPLIT", date(2026, 2, 4), {"from_shares": 1, "to_shares": 5})]
        a = engine.adjust(INST, _series(), actions, strategy=AdjustmentStrategy.FULLY_ADJUSTED, as_of=AS_OF)
        b = engine.adjust(INST, _series(), actions, strategy=AdjustmentStrategy.FULLY_ADJUSTED, as_of=AS_OF)
        assert a.adjusted_candles == b.adjusted_candles
        assert a.evidence == b.evidence


class TestImmutabilityAndNoAction:
    def test_originals_not_mutated(self, engine):
        original = _series()
        snapshot = [(c.close, c.volume) for c in original]
        engine.adjust(INST, original, [_action("s1", "SPLIT", date(2026, 2, 4),
                                                {"from_shares": 1, "to_shares": 5})],
                      strategy=AdjustmentStrategy.SPLIT_ADJUSTED, as_of=AS_OF)
        assert [(c.close, c.volume) for c in original] == snapshot

    def test_no_actions_returns_unadjusted_copy(self, engine):
        result = engine.adjust(INST, _series(), [],
                               strategy=AdjustmentStrategy.FULLY_ADJUSTED, as_of=AS_OF)
        assert len(result.adjusted_candles) == 5
        assert all(not c.adjusted for c in result.adjusted_candles)
        assert result.evidence == ()

    def test_actions_for_other_instrument_ignored(self, engine):
        other = CorporateAction(action_id="o1", instrument_id="OTHER",
                                action_type="SPLIT", ex_date=date(2026, 2, 4),
                                details={"from_shares": 1, "to_shares": 5})
        result = engine.adjust(INST, _series(), [other],
                               strategy=AdjustmentStrategy.SPLIT_ADJUSTED, as_of=AS_OF)
        assert all(not c.adjusted for c in result.adjusted_candles)

    def test_evidence_reports_affected_record_count(self, engine):
        actions = [_action("s1", "SPLIT", date(2026, 2, 4), {"from_shares": 1, "to_shares": 5})]
        result = engine.adjust(INST, _series(), actions,
                               strategy=AdjustmentStrategy.SPLIT_ADJUSTED, as_of=AS_OF)
        assert result.evidence[0].affected_records == 2  # Feb 2 and Feb 3
