"""EM-5's read-only canonical-regime source (Owner/Chief Architect ruling,
2026-08-28, after the production canary found `run_scan_cycle`'s
`regime_lookup` permanently unwired -- holding all-22-fields-known
completeness at a hard 0%).

Wires the real, unmodified `RegimeEngine` into the live scanner via
`regime_replay.reconstruct_session_regime` -- the exact point-in-time-safe
function EM-1c's own historical regime reconstruction already uses
(Owner-approved 2026-08-27): trend/volatility from D1 index/VIX history
strictly BEFORE `session_date`, gap from `session_date`'s own real open vs.
the prior close, `GAP_UNKNOWN` if `session_date`'s own candle is not yet
ingested. No EMR-specific regime definition, no cohort proxy, no
hardcoded labels, no defaulted UNKNOWNs -- every dimension is the
canonical engine's own label, unmodified.

Reads real index/VIX candles through `EmrMarketDataPort` -- the same
read-only bulk channel every other EM-5 evidence input already uses (never
`SqliteRepository` directly). The dependency stays strictly one-way:
this module imports FROM `athena.regime`/`athena.explosive_move.regime_replay`
(canonical -> EMR); nothing in `athena.regime` or any canonical
decision/risk/scoring module imports `athena.explosive_move` (enforced by
`test_em5_isolation.py`).

Symbol resolution mirrors production's own established real-regime
consumer (`ops/owner_validation.py`'s `_resolve_index_candles`/
`_vix_from_candles`): prefer the configured `KiteProviderConfig.index_instruments`/
`india_vix_instrument`, falling back to the same literal symbols, in one
bulk read (never one query per candidate).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from datetime import time as time_of_day
from datetime import tzinfo as tzinfo_type
from pathlib import Path

from athena.config.loader import load_config, load_kite_provider_config
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.explosive_move.live.market_data_port import EmrMarketDataPort
from athena.explosive_move.regime_replay import reconstruct_session_regime

#: Same real fallback symbols `ops/owner_validation.py`'s production
#: regime consumer already established, used only if config-driven
#: resolution is unavailable.
DEFAULT_INDEX_SYMBOL_CANDIDATES: tuple[str, ...] = ("NSE:NIFTY 50", "NIFTY50")
DEFAULT_VIX_SYMBOL_CANDIDATES: tuple[str, ...] = ("NSE:INDIA VIX", "INDIA VIX")

#: Wide enough to comfortably clear RegimeConfig.trend_ma_slow (50 by
#: default) daily sessions even across weekends/holidays -- same margin
#: convention `scanner.py`/`canary_gate.py` already use for their own
#: 50-session floor.
REGIME_LOOKBACK_CALENDAR_DAYS = 120

#: The exact shape `session_invariant_evidence.compute_session_invariant_evidence`'s
#: `regime_field()` reads (frozen EM-2 contract -- never touched here).
RegimeRow = dict[str, str]


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            ordered.append(v)
    return tuple(ordered)


def _first_with_candles(
    candidates: tuple[str, ...], by_symbol: dict[str, list[Candle]],
) -> tuple[str, tuple[Candle, ...]]:
    for symbol_id in candidates:
        candles = by_symbol.get(symbol_id, ())
        if candles:
            return symbol_id, tuple(candles)
    return (candidates[0] if candidates else ""), ()


def build_canonical_regime_lookup(
    *,
    market_port: EmrMarketDataPort,
    config_dir: Path,
    tzinfo: tzinfo_type,
) -> Callable[[date], RegimeRow]:
    """Returns a `regime_lookup(session_date) -> dict` closure for
    `run_scan_cycle`, backed by real, already-ingested NIFTY 50/INDIA VIX
    candles. Always returns a real dict (never `None`) -- when a
    dimension's own data is insufficient, `RegimeEngine`'s own
    `*_UNKNOWN` label is the honest answer, not an absent lookup."""

    regime_config = load_config(config_dir).regime
    index_candidates = list(DEFAULT_INDEX_SYMBOL_CANDIDATES)
    vix_candidates = list(DEFAULT_VIX_SYMBOL_CANDIDATES)
    try:
        kite = load_kite_provider_config(config_dir)
        index_candidates = list(kite.index_instruments) + index_candidates
        vix_candidates = [kite.india_vix_instrument, *vix_candidates]
    except Exception:
        pass
    index_candidates_t = _dedupe(index_candidates)
    vix_candidates_t = _dedupe(vix_candidates)

    def _lookup(session_date: date) -> RegimeRow:
        start = session_date - timedelta(days=REGIME_LOOKBACK_CALENDAR_DAYS)
        start_dt = datetime.combine(start, time_of_day(0, 0), tzinfo=tzinfo)
        end_dt = datetime.combine(session_date, time_of_day(23, 59), tzinfo=tzinfo)

        index_by_symbol = market_port.candles_for_instruments(
            index_candidates_t, Timeframe.D1, start_dt, end_dt,
        )
        vix_by_symbol = market_port.candles_for_instruments(
            vix_candidates_t, Timeframe.D1, start_dt, end_dt,
        )
        index_symbol, nifty_candles = _first_with_candles(index_candidates_t, index_by_symbol)
        _, vix_candles = _first_with_candles(vix_candidates_t, vix_by_symbol)

        result = reconstruct_session_regime(
            session_date=session_date, index_symbol=index_symbol,
            nifty_candles=nifty_candles, vix_candles=vix_candles, config=regime_config,
        )
        return {"trend": result.trend.value, "volatility": result.volatility.value, "gap": result.gap.value}

    return _lookup
