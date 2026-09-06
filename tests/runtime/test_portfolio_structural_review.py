"""Portfolio Intelligence V2 structural review engine tests.

Covers: Support selection, duplicate-level collapse, stale-level rejection,
role reversal (broken support -> reclaim trigger), resistance ordering,
null targets at ATH, structural invalidation / EXIT_RISK, historical as_of /
future leakage, deterministic rerun, stale/incoherent evidence, provenance.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.portfolio.daily_chart_evidence import (
    DailyChartEvidenceProvenance,
    DailyChartEvidenceReason,
    SuperTrendDirection,
    SuperTrendEvidence,
)
from athena.portfolio.structural_review import (
    PortfolioStructuralReviewEngine,
    PortfolioStructuralReviewReason,
    StructuralZoneRole,
)

TZ = ZoneInfo("UTC")
START = datetime(2025, 1, 1, tzinfo=timezone.utc)
INSTRUMENT = "NSE:TEST"


def _series(
    length: int,
    base: int = 100,
    overrides: dict[int, dict[str, int]] | None = None,
    instrument_id: str = INSTRUMENT,
    timeframe: Timeframe = Timeframe.D1,
) -> list[Candle]:
    overrides = overrides or {}
    candles = []
    for i in range(length):
        o = overrides.get(i, {})
        close = Decimal(str(o.get("close", base)))
        low = Decimal(str(o.get("low", int(close) - 1)))
        high = Decimal(str(o.get("high", int(close) + 1)))
        candles.append(
            Candle(
                instrument_id=instrument_id,
                timeframe=timeframe,
                ts_open=START + timedelta(days=i),
                open=close,
                high=high,
                low=low,
                close=close,
                volume=1000,
                source="test",
                adjusted=True,
            )
        )
    return candles


def _supertrend(
    *,
    direction: SuperTrendDirection | None,
    value: Decimal | int | None,
    is_coherent: bool = True,
    latest_session: datetime | None = None,
) -> SuperTrendEvidence:
    provenance = DailyChartEvidenceProvenance(
        instrument_id=INSTRUMENT,
        timeframe=Timeframe.D1,
        as_of=latest_session,
        accepted_price_as_of=latest_session,
        expected_analysis_as_of=latest_session,
        first_d1_session=None,
        latest_d1_session=latest_session,
        candles_used=0,
        source_count=0,
    )
    return SuperTrendEvidence(
        direction=direction,
        reason=DailyChartEvidenceReason.OK if is_coherent else DailyChartEvidenceReason.D1_EVIDENCE_UNAVAILABLE,
        provenance=provenance,
        latest_close=None,
        supertrend=Decimal(value) if value is not None else None,
        final_upper_band=None,
        final_lower_band=None,
        atr=None,
        atr_period=10,
        multiplier=Decimal("3"),
        flipped_on_latest=False,
        is_coherent=is_coherent,
    )


def _resolve(
    candles: list[Candle],
    *,
    as_of: datetime,
    current_price: Decimal | int,
    supertrend: SuperTrendEvidence | None = None,
    trend_label: str | None = "uptrend",
    daily_review_status: str | None = "HOLD",
):
    engine = PortfolioStructuralReviewEngine()
    return engine.resolve(
        instrument_id=INSTRUMENT,
        candles=candles,
        accepted_price_as_of=as_of,
        expected_analysis_as_of=as_of,
        market_timezone=TZ,
        supertrend=supertrend or _supertrend(direction=SuperTrendDirection.BULLISH, value=90, latest_session=as_of),
        current_price=Decimal(current_price),
        trend_label=trend_label,
        daily_review_status=daily_review_status,
    )


def test_support_1_selects_nearest_swing_low_below_price() -> None:
    overrides = {50: {"low": 80, "high": 82, "close": 81}}
    candles = _series(120, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    result = _resolve(candles, as_of=as_of, current_price=100)
    assert result.is_coherent
    assert result.support_1 is not None
    assert result.support_1.lower == Decimal(80)
    assert result.support_1.upper == Decimal(80)
    assert PortfolioStructuralReviewReason.SUPPORT_1_SELECTED in result.reason_codes


def test_duplicate_nearby_lows_collapse_into_one_zone() -> None:
    overrides = {
        40: {"low": 80, "high": 82, "close": 81},
        70: {"low": 81, "high": 83, "close": 82},
    }
    candles = _series(120, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    result = _resolve(candles, as_of=as_of, current_price=100)
    assert result.support_1 is not None
    assert result.support_1.touches == 2
    assert result.support_1.lower == Decimal(80)
    assert result.support_1.upper == Decimal(81)


def test_stale_low_beyond_staleness_window_is_rejected() -> None:
    # A deep swing low 200 sessions before the latest session must be
    # excluded — "prefer more recent structurally relevant levels."
    overrides = {10: {"low": 50, "high": 52, "close": 51}}
    candles = _series(260, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    result = _resolve(candles, as_of=as_of, current_price=100)
    # The stale zone at 50 must not appear as support_1 or major_support.
    if result.support_1 is not None:
        assert result.support_1.lower != Decimal(50)
    if result.major_support is not None:
        assert result.major_support.lower != Decimal(50)


def test_broken_support_becomes_reclaim_review_trigger_not_a_target() -> None:
    # A former support zone at 95 (recently touched) that price has since
    # fallen below must surface as a reclaim trigger, never as a target
    # (role reversal — it is now overhead, not underlying, structure).
    overrides = {90: {"low": 95, "high": 97, "close": 96}}
    candles = _series(100, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    result = _resolve(candles, as_of=as_of, current_price=90)
    assert result.review_trigger is not None
    assert result.review_trigger.lower == Decimal(95)
    assert PortfolioStructuralReviewReason.REVIEW_TRIGGER_RECLAIM in result.reason_codes
    assert result.target_1 is None or result.target_1.lower != Decimal(95)


def test_resistance_targets_are_ordered_ascending() -> None:
    overrides = {
        30: {"low": 118, "high": 120, "close": 119},
        60: {"low": 138, "high": 140, "close": 139},
        90: {"low": 158, "high": 160, "close": 159},
    }
    candles = _series(180, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    result = _resolve(candles, as_of=as_of, current_price=100)
    assert result.target_1 is not None
    assert result.target_2 is not None
    assert result.target_3 is not None
    assert result.target_1.upper < result.target_2.lower
    assert result.target_2.upper < result.target_3.lower
    assert result.target_1.upper == Decimal(120)
    assert result.target_3.upper == Decimal(160)


def test_no_overhead_resistance_leaves_targets_null_at_ath() -> None:
    # Monotonically rising series: current price is the all-time high, so
    # there is no defensible overhead resistance — targets must stay null,
    # never synthetic.
    overrides = {i: {"low": 100 + i - 1, "high": 100 + i + 1, "close": 100 + i} for i in range(0, 150, 5)}
    candles = _series(150, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    result = _resolve(candles, as_of=as_of, current_price=250)
    assert result.target_1 is None
    assert result.target_2 is None
    assert result.target_3 is None
    assert PortfolioStructuralReviewReason.NO_OVERHEAD_RESISTANCE in result.reason_codes
    assert "no confirmed overhead resistance" in (result.guidance or "")


def test_major_support_prefers_nearer_of_structure_and_supertrend() -> None:
    # Both a deeper structural low (70) and the SuperTrend band (~85) are
    # valid tiers below Support 1 (90) — the nearer one is the more
    # immediately relevant risk threshold and must win.
    overrides = {
        50: {"low": 90, "high": 92, "close": 91},  # support_1 candidate
        20: {"low": 70, "high": 72, "close": 71},  # deeper structural low
    }
    candles = _series(150, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    st = _supertrend(direction=SuperTrendDirection.BULLISH, value=85, latest_session=as_of)
    result = _resolve(candles, as_of=as_of, current_price=100, supertrend=st)
    assert result.support_1 is not None and result.support_1.lower == Decimal(90)
    assert result.major_support is not None
    assert result.major_support.upper < Decimal(90)
    assert result.major_support_source == "supertrend"


def test_major_support_prefers_structure_when_nearer_than_supertrend() -> None:
    # Now the structural tier (85-87) sits nearer to Support 1 than the
    # deeper SuperTrend band (60) — structure must win this time.
    overrides = {
        50: {"low": 95, "high": 97, "close": 96},  # support_1
        30: {"low": 86, "high": 88, "close": 87},  # nearer structural tier
    }
    candles = _series(150, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    st = _supertrend(direction=SuperTrendDirection.BULLISH, value=60, latest_session=as_of)
    result = _resolve(candles, as_of=as_of, current_price=100, supertrend=st)
    assert result.support_1 is not None and result.support_1.lower == Decimal(95)
    assert result.major_support is not None
    assert result.major_support.lower == Decimal(86)
    assert result.major_support_source == "structure"


def test_major_support_falls_back_to_supertrend_when_no_deeper_structure() -> None:
    overrides = {50: {"low": 90, "high": 92, "close": 91}}
    candles = _series(150, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    st = _supertrend(direction=SuperTrendDirection.BULLISH, value=85, latest_session=as_of)
    result = _resolve(candles, as_of=as_of, current_price=100, supertrend=st)
    assert result.major_support is not None
    assert result.major_support_source == "supertrend"
    assert PortfolioStructuralReviewReason.MAJOR_SUPPORT_FROM_SUPERTREND in result.reason_codes


def test_exit_risk_requires_bearish_supertrend_and_price_below_major_support() -> None:
    overrides = {20: {"low": 70, "high": 72, "close": 71}}
    candles = _series(150, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    bearish = _supertrend(direction=SuperTrendDirection.BEARISH, value=95, latest_session=as_of)
    result = _resolve(
        candles,
        as_of=as_of,
        current_price=65,
        supertrend=bearish,
        daily_review_status="REVIEW_HOLD_TIGHT",
    )
    assert result.major_support is not None
    assert result.exit_risk is True
    assert PortfolioStructuralReviewReason.EXIT_RISK_STRUCTURAL_INVALIDATION in result.reason_codes
    assert "exit risk" in (result.guidance or "").lower()
    assert "decisively" not in (result.guidance or "").lower()
    assert "no reclaim" not in (result.guidance or "").lower()


def test_major_support_fallback_picks_nearest_not_shallowest_zone() -> None:
    # Regression test for a genuine correctness bug found by the historical
    # PIT robustness replay: when no support zone is currently below price
    # (every known zone now sits above it), Major Support must anchor to
    # whichever zone is NEAREST to current price by absolute distance — not
    # "the shallowest zone recorded across the whole lookback," which can be
    # an arbitrary, far-away zone from an earlier, unrelated (much higher)
    # price regime. Two regimes: an early, higher-priced regime (~220, with
    # its own genuine swing low at 215) the stock has since fallen well away
    # from, and a more recent, lower regime (~112, with a genuine swing low
    # at 108) much closer to the current crashed price of 100.
    early_regime = _series(30, base=220, overrides={15: {"low": 215, "high": 224, "close": 220}})
    recent_regime = _series(90, base=112, overrides={45: {"low": 108, "high": 114, "close": 112}})
    candles = [
        *early_regime,
        *[
            Candle(
                instrument_id=c.instrument_id,
                timeframe=c.timeframe,
                ts_open=c.ts_open + timedelta(days=30),
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
                source=c.source,
                adjusted=c.adjusted,
            )
            for c in recent_regime
        ],
    ]
    as_of = candles[-1].ts_open
    bearish = _supertrend(direction=SuperTrendDirection.BEARISH, value=None, latest_session=as_of)
    # Current price (100) has fallen below both regimes' swing lows (108 and
    # 215), so support_1 is unavailable and the fallback path is exercised.
    result = _resolve(candles, as_of=as_of, current_price=100, supertrend=bearish)
    assert result.support_1 is None
    assert result.major_support is not None
    assert result.major_support.lower == Decimal(108)
    assert result.major_support.upper != Decimal(215)


def test_exit_risk_not_triggered_when_price_below_supertrend_only() -> None:
    # Price below SuperTrend alone (REVIEW_HOLD_TIGHT territory) must never
    # be EXIT_RISK on its own — it requires major structural invalidation.
    candles = _series(150, base=100)
    as_of = candles[-1].ts_open
    bearish = _supertrend(direction=SuperTrendDirection.BEARISH, value=95, latest_session=as_of)
    result = _resolve(candles, as_of=as_of, current_price=98, supertrend=bearish)
    assert result.exit_risk is False
    assert PortfolioStructuralReviewReason.EXIT_RISK_NOT_TRIGGERED in result.reason_codes


def test_exit_risk_false_when_supertrend_bullish_even_below_major_support() -> None:
    overrides = {20: {"low": 70, "high": 72, "close": 71}}
    candles = _series(150, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    bullish = _supertrend(direction=SuperTrendDirection.BULLISH, value=95, latest_session=as_of)
    result = _resolve(candles, as_of=as_of, current_price=65, supertrend=bullish)
    assert result.exit_risk is False


def test_future_candles_never_leak_into_historical_as_of_result() -> None:
    overrides = {50: {"low": 80, "high": 82, "close": 81}}
    candles = _series(120, base=100, overrides=overrides)
    as_of = candles[100].ts_open
    bounded_result = _resolve(candles[:101], as_of=as_of, current_price=100)
    # Inject a dramatic future swing after the as_of cutoff.
    future_overrides = dict(overrides)
    future_overrides[110] = {"low": 10, "high": 12, "close": 11}
    full_candles = _series(120, base=100, overrides=future_overrides)
    leaked_result = _resolve(full_candles, as_of=as_of, current_price=100)
    assert bounded_result.support_1 == leaked_result.support_1
    assert bounded_result.major_support == leaked_result.major_support


def test_deterministic_rerun_produces_identical_result() -> None:
    overrides = {
        30: {"low": 118, "high": 120, "close": 119},
        50: {"low": 80, "high": 82, "close": 81},
    }
    candles = _series(150, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    first = _resolve(candles, as_of=as_of, current_price=100)
    second = _resolve(candles, as_of=as_of, current_price=100)
    assert first == second


def test_incoherent_instrument_id_returns_incoherent_result() -> None:
    candles = _series(150, base=100, instrument_id="NSE:OTHER")
    as_of = candles[-1].ts_open
    result = _resolve(candles, as_of=as_of, current_price=100)
    assert result.is_coherent is False
    assert PortfolioStructuralReviewReason.EVIDENCE_INCOHERENT in result.reason_codes
    assert result.support_1 is None
    assert result.guidance is None


def test_empty_candles_returns_evidence_unavailable() -> None:
    as_of = START
    result = _resolve([], as_of=as_of, current_price=100)
    assert result.is_coherent is False
    assert PortfolioStructuralReviewReason.EVIDENCE_UNAVAILABLE in result.reason_codes


def test_current_price_none_returns_incoherent_result() -> None:
    candles = _series(150, base=100)
    as_of = candles[-1].ts_open
    engine = PortfolioStructuralReviewEngine()
    result = engine.resolve(
        instrument_id=INSTRUMENT,
        candles=candles,
        accepted_price_as_of=as_of,
        expected_analysis_as_of=as_of,
        market_timezone=TZ,
        supertrend=_supertrend(direction=SuperTrendDirection.BULLISH, value=90, latest_session=as_of),
        current_price=None,
        trend_label="uptrend",
        daily_review_status="HOLD",
    )
    assert result.is_coherent is False


def test_insufficient_history_returns_reason() -> None:
    candles = _series(4, base=100)
    as_of = candles[-1].ts_open
    result = _resolve(candles, as_of=as_of, current_price=100)
    assert result.is_coherent is False
    assert PortfolioStructuralReviewReason.INSUFFICIENT_HISTORY in result.reason_codes


def test_provenance_reports_instrument_and_methodology_version() -> None:
    candles = _series(150, base=100)
    as_of = candles[-1].ts_open
    result = _resolve(candles, as_of=as_of, current_price=100)
    assert result.provenance.instrument_id == INSTRUMENT
    assert result.provenance.methodology_version == "portfolio-structural-review-v1"
    assert result.provenance.as_of == as_of
    assert result.provenance.evidence_as_of == candles[-1].ts_open
    assert result.provenance.candles_used == len(candles)


def test_zone_role_labels_are_correct() -> None:
    overrides = {
        50: {"low": 80, "high": 82, "close": 81},
        90: {"low": 118, "high": 120, "close": 119},
    }
    candles = _series(150, base=100, overrides=overrides)
    as_of = candles[-1].ts_open
    result = _resolve(candles, as_of=as_of, current_price=100)
    assert result.support_1 is not None
    assert result.support_1.role is StructuralZoneRole.SUPPORT
    assert result.target_1 is not None
    assert result.target_1.role is StructuralZoneRole.RESISTANCE
