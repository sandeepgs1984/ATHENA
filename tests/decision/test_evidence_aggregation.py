"""Evidence Aggregation Engine tests (M3.1): gather all sources, provenance,
missing detection, partial inputs, determinism, immutability."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import (
    load_config,
    load_market_health_config,
    load_sector_health_config,
)
from athena.data.corporate_actions import AdjustmentStrategy, CorporateActionsEngine
from athena.data.validation.reports import (
    Severity,
    ValidationReport,
    ValidationResult,
    ValidationType,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, CorporateAction, Instrument, MarketSnapshot
from athena.evidence import EvidenceAggregationEngine, EvidenceSource
from athena.market_health import MarketHealthEngine
from athena.regime import RegimeEngine
from athena.sector_health import SectorHealthEngine
from athena.universe import UniverseEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)


def _candles(iid, closes, *, volume=1_000_000):
    out = []
    start = date(2026, 1, 1)
    for i, close in enumerate(closes):
        c = Decimal(str(close))
        out.append(Candle(instrument_id=iid, timeframe=Timeframe.D1,
                          ts_open=datetime.combine(start + timedelta(days=i),
                                                   datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                          open=c, high=c + 1, low=c - 1, close=c, volume=volume, source="test"))
    return out


@pytest.fixture()
def engines(config_dir):
    cfg = load_config(config_dir)
    return {
        "regime": RegimeEngine(cfg.regime),
        "market_health": MarketHealthEngine(load_market_health_config(config_dir)),
        "sector_health": SectorHealthEngine(load_sector_health_config(config_dir)),
        "universe": UniverseEngine(cfg.universe),
        "aggregator": EvidenceAggregationEngine(),
    }


def _snapshot(vix=15, adv=60, dec=40):
    return MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                          breadth_advances=adv, breadth_declines=dec,
                          india_vix=Decimal(str(vix)))


def _full_inputs(engines):
    idx = _candles("NIFTY50", range(100, 160))
    regime = engines["regime"].assess("NIFTY50", idx, _snapshot(), as_of=AS_OF)
    market_health = engines["market_health"].assess("NIFTY50", idx, _snapshot(), as_of=AS_OF)
    sector_health = engines["sector_health"].assess_many(
        {"NIFTY_BANK": _candles("NIFTY_BANK", range(100, 140))}, as_of=AS_OF)
    instruments = [Instrument(instrument_id="I1", symbol="AAA", exchange="NSE", series="EQ",
                              isin=None, lot_size=1, tick_size=Decimal("0.05"), status="ACTIVE")]
    universe = engines["universe"].build(instruments, {"I1": _candles("I1", range(100, 140))},
                                         as_of=AS_OF)
    ca_engine = CorporateActionsEngine()
    ca_result = ca_engine.adjust(
        "I1", _candles("I1", range(100, 140)),
        [CorporateAction(action_id="s1", instrument_id="I1", action_type="SPLIT",
                         ex_date=date(2026, 1, 20), details={"from_shares": "1", "to_shares": "2"})],
        strategy=AdjustmentStrategy.SPLIT_ADJUSTED, as_of=AS_OF)
    validation = [ValidationReport(validation_type=ValidationType.FRESHNESS,
                                   result=ValidationResult.PASSED, severity=Severity.INFO,
                                   explanation="data current", ts=AS_OF)]
    return dict(regime=regime, market_health=market_health, sector_health=sector_health,
                universe=universe, corporate_action_evidence=ca_result.evidence,
                validation_reports=validation)


class TestAggregation:
    def test_gathers_all_sources(self, engines):
        bundle = engines["aggregator"].aggregate(as_of=AS_OF, **_full_inputs(engines))
        assert bundle.has_source(EvidenceSource.REGIME)
        assert bundle.has_source(EvidenceSource.MARKET_HEALTH)
        assert bundle.has_source(EvidenceSource.SECTOR_HEALTH)
        assert bundle.has_source(EvidenceSource.UNIVERSE)
        assert bundle.has_source(EvidenceSource.CORPORATE_ACTION)
        assert bundle.has_source(EvidenceSource.VALIDATION)

    def test_provenance_counts(self, engines):
        bundle = engines["aggregator"].aggregate(as_of=AS_OF, **_full_inputs(engines))
        assert bundle.provenance[EvidenceSource.REGIME.value] == 3   # trend, volatility, gap
        assert bundle.provenance[EvidenceSource.MARKET_HEALTH.value] == 4
        assert bundle.provenance[EvidenceSource.VALIDATION.value] == 1

    def test_regime_items_carry_payload_and_provenance(self, engines):
        bundle = engines["aggregator"].aggregate(as_of=AS_OF, **_full_inputs(engines))
        regime_items = bundle.by_source(EvidenceSource.REGIME)
        assert all(item.source is EvidenceSource.REGIME for item in regime_items)
        assert all(item.explanation for item in regime_items)
        assert all(item.payload is not None for item in regime_items)


class TestMissingDetection:
    def test_missing_required_source_detected(self, engines):
        # Provide only regime; require regime + universe → universe missing
        idx = _candles("NIFTY50", range(100, 160))
        regime = engines["regime"].assess("NIFTY50", idx, _snapshot(), as_of=AS_OF)
        bundle = engines["aggregator"].aggregate(
            as_of=AS_OF, regime=regime,
            required_sources=(EvidenceSource.REGIME, EvidenceSource.UNIVERSE))
        assert not bundle.is_complete
        assert EvidenceSource.UNIVERSE.value in bundle.missing_sources
        assert EvidenceSource.REGIME.value not in bundle.missing_sources

    def test_complete_when_all_required_present(self, engines):
        bundle = engines["aggregator"].aggregate(
            as_of=AS_OF, **_full_inputs(engines),
            required_sources=(EvidenceSource.REGIME, EvidenceSource.UNIVERSE))
        assert bundle.is_complete
        assert bundle.missing_sources == ()

    def test_empty_aggregation(self, engines):
        bundle = engines["aggregator"].aggregate(as_of=AS_OF)
        assert bundle.items == ()
        assert bundle.present_sources == ()
        assert bundle.is_complete  # nothing required, nothing missing


class TestDeterminismAndImmutability:
    def test_deterministic_repeat(self, engines):
        inputs = _full_inputs(engines)
        a = engines["aggregator"].aggregate(as_of=AS_OF, **inputs)
        b = engines["aggregator"].aggregate(as_of=AS_OF, **inputs)
        assert a == b

    def test_bundle_items_immutable(self, engines):
        import dataclasses
        bundle = engines["aggregator"].aggregate(as_of=AS_OF, **_full_inputs(engines))
        with pytest.raises(dataclasses.FrozenInstanceError):
            bundle.items[0].reference_id = "x"

    def test_provenance_immutable(self, engines):
        bundle = engines["aggregator"].aggregate(as_of=AS_OF, **_full_inputs(engines))
        with pytest.raises(TypeError):
            bundle.provenance["REGIME"] = 99

    def test_aggregation_adds_no_scores_or_decisions(self, engines):
        # The bundle only carries EvidenceItems + provenance + missing — no score/decision fields.
        bundle = engines["aggregator"].aggregate(as_of=AS_OF, **_full_inputs(engines))
        assert set(bundle.__slots__) == {
            "bundle_id", "as_of", "items", "missing_sources", "provenance"}
