"""Universe Engine tests (M2.4): eligibility rules, exclusions, missing data,
constituent breadth export, multiple exchanges, determinism, immutability, config."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument
from athena.universe import UniverseEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def engine(config_dir) -> UniverseEngine:
    return UniverseEngine(load_config(config_dir).universe)


def _instrument(iid, *, symbol="AAA", series="EQ", exchange="NSE", status="ACTIVE") -> Instrument:
    return Instrument(instrument_id=iid, symbol=symbol, exchange=exchange, series=series,
                      isin=None, lot_size=1, tick_size=Decimal("0.05"), status=status)


def _candles(iid, n, *, volume=1_000_000, rising=True) -> list[Candle]:
    out = []
    start = date(2026, 1, 1)
    for i in range(n):
        base = Decimal(100 + (i if rising else -i))
        out.append(Candle(instrument_id=iid, timeframe=Timeframe.D1,
                          ts_open=datetime.combine(start + timedelta(days=i),
                                                   datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                          open=base, high=base + 1, low=base - 1, close=base,
                          volume=volume, source="test"))
    return out


def _assessment(result, iid):
    return next(a for a in result.assessments if a.instrument_id == iid)


class TestEligibility:
    def test_eligible_instrument_included(self, engine):
        r = engine.build([_instrument("I1")], {"I1": _candles("I1", 40)}, as_of=AS_OF)
        assert _assessment(r, "I1").included
        assert any(m.instrument_id == "I1" for m in r.universe.members)

    def test_inactive_excluded(self, engine):
        r = engine.build([_instrument("I1", status="SUSPENDED")], {"I1": _candles("I1", 40)}, as_of=AS_OF)
        a = _assessment(r, "I1")
        assert not a.included
        assert any("active_status" in reason for reason in a.exclusion_reasons)

    def test_unsupported_series_excluded(self, engine):
        r = engine.build([_instrument("I1", series="T2T")], {"I1": _candles("I1", 40)}, as_of=AS_OF)
        assert not _assessment(r, "I1").included

    def test_ineligible_exchange_excluded(self, engine):
        r = engine.build([_instrument("I1", exchange="XYZ")], {"I1": _candles("I1", 40)}, as_of=AS_OF)
        assert not _assessment(r, "I1").included

    def test_missing_history_excluded(self, engine):
        r = engine.build([_instrument("I1")], {"I1": _candles("I1", 5)}, as_of=AS_OF)
        a = _assessment(r, "I1")
        assert not a.included
        assert any("min_history" in reason for reason in a.exclusion_reasons)

    def test_insufficient_liquidity_excluded(self, engine):
        r = engine.build([_instrument("I1")], {"I1": _candles("I1", 40, volume=1000)}, as_of=AS_OF)
        a = _assessment(r, "I1")
        assert not a.included
        assert any("min_liquidity" in reason for reason in a.exclusion_reasons)

    def test_missing_dataset_excluded_with_evidence(self, engine):
        r = engine.build([_instrument("I1")], {}, as_of=AS_OF)  # no candles at all
        a = _assessment(r, "I1")
        assert not a.included
        assert any("data_present" in reason for reason in a.exclusion_reasons)
        # data-dependent rules explicitly reported, not silently skipped
        assert any(e.rule == "min_history" for e in a.evidence)


class TestCompleteness:
    def test_completeness_rule_runs_with_calendar(self, engine, config_dir):
        calendar = CalendarEngine.from_config_dir(config_dir, load_config(config_dir).market)
        # Dense recent history ending near as_of → high completeness
        candles = []
        d = date(2026, 3, 1)
        made = 0
        while made < 40:
            d -= timedelta(days=1)
            if calendar.context_for(d).is_trading_session:
                ts = datetime.combine(d, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
                candles.append(Candle(instrument_id="I1", timeframe=Timeframe.D1, ts_open=ts,
                                      open=Decimal("100"), high=Decimal("101"), low=Decimal("99"),
                                      close=Decimal("100"), volume=1_000_000, source="test"))
                made += 1
        r = engine.build([_instrument("I1")], {"I1": candles}, as_of=AS_OF,
                         calendar=calendar, history_window_days=45)
        a = _assessment(r, "I1")
        assert any(e.rule == "data_completeness" for e in a.evidence)


class TestConstituentBreadth:
    def test_breadth_export_by_sector(self, engine):
        instruments = [_instrument("BANK1"), _instrument("BANK2"), _instrument("IT1")]
        candles = {
            "BANK1": _candles("BANK1", 40, rising=True),   # advancing
            "BANK2": _candles("BANK2", 40, rising=False),  # declining
            "IT1": _candles("IT1", 40, rising=True),       # advancing
        }
        sectors = {"BANK1": "NIFTY_BANK", "BANK2": "NIFTY_BANK", "IT1": "NIFTY_IT"}
        r = engine.build(instruments, candles, as_of=AS_OF, sector_by_instrument=sectors)
        assert r.constituent_breadth["NIFTY_BANK"] == (1, 1)
        assert r.constituent_breadth["NIFTY_IT"] == (1, 0)

    def test_breadth_empty_without_sector_map(self, engine):
        r = engine.build([_instrument("I1")], {"I1": _candles("I1", 40)}, as_of=AS_OF)
        assert r.constituent_breadth == {}


class TestMultiExchangeAndSummary:
    def test_mixed_exchanges(self, engine):
        instruments = [_instrument("NSE1", exchange="NSE"), _instrument("BSE1", exchange="BSE")]
        candles = {"NSE1": _candles("NSE1", 40), "BSE1": _candles("BSE1", 40)}
        r = engine.build(instruments, candles, as_of=AS_OF)
        assert _assessment(r, "NSE1").included
        assert not _assessment(r, "BSE1").included  # BSE not in eligible_exchanges
        assert r.summary["included"] == 1 and r.summary["excluded"] == 1

    def test_summary_counts(self, engine):
        instruments = [_instrument("I1"), _instrument("I2", status="DELISTED")]
        candles = {"I1": _candles("I1", 40), "I2": _candles("I2", 40)}
        r = engine.build(instruments, candles, as_of=AS_OF)
        assert r.summary == {"evaluated": 2, "included": 1, "excluded": 1,
                             "configured_max": 100}


class TestDeterminismAndImmutability:
    def test_deterministic_repeat(self, engine):
        instruments = [_instrument("I1"), _instrument("I2")]
        candles = {"I1": _candles("I1", 40), "I2": _candles("I2", 40)}
        a = engine.build(instruments, candles, as_of=AS_OF)
        b = engine.build(instruments, candles, as_of=AS_OF)
        assert a.assessments == b.assessments
        assert a.universe == b.universe

    def test_members_sorted_by_id(self, engine):
        instruments = [_instrument("ZZZ"), _instrument("AAA")]
        candles = {"ZZZ": _candles("ZZZ", 40), "AAA": _candles("AAA", 40)}
        r = engine.build(instruments, candles, as_of=AS_OF)
        ids = [m.instrument_id for m in r.universe.members]
        assert ids == sorted(ids)

    def test_evidence_immutable(self, engine):
        r = engine.build([_instrument("I1")], {"I1": _candles("I1", 40)}, as_of=AS_OF)
        with pytest.raises(TypeError):
            _assessment(r, "I1").evidence[0].inputs["status"] = "X"


class TestConfig:
    def test_production_config_has_eligibility_fields(self):
        cfg = load_config(REPO / "config").universe
        assert cfg.supported_series and cfg.eligible_exchanges
        assert 0 < cfg.min_history_completeness <= 1

    def test_empty_supported_series_rejected(self, config_dir):
        from athena.errors import ConfigError
        (config_dir / "universe.json").write_text(
            '{"max_universe_size":100,"min_avg_daily_volume":500000,'
            '"min_trading_history_days":30,"supported_series":[],'
            '"eligible_exchanges":["NSE"],"min_history_completeness":0.9,'
            '"include_index_constituents":[],"custom_symbols":[]}', encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(config_dir)
