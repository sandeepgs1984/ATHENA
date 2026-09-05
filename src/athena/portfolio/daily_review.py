"""Portfolio Daily Chart Review adapter (PS-P10D).

Consumes the PS-P10B D1 evidence primitives and produces the frozen
`portfolio-daily-review-v0` review layer. This module does not influence
Portfolio Status, Conviction, Trend, Setup, Key Trigger, Next Action,
EntryQualification, or TradePlan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum, unique

from athena.portfolio.daily_chart_evidence import (
    AthRollingHighEvidence,
    DailyChartEvidenceReason,
    RsiReviewEvidence,
    SuperTrendDirection,
    SuperTrendEvidence,
    VolumeReviewEvidence,
)

PORTFOLIO_DAILY_REVIEW_VERSION = "portfolio-daily-review-v0"


@unique
class PortfolioDailyReviewStatus(str, Enum):
    HOLD_STRONG = "HOLD_STRONG"
    HOLD = "HOLD"
    REVIEW_HOLD_TIGHT = "REVIEW_HOLD_TIGHT"


@unique
class PortfolioDailyReviewReason(str, Enum):
    EVIDENCE_INCOHERENT = "EVIDENCE_INCOHERENT"
    EVIDENCE_STALE_OR_SESSION_MISMATCH = "EVIDENCE_STALE_OR_SESSION_MISMATCH"
    EVIDENCE_UNAVAILABLE_OR_INSUFFICIENT_HISTORY = (
        "EVIDENCE_UNAVAILABLE_OR_INSUFFICIENT_HISTORY"
    )
    BULLISH_TRAILING_STRUCTURE_INTACT = "BULLISH_TRAILING_STRUCTURE_INTACT"
    NEW_AVAILABLE_HISTORY_HIGH = "NEW_AVAILABLE_HISTORY_HIGH"
    BEARISH_TRAILING_STRUCTURE_REVIEW = "BEARISH_TRAILING_STRUCTURE_REVIEW"
    PROFIT_CUSHION_PROTECT_WINNER_CONTEXT = "PROFIT_CUSHION_PROTECT_WINNER_CONTEXT"
    LOSS_CONTEXT_REVIEW_DISCIPLINE = "LOSS_CONTEXT_REVIEW_DISCIPLINE"
    VOLUME_CONTEXT_ONLY = "VOLUME_CONTEXT_ONLY"
    SUPPORT_METHOD_DEFERRED = "SUPPORT_METHOD_DEFERRED"
    TARGET_METHOD_DEFERRED = "TARGET_METHOD_DEFERRED"
    EXIT_RISK_DEFERRED = "EXIT_RISK_DEFERRED"
    REVIEW_CONVICTION_DEFERRED = "REVIEW_CONVICTION_DEFERRED"
    UNADJUSTED_HISTORY_LIMITATION = "UNADJUSTED_HISTORY_LIMITATION"


@dataclass(frozen=True, slots=True)
class PortfolioDailyReviewContext:
    quantity: int
    avg_price: Decimal
    current_price: Decimal | None
    pnl: Decimal | None
    pnl_pct: Decimal | None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("PortfolioDailyReviewContext.quantity must be > 0")
        if self.avg_price <= Decimal("0"):
            raise ValueError("PortfolioDailyReviewContext.avg_price must be > 0")


@dataclass(frozen=True, slots=True)
class PortfolioDailyReviewResult:
    review_status: PortfolioDailyReviewStatus | None
    methodology_version: str
    as_of: datetime | None
    evidence_as_of: datetime | None
    reason_codes: tuple[PortfolioDailyReviewReason, ...]
    guidance: str | None
    availability_reason: PortfolioDailyReviewReason | None
    supertrend_direction: SuperTrendDirection | None
    supertrend_value: Decimal | None
    supertrend_version: str
    rsi14: Decimal | None
    volume: int | None
    volume_ma20: Decimal | None
    available_history_high: Decimal | None
    latest_high_exceeds_prior_available_high: bool | None
    trailing_structure_level: Decimal | None


class PortfolioDailyReviewAdapter:
    """Resolve the frozen v0 daily-chart review for one Portfolio holding."""

    def resolve(
        self,
        *,
        supertrend: SuperTrendEvidence,
        rsi: RsiReviewEvidence,
        volume: VolumeReviewEvidence,
        history_high: AthRollingHighEvidence,
        position: PortfolioDailyReviewContext,
    ) -> PortfolioDailyReviewResult:
        reasons = [
            PortfolioDailyReviewReason.SUPPORT_METHOD_DEFERRED,
            PortfolioDailyReviewReason.TARGET_METHOD_DEFERRED,
            PortfolioDailyReviewReason.EXIT_RISK_DEFERRED,
            PortfolioDailyReviewReason.REVIEW_CONVICTION_DEFERRED,
        ]
        context_reasons = self._context_reasons(rsi, volume, history_high, position)
        availability = self._availability_reason(supertrend)
        if availability is not None:
            reasons.append(availability)
            reasons.extend(context_reasons)
            return self._result(
                status=None,
                availability=availability,
                reasons=reasons,
                supertrend=supertrend,
                rsi=rsi,
                volume=volume,
                history_high=history_high,
                guidance=self._guidance(None, reasons),
            )

        status: PortfolioDailyReviewStatus | None
        trailing_level: Decimal | None = None
        bullish_trailing_intact = (
            supertrend.direction is SuperTrendDirection.BULLISH
            and supertrend.latest_close is not None
            and supertrend.supertrend is not None
            and supertrend.latest_close >= supertrend.supertrend
        )
        new_high = history_high.latest_high_exceeds_prior_history is True
        if bullish_trailing_intact and new_high:
            status = PortfolioDailyReviewStatus.HOLD_STRONG
            trailing_level = supertrend.supertrend
            reasons.extend(
                [
                    PortfolioDailyReviewReason.BULLISH_TRAILING_STRUCTURE_INTACT,
                    PortfolioDailyReviewReason.NEW_AVAILABLE_HISTORY_HIGH,
                ]
            )
        elif bullish_trailing_intact:
            status = PortfolioDailyReviewStatus.HOLD
            trailing_level = supertrend.supertrend
            reasons.append(PortfolioDailyReviewReason.BULLISH_TRAILING_STRUCTURE_INTACT)
        elif (
            supertrend.direction is SuperTrendDirection.BEARISH
            or (
                supertrend.latest_close is not None
                and supertrend.supertrend is not None
                and supertrend.latest_close < supertrend.supertrend
            )
        ):
            status = PortfolioDailyReviewStatus.REVIEW_HOLD_TIGHT
            reasons.append(PortfolioDailyReviewReason.BEARISH_TRAILING_STRUCTURE_REVIEW)
        else:
            status = None
            reasons.append(
                PortfolioDailyReviewReason.EVIDENCE_UNAVAILABLE_OR_INSUFFICIENT_HISTORY
            )

        reasons.extend(context_reasons)
        guidance = self._guidance(status, reasons)
        result = self._result(
            status=status,
            availability=None if status is not None else reasons[-1],
            reasons=reasons,
            supertrend=supertrend,
            rsi=rsi,
            volume=volume,
            history_high=history_high,
            guidance=guidance,
        )
        return PortfolioDailyReviewResult(
            review_status=result.review_status,
            methodology_version=result.methodology_version,
            as_of=result.as_of,
            evidence_as_of=result.evidence_as_of,
            reason_codes=result.reason_codes,
            guidance=result.guidance,
            availability_reason=result.availability_reason,
            supertrend_direction=result.supertrend_direction,
            supertrend_value=result.supertrend_value,
            supertrend_version=result.supertrend_version,
            rsi14=result.rsi14,
            volume=result.volume,
            volume_ma20=result.volume_ma20,
            available_history_high=result.available_history_high,
            latest_high_exceeds_prior_available_high=(
                result.latest_high_exceeds_prior_available_high
            ),
            trailing_structure_level=trailing_level,
        )

    @staticmethod
    def _availability_reason(
        supertrend: SuperTrendEvidence,
    ) -> PortfolioDailyReviewReason | None:
        if supertrend.reason is DailyChartEvidenceReason.D1_EVIDENCE_INCOHERENT:
            return PortfolioDailyReviewReason.EVIDENCE_INCOHERENT
        if supertrend.reason in (
            DailyChartEvidenceReason.ACCEPTED_SESSION_MISMATCH,
            DailyChartEvidenceReason.EXPECTED_SESSION_MISMATCH,
        ):
            return PortfolioDailyReviewReason.EVIDENCE_STALE_OR_SESSION_MISMATCH
        if not supertrend.is_coherent or supertrend.direction is None:
            return PortfolioDailyReviewReason.EVIDENCE_UNAVAILABLE_OR_INSUFFICIENT_HISTORY
        return None

    @staticmethod
    def _context_reasons(
        rsi: RsiReviewEvidence,
        volume: VolumeReviewEvidence,
        history_high: AthRollingHighEvidence,
        position: PortfolioDailyReviewContext,
    ) -> list[PortfolioDailyReviewReason]:
        reasons: list[PortfolioDailyReviewReason] = []
        if position.pnl_pct is not None and position.pnl_pct > Decimal("0"):
            reasons.append(
                PortfolioDailyReviewReason.PROFIT_CUSHION_PROTECT_WINNER_CONTEXT
            )
        elif position.pnl_pct is not None and position.pnl_pct < Decimal("0"):
            reasons.append(PortfolioDailyReviewReason.LOSS_CONTEXT_REVIEW_DISCIPLINE)
        if volume.latest_volume is not None and volume.volume_ma is not None:
            reasons.append(PortfolioDailyReviewReason.VOLUME_CONTEXT_ONLY)
        if history_high.adjusted_history is False:
            reasons.append(PortfolioDailyReviewReason.UNADJUSTED_HISTORY_LIMITATION)
        return reasons

    @staticmethod
    def _result(
        *,
        status: PortfolioDailyReviewStatus | None,
        availability: PortfolioDailyReviewReason | None,
        reasons: list[PortfolioDailyReviewReason],
        supertrend: SuperTrendEvidence,
        rsi: RsiReviewEvidence,
        volume: VolumeReviewEvidence,
        history_high: AthRollingHighEvidence,
        guidance: str | None,
    ) -> PortfolioDailyReviewResult:
        return PortfolioDailyReviewResult(
            review_status=status,
            methodology_version=PORTFOLIO_DAILY_REVIEW_VERSION,
            as_of=supertrend.provenance.as_of,
            evidence_as_of=supertrend.provenance.latest_d1_session,
            reason_codes=tuple(dict.fromkeys(reasons)),
            guidance=guidance,
            availability_reason=availability,
            supertrend_direction=supertrend.direction,
            supertrend_value=supertrend.supertrend,
            supertrend_version=supertrend.version,
            rsi14=rsi.value,
            volume=volume.latest_volume,
            volume_ma20=volume.volume_ma,
            available_history_high=history_high.prior_available_history_high,
            latest_high_exceeds_prior_available_high=(
                history_high.latest_high_exceeds_prior_history
            ),
            trailing_structure_level=(
                supertrend.supertrend
                if status
                in (
                    PortfolioDailyReviewStatus.HOLD,
                    PortfolioDailyReviewStatus.HOLD_STRONG,
                )
                else None
            ),
        )

    @staticmethod
    def _guidance(
        status: PortfolioDailyReviewStatus | None,
        reasons: list[PortfolioDailyReviewReason],
    ) -> str | None:
        reason_set = set(reasons)
        if status is PortfolioDailyReviewStatus.HOLD_STRONG:
            return (
                "New available-history high; protect winner while SuperTrend "
                "structure remains intact. Targets deferred."
            )
        if status is PortfolioDailyReviewStatus.HOLD:
            return "Hold while SuperTrend trailing structure remains intact; targets deferred."
        if status is PortfolioDailyReviewStatus.REVIEW_HOLD_TIGHT:
            if PortfolioDailyReviewReason.LOSS_CONTEXT_REVIEW_DISCIPLINE in reason_set:
                return (
                    "Review closely: price is below bearish SuperTrend evidence; "
                    "loss alone does not create EXIT_RISK."
                )
            return (
                "Review closely: price is below bearish SuperTrend evidence; "
                "support methodology deferred."
            )
        if PortfolioDailyReviewReason.EVIDENCE_STALE_OR_SESSION_MISMATCH in reason_set:
            return "Daily Review unavailable: D1 evidence is stale for the accepted Portfolio session."
        if PortfolioDailyReviewReason.EVIDENCE_INCOHERENT in reason_set:
            return "Daily Review unavailable: D1 evidence is incoherent for this holding."
        if (
            PortfolioDailyReviewReason.EVIDENCE_UNAVAILABLE_OR_INSUFFICIENT_HISTORY
            in reason_set
        ):
            return "Daily Review unavailable: completed D1 evidence is unavailable or insufficient."
        return None
