"""Immutable daily briefing artifacts (M10.3)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from types import MappingProxyType


@unique
class BriefingStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class BriefingRunSummary:
    """One run ledger row condensed for a briefing."""

    run_id: str
    trigger: str
    status: str
    started_ts: datetime
    candles_written: int = 0
    quotes_written: int = 0

    def __post_init__(self) -> None:
        if self.started_ts.tzinfo is None:
            raise ValueError("BriefingRunSummary.started_ts must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "trigger": self.trigger,
            "status": self.status,
            "started_ts": self.started_ts.isoformat(),
            "candles_written": self.candles_written,
            "quotes_written": self.quotes_written,
        }


@dataclass(frozen=True, slots=True)
class BriefingDecisionSummary:
    """Lightweight decision line for a briefing (trace optional)."""

    decision_id: str
    decision_type: str
    instrument_id: str | None
    direction: str
    explanation: str
    trace_stage_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type,
            "instrument_id": self.instrument_id,
            "direction": self.direction,
            "explanation": self.explanation,
            "trace_stage_count": self.trace_stage_count,
        }


@dataclass(frozen=True, slots=True)
class BriefingNearMiss:
    """A WATCH decision that passed every gate and sits within the configured
    margin of the trade threshold (AUX-4a). ``composite`` and ``score_gap`` are
    read from the same persisted report the decision counterfactual endpoint
    (M-X2) uses -- never recomputed here."""

    decision_id: str
    instrument_id: str | None
    composite: str
    score_gap: str
    trade_threshold: int

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "instrument_id": self.instrument_id,
            "composite": self.composite,
            "score_gap": self.score_gap,
            "trade_threshold": self.trade_threshold,
        }


@dataclass(frozen=True, slots=True)
class BriefingJournalPrompt:
    """Prompt to record a user action/outcome for a decision (R6 / Blueprint §8)."""

    decision_id: str
    instrument_id: str | None
    decision_type: str
    prompt: str

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "instrument_id": self.instrument_id,
            "decision_type": self.decision_type,
            "prompt": self.prompt,
        }


@dataclass(frozen=True, slots=True)
class DailyBriefing:
    """Immutable daily briefing — assemble once, notify many."""

    briefing_id: str
    as_of: datetime
    status: BriefingStatus
    runs: tuple[BriefingRunSummary, ...]
    decisions: tuple[BriefingDecisionSummary, ...]
    text_summary: str
    machine: Mapping[str, object]
    degradation_reasons: tuple[str, ...] = ()
    day_summary: Mapping[str, object] = field(default_factory=dict)
    journal_prompts: tuple[BriefingJournalPrompt, ...] = ()
    near_misses: tuple[BriefingNearMiss, ...] = ()

    def __post_init__(self) -> None:
        if not self.briefing_id:
            raise ValueError("DailyBriefing.briefing_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("DailyBriefing.as_of must be timezone-aware")
        if not self.text_summary:
            raise ValueError("DailyBriefing.text_summary is mandatory")
        object.__setattr__(self, "machine", MappingProxyType(dict(self.machine)))
        object.__setattr__(self, "day_summary", MappingProxyType(dict(self.day_summary)))
        if self.status is BriefingStatus.DEGRADED and not self.degradation_reasons:
            raise ValueError("DEGRADED briefing must carry degradation_reasons")
        if self.status is BriefingStatus.OK and self.degradation_reasons:
            raise ValueError("OK briefing cannot carry degradation_reasons")

    def to_dict(self) -> dict[str, object]:
        return {
            "briefing_id": self.briefing_id,
            "as_of": self.as_of.isoformat(),
            "status": self.status.value,
            "runs": [r.to_dict() for r in self.runs],
            "decisions": [d.to_dict() for d in self.decisions],
            "day_summary": dict(self.day_summary),
            "journal_prompts": [p.to_dict() for p in self.journal_prompts],
            "near_misses": [n.to_dict() for n in self.near_misses],
            "text_summary": self.text_summary,
            "machine": dict(self.machine),
            "degradation_reasons": list(self.degradation_reasons),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    def to_text(self) -> str:
        return self.text_summary


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    """Outcome of one notifier delivery."""

    channel: str
    ok: bool
    detail: str
    target: str = ""

    def __post_init__(self) -> None:
        if not self.channel:
            raise ValueError("DeliveryReceipt.channel is mandatory")
        if not self.detail:
            raise ValueError("DeliveryReceipt.detail is mandatory")


@dataclass(frozen=True, slots=True)
class BriefingDispatchResult:
    """Build + notify result for one ``athena brief`` invocation."""

    briefing: DailyBriefing
    receipts: tuple[DeliveryReceipt, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipts", tuple(self.receipts))
