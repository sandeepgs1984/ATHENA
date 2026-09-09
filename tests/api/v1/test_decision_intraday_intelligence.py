"""GET /decisions/{decision_id}/intraday-intelligence (ID-11).

Proves the Owner-facing read model composes the frozen EntryQualification ->
EntryActionability -> PositionSizing -> LivePlanSupervision chain correctly,
never fabricates a domain state for a genuine infrastructure failure, never
converts a non-current EntryActionability's real engine verdicts
(NOT_SIZED/NOT_APPLICABLE + UPSTREAM_NOT_CURRENT) into UNAVAILABLE, never
writes anything, and never exposes `total_deployable_capital`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.dependencies import get_decision_provider
from athena.api.security.models import Role
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction, Timeframe
from athena.domain.market import Candle, Instrument
from athena.intraday import (
    DEFAULT_METHODOLOGY_VERSION as EQ_DEFAULT_METHODOLOGY_VERSION,
)
from athena.intraday import (
    ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION,
    EntryActionability,
    EntryActionabilityReasonCode,
    EntryActionabilityState,
    EntryEvidenceFinality,
    EntryLocationContext,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationState,
    EntryReference,
    EntryReferenceBasis,
    InvalidationBasis,
    OperativeInvalidation,
    RewardBasis,
    RewardReference,
)

IST = ZoneInfo("Asia/Kolkata")
IID = "NSE:TEST"
DAY = date(2026, 3, 2)
EQ_AS_OF = datetime(2026, 3, 2, 9, 40, tzinfo=IST)
EA_AS_OF = datetime(2026, 3, 2, 9, 45, tzinfo=IST)
EVIDENCE_AS_OF = datetime(2026, 3, 2, 9, 45, tzinfo=IST)
READ_NOW = datetime(2026, 3, 2, 9, 50, tzinfo=IST)


@pytest.fixture(autouse=True)
def _reset_decision_provider() -> None:
    """The default `_decision_provider` is a process-wide singleton
    (`api/dependencies.py`) -- clear it before/after each test in this file
    so decisions from one test/file never leak into another."""
    get_decision_provider().decisions.clear()  # type: ignore[attr-defined]
    yield
    get_decision_provider().decisions.clear()  # type: ignore[attr-defined]


def _repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "id11-api.db")
    r.initialize()
    return r


def _trade_plan() -> TradePlan:
    return TradePlan(
        entry_low=Decimal("99"), entry_high=Decimal("101"), stop_loss=Decimal("95"),
        targets=(Decimal("110"),), position_size=1, risk_amount=Decimal("500"),
        risk_reward=Decimal("2.0"), valid_from=EA_AS_OF, valid_until=EA_AS_OF + timedelta(hours=6),
    )


def _decision(decision_id: str = "decision-1", **overrides: object) -> Decision:
    fields: dict[str, object] = dict(
        decision_id=decision_id, ts=EA_AS_OF, run_id="run-1", cycle_id="cycle-1",
        decision_type=DecisionType.TRADE, explanation="test decision", instrument_id=IID,
        direction=Direction.LONG, trade_plan=_trade_plan(),
    )
    fields.update(overrides)
    return Decision(**fields)  # type: ignore[arg-type]


def _eq(decision_id: str = "decision-1", **overrides: object) -> EntryQualification:
    fields: dict[str, object] = dict(
        instrument_id=IID, session_date=DAY, as_of=EQ_AS_OF, run_id="run-1", cycle_id="cycle-1",
        decision_id=decision_id, decision_type=DecisionType.TRADE,
        state=EntryQualificationState.QUALIFIED,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        confirmation=EntryQualificationConfirmation.CONFIRMED_BY_POLICY,
        reason_codes=(), evidence_refs=(), methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        config_snapshot_id=None, explanation="test eq",
    )
    fields.update(overrides)
    return EntryQualification(**fields)  # type: ignore[arg-type]


def _actionable_ea(decision_id: str = "decision-1", **overrides: object) -> EntryActionability:
    fields: dict[str, object] = dict(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id=decision_id, entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF,
        entry_actionability_methodology_version=ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION,
        decision_type=DecisionType.TRADE, direction=Direction.LONG,
        entry_qualification_state=EntryQualificationState.QUALIFIED, run_id="run-1", cycle_id="cycle-1",
        state=EntryActionabilityState.ACTIONABLE, reason_codes=(),
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        evidence_as_of=EVIDENCE_AS_OF,
        entry_reference=EntryReference(price=Decimal("100.00"), basis=EntryReferenceBasis.QUALIFYING_M5_CLOSE),
        entry_location_context=EntryLocationContext(vwap=Decimal("99.50"), vwap_deviation_pct=Decimal("0.50")),
        operative_invalidation=OperativeInvalidation(level=Decimal("98.00"), basis=InvalidationBasis.VWAP_LOSS),
        reward=RewardReference(
            t1_price=Decimal("101.00"), t2_price=Decimal("101.50"), basis=RewardBasis.GOAL_BANDS_ONLY,
            reward_risk_to_t1=Decimal("0.5"), reward_risk_to_t2=Decimal("0.75"),
        ),
        opening_range_context=None, evaluated_at=EA_AS_OF, explanation="actionable test",
    )
    fields.update(overrides)
    return EntryActionability(**fields)  # type: ignore[arg-type]


def _m5(ts: datetime, *, close: str) -> Candle:
    c = Decimal(close)
    return Candle(
        instrument_id=IID, timeframe=Timeframe.M5, ts_open=ts,
        open=c, high=c + Decimal("0.2"), low=c - Decimal("0.2"), close=c,
        volume=10_000, source="test",
    )


def _register_decision(client: TestClient, repo: SqliteRepository, decision: Decision) -> None:
    """Registers `decision` both in the real repository (required by
    `save_entry_qualification`/`save_entry_actionability`'s own Decision-
    binding FK check) and in the in-memory `DecisionProvider` the service's
    `get_decision(decision_id)` call actually reads -- the two must name
    the identical Decision."""
    repo.save_decision(decision)
    get_decision_provider().decisions.append(decision)  # type: ignore[attr-defined]
    client.app.state.sqlite_repo = repo


def _set_read_clock(client: TestClient, instant: datetime) -> None:
    """Injects a deterministic read-time instant for
    `DecisionsService.get_intraday_intelligence` (ID-11 source-review
    correction: the endpoint has no public `as_of`/`checkpoint`/`replay`
    query parameter -- it always reads the service's own current-clock
    instant). Mirrors the EMR router's own `request.app.state.emr_clock`
    convention."""
    client.app.state.decisions_clock = lambda: instant


def _url(decision_id: str) -> str:
    return f"/api/v1/decisions/{decision_id}/intraday-intelligence"


class TestIntradayIntelligenceHappyPath:
    def test_actionable_current_long_full_chain(self, client: TestClient, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _register_decision(client, repo, _decision())
        repo.upsert_instrument(
            Instrument(instrument_id=IID, symbol="TEST", exchange="NSE", series="EQ", status="ACTIVE", lot_size=1)
        )
        repo.add_candles(
            [_m5(EVIDENCE_AS_OF, close="100.1"), _m5(EVIDENCE_AS_OF + timedelta(minutes=5), close="100.2")]
        )
        eq = _eq()
        repo.save_entry_qualification(eq, persisted_at=EQ_AS_OF)
        ea = _actionable_ea()
        repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)

        _set_read_clock(client, READ_NOW)
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get(_url("decision-1"), headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["qualification"]["state"] == "QUALIFIED"
        assert data["qualification"]["coherence"] == "COHERENT"
        assert data["actionability"]["state"] == "ACTIONABLE"
        assert data["actionability"]["currentness"] == "CURRENT"
        assert data["actionability"]["entry_reference"] == "100.00"
        assert data["actionability"]["t1"] == "101.00"
        # The real config/position_sizing_policy.json is live in this repo
        # (total_deployable_capital=1,000,000; risk_budget_per_trade_pct=0.50%;
        # max_position_value_pct=15.00%) -- with entry=100, invalidation=98
        # (per_share_risk=2): risk_quantity=floor(5000/2)=2500,
        # max_value_quantity=floor(150000/100)=1500,
        # theoretical_capital_quantity=floor(1000000/100)=10000 -> the
        # MAX_POSITION_VALUE constraint binds at 1500.
        assert data["sizing"]["state"] == "SIZED"
        assert data["sizing"]["suggested_quantity"] == "1500"
        assert data["sizing"]["binding_constraint"] == "MAX_POSITION_VALUE"
        assert data["supervision"]["state"] in ("VALID", "INVALIDATED")
        # Privacy: total_deployable_capital must never appear anywhere.
        assert "total_deployable_capital" not in response.text
        repo.close()

    def test_watch_bound_not_actionable_remains_visible(self, client: TestClient, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _register_decision(
            client, repo, _decision(decision_type=DecisionType.WATCH, direction=Direction.NONE, trade_plan=None)
        )
        repo.upsert_instrument(
            Instrument(instrument_id=IID, symbol="TEST", exchange="NSE", series="EQ", status="ACTIVE", lot_size=1)
        )
        eq = _eq(decision_type=DecisionType.WATCH, state=EntryQualificationState.NOT_YET)
        repo.save_entry_qualification(eq, persisted_at=EQ_AS_OF)
        ea = EntryActionability(
            instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
            decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
            entry_actionability_as_of=EA_AS_OF,
            entry_actionability_methodology_version=ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION,
            decision_type=DecisionType.WATCH, direction=Direction.NONE,
            entry_qualification_state=EntryQualificationState.NOT_YET, run_id="run-1", cycle_id="cycle-1",
            state=EntryActionabilityState.NOT_ACTIONABLE,
            reason_codes=(EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,),
            evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
            evidence_as_of=None, entry_reference=None, entry_location_context=None,
            operative_invalidation=None, reward=None, opening_range_context=None,
            evaluated_at=EA_AS_OF, explanation="watch not actionable",
        )
        repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)

        _set_read_clock(client, READ_NOW)
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get(_url("decision-1"), headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["actionability"]["state"] == "NOT_ACTIONABLE"
        assert data["actionability"]["reason"] == "UPSTREAM_DECISION_NOT_TRADE"
        repo.close()


class TestIntradayIntelligenceNonCurrentSemantics:
    def test_stale_ea_yields_real_engine_verdicts_never_unavailable(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """A genuinely stale EA (evidence older than the frozen 600s
        currentness band) must reproduce the frozen engines' own real
        NOT_SIZED/NOT_APPLICABLE + UPSTREAM_NOT_CURRENT verdicts -- never a
        fabricated UNAVAILABLE (ID-11 design contract §8). SUPERSEDED is
        proven distinct in TestIntradayIntelligenceSupersededSemantics
        below, and at the composition level in
        test_intraday_composition.py.
        """
        repo = _repo(tmp_path)
        _register_decision(client, repo, _decision())
        repo.upsert_instrument(
            Instrument(instrument_id=IID, symbol="TEST", exchange="NSE", series="EQ", status="ACTIVE", lot_size=1)
        )
        eq = _eq()
        repo.save_entry_qualification(eq, persisted_at=EQ_AS_OF)
        ea = _actionable_ea()
        repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)

        # 20 minutes past evidence_as_of (9:45) -- well beyond the frozen
        # 600s/10-minute currentness band.
        stale_read_time = EVIDENCE_AS_OF + timedelta(minutes=20)
        _set_read_clock(client, stale_read_time)
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get(_url("decision-1"), headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["actionability"]["currentness"] == "STALE"
        assert data["sizing"]["state"] == "NOT_SIZED"
        assert data["sizing"]["reason"] == "UPSTREAM_NOT_CURRENT"
        assert data["supervision"]["state"] == "NOT_APPLICABLE"
        assert data["supervision"]["reason"] == "UPSTREAM_NOT_CURRENT"
        # Upstream-echoed risk geometry is still present for explainability.
        assert data["actionability"]["entry_reference"] == "100.00"
        repo.close()

    def test_unresolvable_decision_id_returns_404(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get(_url("nope"), headers=headers)
        assert response.status_code == 404

    def test_missing_repository_returns_503_not_domain_state(self, client: TestClient) -> None:
        # Explicitly no repository at all -- the harness's own `create_app()`
        # otherwise wires a real (test-redirected) one by default.
        client.app.state.sqlite_repo = None
        get_decision_provider().decisions.append(_decision())  # type: ignore[attr-defined]
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get(_url("decision-1"), headers=headers)
        assert response.status_code == 503
        assert "sizing" not in response.json()

    def test_missing_instrument_returns_500_not_400_or_domain_state(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        repo = _repo(tmp_path)
        _register_decision(client, repo, _decision())
        # Insert the instrument only long enough to satisfy save_entry_*'s
        # own binding checks, then remove it -- reproducing "the canonical
        # instrument catalog no longer has this instrument" at read time.
        repo.upsert_instrument(
            Instrument(instrument_id=IID, symbol="TEST", exchange="NSE", series="EQ", status="ACTIVE", lot_size=1)
        )
        eq = _eq()
        repo.save_entry_qualification(eq, persisted_at=EQ_AS_OF)
        ea = _actionable_ea()
        repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)
        repo._write_many("DELETE FROM instruments WHERE instrument_id=?", [(IID,)])

        _set_read_clock(client, READ_NOW)
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get(_url("decision-1"), headers=headers)
        assert response.status_code == 500
        body = response.json()
        assert "sizing" not in body
        assert "NOT_SIZED" not in response.text
        assert "UNAVAILABLE" not in response.text
        repo.close()


class TestIntradayIntelligenceSupersededSemantics:
    def test_superseded_ea_yields_real_engine_verdicts_never_unavailable(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """An EntryActionability bound to an OLDER EntryQualification
        observation for the same Decision must remain reachable once a
        NEWER coherent EntryQualification exists for that same Decision --
        `is_currently_usable` (never DTO/service logic) must then classify
        it SUPERSEDED, and the frozen downstream engines must still return
        their real NOT_SIZED/NOT_APPLICABLE + UPSTREAM_NOT_CURRENT
        verdicts, exactly like STALE. It must NOT be reported as
        EntryActionability UNAVAILABLE merely because the EA's own bound
        EQ identity is no longer the current one (ID-11 source-review
        correction).
        """
        repo = _repo(tmp_path)
        _register_decision(client, repo, _decision())
        repo.upsert_instrument(
            Instrument(instrument_id=IID, symbol="TEST", exchange="NSE", series="EQ", status="ACTIVE", lot_size=1)
        )

        eq1 = _eq()
        repo.save_entry_qualification(eq1, persisted_at=EQ_AS_OF)
        ea1 = _actionable_ea()
        repo.save_entry_actionability(ea1, persisted_at=EA_AS_OF)

        # A newer, coherent EntryQualification observation for the SAME
        # Decision -- ea1 above remains bound to eq1's own (now
        # superseded) identity, so it must classify SUPERSEDED, never
        # silently vanish into UNAVAILABLE.
        eq2_as_of = EQ_AS_OF + timedelta(minutes=15)
        eq2 = _eq(as_of=eq2_as_of)
        repo.save_entry_qualification(eq2, persisted_at=eq2_as_of)

        read_now = eq2_as_of + timedelta(minutes=5)
        _set_read_clock(client, read_now)
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get(_url("decision-1"), headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["qualification"]["state"] == "QUALIFIED"
        assert data["qualification"]["coherence"] == "COHERENT"
        # ea1's real persisted methodology state/evidence is preserved for
        # explainability -- never fabricated UNAVAILABLE.
        assert data["actionability"]["state"] == "ACTIONABLE"
        assert data["actionability"]["currentness"] == "SUPERSEDED"
        assert data["actionability"]["entry_reference"] == "100.00"
        assert data["sizing"]["state"] == "NOT_SIZED"
        assert data["sizing"]["reason"] == "UPSTREAM_NOT_CURRENT"
        assert data["supervision"]["state"] == "NOT_APPLICABLE"
        assert data["supervision"]["reason"] == "UPSTREAM_NOT_CURRENT"
        repo.close()


class TestIntradayIntelligenceAbsence:
    def test_no_entry_qualification_renders_unavailable(self, client: TestClient, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _register_decision(client, repo, _decision())

        _set_read_clock(client, READ_NOW)
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get(_url("decision-1"), headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["qualification"]["state"] == "UNAVAILABLE"
        assert data["qualification"]["coherence"] == "UNAVAILABLE"
        assert data["actionability"]["state"] == "UNAVAILABLE"
        assert data["sizing"]["state"] == "UNAVAILABLE"
        assert data["supervision"]["state"] == "UNAVAILABLE"
        repo.close()
