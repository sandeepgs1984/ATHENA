"""Market Summary API tests (MH-3 / F-5 §8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena import BLUEPRINT_VERSION, __version__
from athena.api.security.models import Role
from athena.api.v1.services.market_summary_service import MarketSummaryService
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import RunStatus, RunTrigger, Timeframe
from athena.domain.market import Candle, Instrument, MarketSnapshot
from athena.domain.run import RunRecord

AS_OF = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)


def _run(run_id: str = "run-mh3") -> RunRecord:
    return RunRecord(
        run_id=run_id,
        cycle_id="cyc",
        trigger=RunTrigger.REFRESH,
        started_ts=AS_OF,
        finished_ts=AS_OF,
        status=RunStatus.COMPLETED,
        software_version=__version__,
        blueprint_version=BLUEPRINT_VERSION,
        strategy_profile="t",
        strategy_profile_version="1",
        indicator_versions={},
        config_snapshot_id="cfg",
    )


def _d1(instrument_id: str, day_offset: int, close: str) -> Candle:
    ts = AS_OF - timedelta(days=day_offset)
    value = Decimal(close)
    return Candle(
        instrument_id=instrument_id,
        timeframe=Timeframe.D1,
        ts_open=ts.replace(hour=3, minute=45),
        open=value,
        high=value + 1,
        low=value - 1,
        close=value,
        volume=1000,
        source="test",
    )


class TestMarketSummaryService:
    def test_empty_repo_returns_unavailable_not_fabricated(self, tmp_path: Path) -> None:
        repo = SqliteRepository(tmp_path / "empty.db")
        repo.initialize()
        summary = MarketSummaryService(repo).market_summary()
        assert summary.available is False
        assert summary.market_health.score is None
        assert summary.breadth is None
        assert summary.sparklines.nifty_closes == ()
        assert "No completed validation" in (
            summary.market_health.unavailable_reason or ""
        )
        repo.close()

    def test_reads_score_breadth_and_sparklines_from_persisted_detail(
        self, tmp_path: Path
    ) -> None:
        repo = SqliteRepository(tmp_path / "sum.db")
        repo.initialize()
        repo.upsert_instrument(
            Instrument(
                instrument_id="NSE:NIFTY 50",
                symbol="NIFTY 50",
                exchange="NSE",
                series="INDEX",
                status="ACTIVE",
            )
        )
        repo.upsert_instrument(
            Instrument(
                instrument_id="NSE:INDIA VIX",
                symbol="INDIA VIX",
                exchange="NSE",
                series="INDEX",
                status="ACTIVE",
            )
        )
        repo.add_candles(
            [
                _d1("NSE:NIFTY 50", 3, "23800"),
                _d1("NSE:NIFTY 50", 2, "23900"),
                _d1("NSE:NIFTY 50", 1, "24000"),
                _d1("NSE:INDIA VIX", 2, "13.10"),
                _d1("NSE:INDIA VIX", 1, "13.30"),
            ]
        )
        repo.add_snapshot(
            MarketSnapshot(
                ts=AS_OF,
                indices={"NIFTY 50": Decimal("24010")},
                breadth_advances=70,
                breadth_declines=30,
                india_vix=Decimal("13.40"),
                breadth_neutral=5,
            )
        )
        repo.save_run(
            _run(),
            detail={
                "phase": "finished",
                "pipeline": {
                    "mode": "owner_validation",
                    "regime_assessment": {
                        "trend": "BULL_TREND",
                        "volatility": "NORMAL_VOLATILITY",
                        "gap": "NO_GAP",
                        "market_health": {
                            "breadth": "STRONG_BREADTH",
                            "trend_quality": "STRONG_TREND_QUALITY",
                            "momentum": "HEALTHY_MOMENTUM",
                            "volatility": "VOLATILITY_NORMAL",
                        },
                        "explanation": "Bullish with normal volatility.",
                    },
                    "market_metric_inputs": {
                        "breadth": {
                            "advances": 70,
                            "declines": 30,
                            "neutral": 5,
                            "universe_size": 100,
                            "scored": 105,
                            "coverage": "1.05",
                            "advance_ratio": "0.7",
                        },
                        "gap_stability": {
                            "gap_days": 2,
                            "scored_days": 20,
                            "stability_ratio": "0.9",
                            "gap_pct_threshold": "0.5",
                        },
                    },
                    "market_health_score": {
                        "score": {
                            "ts": AS_OF.isoformat(),
                            "components": {
                                "trend_quality": 80,
                                "breadth": 80,
                                "liquidity": 50,
                                "volatility": 55,
                                "institutional_strength": 70,
                                "gap_stability": 80,
                            },
                            "total": 70,
                            "explanation": "MarketHealthScore 70/100",
                        },
                        "components": [],
                        "unavailable_reason": None,
                    },
                },
            },
        )

        summary = MarketSummaryService(repo).market_summary()
        assert summary.available is True
        assert summary.run_id == "run-mh3"
        assert summary.regime is not None
        assert summary.regime.trend == "BULL_TREND"
        assert summary.market_health.score == 70
        assert summary.market_health.components is not None
        assert summary.market_health.dimensions["breadth"] == "STRONG_BREADTH"
        assert summary.breadth is not None
        assert summary.breadth.advances == 70
        assert summary.breadth.declines == 30
        assert summary.breadth.neutral == 5
        assert summary.breadth.advance_pct == Decimal("70.0")
        assert summary.breadth.label == "Universe breadth"
        assert summary.gap_detail is not None
        assert summary.gap_detail.points == 80
        assert summary.vix is not None
        assert summary.vix.level == Decimal("13.40")
        assert len(summary.sparklines.nifty_closes) >= 2
        assert len(summary.sparklines.vix_closes) >= 1
        repo.close()

    def test_score_null_when_unavailable_reason_present(self, tmp_path: Path) -> None:
        repo = SqliteRepository(tmp_path / "miss.db")
        repo.initialize()
        repo.save_run(
            _run("run-partial"),
            detail={
                "pipeline": {
                    "mode": "owner_validation",
                    "regime_assessment": {
                        "trend": "SIDEWAYS",
                        "volatility": "VOLATILITY_UNKNOWN",
                        "gap": "NO_GAP",
                        "market_health": {},
                        "explanation": "partial",
                    },
                    "market_health_score": {
                        "score": None,
                        "components": [
                            {
                                "name": "institutional_strength",
                                "points": None,
                                "band": None,
                                "explanation": "no flow",
                                "inputs": {},
                            }
                        ],
                        "unavailable_reason": (
                            "MarketHealthScore unavailable — missing required "
                            "component(s): institutional_strength"
                        ),
                    },
                    "market_metric_inputs": {
                        "breadth": {
                            "advances": 10,
                            "declines": 5,
                            "neutral": 1,
                            "universe_size": 20,
                            "scored": 16,
                            "coverage": "0.8",
                            "advance_ratio": "0.6667",
                        }
                    },
                }
            },
        )
        summary = MarketSummaryService(repo).market_summary()
        assert summary.market_health.score is None
        assert "institutional_strength" in (
            summary.market_health.unavailable_reason or ""
        )
        assert summary.breadth is not None
        assert summary.breadth.advances == 10
        repo.close()


def test_market_summary_endpoint_requires_auth(client: TestClient) -> None:
    unauthenticated = client.get("/api/v1/market/summary")
    assert unauthenticated.status_code == 401

    headers = get_auth_headers(client, Role.READONLY)
    ok = client.get("/api/v1/market/summary", headers=headers)
    assert ok.status_code == 200
    data = ok.json()["data"]
    assert "market_health" in data
    assert "breadth" in data
    assert "sparklines" in data
    assert "regime" in data
    # Shape only — live DB contents vary.
    assert "score" in data["market_health"]
    assert "dimensions" in data["market_health"]
