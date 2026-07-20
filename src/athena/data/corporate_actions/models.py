"""Typed corporate action model (M1.4).

Parses the canonical, frozen ``CorporateAction`` domain object (action_type +
details mapping) into validated, immutable typed actions the adjustment engine
can apply deterministically. This module adds NO fields to the frozen domain
model (ATHENA-002 §4) — it interprets it.

Explicit detail keys (no ambiguity, never inferred):
- SPLIT     : {"from_shares": int>0, "to_shares": int>0}       e.g. 1->5
- BONUS     : {"bonus_shares": int>0, "held_shares": int>0}    e.g. 1:1
- DIVIDEND  : {"amount": Decimal>0}                             cash per share
- RENAME    : {"old_symbol": str, "new_symbol": str}
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum, unique

from athena.domain.market import CorporateAction
from athena.errors import CorporateActionError


@unique
class CorporateActionType(str, Enum):
    SPLIT = "SPLIT"
    BONUS = "BONUS"
    DIVIDEND = "DIVIDEND"
    RENAME = "RENAME"


@unique
class AdjustmentStrategy(str, Enum):
    """Explicit, traceable adjustment strategies (never hidden behavior)."""

    RAW = "RAW"                                  # no adjustment
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"            # splits only
    SPLIT_BONUS_ADJUSTED = "SPLIT_BONUS_ADJUSTED"  # splits + bonuses
    FULLY_ADJUSTED = "FULLY_ADJUSTED"            # splits + bonuses + dividends

    def includes(self, action_type: CorporateActionType) -> bool:
        mapping = {
            AdjustmentStrategy.RAW: set(),
            AdjustmentStrategy.SPLIT_ADJUSTED: {CorporateActionType.SPLIT},
            AdjustmentStrategy.SPLIT_BONUS_ADJUSTED: {
                CorporateActionType.SPLIT, CorporateActionType.BONUS},
            AdjustmentStrategy.FULLY_ADJUSTED: {
                CorporateActionType.SPLIT, CorporateActionType.BONUS,
                CorporateActionType.DIVIDEND},
        }
        return action_type in mapping[self]


@dataclass(frozen=True, slots=True)
class Split:
    action_id: str
    instrument_id: str
    ex_date: date
    from_shares: int
    to_shares: int
    explanation: str

    action_type = CorporateActionType.SPLIT

    def __post_init__(self) -> None:
        if self.from_shares <= 0 or self.to_shares <= 0:
            raise CorporateActionError(
                f"split {self.action_id}: from_shares/to_shares must be > 0")

    @property
    def price_factor(self) -> Decimal:
        return Decimal(self.from_shares) / Decimal(self.to_shares)

    @property
    def volume_factor(self) -> Decimal:
        return Decimal(self.to_shares) / Decimal(self.from_shares)


@dataclass(frozen=True, slots=True)
class Bonus:
    action_id: str
    instrument_id: str
    ex_date: date
    bonus_shares: int
    held_shares: int
    explanation: str

    action_type = CorporateActionType.BONUS

    def __post_init__(self) -> None:
        if self.bonus_shares <= 0 or self.held_shares <= 0:
            raise CorporateActionError(
                f"bonus {self.action_id}: bonus_shares/held_shares must be > 0")

    @property
    def price_factor(self) -> Decimal:
        return Decimal(self.held_shares) / Decimal(self.held_shares + self.bonus_shares)

    @property
    def volume_factor(self) -> Decimal:
        return Decimal(self.held_shares + self.bonus_shares) / Decimal(self.held_shares)


@dataclass(frozen=True, slots=True)
class Dividend:
    action_id: str
    instrument_id: str
    ex_date: date
    amount: Decimal
    explanation: str

    action_type = CorporateActionType.DIVIDEND

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise CorporateActionError(f"dividend {self.action_id}: amount must be > 0")


@dataclass(frozen=True, slots=True)
class Rename:
    action_id: str
    instrument_id: str
    ex_date: date
    old_symbol: str
    new_symbol: str
    explanation: str

    action_type = CorporateActionType.RENAME

    def __post_init__(self) -> None:
        if not self.old_symbol or not self.new_symbol:
            raise CorporateActionError(
                f"rename {self.action_id}: old_symbol and new_symbol are required")


TypedAction = Split | Bonus | Dividend | Rename


def _require_int(details: dict, key: str, action_id: str) -> int:
    if key not in details:
        raise CorporateActionError(f"action {action_id}: missing '{key}'")
    try:
        return int(details[key])
    except (TypeError, ValueError) as exc:
        raise CorporateActionError(f"action {action_id}: '{key}' must be an integer") from exc


def _require_decimal(details: dict, key: str, action_id: str) -> Decimal:
    if key not in details:
        raise CorporateActionError(f"action {action_id}: missing '{key}'")
    try:
        return Decimal(str(details[key]))
    except (InvalidOperation, TypeError) as exc:
        raise CorporateActionError(f"action {action_id}: '{key}' must be a number") from exc


def _require_str(details: dict, key: str, action_id: str) -> str:
    value = details.get(key)
    if not isinstance(value, str) or not value:
        raise CorporateActionError(f"action {action_id}: '{key}' must be a non-empty string")
    return value


def parse_action(raw: CorporateAction) -> TypedAction:
    """Interpret a canonical CorporateAction into a validated typed action.

    Raises CorporateActionError for unknown types or malformed parameters —
    corporate actions are historical truth; bad definitions fail loudly.
    """
    try:
        kind = CorporateActionType(raw.action_type)
    except ValueError as exc:
        raise CorporateActionError(
            f"action {raw.action_id}: unknown action type '{raw.action_type}' "
            f"(supported: {[t.value for t in CorporateActionType]})"
        ) from exc

    details = dict(raw.details)
    common = dict(action_id=raw.action_id, instrument_id=raw.instrument_id, ex_date=raw.ex_date)

    if kind is CorporateActionType.SPLIT:
        f = _require_int(details, "from_shares", raw.action_id)
        t = _require_int(details, "to_shares", raw.action_id)
        return Split(**common, from_shares=f, to_shares=t,
                     explanation=f"{f}-for-{t} split on {raw.ex_date.isoformat()}")
    if kind is CorporateActionType.BONUS:
        b = _require_int(details, "bonus_shares", raw.action_id)
        h = _require_int(details, "held_shares", raw.action_id)
        return Bonus(**common, bonus_shares=b, held_shares=h,
                     explanation=f"{b}:{h} bonus on {raw.ex_date.isoformat()}")
    if kind is CorporateActionType.DIVIDEND:
        amt = _require_decimal(details, "amount", raw.action_id)
        return Dividend(**common, amount=amt,
                        explanation=f"cash dividend {amt} on {raw.ex_date.isoformat()}")
    old = _require_str(details, "old_symbol", raw.action_id)
    new = _require_str(details, "new_symbol", raw.action_id)
    return Rename(**common, old_symbol=old, new_symbol=new,
                  explanation=f"rename {old} -> {new} on {raw.ex_date.isoformat()}")
