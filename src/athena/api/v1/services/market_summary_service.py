"""Market Summary read model (MH-3 / F-5 §8).

Assembles persisted validation-run artifacts + candle history into one honest
DTO for the Market Intelligence hero. Never fabricates score or breadth —
absent inputs become null / empty arrays for the UI to render as Unavailable.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from athena.api.v1.dtos.market import (
    MarketBreadthSummaryDTO,
    MarketGapDetailDTO,
    MarketHealthSummaryDTO,
    MarketRegimeSummaryDTO,
    MarketSparklinesDTO,
    MarketSummaryDTO,
    MarketVixSummaryDTO,
)
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import RunStatus, Timeframe

_NIFTY_CANDLE_IDS = ("NSE:NIFTY 50", "NIFTY 50", "NIFTY50")
_VIX_CANDLE_IDS = ("NSE:INDIA VIX", "INDIA VIX")
_SPARKLINE_LIMIT = 20


def _from_detail(detail: object, key: str) -> object:
    """Read a key from nested ``pipeline`` or flat run detail."""
    if not isinstance(detail, dict):
        return None
    pipeline = detail.get("pipeline")
    if isinstance(pipeline, dict) and key in pipeline:
        return pipeline[key]
    return detail.get(key)


class MarketSummaryService:
    """Read-only Market Summary for the dashboard hero (MH-3)."""

    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo

    def market_summary(self) -> MarketSummaryDTO:
        run = self._latest_completed_validation_run()
        if run is None:
            return self._empty(as_of=None, available=False)

        detail = self._repo.get_run_detail(run.run_id)
        regime_raw = _from_detail(detail, "regime_assessment")
        score_raw = _from_detail(detail, "market_health_score")
        metrics_raw = _from_detail(detail, "market_metric_inputs")

        regime = self._regime(regime_raw)
        health = self._health(regime_raw, score_raw)
        breadth = self._breadth(metrics_raw)
        gap_detail = self._gap_detail(metrics_raw, score_raw)
        vix = self._vix()
        sparklines = self._sparklines()

        available = any(
            (
                regime is not None,
                health.score is not None or bool(health.dimensions),
                breadth is not None,
                sparklines.nifty_closes or sparklines.vix_closes,
            )
        )
        return MarketSummaryDTO(
            as_of=run.finished_ts or run.started_ts,
            available=available,
            run_id=run.run_id,
            regime=regime,
            market_health=health,
            breadth=breadth,
            gap_detail=gap_detail,
            vix=vix,
            sparklines=sparklines,
        )

    def _empty(self, *, as_of: datetime | None, available: bool) -> MarketSummaryDTO:
        return MarketSummaryDTO(
            as_of=as_of,
            available=available,
            run_id=None,
            regime=None,
            market_health=MarketHealthSummaryDTO(
                score=None,
                components=None,
                explanation=None,
                unavailable_reason="No completed validation run yet",
                dimensions={},
            ),
            breadth=None,
            gap_detail=None,
            vix=None,
            sparklines=MarketSparklinesDTO(nifty_closes=(), vix_closes=()),
        )

    def _latest_completed_validation_run(self):
        """Newest finished run that carries owner-validation pipeline detail."""
        for run in self._repo.list_runs(limit=50):
            if run.status is not RunStatus.COMPLETED:
                continue
            detail = self._repo.get_run_detail(run.run_id)
            if not isinstance(detail, dict):
                continue
            # Prefer runs that actually wrote MH artifacts or regime.
            if (
                _from_detail(detail, "market_health_score") is not None
                or _from_detail(detail, "market_metric_inputs") is not None
                or _from_detail(detail, "regime_assessment") is not None
                or _from_detail(detail, "mode") == "owner_validation"
            ):
                return run
        return None

    @staticmethod
    def _regime(raw: object) -> MarketRegimeSummaryDTO | None:
        if not isinstance(raw, dict):
            return None
        evidence: tuple[str, ...] = ()
        ev = raw.get("evidence")
        if isinstance(ev, list):
            evidence = tuple(str(item) for item in ev if item)
        return MarketRegimeSummaryDTO(
            trend=str(raw.get("trend") or "TREND_UNKNOWN"),
            volatility=str(raw.get("volatility") or "VOLATILITY_UNKNOWN"),
            gap=str(raw.get("gap") or "GAP_UNKNOWN"),
            explanation=str(raw.get("explanation") or "") or None,
            evidence=evidence,
        )

    @staticmethod
    def _health(regime_raw: object, score_raw: object) -> MarketHealthSummaryDTO:
        dimensions: dict[str, str] = {}
        if isinstance(regime_raw, dict):
            mh = regime_raw.get("market_health")
            if isinstance(mh, dict):
                dimensions = {str(k): str(v) for k, v in mh.items()}

        score: int | None = None
        components: dict[str, int] | None = None
        explanation: str | None = None
        unavailable_reason: str | None = None

        if isinstance(score_raw, dict):
            unavailable_reason = (
                str(score_raw["unavailable_reason"])
                if score_raw.get("unavailable_reason")
                else None
            )
            payload = score_raw.get("score")
            if isinstance(payload, dict) and payload.get("total") is not None:
                try:
                    score = int(payload["total"])
                except (TypeError, ValueError):
                    score = None
                comps = payload.get("components")
                if isinstance(comps, dict):
                    components = {
                        str(k): int(v)
                        for k, v in comps.items()
                        if v is not None
                    }
                explanation = (
                    str(payload["explanation"])
                    if payload.get("explanation")
                    else None
                )
            elif unavailable_reason is None:
                unavailable_reason = "MarketHealthScore not available for this run"

        elif isinstance(regime_raw, dict):
            # Older path: score nested only under regime_assessment.
            nested = regime_raw.get("market_health_score")
            if isinstance(nested, dict) and nested.get("total") is not None:
                try:
                    score = int(nested["total"])
                except (TypeError, ValueError):
                    score = None
                comps = nested.get("components")
                if isinstance(comps, dict):
                    components = {
                        str(k): int(v)
                        for k, v in comps.items()
                        if v is not None
                    }
                explanation = (
                    str(nested["explanation"])
                    if nested.get("explanation")
                    else None
                )

        if score is None and unavailable_reason is None and not dimensions:
            unavailable_reason = "No market health assessment on the latest run"

        return MarketHealthSummaryDTO(
            score=score,
            components=components,
            explanation=explanation,
            unavailable_reason=unavailable_reason if score is None else None,
            dimensions=dimensions,
        )

    @staticmethod
    def _breadth(metrics_raw: object) -> MarketBreadthSummaryDTO | None:
        if not isinstance(metrics_raw, dict):
            return None
        raw = metrics_raw.get("breadth")
        if not isinstance(raw, dict):
            return None
        try:
            advances = int(raw.get("advances", 0))
            declines = int(raw.get("declines", 0))
            neutral = int(raw.get("neutral", 0))
            universe_size = int(raw.get("universe_size", 0))
            scored = int(raw.get("scored", 0))
        except (TypeError, ValueError):
            return None
        if universe_size <= 0 and scored <= 0 and advances + declines + neutral <= 0:
            return None
        coverage = None
        if raw.get("coverage") not in (None, ""):
            try:
                coverage = Decimal(str(raw["coverage"]))
            except Exception:
                coverage = None
        advance_pct = None
        denom = advances + declines
        if denom > 0:
            advance_pct = (Decimal(advances) / Decimal(denom) * Decimal(100)).quantize(
                Decimal("0.1")
            )
        elif raw.get("advance_ratio") not in (None, ""):
            try:
                advance_pct = (
                    Decimal(str(raw["advance_ratio"])) * Decimal(100)
                ).quantize(Decimal("0.1"))
            except Exception:
                advance_pct = None
        return MarketBreadthSummaryDTO(
            advances=advances,
            declines=declines,
            neutral=neutral,
            advance_pct=advance_pct,
            universe_size=universe_size,
            scored=scored,
            coverage=coverage,
            label="Universe breadth",
        )

    @staticmethod
    def _gap_detail(
        metrics_raw: object, score_raw: object
    ) -> MarketGapDetailDTO | None:
        points: int | None = None
        if isinstance(score_raw, dict):
            score = score_raw.get("score")
            if isinstance(score, dict):
                comps = score.get("components")
                if isinstance(comps, dict) and "gap_stability" in comps:
                    try:
                        points = int(comps["gap_stability"])
                    except (TypeError, ValueError):
                        points = None
            if points is None:
                for item in score_raw.get("components") or ():
                    if isinstance(item, dict) and item.get("name") == "gap_stability":
                        try:
                            points = (
                                int(item["points"])
                                if item.get("points") is not None
                                else None
                            )
                        except (TypeError, ValueError):
                            points = None
                        break

        pct: Decimal | None = None
        if isinstance(metrics_raw, dict):
            gap = metrics_raw.get("gap_stability")
            if isinstance(gap, dict) and gap.get("stability_ratio") not in (None, ""):
                try:
                    pct = (
                        Decimal(str(gap["stability_ratio"])) * Decimal(100)
                    ).quantize(Decimal("0.1"))
                except Exception:
                    pct = None
        if points is None and pct is None:
            return None
        return MarketGapDetailDTO(points=points, pct=pct)

    def _vix(self) -> MarketVixSummaryDTO | None:
        snapshot = self._repo.get_latest_snapshot()
        if snapshot is None or snapshot.india_vix is None:
            return None
        level = snapshot.india_vix
        change_pct = None
        candles = self._first_candle_series(_VIX_CANDLE_IDS, limit=5)
        if candles:
            snap_date = snapshot.ts.astimezone(snapshot.ts.tzinfo).date()
            prior = [
                c
                for c in candles
                if c.ts_open.astimezone(snapshot.ts.tzinfo).date() < snap_date
            ]
            if prior and prior[-1].close:
                baseline = prior[-1].close
                change_pct = ((level - baseline) / baseline * Decimal(100)).quantize(
                    Decimal("0.01")
                )
        return MarketVixSummaryDTO(level=level, change_pct=change_pct)

    def _sparklines(self) -> MarketSparklinesDTO:
        nifty = self._close_series(_NIFTY_CANDLE_IDS, _SPARKLINE_LIMIT)
        vix = self._close_series(_VIX_CANDLE_IDS, _SPARKLINE_LIMIT)
        return MarketSparklinesDTO(nifty_closes=nifty, vix_closes=vix)

    def _first_candle_series(self, instrument_ids: tuple[str, ...], *, limit: int):
        for iid in instrument_ids:
            series = self._repo.list_candles_recent(iid, Timeframe.D1, limit=limit)
            if series:
                return series
        return []

    def _close_series(
        self, instrument_ids: tuple[str, ...], limit: int
    ) -> tuple[Decimal, ...]:
        series = self._first_candle_series(instrument_ids, limit=limit)
        if not series:
            return ()
        return tuple(c.close for c in series)
