"""Institutional flow provider + repository tests (MH-1 / ADR-008 / DD-11)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from athena.config.models import InstitutionalNseProviderConfig
from athena.data.ingestion.institutional_flow import InstitutionalFlowIngestor
from athena.data.providers.file_institutional_provider import FileInstitutionalFlowProvider
from athena.data.providers.nse_institutional_provider import (
    NseInstitutionalFlowProvider,
    parse_nse_fiidii_payload,
    parse_nse_flow_date,
)
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import HealthStatus
from athena.domain.market import InstitutionalFlowSession, MarketSnapshot
from athena.errors import ProviderError
from athena.market_health.aggregates import (
    compute_gap_stability,
    compute_liquidity_aggregate,
    compute_universe_breadth,
)
from athena.domain.market import Candle
from athena.domain.enums import Timeframe


def _candle(iid: str, day: str, close: str, *, open_: str | None = None, volume: int = 1000) -> Candle:
    ts = datetime.fromisoformat(f"{day}T03:45:00+00:00")
    o = Decimal(open_ if open_ is not None else close)
    c = Decimal(close)
    return Candle(
        instrument_id=iid,
        timeframe=Timeframe.D1,
        ts_open=ts,
        open=o,
        high=max(o, c),
        low=min(o, c),
        close=c,
        volume=volume,
        source="test",
    )


class TestUniverseBreadth:
    def test_adv_dec_neutral(self) -> None:
        candles = {
            "A": [_candle("A", "2026-07-20", "100"), _candle("A", "2026-07-21", "110")],
            "B": [_candle("B", "2026-07-20", "100"), _candle("B", "2026-07-21", "90")],
            "C": [_candle("C", "2026-07-20", "100"), _candle("C", "2026-07-21", "100")],
            "D": [_candle("D", "2026-07-21", "50")],  # unscored
        }
        result = compute_universe_breadth(candles)
        assert result.advances == 1
        assert result.declines == 1
        assert result.neutral == 1
        assert result.scored == 3
        assert result.universe_size == 4
        assert result.advance_ratio == Decimal("0.5")


class TestLiquidityAndGap:
    def test_liquidity_median(self) -> None:
        candles = {
            "A": [
                _candle("A", "2026-07-20", "10", volume=100),
                _candle("A", "2026-07-21", "10", volume=100),
            ],
            "B": [
                _candle("B", "2026-07-20", "20", volume=100),
                _candle("B", "2026-07-21", "20", volume=100),
            ],
        }
        result = compute_liquidity_aggregate(candles, lookback_days=5)
        assert result.member_count == 2
        assert result.median_turnover == Decimal("1500")  # median of 1000 and 2000

    def test_gap_stability(self) -> None:
        series = [
            _candle("N", "2026-07-20", "100", open_="100"),
            _candle("N", "2026-07-21", "100", open_="101"),  # 1% gap
            _candle("N", "2026-07-22", "100", open_="100"),  # 0% gap
        ]
        result = compute_gap_stability(
            series, window=5, gap_pct_threshold=Decimal("0.5")
        )
        assert result.scored_days == 2
        assert result.gap_days == 1
        assert result.stability_ratio == Decimal("0.5")


class TestFileInstitutionalProvider:
    def test_reads_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "flows.csv"
        csv_path.write_text(
            "session_date,fii_buy,fii_sell,fii_net,dii_buy,dii_sell,dii_net,provisional\n"
            "2026-07-21,10,5,5,8,9,-1,true\n",
            encoding="utf-8",
        )
        from athena.config.models import InstitutionalFileProviderConfig

        provider = FileInstitutionalFlowProvider(
            InstitutionalFileProviderConfig(data_root=str(tmp_path), flows_file="flows.csv"),
            tmp_path,
        )
        latest = provider.latest_session()
        assert latest.session_date == date(2026, 7, 21)
        assert latest.fii_net == Decimal("5")
        assert latest.provisional is True
        assert provider.health().status is HealthStatus.OK


class TestNseParse:
    def test_parse_date_and_payload(self) -> None:
        assert parse_nse_flow_date("21-Jul-2026") == date(2026, 7, 21)
        fetched = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
        sessions = parse_nse_fiidii_payload(
            [
                {
                    "category": "FII/FPI",
                    "date": "21-Jul-2026",
                    "buyValue": "100.5",
                    "sellValue": "40.0",
                    "netValue": "60.5",
                },
                {
                    "category": "DII",
                    "date": "21-Jul-2026",
                    "buyValue": "80",
                    "sellValue": "90",
                    "netValue": "-10",
                },
            ],
            fetched_at=fetched,
        )
        assert len(sessions) == 1
        assert sessions[0].fii_net == Decimal("60.5")
        assert sessions[0].dii_net == Decimal("-10")
        assert sessions[0].provisional is True

    def test_nse_provider_uses_injected_transport(self) -> None:
        payload = (
            b'[{"category":"FII/FPI","date":"22-Jul-2026","buyValue":"1","sellValue":"0","netValue":"1"},'
            b'{"category":"DII","date":"22-Jul-2026","buyValue":"0","sellValue":"1","netValue":"-1"}]'
        )

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return payload

        calls: list[str] = []

        def fake_urlopen(request, timeout=0):  # noqa: ANN001
            calls.append(request.full_url)
            if "api/fiidii" in request.full_url:
                return _Resp()
            return _Resp() if False else type(
                "H",
                (),
                {
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *a: False,
                    "read": lambda self: b"ok",
                },
            )()

        # Simpler: always return HTML for home, JSON for api
        def urlopen_fn(request, timeout=0):  # noqa: ANN001
            url = request.full_url
            calls.append(url)

            class R:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self):
                    if "fiidii" in url:
                        return payload
                    return b"<html/>"

            return R()

        provider = NseInstitutionalFlowProvider(
            InstitutionalNseProviderConfig(),
            urlopen_fn=urlopen_fn,
            clock=lambda: datetime(2026, 7, 22, 15, 0, tzinfo=timezone.utc),
        )
        latest = provider.latest_session()
        assert latest.session_date == date(2026, 7, 22)
        assert latest.fii_net == Decimal("1")
        assert any("fiidii" in u for u in calls)


class TestInstitutionalPersistence:
    def test_append_and_prefer_final(self, tmp_path: Path) -> None:
        repo = SqliteRepository(tmp_path / "t.db")
        repo.initialize()
        t0 = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)
        repo.add_institutional_flow(
            InstitutionalFlowSession(
                session_date=date(2026, 7, 21),
                fii_buy=Decimal("10"), fii_sell=Decimal("5"), fii_net=Decimal("5"),
                dii_buy=Decimal("1"), dii_sell=Decimal("2"), dii_net=Decimal("-1"),
                provisional=True, source_id="nse", fetched_at=t0,
            )
        )
        repo.add_institutional_flow(
            InstitutionalFlowSession(
                session_date=date(2026, 7, 21),
                fii_buy=Decimal("11"), fii_sell=Decimal("5"), fii_net=Decimal("6"),
                dii_buy=Decimal("1"), dii_sell=Decimal("2"), dii_net=Decimal("-1"),
                provisional=False, source_id="nsdl", fetched_at=t1,
            )
        )
        latest = repo.get_latest_institutional_flow(prefer_final=True)
        assert latest is not None
        assert latest.provisional is False
        assert latest.fii_net == Decimal("6")

    def test_ingestor_skips_duplicate_and_survives_provider_error(
        self, tmp_path: Path
    ) -> None:
        repo = SqliteRepository(tmp_path / "t.db")
        repo.initialize()
        session = InstitutionalFlowSession(
            session_date=date(2026, 7, 21),
            fii_buy=Decimal("10"), fii_sell=Decimal("5"), fii_net=Decimal("5"),
            dii_buy=Decimal("1"), dii_sell=Decimal("2"), dii_net=Decimal("-1"),
            provisional=True, source_id="file",
            fetched_at=datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc),
        )

        class _Ok:
            name = "ok"

            def latest_session(self):
                return session

            def sessions(self, start, end):
                return [session]

            def health(self):
                from athena.domain.interfaces import ProviderHealth

                return ProviderHealth(status=HealthStatus.OK, detail="ok")

        as_of = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
        first = InstitutionalFlowIngestor(repo, _Ok()).run(as_of=as_of)
        second = InstitutionalFlowIngestor(repo, _Ok()).run(as_of=as_of)
        assert first.written is True
        assert second.skipped_duplicate is True

        class _Fail:
            name = "fail"

            def latest_session(self):
                raise ProviderError("boom")

            def sessions(self, start, end):
                raise ProviderError("boom")

            def health(self):
                from athena.domain.interfaces import ProviderHealth

                return ProviderHealth(status=HealthStatus.WARN, detail="boom")

        failed = InstitutionalFlowIngestor(repo, _Fail()).run(as_of=as_of)
        assert failed.written is False
        assert failed.error == "boom"


class TestSnapshotHistory:
    def test_list_snapshots_recent_and_breadth_neutral(self, tmp_path: Path) -> None:
        repo = SqliteRepository(tmp_path / "t.db")
        repo.initialize()
        t1 = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
        repo.add_snapshot(
            MarketSnapshot(
                ts=t1, indices={"NIFTY": Decimal("1")},
                breadth_advances=1, breadth_declines=1, breadth_neutral=2,
            )
        )
        repo.add_snapshot(
            MarketSnapshot(
                ts=t2, indices={"NIFTY": Decimal("2")},
                breadth_advances=3, breadth_declines=1, breadth_neutral=0,
                india_vix=Decimal("14"),
            )
        )
        recent = repo.list_snapshots_recent(limit=10)
        assert len(recent) == 2
        assert recent[0].ts == t1
        assert recent[0].breadth_neutral == 2
        assert recent[1].breadth_advances == 3
        assert repo.get_latest_snapshot() is not None
        assert repo.get_latest_snapshot().ts == t2
