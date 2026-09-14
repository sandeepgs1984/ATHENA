"""SI-P1 Symbol Intelligence composer tests."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import pytest

from athena.api.exceptions import DecisionNotFoundError
from athena.api.v1.dtos.decisions import (
    DecisionAnalysisDTO,
    DecisionDTO,
    DecisionMetadataDTO,
)
from athena.api.v1.dtos.symbol_intelligence import SiLiveQuoteDTO
from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.store.repository import SqliteRepository
from athena.data.validation.calendar_expectations import latest_trading_day_on_or_before
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction, Timeframe
from athena.domain.market import Candle, Instrument
from athena.symbol_intelligence.composer import SymbolIntelligenceComposer
from athena.symbol_intelligence.d1_adapter import SiD1AdapterResult, SiStructuralZone

IST = ZoneInfo("Asia/Kolkata")
CONFIG = Path("config")
HELD = "NSE:MARKSANS"
OTHER = "NSE:INFY"


class StubDecisions:
    def __init__(self, dto: DecisionDTO) -> None:
        self._dto = dto

    def get_decision(self, decision_id: str) -> DecisionDTO:
        return self._dto

    def get_trade_plan_freshness(self, decision_id: str, *, as_of=None):
        return None

    def get_decision_depth(self, decision_id: str):
        raise DecisionNotFoundError(decision_id)

    def get_intraday_intelligence(self, decision_id: str):
        raise DecisionNotFoundError(decision_id)


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    db = SqliteRepository(tmp_path / "si.db")
    db.initialize()
    yield db
    db.close()


def _expected_session(read_as_of: datetime):
    cfg = load_config(CONFIG)
    calendar = CalendarEngine.from_config_dir(CONFIG, cfg.market)
    return latest_trading_day_on_or_before(calendar, read_as_of.astimezone(IST).date())


def _instrument(instrument_id: str, symbol: str, exchange: str = "NSE") -> Instrument:
    return Instrument(
        instrument_id=instrument_id,
        symbol=symbol,
        exchange=exchange,
        series="EQ",
        name=symbol,
        sector="PHARMA",
    )


def _d1_bars(instrument_id: str, last_day, count: int = 60) -> list[Candle]:
    candles: list[Candle] = []
    day = last_day
    produced = 0
    while produced < count:
        if day.weekday() < 5:
            close = Decimal("100") + Decimal(produced)
            ts = datetime.combine(day, time(9, 15), tzinfo=IST)
            candles.append(
                Candle(
                    instrument_id=instrument_id,
                    timeframe=Timeframe.D1,
                    ts_open=ts,
                    open=close,
                    high=close + Decimal("2"),
                    low=close - Decimal("2"),
                    close=close,
                    volume=10_000 + produced,
                    source="test",
                )
            )
            produced += 1
        day = day - timedelta(days=1)
    candles.reverse()
    return candles


def _holding(repo: SqliteRepository, instrument_id: str) -> None:
    conn = repo._conn  # type: ignore[attr-defined]
    conn.execute(
        """
        INSERT INTO portfolio_imports (
            import_id, filename, source, uploaded_at, parser_version, status,
            total_rows, accepted_rows, rejected_rows, unresolved_rows, ambiguous_rows
        )
        VALUES ('digest-import', 'holdings.csv', 'generic', '2026-09-02T10:00:00+00:00',
            'v1', 'CONFIRMED', 1, 1, 0, 0, 0)
        """
    )
    conn.execute(
        """
        INSERT INTO portfolio_holdings (
            holding_id, instrument_id, quantity, avg_price, imported_at, updated_at,
            source_import_id, source_row_id
        ) VALUES (?, ?, 10, '80.00', '2026-09-02T10:00:00+00:00',
            '2026-09-02T10:00:00+00:00', 'digest-import', '1')
        """,
        (f"hold-{instrument_id}", instrument_id),
    )
    conn.commit()


def _decision_dto(instrument_id: str, ts: datetime) -> DecisionDTO:
    return DecisionDTO(
        metadata=DecisionMetadataDTO(
            decision_id="d-si-1",
            ts=ts,
            run_id="run-si",
            cycle_id="cycle-si",
            instrument_id=instrument_id,
            direction="NONE",
            decision_type="WATCH",
        ),
        analysis=DecisionAnalysisDTO(),
        trade_plan=None,
        explanation="persisted watch",
    )


def _composer(
    repo: SqliteRepository,
    dto: DecisionDTO | None,
    now: datetime,
    *,
    d1_adapter=None,
    hydrator=None,
    live_quote_fn=None,
) -> SymbolIntelligenceComposer:
    return SymbolIntelligenceComposer(
        repo,
        config_dir=CONFIG,
        decisions_service=None if dto is None else StubDecisions(dto),
        my_portfolio_service=None,
        now_fn=lambda: now,
        d1_adapter=d1_adapter,
        hydrator=hydrator,
        live_quote_fn=live_quote_fn,
    )


def test_held_symbol_with_decision_and_d1(repo: SqliteRepository, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    expected = _expected_session(now)
    repo.upsert_instrument(_instrument(HELD, "MARKSANS"))
    repo.add_candles(_d1_bars(HELD, expected))
    ts = datetime.combine(expected, time(15, 30), tzinfo=IST)
    repo.save_decision(
        Decision(
            decision_id="d-si-1",
            ts=ts,
            run_id="run-si",
            cycle_id="cycle-si",
            decision_type=DecisionType.WATCH,
            explanation="persisted watch",
            instrument_id=HELD,
            direction=Direction.NONE,
        )
    )
    _holding(repo, HELD)
    monkeypatch.setattr(
        "athena.symbol_intelligence.composer.darvax_activation_requested",
        lambda _cfg: True,
    )
    writes: list[str] = []
    monkeypatch.setattr(SqliteRepository, "save_decision", lambda *a, **k: writes.append("decision"))
    monkeypatch.setattr(SqliteRepository, "add_candles", lambda *a, **k: writes.append("candles"))

    bundle = _composer(repo, _decision_dto(HELD, ts), now).compose(HELD)
    assert writes == []
    assert bundle.identity.resolved is True
    assert bundle.identity.ingested is True
    assert bundle.decision.present is True
    assert bundle.decision.decision_type == "WATCH"
    assert bundle.d1.present is True
    assert bundle.d1.available_history_high is not None
    assert bundle.portfolio is not None
    assert bundle.portfolio.status == "HELD"
    assert bundle.portfolio.quantity == 10
    assert bundle.darvax.status == "ENABLED_IFRAME"
    assert parse_qs(urlparse(bundle.darvax.iframe_url).query)["symbol"] == [HELD]
    assert urlparse(bundle.darvax.iframe_url).path == "/darvax/symbol360"
    assert bundle.d1.rsi_is_coherent is True
    assert bundle.d1.supertrend_is_coherent is True
    assert bundle.d1.volume_is_coherent is True
    assert bundle.d1.ath_is_coherent is True
    assert bundle.d1.symbol_trend_is_coherent is True
    named_rsi = next(item for item in bundle.momentum_quality.named_evidence if item.name == "rsi14")
    assert named_rsi.is_coherent is True
    assert named_rsi.value is not None
    assert bundle.darvax.experimental_label == "EXPERIMENTAL_UNVALIDATED"
    assert bundle.momentum_quality.value is None
    assert bundle.entry_quality.value is None
    assert bundle.fundamentals.status == "NOT_INGESTED"
    assert bundle.news.status == "NOT_INGESTED"
    lineages = {item.lineage for item in bundle.sources}
    assert lineages == {"D1_CANDLES", "ATHENA_DECISION", "PORTFOLIO", "DARVAX"}
    assert bundle.overall_freshness.status == "READY"
    assert any(item.lineage == "PORTFOLIO_STRUCTURAL_REVIEW" for item in bundle.entry_quality.named_evidence)


def test_non_held_never_receives_hold_semantics(repo: SqliteRepository) -> None:
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    expected = _expected_session(now)
    repo.upsert_instrument(_instrument(OTHER, "INFY", "NSE"))
    repo.add_candles(_d1_bars(OTHER, expected))
    bundle = _composer(repo, None, now).compose(OTHER)
    assert bundle.portfolio is not None
    assert bundle.portfolio.status == "NOT_HELD"
    assert bundle.portfolio.next_action is None
    assert bundle.portfolio.interpretation_status is None
    assert bundle.portfolio.daily_review_status is None
    assert bundle.decision.present is False
    assert bundle.decision.null_reason == "NO_DECISION / NOT_ANALYZED"


def test_no_d1_and_unresolved_and_stale(repo: SqliteRepository) -> None:
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    repo.upsert_instrument(_instrument(OTHER, "INFY"))
    empty = _composer(repo, None, now).compose(OTHER)
    assert empty.d1.present is False
    assert any(item.code == "NO_D1_DATA" for item in empty.unavailable)

    unresolved = _composer(repo, None, now).compose("NO_SUCH_TICKER")
    assert unresolved.identity.resolved is False
    assert unresolved.identity.resolution_code == "UNKNOWN_INSTRUMENT"
    assert unresolved.overall_freshness.status == "UNAVAILABLE"

    repo.add_candles(_d1_bars(OTHER, _expected_session(now) - timedelta(days=10), count=30))
    stale = _composer(repo, None, now).compose("INFY")
    assert stale.d1.present is True
    d1_src = next(item for item in stale.sources if item.source == "D1_CANDLES")
    assert d1_src.status == "STALE"


def test_darvax_disabled_and_search(repo: SqliteRepository, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    repo.upsert_instrument(_instrument(HELD, "MARKSANS"))
    repo.upsert_instrument(_instrument("BSE:MARKSANS", "MARKSANS", "BSE"))
    monkeypatch.setattr(
        "athena.symbol_intelligence.composer.darvax_activation_requested",
        lambda _cfg: False,
    )
    composer = _composer(repo, None, now)
    bundle = composer.compose(HELD)
    assert bundle.darvax.status == "DISABLED"
    darvax = next(item for item in bundle.sources if item.source == "DARVAX")
    assert darvax.status == "UNAVAILABLE"
    ambiguous = composer.compose("MARKSANS")
    assert ambiguous.identity.resolved is False
    assert ambiguous.identity.resolution_code == "AMBIGUOUS_SYMBOL"
    assert "Ambiguous" in (ambiguous.identity.unresolved_reason or "")
    hits = composer.search("MARK")
    assert {hit.instrument_id for hit in hits.hits} >= {HELD, "BSE:MARKSANS"}


def test_canonical_darvax_iframe_distinguishes_exchange(
    repo: SqliteRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    repo.upsert_instrument(_instrument(HELD, "MARKSANS"))
    repo.upsert_instrument(_instrument("BSE:MARKSANS", "MARKSANS", "BSE"))
    monkeypatch.setattr(
        "athena.symbol_intelligence.composer.darvax_activation_requested",
        lambda _cfg: True,
    )
    nse = _composer(repo, None, now).compose(HELD)
    bse = _composer(repo, None, now).compose("BSE:MARKSANS")
    assert parse_qs(urlparse(nse.darvax.iframe_url).query)["symbol"] == ["NSE:MARKSANS"]
    assert parse_qs(urlparse(bse.darvax.iframe_url).query)["symbol"] == ["BSE:MARKSANS"]
    assert "MARKSANS" in nse.darvax.iframe_url
    assert nse.darvax.iframe_url != bse.darvax.iframe_url


class _IncoherentD1:
    def evaluate(self, **kwargs):
        session = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
        return SiD1AdapterResult(
            latest_session=session,
            latest_open=Decimal("10"),
            latest_high=Decimal("11"),
            latest_low=Decimal("9"),
            latest_close=Decimal("10"),
            latest_volume=1000,
            adjusted=False,
            candles_used=5,
            rsi_value=Decimal("55"),
            rsi_reason="OWNING_ENGINE_INCOHERENT",
            rsi_coherent=False,
            supertrend_direction="UP",
            supertrend_value=Decimal("9"),
            supertrend_reason="OWNING_ENGINE_INCOHERENT",
            supertrend_coherent=False,
            supertrend_version="supertrend-10-3-athena-v0",
            volume_latest=1000,
            volume_ma=Decimal("800"),
            volume_reason="OWNING_ENGINE_INCOHERENT",
            volume_coherent=False,
            available_history_high=Decimal("20"),
            available_history_high_session=session,
            latest_high_exceeds_prior_history=False,
            latest_close_above_prior_history_high=False,
            ath_reason="OWNING_ENGINE_INCOHERENT",
            ath_coherent=False,
            ath_adjusted_history=False,
            symbol_trend="UP",
            symbol_trend_reason="OWNING_ENGINE_INCOHERENT",
            symbol_trend_coherent=False,
            fast_sma=Decimal("10"),
            slow_sma=Decimal("9"),
            support_1=SiStructuralZone(
                lower=Decimal("8"), upper=Decimal("8.5"), role="SUPPORT"
            ),
            major_support=None,
            review_trigger=None,
            target_1=None,
            target_2=None,
            target_3=None,
            structural_reason_codes=("STRUCTURAL_EVIDENCE_UNAVAILABLE",),
            structural_coherent=False,
            expected_session=session.date(),
        )


def test_incoherent_d1_is_not_usable_named_evidence(repo: SqliteRepository) -> None:
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    repo.upsert_instrument(_instrument(OTHER, "INFY"))
    bundle = _composer(repo, None, now, d1_adapter=_IncoherentD1()).compose(OTHER)
    assert bundle.d1.rsi14 == Decimal("55")
    assert bundle.d1.rsi_is_coherent is False
    assert bundle.d1.rsi_reason == "OWNING_ENGINE_INCOHERENT"
    assert bundle.d1.structural_is_coherent is False
    assert bundle.d1.support_1 is not None
    named = {item.name: item for item in bundle.momentum_quality.named_evidence}
    assert named["rsi14"].value is None
    assert named["rsi14"].is_coherent is False
    assert named["rsi14"].reason == "OWNING_ENGINE_INCOHERENT"
    assert named["supertrend_10_3"].value is None
    assert named["symbol_d1_trend"].value is None
    structural = next(
        item for item in bundle.entry_quality.named_evidence if item.name == "structural_support_1"
    )
    assert structural.value is None
    assert structural.is_coherent is False
    assert "STRUCTURAL_EVIDENCE_UNAVAILABLE" in (structural.reason or "")
    assert bundle.momentum_quality.value is None
    assert bundle.entry_quality.value is None


def test_symbol_master_outside_universe_resolves_without_athena_artifacts(
    repo: SqliteRepository,
) -> None:
    from athena.symbols.catalog import build_symbol_records

    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    outside = _instrument("NSE:OUTSIDEX", "OUTSIDEX")
    repo.upsert_symbol_records(build_symbol_records([outside], observed_at=now, source="kite"))
    composer = _composer(repo, None, now)
    bundle = composer.compose("NSE:OUTSIDEX")
    assert bundle.identity.resolved is True
    assert bundle.identity.resolution_code == "VALID_INSTRUMENT"
    assert bundle.identity.catalog == "SYMBOL_MASTER"
    assert bundle.identity.ingested is False
    assert bundle.identity.instrument_id == "NSE:OUTSIDEX"
    assert any(item.code == "NO_D1_DATA" for item in bundle.unavailable)
    assert any(item.code == "NO_DECISION" for item in bundle.unavailable)
    assert "NOT_ANALYZED" in next(
        item.detail for item in bundle.unavailable if item.code == "NO_DECISION"
    )
    assert bundle.decision.present is False
    assert bundle.d1.present is False
    assert bundle.portfolio is not None
    assert bundle.portfolio.status == "NOT_HELD"
    hits = composer.search("OUTSIDEX")
    assert any(hit.instrument_id == "NSE:OUTSIDEX" for hit in hits.hits)


def test_valid_ingested_symbol_with_d1_but_no_decision(repo: SqliteRepository) -> None:
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    expected = _expected_session(now)
    repo.upsert_instrument(_instrument(OTHER, "INFY"))
    repo.add_candles(_d1_bars(OTHER, expected))
    bundle = _composer(repo, None, now).compose(OTHER)
    assert bundle.identity.resolved is True
    assert bundle.identity.ingested is True
    assert bundle.d1.present is True
    assert bundle.decision.present is False
    assert bundle.decision.null_reason == "NO_DECISION / NOT_ANALYZED"
    assert any(item.code == "NO_DECISION" for item in bundle.unavailable)
    assert not any(item.code == "NO_D1_DATA" for item in bundle.unavailable)
    d1_src = next(item for item in bundle.sources if item.source == "D1_CANDLES")
    assert d1_src.status == "CURRENT"
    assert bundle.overall_freshness.status == "PARTIAL"
    assert "ATHENA Decision unavailable" in bundle.overall_freshness.explanation


def test_si_python_does_not_import_darvax_or_decision_engine() -> None:
    import ast

    paths = list(Path("src/athena/symbol_intelligence").glob("*.py"))
    paths.extend(
        [
            Path("src/athena/api/v1/routers/symbol_intelligence.py"),
            Path("src/athena/api/v1/services/symbol_intelligence_service.py"),
            Path("src/athena/api/v1/dtos/symbol_intelligence.py"),
        ]
    )
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("athena.darvax")
                    assert alias.name != "athena.decision.engine"
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("athena.darvax")
                assert node.module != "athena.decision.engine"
                if node.module.startswith("athena.decision"):
                    assert "engine" not in {alias.name for alias in node.names}


class _Hydrator:
    def __init__(self, *, needed: bool, outcome, write=None) -> None:
        self.needed = needed
        self.outcome = outcome
        self.write = write
        self.hydrate_calls: list[str] = []
        self.need_calls = 0

    def needs_refresh(self, instrument_id, *, expected_session, as_of, market_tz) -> bool:
        self.need_calls += 1
        return self.needed

    def hydrate(self, instrument_id, *, as_of):
        self.hydrate_calls.append(instrument_id)
        if self.write is not None:
            self.write()
        return self.outcome


def test_get_compose_does_not_hydrate_stale_d1(repo: SqliteRepository) -> None:
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    expected = _expected_session(now)
    repo.upsert_instrument(_instrument(OTHER, "INFY"))
    repo.add_candles(_d1_bars(OTHER, expected - timedelta(days=21), count=40))
    hydrator = _Hydrator(
        needed=True,
        outcome=None,
    )
    bundle = _composer(repo, None, now, hydrator=hydrator).compose(OTHER)
    assert hydrator.need_calls == 0
    assert hydrator.hydrate_calls == []
    assert next(item for item in bundle.sources if item.source == "D1_CANDLES").status == "STALE"
    assert bundle.hydration is not None
    assert bundle.hydration.attempted is False


def test_analyze_hydrates_then_rereads_d1(repo: SqliteRepository, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    expected = _expected_session(now)
    repo.upsert_instrument(_instrument(OTHER, "INFY"))
    repo.add_candles(_d1_bars(OTHER, expected - timedelta(days=21), count=40))
    from athena.symbol_intelligence.d1_hydrate import SiHydrationOutcome

    hydrator = _Hydrator(
        needed=True,
        outcome=SiHydrationOutcome(status="HYDRATED", detail="test hydrate", candles_written=10),
        write=lambda: repo.add_candles(_d1_bars(OTHER, expected, count=60)),
    )
    writes: list[str] = []
    monkeypatch.setattr(SqliteRepository, "save_decision", lambda *a, **k: writes.append("decision"))
    live = SiLiveQuoteDTO(
        present=True,
        last_price=Decimal("999.00"),
        change_pct=Decimal("1.25"),
    )
    bundle = _composer(repo, None, now, hydrator=hydrator, live_quote_fn=lambda _i: live).compose(
        OTHER, refresh_market=True
    )
    assert hydrator.hydrate_calls == [OTHER]
    assert writes == []
    assert bundle.d1.present is True
    assert next(item for item in bundle.sources if item.source == "D1_CANDLES").status == "CURRENT"
    assert bundle.hydration is not None
    assert bundle.hydration.status == "HYDRATED"
    assert bundle.live is not None
    assert bundle.live.present is True
    assert bundle.live.last_price == Decimal("999.00")
    assert bundle.live.quote_kind == "LATEST_QUOTE"
    assert bundle.live.market_state == "MARKET CLOSED"
    assert bundle.live.label == "LATEST QUOTE · MARKET CLOSED"
    assert bundle.overall_freshness.status == "PARTIAL"
    assert bundle.d1.close != bundle.live.last_price
    assert bundle.decision.present is False
    assert bundle.momentum_quality.value is None


def test_closed_market_quote_is_latest_not_live(repo: SqliteRepository) -> None:
    from athena.data.providers.kite_ltp import LiveQuoteView
    from athena.domain.market import Quote

    now = datetime(2026, 9, 13, 10, 0, tzinfo=IST)
    expected = _expected_session(now)
    repo.upsert_instrument(_instrument(OTHER, "INFY"))
    repo.add_candles(_d1_bars(OTHER, expected))
    view = LiveQuoteView(
        quote=Quote(
            instrument_id=OTHER,
            ts=now,
            last_price=Decimal("521.60"),
            volume=1000,
            source="kite",
        ),
        change_pct=Decimal("-2.64"),
    )
    bundle = _composer(repo, None, now, live_quote_fn=lambda _i: view).compose(
        OTHER, refresh_market=True
    )
    assert bundle.live is not None
    assert bundle.live.present is True
    assert bundle.live.quote_kind == "LATEST_QUOTE"
    assert bundle.live.market_state == "MARKET CLOSED"
    assert bundle.live.label == "LATEST QUOTE · MARKET CLOSED"
    assert "LIVE" not in bundle.live.label
    assert next(item for item in bundle.sources if item.source == "D1_CANDLES").status == "CURRENT"
    assert bundle.overall_freshness.status == "PARTIAL"


def test_open_market_quote_is_live(repo: SqliteRepository) -> None:
    from athena.data.providers.kite_ltp import LiveQuoteView
    from athena.domain.market import Quote

    now = datetime(2026, 9, 11, 13, 25, tzinfo=IST)
    expected = _expected_session(now)
    repo.upsert_instrument(_instrument(OTHER, "INFY"))
    repo.add_candles(_d1_bars(OTHER, expected))
    view = LiveQuoteView(
        quote=Quote(
            instrument_id=OTHER,
            ts=now,
            last_price=Decimal("521.60"),
            volume=1000,
            source="kite",
        ),
        change_pct=Decimal("-2.64"),
    )
    bundle = _composer(repo, None, now, live_quote_fn=lambda _i: view).compose(
        OTHER, refresh_market=True
    )
    assert bundle.live is not None
    assert bundle.live.quote_kind == "LIVE"
    assert bundle.live.market_state == "MARKET OPEN"
    assert bundle.live.label == "LIVE · MARKET OPEN"
    assert bundle.overall_freshness.status == "PARTIAL"


def test_analyze_hydration_failure_keeps_stale(repo: SqliteRepository) -> None:
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    expected = _expected_session(now)
    repo.upsert_instrument(_instrument(OTHER, "INFY"))
    repo.add_candles(_d1_bars(OTHER, expected - timedelta(days=21), count=40))
    from athena.symbol_intelligence.d1_hydrate import SiHydrationOutcome

    hydrator = _Hydrator(
        needed=True,
        outcome=SiHydrationOutcome(status="FAILED", detail="Kite refused D1 hydration."),
    )
    bundle = _composer(repo, None, now, hydrator=hydrator).compose(OTHER, refresh_market=True)
    assert hydrator.hydrate_calls == [OTHER]
    assert next(item for item in bundle.sources if item.source == "D1_CANDLES").status == "STALE"
    assert bundle.overall_freshness.status == "STALE"
    assert any(item.code == "D1_HYDRATION_FAILED" for item in bundle.unavailable)


def test_outside_universe_analyze_can_hydrate(repo: SqliteRepository) -> None:
    from athena.symbol_intelligence.d1_hydrate import SiHydrationOutcome
    from athena.symbols.catalog import build_symbol_records

    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    expected = _expected_session(now)
    outside = _instrument("NSE:TI", "TI")
    repo.upsert_symbol_records(build_symbol_records([outside], observed_at=now, source="kite"))
    hydrator = _Hydrator(
        needed=True,
        outcome=SiHydrationOutcome(status="HYDRATED", detail="outside", candles_written=60),
        write=lambda: (
            repo.upsert_instrument(outside),
            repo.add_candles(_d1_bars("NSE:TI", expected, count=60)),
        ),
    )
    bundle = _composer(repo, None, now, hydrator=hydrator).compose("NSE:TI", refresh_market=True)
    assert bundle.identity.resolved is True
    assert bundle.identity.catalog == "SYMBOL_MASTER"
    assert hydrator.hydrate_calls == ["NSE:TI"]
    assert bundle.d1.present is True
    assert bundle.decision.present is False


def test_hydrator_needs_refresh_detects_stale_and_current(repo: SqliteRepository) -> None:
    from athena.symbol_intelligence.d1_hydrate import SymbolIntelligenceD1Hydrator

    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    expected = _expected_session(now)
    repo.upsert_instrument(_instrument(OTHER, "INFY"))
    hydrator = SymbolIntelligenceD1Hydrator(
        repo,
        config_dir=CONFIG,
        ingest_fn=lambda **k: type("R", (), {"candles_written": 0})(),
    )
    assert hydrator.needs_refresh(OTHER, expected_session=expected, as_of=now, market_tz=IST) is True
    repo.add_candles(_d1_bars(OTHER, expected, count=5))
    assert hydrator.needs_refresh(OTHER, expected_session=expected, as_of=now, market_tz=IST) is False


def test_ui_keeps_audit_strings_out_of_primary_metrics() -> None:
    js = Path("src/athena/api/static/js/08c-symbol-intelligence.js").read_text(encoding="utf-8")
    assert "si-lineage" not in js
    assert "si-audit-table" in js
    assert "rsi_reason" not in js
    assert "DARVAX UNAVAILABLE" in js
    assert 'method: "POST"' in js
    assert "LIVE / CURRENT SESSION" not in js
    assert "function siMarketDataStatus" in js
    assert "function siCoverageStatus" in js
    assert 'function siQuoteCaption(live, d1)' in js
    assert '["LAST CLOSE", session === "—" ? "" : session, siEscape(market)]' in js
    assert "LIVE · MARKET OPEN" in js
