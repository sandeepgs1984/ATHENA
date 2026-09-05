"""PS-P10D Portfolio Daily Chart Review adapter tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from athena.domain.enums import Timeframe
from athena.portfolio.daily_chart_evidence import (
    SUPERTREND_ATR_PERIOD,
    SUPERTREND_MULTIPLIER,
    SUPERTREND_VERSION,
    AthRollingHighEvidence,
    DailyChartEvidenceProvenance,
    DailyChartEvidenceReason,
    RsiReviewEvidence,
    SuperTrendDirection,
    SuperTrendEvidence,
    VolumeReviewEvidence,
)
from athena.portfolio.daily_review import (
    PORTFOLIO_DAILY_REVIEW_VERSION,
    PortfolioDailyReviewAdapter,
    PortfolioDailyReviewContext,
    PortfolioDailyReviewReason,
    PortfolioDailyReviewStatus,
)

AS_OF = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)


def _provenance() -> DailyChartEvidenceProvenance:
    return DailyChartEvidenceProvenance(
        instrument_id="NSE:INFY",
        timeframe=Timeframe.D1,
        as_of=AS_OF,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        first_d1_session=AS_OF,
        latest_d1_session=AS_OF,
        candles_used=40,
        source_count=40,
    )


def _supertrend(
    direction: SuperTrendDirection | None,
    *,
    close: str = "120",
    level: str = "100",
    reason: DailyChartEvidenceReason = DailyChartEvidenceReason.OK,
    coherent: bool = True,
) -> SuperTrendEvidence:
    return SuperTrendEvidence(
        direction=direction,
        reason=reason,
        provenance=_provenance(),
        latest_close=Decimal(close) if coherent else None,
        supertrend=Decimal(level) if coherent else None,
        final_upper_band=Decimal("130") if coherent else None,
        final_lower_band=Decimal("100") if coherent else None,
        atr=Decimal("5") if coherent else None,
        atr_period=SUPERTREND_ATR_PERIOD,
        multiplier=SUPERTREND_MULTIPLIER,
        flipped_on_latest=False,
        is_coherent=coherent,
        version=SUPERTREND_VERSION,
    )


def _rsi(
    value: str | None = "65",
    *,
    reason: DailyChartEvidenceReason | None = None,
) -> RsiReviewEvidence:
    return RsiReviewEvidence(
        value=Decimal(value) if value is not None else None,
        reason=(
            reason
            or (
                DailyChartEvidenceReason.OK
                if value is not None
                else DailyChartEvidenceReason.INSUFFICIENT_HISTORY
            )
        ),
        provenance=_provenance(),
        period=14,
        is_coherent=value is not None,
    )


def _volume(*, available: bool = True) -> VolumeReviewEvidence:
    return VolumeReviewEvidence(
        latest_volume=2000 if available else None,
        volume_ma=Decimal("1000") if available else None,
        reason=(
            DailyChartEvidenceReason.OK
            if available
            else DailyChartEvidenceReason.INSUFFICIENT_HISTORY
        ),
        provenance=_provenance(),
        period=20,
        is_coherent=available,
    )


def _history_high(
    *,
    new_high: bool = False,
    available: bool = True,
) -> AthRollingHighEvidence:
    return AthRollingHighEvidence(
        latest_high=Decimal("125") if available else None,
        latest_close=Decimal("120") if available else None,
        prior_available_history_high=Decimal("124") if available else None,
        prior_available_history_high_session=AS_OF if available else None,
        latest_high_exceeds_prior_history=new_high if available else None,
        latest_close_above_prior_history_high=False if available else None,
        rolling_sessions=50,
        prior_rolling_high=Decimal("124") if available else None,
        prior_rolling_high_session=AS_OF if available else None,
        latest_high_exceeds_prior_rolling=new_high if available else None,
        latest_close_above_prior_rolling_high=False if available else None,
        adjusted_history=False if available else None,
        reason=(
            DailyChartEvidenceReason.OK
            if available
            else DailyChartEvidenceReason.INSUFFICIENT_HISTORY
        ),
        provenance=_provenance(),
        is_coherent=available,
    )


def _position(*, pnl_pct: str = "12.5") -> PortfolioDailyReviewContext:
    return PortfolioDailyReviewContext(
        quantity=10,
        avg_price=Decimal("100"),
        current_price=Decimal("120"),
        pnl=Decimal("200"),
        pnl_pct=Decimal(pnl_pct),
    )


def _resolve(
    *,
    supertrend: SuperTrendEvidence,
    rsi: RsiReviewEvidence | None = None,
    volume: VolumeReviewEvidence | None = None,
    high: AthRollingHighEvidence | None = None,
    position: PortfolioDailyReviewContext | None = None,
):
    return PortfolioDailyReviewAdapter().resolve(
        supertrend=supertrend,
        rsi=rsi or _rsi(),
        volume=volume or _volume(),
        history_high=high or _history_high(),
        position=position or _position(),
    )


def test_hold_strong_requires_bullish_supertrend_and_new_available_history_high() -> None:
    result = _resolve(
        supertrend=_supertrend(SuperTrendDirection.BULLISH),
        high=_history_high(new_high=True),
    )

    assert result.methodology_version == PORTFOLIO_DAILY_REVIEW_VERSION
    assert result.review_status is PortfolioDailyReviewStatus.HOLD_STRONG
    assert result.trailing_structure_level == Decimal("100")
    assert PortfolioDailyReviewReason.NEW_AVAILABLE_HISTORY_HIGH in result.reason_codes
    assert "Targets deferred" in str(result.guidance)


def test_hold_uses_bullish_supertrend_without_available_history_breakout() -> None:
    result = _resolve(supertrend=_supertrend(SuperTrendDirection.BULLISH))

    assert result.review_status is PortfolioDailyReviewStatus.HOLD
    assert PortfolioDailyReviewReason.BULLISH_TRAILING_STRUCTURE_INTACT in result.reason_codes
    assert PortfolioDailyReviewReason.NEW_AVAILABLE_HISTORY_HIGH not in result.reason_codes


def test_bearish_supertrend_reviews_without_exit_risk() -> None:
    result = _resolve(
        supertrend=_supertrend(SuperTrendDirection.BEARISH, close="90", level="100"),
        position=_position(pnl_pct="-8"),
    )

    assert result.review_status is PortfolioDailyReviewStatus.REVIEW_HOLD_TIGHT
    assert result.trailing_structure_level is None
    assert PortfolioDailyReviewReason.BEARISH_TRAILING_STRUCTURE_REVIEW in result.reason_codes
    assert PortfolioDailyReviewReason.EXIT_RISK_DEFERRED in result.reason_codes
    assert "does not create EXIT_RISK" in str(result.guidance)


def test_stale_or_unavailable_evidence_returns_null_review_status() -> None:
    stale = _resolve(
        supertrend=_supertrend(
            None,
            reason=DailyChartEvidenceReason.EXPECTED_SESSION_MISMATCH,
            coherent=False,
        )
    )
    unavailable = _resolve(
        supertrend=_supertrend(
            None,
            reason=DailyChartEvidenceReason.INSUFFICIENT_HISTORY,
            coherent=False,
        )
    )

    assert stale.review_status is None
    assert (
        stale.availability_reason
        is PortfolioDailyReviewReason.EVIDENCE_STALE_OR_SESSION_MISMATCH
    )
    assert unavailable.review_status is None
    assert (
        unavailable.availability_reason
        is PortfolioDailyReviewReason.EVIDENCE_UNAVAILABLE_OR_INSUFFICIENT_HISTORY
    )


def test_context_evidence_unavailable_does_not_block_supertrend_status() -> None:
    bullish_without_high = _resolve(
        supertrend=_supertrend(SuperTrendDirection.BULLISH),
        high=_history_high(available=False),
    )
    bearish_without_high = _resolve(
        supertrend=_supertrend(SuperTrendDirection.BEARISH, close="90", level="100"),
        high=_history_high(available=False),
    )
    bullish_without_rsi = _resolve(
        supertrend=_supertrend(SuperTrendDirection.BULLISH),
        rsi=_rsi(None),
    )
    bullish_without_volume = _resolve(
        supertrend=_supertrend(SuperTrendDirection.BULLISH),
        volume=_volume(available=False),
    )

    assert bullish_without_high.review_status is PortfolioDailyReviewStatus.HOLD
    assert (
        bearish_without_high.review_status
        is PortfolioDailyReviewStatus.REVIEW_HOLD_TIGHT
    )
    assert bullish_without_rsi.review_status is PortfolioDailyReviewStatus.HOLD
    assert bullish_without_volume.review_status is PortfolioDailyReviewStatus.HOLD


def test_position_profit_rsi_and_volume_do_not_override_review_status() -> None:
    bearish_winner = _resolve(
        supertrend=_supertrend(SuperTrendDirection.BEARISH, close="90", level="100"),
        rsi=_rsi("82"),
        volume=_volume(),
        high=_history_high(new_high=True),
        position=_position(pnl_pct="68"),
    )
    bullish_loser = _resolve(
        supertrend=_supertrend(SuperTrendDirection.BULLISH),
        rsi=_rsi("35"),
        volume=_volume(),
        high=_history_high(new_high=False),
        position=_position(pnl_pct="-20"),
    )

    assert bearish_winner.review_status is PortfolioDailyReviewStatus.REVIEW_HOLD_TIGHT
    assert bullish_loser.review_status is PortfolioDailyReviewStatus.HOLD
    assert PortfolioDailyReviewReason.VOLUME_CONTEXT_ONLY in bearish_winner.reason_codes
    assert PortfolioDailyReviewReason.LOSS_CONTEXT_REVIEW_DISCIPLINE in bullish_loser.reason_codes
    assert "RSI alone" not in str(bearish_winner.guidance)
