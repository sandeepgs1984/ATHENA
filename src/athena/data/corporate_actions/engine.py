"""Corporate Actions Engine (M1.4).

Applies corporate actions to canonical candle datasets deterministically,
producing ADJUSTED COPIES with full evidence. Never mutates originals, never
fetches or persists anything, knows nothing about providers or storage.

Adjustment model (standard back-adjustment):
- An action with ex_date D affects only candles strictly BEFORE D (historical
  prices are scaled to be comparable with post-action prices).
- Split from->to: price *= from/to, volume *= to/from.
- Bonus b:h        : price *= h/(h+b), volume *= (h+b)/h.
- Dividend amount  : price *= (Cprev - amount)/Cprev, where Cprev is the raw
  close of the last candle before D; volume unchanged.
- Factors are cumulative (product of all applicable actions per candle).
- Renames never change candle values; they map identifiers and are recorded as
  evidence.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Sequence

from athena.calendar.engine import CalendarEngine
from athena.data.corporate_actions.evidence import AdjustmentEvidence, AdjustmentResult
from athena.data.corporate_actions.models import (
    AdjustmentStrategy,
    Bonus,
    CorporateActionType,
    Dividend,
    Rename,
    Split,
    TypedAction,
    parse_action,
)
from athena.domain.market import Candle, CorporateAction
from athena.errors import CorporateActionError

_ONE = Decimal(1)


class CorporateActionsEngine:
    """Deterministic, explainable corporate-action adjustment."""

    def __init__(self, calendar: Optional[CalendarEngine] = None) -> None:
        # Calendar is optional and used only to ANNOTATE whether an ex_date is a
        # trading session — effective dates are never inferred (M1.4 rule).
        self._calendar = calendar

    # ------------------------------------------------------------------ renames

    def build_symbol_map(self, actions: Sequence[CorporateAction]) -> Dict[str, str]:
        """Direct old->new symbol mapping from RENAME actions (ex_date order)."""
        renames = sorted(
            (a for a in self._typed(actions) if isinstance(a, Rename)),
            key=lambda a: a.ex_date,
        )
        return {r.old_symbol: r.new_symbol for r in renames}

    def resolve_symbol(self, actions: Sequence[CorporateAction], symbol: str) -> str:
        """Follow the rename chain to the current symbol (A->B->C resolves A->C)."""
        mapping = self.build_symbol_map(actions)
        seen = set()
        current = symbol
        while current in mapping and current not in seen:
            seen.add(current)
            current = mapping[current]
        return current

    # --------------------------------------------------------------- adjustment

    def adjust(
        self,
        instrument_id: str,
        candles: Sequence[Candle],
        actions: Sequence[CorporateAction],
        *,
        strategy: AdjustmentStrategy,
        as_of: datetime,
    ) -> AdjustmentResult:
        """Return an adjusted copy of ``candles`` for ``instrument_id`` under ``strategy``."""
        ordered = sorted(candles, key=lambda c: c.ts_open)
        typed = [a for a in self._typed(actions) if a.instrument_id == instrument_id]

        price_actions = [a for a in typed if not isinstance(a, Rename)]
        renames = [a for a in typed if isinstance(a, Rename)]

        # Precompute each applicable action's factors + evidence.
        applied: List[tuple[TypedAction, Decimal, Decimal]] = []
        evidence: List[AdjustmentEvidence] = []

        for action in sorted(price_actions, key=lambda a: a.ex_date):
            if not strategy.includes(action.action_type):
                continue
            price_factor, volume_factor = self._factors(action, ordered)
            affected = sum(1 for c in ordered if c.ts_open.date() < action.ex_date)
            applied.append((action, price_factor, volume_factor))
            evidence.append(AdjustmentEvidence(
                action_id=action.action_id,
                action_type=action.action_type,
                ex_date=action.ex_date,
                price_factor=price_factor,
                volume_factor=volume_factor,
                affected_records=affected,
                explanation=(f"{action.explanation}: applied price*{price_factor} "
                             f"volume*{volume_factor} to {affected} pre-ex candle(s)"),
                metadata=self._calendar_note(action),
            ))

        adjusted = tuple(self._apply(c, applied) for c in ordered)

        for r in sorted(renames, key=lambda a: a.ex_date):
            evidence.append(AdjustmentEvidence(
                action_id=r.action_id, action_type=CorporateActionType.RENAME,
                ex_date=r.ex_date, price_factor=_ONE, volume_factor=_ONE,
                affected_records=0,
                explanation=f"{r.explanation}: identifier mapping only, no price/volume change",
                metadata={"old_symbol": r.old_symbol, "new_symbol": r.new_symbol,
                          **self._calendar_note(r)},
            ))

        summary = (f"{strategy.value}: {len(applied)} price adjustment(s), "
                   f"{len(renames)} rename(s) over {len(ordered)} candle(s)")
        return AdjustmentResult(
            instrument_id=instrument_id, strategy=strategy,
            adjusted_candles=adjusted, evidence=tuple(evidence),
            explanation=summary, ts=as_of,
        )

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _typed(actions: Sequence[CorporateAction]) -> List[TypedAction]:
        return [parse_action(a) for a in actions]

    def _factors(self, action: TypedAction, ordered: Sequence[Candle]) -> tuple[Decimal, Decimal]:
        if isinstance(action, (Split, Bonus)):
            return action.price_factor, action.volume_factor
        if isinstance(action, Dividend):
            prev = [c for c in ordered if c.ts_open.date() < action.ex_date]
            if not prev:
                return _ONE, _ONE  # nothing before ex-date to adjust
            ref_close = prev[-1].close
            if action.amount >= ref_close:
                raise CorporateActionError(
                    f"dividend {action.action_id}: amount {action.amount} >= reference close "
                    f"{ref_close} (implausible)")
            return (ref_close - action.amount) / ref_close, _ONE
        raise CorporateActionError(f"unsupported price action: {action}")

    @staticmethod
    def _apply(candle: Candle, applied: List[tuple[TypedAction, Decimal, Decimal]]) -> Candle:
        price_factor = _ONE
        volume_factor = _ONE
        for action, pf, vf in applied:
            if candle.ts_open.date() < action.ex_date:
                price_factor *= pf
                volume_factor *= vf
        if price_factor == _ONE and volume_factor == _ONE:
            return candle  # untouched (on/after all ex-dates, or RAW)
        new_volume = int((Decimal(candle.volume) * volume_factor).quantize(
            _ONE, rounding=ROUND_HALF_UP))
        return replace(
            candle,
            open=candle.open * price_factor,
            high=candle.high * price_factor,
            low=candle.low * price_factor,
            close=candle.close * price_factor,
            volume=new_volume,
            adjusted=True,
        )

    def _calendar_note(self, action: TypedAction) -> Dict[str, str]:
        if self._calendar is None:
            return {}
        try:
            ctx = self._calendar.context_for(action.ex_date)
        except Exception:  # calendar has no data for that year — annotate, never fail
            return {"ex_date_session": "unknown"}
        return {"ex_date_session": ctx.session_type.value}
