"""Portfolio Structural Review engine (Portfolio Intelligence V2).

Separate, additive structural intelligence layer over persisted D1 evidence.
Does not redefine Portfolio Status, Conviction, D1 Trend, OR Setup, Daily
Review v0, Next Action, TradePlan, or SuperTrend 10,3 — those stay exactly as
V1 froze them. This module only adds owner-facing structural Support /
Major Support (invalidation) / Review Trigger / Targets / EXIT_RISK,
derived from bounded, point-in-time-safe candidate generation followed by a
deliberately separate significance-based selection step (PS-P10C.1 failed
because it exposed mechanical candidates directly; this engine never does).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum, unique
from zoneinfo import ZoneInfo

from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.portfolio.daily_chart_evidence import SuperTrendDirection, SuperTrendEvidence

PORTFOLIO_STRUCTURAL_REVIEW_VERSION = "portfolio-structural-review-v1"

# Bounded lookback: only swing points from roughly the last year of D1
# sessions are eligible candidates — "prefer more recent structurally
# relevant levels over ancient irrelevant levels."
STRUCTURAL_LOOKBACK_SESSIONS = 252
# Fractal half-window: a candle is a swing point only if it is the extreme
# among this many sessions on both sides, and only once those confirming
# sessions actually exist in the point-in-time-bounded set (never a lookahead).
SWING_HALF_WINDOW = 3
# Two swing points within this fraction of each other collapse into one
# zone, avoiding dense near-duplicate levels.
ZONE_MERGE_TOLERANCE_PCT = Decimal("0.015")
# A zone must have been touched within this many sessions to still be
# considered "active" rather than stale/irrelevant.
ZONE_STALENESS_SESSIONS = 180
# A former support zone is treated as "recently lost" (reclaim-trigger
# territory) only if it was active this recently.
RECLAIM_LOOKBACK_SESSIONS = 60


@unique
class StructuralZoneRole(str, Enum):
    SUPPORT = "SUPPORT"
    RESISTANCE = "RESISTANCE"


@unique
class PortfolioStructuralReviewReason(str, Enum):
    EVIDENCE_UNAVAILABLE = "STRUCTURAL_EVIDENCE_UNAVAILABLE"
    EVIDENCE_INCOHERENT = "STRUCTURAL_EVIDENCE_INCOHERENT"
    INSUFFICIENT_HISTORY = "STRUCTURAL_INSUFFICIENT_HISTORY"
    SUPPORT_1_SELECTED = "SUPPORT_1_SELECTED"
    SUPPORT_1_UNAVAILABLE = "SUPPORT_1_UNAVAILABLE"
    MAJOR_SUPPORT_FROM_SUPERTREND = "MAJOR_SUPPORT_FROM_SUPERTREND"
    MAJOR_SUPPORT_FROM_STRUCTURE = "MAJOR_SUPPORT_FROM_STRUCTURE"
    MAJOR_SUPPORT_UNAVAILABLE = "MAJOR_SUPPORT_UNAVAILABLE"
    TARGET_1_SELECTED = "TARGET_1_SELECTED"
    TARGET_2_SELECTED = "TARGET_2_SELECTED"
    TARGET_3_SELECTED = "TARGET_3_SELECTED"
    NO_OVERHEAD_RESISTANCE = "NO_OVERHEAD_RESISTANCE"
    REVIEW_TRIGGER_RECLAIM = "REVIEW_TRIGGER_RECLAIM"
    REVIEW_TRIGGER_BREAKOUT = "REVIEW_TRIGGER_BREAKOUT"
    REVIEW_TRIGGER_UNAVAILABLE = "REVIEW_TRIGGER_UNAVAILABLE"
    EXIT_RISK_STRUCTURAL_INVALIDATION = "EXIT_RISK_STRUCTURAL_INVALIDATION"
    EXIT_RISK_NOT_TRIGGERED = "EXIT_RISK_NOT_TRIGGERED"


@dataclass(frozen=True, slots=True)
class StructuralZone:
    """One owner-facing structural level, expressed as a zone (never a
    single false-precise price when the evidence represents an area)."""

    lower: Decimal
    upper: Decimal
    role: StructuralZoneRole
    touches: int
    source_sessions: tuple[datetime, ...]
    most_recent_session: datetime

    def midpoint(self) -> Decimal:
        return (self.lower + self.upper) / Decimal(2)


@dataclass(frozen=True, slots=True)
class PortfolioStructuralReviewProvenance:
    instrument_id: str
    as_of: datetime | None
    evidence_as_of: datetime | None
    candles_used: int
    methodology_version: str = PORTFOLIO_STRUCTURAL_REVIEW_VERSION


@dataclass(frozen=True, slots=True)
class PortfolioStructuralReviewResult:
    is_coherent: bool
    reason_codes: tuple[PortfolioStructuralReviewReason, ...]
    support_1: StructuralZone | None
    major_support: StructuralZone | None
    major_support_source: str | None
    review_trigger: StructuralZone | None
    target_1: StructuralZone | None
    target_2: StructuralZone | None
    target_3: StructuralZone | None
    exit_risk: bool
    guidance: str | None
    provenance: PortfolioStructuralReviewProvenance
    methodology_version: str = PORTFOLIO_STRUCTURAL_REVIEW_VERSION


@dataclass(frozen=True, slots=True)
class _PreparedD1:
    candles: tuple[Candle, ...]
    is_coherent: bool
    reason: PortfolioStructuralReviewReason


class PortfolioStructuralReviewEngine:
    """Deterministic, point-in-time-safe structural level selection.

    Two-stage design (never expose mechanical candidates directly):
    1. Candidate generation — confirmed D1 swing highs/lows within a bounded
       recent lookback, clustered into non-overlapping zones.
    2. Structural selection — the owner-facing Support 1 / Major Support /
       Review Trigger / Target 1-3 / EXIT_RISK are chosen from those zones
       by proximity, recency, and touch count only; dense, stale, or
       already-consumed candidates are never surfaced.
    """

    def resolve(
        self,
        *,
        instrument_id: str,
        candles: Sequence[Candle],
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
        supertrend: SuperTrendEvidence,
        current_price: Decimal | None,
        trend_label: str | None,
        daily_review_status: str | None,
    ) -> PortfolioStructuralReviewResult:
        prepared = self._prepare_d1(
            instrument_id=instrument_id,
            candles=candles,
            accepted_price_as_of=accepted_price_as_of,
            expected_analysis_as_of=expected_analysis_as_of,
            market_timezone=market_timezone,
        )
        as_of = expected_analysis_as_of or accepted_price_as_of
        evidence_as_of = prepared.candles[-1].ts_open if prepared.candles else None
        provenance = PortfolioStructuralReviewProvenance(
            instrument_id=instrument_id,
            as_of=as_of,
            evidence_as_of=evidence_as_of,
            candles_used=len(prepared.candles),
        )

        if not prepared.is_coherent or current_price is None:
            reason = prepared.reason if not prepared.is_coherent else (
                PortfolioStructuralReviewReason.EVIDENCE_UNAVAILABLE
            )
            return self._empty_result(reason, provenance)

        bounded = list(prepared.candles[-STRUCTURAL_LOOKBACK_SESSIONS:])
        if len(bounded) < 2 * SWING_HALF_WINDOW + 1:
            return self._empty_result(
                PortfolioStructuralReviewReason.INSUFFICIENT_HISTORY, provenance
            )

        swing_lows = _confirmed_swing_lows(bounded)
        swing_highs = _confirmed_swing_highs(bounded)
        support_zones = _cluster_zones(swing_lows, StructuralZoneRole.SUPPORT)
        resistance_zones = _cluster_zones(swing_highs, StructuralZoneRole.RESISTANCE)

        latest_session = bounded[-1].ts_open
        support_zones = _reject_stale(support_zones, latest_session)
        resistance_zones = _reject_stale(resistance_zones, latest_session)

        reasons: list[PortfolioStructuralReviewReason] = []

        below = sorted(
            (z for z in support_zones if z.upper < current_price),
            key=lambda z: z.upper,
            reverse=True,
        )
        above = sorted(
            (z for z in resistance_zones if z.lower > current_price),
            key=lambda z: z.lower,
        )

        support_1 = below[0] if below else None
        if support_1 is not None:
            reasons.append(PortfolioStructuralReviewReason.SUPPORT_1_SELECTED)
        else:
            reasons.append(PortfolioStructuralReviewReason.SUPPORT_1_UNAVAILABLE)

        major_support, major_support_source = self._select_major_support(
            support_zones=support_zones,
            support_1=support_1,
            supertrend=supertrend,
            current_price=current_price,
        )
        if major_support is not None:
            reasons.append(
                PortfolioStructuralReviewReason.MAJOR_SUPPORT_FROM_SUPERTREND
                if major_support_source == "supertrend"
                else PortfolioStructuralReviewReason.MAJOR_SUPPORT_FROM_STRUCTURE
            )
        else:
            reasons.append(PortfolioStructuralReviewReason.MAJOR_SUPPORT_UNAVAILABLE)

        target_1 = above[0] if len(above) > 0 else None
        target_2 = above[1] if len(above) > 1 else None
        target_3 = above[2] if len(above) > 2 else None
        for target, code in (
            (target_1, PortfolioStructuralReviewReason.TARGET_1_SELECTED),
            (target_2, PortfolioStructuralReviewReason.TARGET_2_SELECTED),
            (target_3, PortfolioStructuralReviewReason.TARGET_3_SELECTED),
        ):
            if target is not None:
                reasons.append(code)
        if target_1 is None:
            reasons.append(PortfolioStructuralReviewReason.NO_OVERHEAD_RESISTANCE)

        review_trigger, trigger_is_reclaim = self._select_review_trigger(
            support_zones=support_zones,
            target_1=target_1,
            current_price=current_price,
            latest_session=latest_session,
        )
        if review_trigger is not None:
            reasons.append(
                PortfolioStructuralReviewReason.REVIEW_TRIGGER_RECLAIM
                if trigger_is_reclaim
                else PortfolioStructuralReviewReason.REVIEW_TRIGGER_BREAKOUT
            )
        else:
            reasons.append(PortfolioStructuralReviewReason.REVIEW_TRIGGER_UNAVAILABLE)

        exit_risk = self._exit_risk(
            major_support=major_support,
            supertrend=supertrend,
            current_price=current_price,
        )
        reasons.append(
            PortfolioStructuralReviewReason.EXIT_RISK_STRUCTURAL_INVALIDATION
            if exit_risk
            else PortfolioStructuralReviewReason.EXIT_RISK_NOT_TRIGGERED
        )

        guidance = _compose_guidance(
            trend_label=trend_label,
            daily_review_status=daily_review_status,
            supertrend=supertrend,
            support_1=support_1,
            major_support=major_support,
            review_trigger=review_trigger,
            trigger_is_reclaim=trigger_is_reclaim,
            target_1=target_1,
            exit_risk=exit_risk,
        )

        return PortfolioStructuralReviewResult(
            is_coherent=True,
            reason_codes=tuple(dict.fromkeys(reasons)),
            support_1=support_1,
            major_support=major_support,
            major_support_source=major_support_source,
            review_trigger=review_trigger,
            target_1=target_1,
            target_2=target_2,
            target_3=target_3,
            exit_risk=exit_risk,
            guidance=guidance,
            provenance=provenance,
        )

    @staticmethod
    def _select_major_support(
        *,
        support_zones: Sequence[StructuralZone],
        support_1: StructuralZone | None,
        supertrend: SuperTrendEvidence,
        current_price: Decimal,
    ) -> tuple[StructuralZone | None, str | None]:
        supertrend_zone: StructuralZone | None = None
        if (
            supertrend.is_coherent
            and supertrend.direction is SuperTrendDirection.BULLISH
            and supertrend.supertrend is not None
            and supertrend.supertrend < current_price
        ):
            band = supertrend.supertrend * ZONE_MERGE_TOLERANCE_PCT
            supertrend_zone = StructuralZone(
                lower=supertrend.supertrend - band,
                upper=supertrend.supertrend + band,
                role=StructuralZoneRole.SUPPORT,
                touches=1,
                source_sessions=(supertrend.provenance.latest_d1_session,)
                if supertrend.provenance.latest_d1_session
                else (),
                most_recent_session=supertrend.provenance.latest_d1_session
                or _epoch_placeholder(),
            )

        # The structural tier is found by POSITION in the full zone
        # ordering (deliberately independent of whether current price has
        # ALSO since fallen beneath it — that is exactly the condition
        # EXIT_RISK checks for, never a disqualifier here). Using a price
        # threshold instead would make it mathematically impossible for
        # price to ever be assessed as having broken below Major Support,
        # since Major Support would always be defined as "deeper than
        # Support 1, which is itself already below price."
        all_support_sorted = sorted(support_zones, key=lambda z: z.upper, reverse=True)
        deeper_structural: StructuralZone | None = None
        if support_1 is not None and support_1 in all_support_sorted:
            idx = all_support_sorted.index(support_1)
            if idx + 1 < len(all_support_sorted):
                deeper_structural = all_support_sorted[idx + 1]
        elif support_1 is None and all_support_sorted:
            # No currently-active support at all (price already fell
            # through every known zone) — the shallowest known zone is the
            # one price broke, so it anchors Major Support.
            deeper_structural = all_support_sorted[0]

        ceiling = support_1.lower if support_1 is not None else current_price
        st_candidate = (
            supertrend_zone if supertrend_zone is not None and supertrend_zone.upper < ceiling else None
        )
        candidates = [z for z in (deeper_structural, st_candidate) if z is not None]
        if not candidates:
            return None, None
        # Nearest deeper tier below Support 1, not the single deepest zone
        # ever recorded — matches the golden dataset's "next tier down"
        # pattern (e.g. Support 1 2750-2800, Major Support 2560-2600) and
        # represents the more immediately relevant risk threshold.
        nearest = max(candidates, key=lambda z: z.upper)
        source = "supertrend" if nearest is st_candidate else "structure"
        return nearest, source

    @staticmethod
    def _select_review_trigger(
        *,
        support_zones: Sequence[StructuralZone],
        target_1: StructuralZone | None,
        current_price: Decimal,
        latest_session: datetime,
    ) -> tuple[StructuralZone | None, bool]:
        lost = [
            z
            for z in support_zones
            if z.lower > current_price
            and _sessions_between(z.most_recent_session, latest_session)
            <= RECLAIM_LOOKBACK_SESSIONS
        ]
        if lost:
            nearest_lost = min(lost, key=lambda z: z.lower)
            return nearest_lost, True
        if target_1 is not None:
            return target_1, False
        return None, False

    @staticmethod
    def _exit_risk(
        *,
        major_support: StructuralZone | None,
        supertrend: SuperTrendEvidence,
        current_price: Decimal,
    ) -> bool:
        if major_support is None:
            return False
        if not supertrend.is_coherent or supertrend.direction is not SuperTrendDirection.BEARISH:
            return False
        return current_price < major_support.lower

    def _empty_result(
        self,
        reason: PortfolioStructuralReviewReason,
        provenance: PortfolioStructuralReviewProvenance,
    ) -> PortfolioStructuralReviewResult:
        return PortfolioStructuralReviewResult(
            is_coherent=False,
            reason_codes=(reason,),
            support_1=None,
            major_support=None,
            major_support_source=None,
            review_trigger=None,
            target_1=None,
            target_2=None,
            target_3=None,
            exit_risk=False,
            guidance=None,
            provenance=provenance,
        )

    def _prepare_d1(
        self,
        *,
        instrument_id: str,
        candles: Sequence[Candle],
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
    ) -> _PreparedD1:
        if accepted_price_as_of is not None and accepted_price_as_of.tzinfo is None:
            raise ValueError("accepted_price_as_of must be timezone-aware")
        if expected_analysis_as_of is not None and expected_analysis_as_of.tzinfo is None:
            raise ValueError("expected_analysis_as_of must be timezone-aware")

        as_of = expected_analysis_as_of or accepted_price_as_of
        cutoff_session = as_of.astimezone(market_timezone).date() if as_of else None
        allowed = [
            candle
            for candle in candles
            if cutoff_session is None
            or candle.ts_open.astimezone(market_timezone).date() <= cutoff_session
        ]
        ordered = tuple(sorted(allowed, key=lambda candle: candle.ts_open))
        if not ordered:
            return _PreparedD1(
                candles=ordered,
                is_coherent=False,
                reason=PortfolioStructuralReviewReason.EVIDENCE_UNAVAILABLE,
            )
        if any(candle.instrument_id != instrument_id for candle in ordered) or any(
            candle.timeframe is not Timeframe.D1 for candle in ordered
        ):
            return _PreparedD1(
                candles=ordered,
                is_coherent=False,
                reason=PortfolioStructuralReviewReason.EVIDENCE_INCOHERENT,
            )
        return _PreparedD1(
            candles=ordered,
            is_coherent=True,
            reason=PortfolioStructuralReviewReason.EVIDENCE_UNAVAILABLE,
        )


def _epoch_placeholder() -> datetime:
    from datetime import timezone

    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _sessions_between(earlier: datetime, later: datetime) -> int:
    return max(0, (later.date() - earlier.date()).days)


def _confirmed_swing_lows(candles: Sequence[Candle]) -> list[Candle]:
    swings = []
    n = len(candles)
    for i in range(SWING_HALF_WINDOW, n - SWING_HALF_WINDOW):
        neighbors = list(candles[i - SWING_HALF_WINDOW : i]) + list(
            candles[i + 1 : i + SWING_HALF_WINDOW + 1]
        )
        # Strict local minimum only — a candle tied with its neighbors (a
        # flat run) is not a genuine reaction low, it is noise.
        if all(candles[i].low < c.low for c in neighbors):
            swings.append(candles[i])
    return swings


def _confirmed_swing_highs(candles: Sequence[Candle]) -> list[Candle]:
    swings = []
    n = len(candles)
    for i in range(SWING_HALF_WINDOW, n - SWING_HALF_WINDOW):
        neighbors = list(candles[i - SWING_HALF_WINDOW : i]) + list(
            candles[i + 1 : i + SWING_HALF_WINDOW + 1]
        )
        if all(candles[i].high > c.high for c in neighbors):
            swings.append(candles[i])
    return swings


def _cluster_zones(
    swings: Sequence[Candle], role: StructuralZoneRole
) -> list[StructuralZone]:
    if not swings:
        return []
    price_of: Callable[[Candle], Decimal] = (
        (lambda c: c.low) if role is StructuralZoneRole.SUPPORT else (lambda c: c.high)
    )
    ordered = sorted(swings, key=price_of)

    clusters: list[list[Candle]] = []
    for candle in ordered:
        price = price_of(candle)
        if clusters:
            cluster_prices = [price_of(c) for c in clusters[-1]]
            cluster_mid = sum(cluster_prices, Decimal(0)) / len(cluster_prices)
            if abs(price - cluster_mid) <= cluster_mid * ZONE_MERGE_TOLERANCE_PCT:
                clusters[-1].append(candle)
                continue
        clusters.append([candle])

    zones = []
    for cluster in clusters:
        prices = [price_of(c) for c in cluster]
        sessions = tuple(sorted(c.ts_open for c in cluster))
        zones.append(
            StructuralZone(
                lower=min(prices),
                upper=max(prices),
                role=role,
                touches=len(cluster),
                source_sessions=sessions,
                most_recent_session=sessions[-1],
            )
        )
    return zones


def _reject_stale(
    zones: Sequence[StructuralZone], latest_session: datetime
) -> list[StructuralZone]:
    return [
        z
        for z in zones
        if _sessions_between(z.most_recent_session, latest_session)
        <= ZONE_STALENESS_SESSIONS
    ]


def _format_zone(zone: StructuralZone) -> str:
    if zone.lower == zone.upper:
        return f"₹{zone.lower:,.2f}"
    return f"₹{zone.lower:,.2f}-{zone.upper:,.2f}"


def _compose_guidance(
    *,
    trend_label: str | None,
    daily_review_status: str | None,
    supertrend: SuperTrendEvidence,
    support_1: StructuralZone | None,
    major_support: StructuralZone | None,
    review_trigger: StructuralZone | None,
    trigger_is_reclaim: bool,
    target_1: StructuralZone | None,
    exit_risk: bool,
) -> str | None:
    trend_phrase = (
        f"{trend_label.capitalize()} remains intact"
        if trend_label and supertrend.direction is SuperTrendDirection.BULLISH
        else "Trend has weakened"
        if supertrend.direction is SuperTrendDirection.BEARISH
        else "Structure is unclear"
    )

    if exit_risk and major_support is not None:
        return (
            f"{trend_phrase.replace('remains intact', 'is damaged')}; "
            f"{_format_zone(major_support)} structural invalidation is broken with no reclaim. "
            "Exit risk is elevated."
        )

    if supertrend.direction is SuperTrendDirection.BEARISH:
        if support_1 is not None and major_support is not None:
            return (
                f"{trend_phrase}. Hold tight while {_format_zone(support_1)} support remains "
                f"intact; failure of {_format_zone(major_support)} structural invalidation raises "
                "exit risk."
            )
        if support_1 is not None:
            return f"{trend_phrase}. Hold tight while {_format_zone(support_1)} support remains intact."
        return f"{trend_phrase}. No defensible nearby structural support identified — review closely."

    if supertrend.direction is SuperTrendDirection.BULLISH:
        if target_1 is None:
            return (
                "Near available-history high with no confirmed overhead resistance. "
                "Ride trend and protect winner; no synthetic targets."
            )
        trigger_is_same_as_target = (
            review_trigger is not None
            and not trigger_is_reclaim
            and review_trigger.lower == target_1.lower
            and review_trigger.upper == target_1.upper
        )
        if review_trigger is not None and trigger_is_reclaim:
            trigger_phrase = (
                f"watch reclaim of {_format_zone(review_trigger)} for continuation "
                f"toward {_format_zone(target_1)}"
            )
        elif trigger_is_same_as_target:
            # Trigger and Target 1 are the same zone — say the price once,
            # never "watch X breakout ... toward X" repeating one number.
            trigger_phrase = f"watch {_format_zone(target_1)} breakout for continuation"
        elif review_trigger is not None:
            trigger_phrase = (
                f"watch {_format_zone(review_trigger)} breakout for continuation "
                f"toward {_format_zone(target_1)}"
            )
        else:
            trigger_phrase = f"watch for a confirmed breakout toward {_format_zone(target_1)}"
        support_phrase = (
            f"Hold while {_format_zone(support_1)} support holds"
            if support_1 is not None
            else "Hold while trend remains intact"
        )
        return f"{trend_phrase}. {support_phrase}; {trigger_phrase}."

    return None
