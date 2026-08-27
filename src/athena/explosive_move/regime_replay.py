"""EM-1c regime-evidence prerequisite: point-in-time-safe historical replay
of the canonical, unmodified ``RegimeEngine`` for a single EMR study
session -- Owner/Chief Architect decision, 2026-08-27.

The engine itself has no per-checkpoint concept (D1-only, session-level).
Contract audit finding: in ATHENA's real production system, session T's
own D1 candle does not exist until the CLOSING ingestion cycle (15:45 IST,
after market close) -- so any live intraday regime read is structurally
based on data through T-1 only. Historical reconstruction must enforce the
same cutoff explicitly, since (unlike the live system) it has the full
benefit of hindsight and would otherwise leak T's own close into T's own
regime label.

Point-in-time rule (frozen, do not weaken):
  - TREND and VOLATILITY: computed from index/VIX D1 history strictly
    BEFORE session_date (``ts_open.date() < session_date``) -- T's own
    final OHLC candle is never included.
  - GAP: session T's own OPEN is legitimate information (known at 09:15,
    before every accepted EMR checkpoint), so gap may use T's real open
    vs T-1's real close. T's high/low/close must never enter the
    computation for any dimension.
  - If session_date's own candle is genuinely absent from the acquired
    index series, gap is UNKNOWN -- never silently computed from the
    wrong (T-1-vs-T-2) pair.
  - All nine EM-1a accepted checkpoints on session_date share this single
    session-level regime, since none of live ATHENA's real regime inputs
    vary by intraday time-of-day.

This module reuses ``RegimeEngine``/``config/regime.json`` completely
unmodified -- it never redesigns the engine, never introduces an
EMR-specific regime definition, and never tunes its thresholds. It is
pure: no I/O, no clock reads; candles are caller-supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from athena.config.models import RegimeConfig
from athena.domain.market import Candle, MarketSnapshot
from athena.regime.engine import RegimeEngine
from athena.regime.models import RegimeLabel

IST = ZoneInfo("Asia/Kolkata")

REGIME_REPLAY_CONTRACT_VERSION = "em1c-regime-replay-v1"


@dataclass(frozen=True, slots=True)
class SessionRegimeResult:
    session_date: date
    index_symbol: str
    index_data_cutoff: date | None  # last NIFTY D1 candle date strictly before session_date
    vix_data_cutoff: date | None  # last VIX D1 candle date strictly before session_date
    trend: RegimeLabel
    volatility: RegimeLabel
    gap: RegimeLabel
    trend_explanation: str
    volatility_explanation: str
    gap_explanation: str


def reconstruct_session_regime(
    *,
    session_date: date,
    index_symbol: str,
    nifty_candles: tuple[Candle, ...],
    vix_candles: tuple[Candle, ...],
    config: RegimeConfig,
) -> SessionRegimeResult:
    """Reconstruct session_date's point-in-time-safe regime label.

    ``nifty_candles``/``vix_candles`` may span the whole acquired history --
    this function does its own T-1 slicing, so callers do not need to
    pre-filter (and should not, to keep the leakage boundary in one place).
    """

    before_nifty = tuple(sorted(
        (c for c in nifty_candles if c.ts_open.date() < session_date), key=lambda c: c.ts_open,
    ))
    through_nifty = tuple(sorted(
        (c for c in nifty_candles if c.ts_open.date() <= session_date), key=lambda c: c.ts_open,
    ))
    before_vix = tuple(sorted(
        (c for c in vix_candles if c.ts_open.date() < session_date), key=lambda c: c.ts_open,
    ))

    has_own_candle = bool(through_nifty) and through_nifty[-1].ts_open.date() == session_date

    vix_snapshot = None
    if before_vix:
        vix_snapshot = MarketSnapshot(
            ts=datetime.combine(session_date, time(9, 15), tzinfo=IST),
            indices={}, india_vix=before_vix[-1].close,
        )

    engine = RegimeEngine(config)
    as_of = datetime.combine(session_date, time(9, 15), tzinfo=IST)

    # Trend + volatility: computed strictly from T-1-and-earlier evidence.
    trend_vol_result = engine.assess(index_symbol, before_nifty, vix_snapshot, as_of=as_of)
    trend_evidence = next(e for e in trend_vol_result.evidence if e.dimension == "trend")
    volatility_evidence = next(e for e in trend_vol_result.evidence if e.dimension == "volatility")

    # Gap: only legitimate when T's own real candle is present; its
    # trend/volatility results from this second call are always discarded
    # (they would read T's own close, a real leak) -- gap alone is kept.
    if has_own_candle:
        gap_only_result = engine.assess(index_symbol, through_nifty, None, as_of=as_of)
        gap_evidence = next(e for e in gap_only_result.evidence if e.dimension == "gap")
    else:
        gap_evidence = None

    return SessionRegimeResult(
        session_date=session_date,
        index_symbol=index_symbol,
        index_data_cutoff=before_nifty[-1].ts_open.date() if before_nifty else None,
        vix_data_cutoff=before_vix[-1].ts_open.date() if before_vix else None,
        trend=trend_evidence.outcome,
        volatility=volatility_evidence.outcome,
        gap=gap_evidence.outcome if gap_evidence is not None else RegimeLabel.GAP_UNKNOWN,
        trend_explanation=trend_evidence.explanation,
        volatility_explanation=volatility_evidence.explanation,
        gap_explanation=(
            gap_evidence.explanation if gap_evidence is not None
            else f"session {session_date.isoformat()}'s own index candle is absent from the "
                 "acquired history -- gap cannot be legitimately computed"
        ),
    )
