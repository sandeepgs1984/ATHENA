"""Unit tests for DecisionsService.get_decision_context (M-D4).

Covers external-link matching (GLOBAL / exact instrument / bare-symbol fallback),
calendar-context surfacing, and UNKNOWN-safe regime/market-health mapping —
independent of the HTTP layer.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from tests.conftest import rewrite_json

from athena.api.exceptions import DecisionNotFoundError
from athena.api.v1.providers.in_memory import InMemoryDecisionProvider
from athena.api.v1.services.decisions_service import DecisionsService
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction


def _seed_links(config_dir, links):
    rewrite_json(config_dir / "external_links.json", lambda d: d["links"].extend(links))


def _decision(instrument_id: str = "NSE:RELIANCE") -> Decision:
    return Decision(
        decision_id="dec-ctx-1",
        ts=datetime(2026, 7, 22, 9, 30, tzinfo=timezone.utc),
        run_id="run-ctx-1",
        cycle_id="cycle-ctx-1",
        instrument_id=instrument_id,
        direction=Direction.NONE,
        decision_type=DecisionType.WATCH,
        explanation="context test decision",
    )


@pytest.fixture()
def provider() -> InMemoryDecisionProvider:
    p = InMemoryDecisionProvider()
    p.decisions.append(_decision())
    return p


def test_context_not_found_raises(config_dir, provider):
    service = DecisionsService(provider, config_dir=config_dir)
    with pytest.raises(DecisionNotFoundError):
        service.get_decision_context("dec-missing")


def test_calendar_context_reflects_decision_date(config_dir, provider):
    service = DecisionsService(provider, config_dir=config_dir)
    ctx = service.get_decision_context("dec-ctx-1")
    assert ctx.decision_id == "dec-ctx-1"
    assert ctx.instrument_id == "NSE:RELIANCE"
    assert ctx.calendar.context_date == "2026-07-22"
    assert ctx.calendar.exchange == "NSE"


def test_regime_and_market_health_default_unknown(config_dir, provider):
    service = DecisionsService(provider, config_dir=config_dir)
    ctx = service.get_decision_context("dec-ctx-1")
    assert ctx.regime.status == "UNKNOWN"
    assert ctx.market_health.status == "UNKNOWN"


def test_external_links_global_always_included(config_dir, provider):
    _seed_links(config_dir, [{
        "instrument_id": "GLOBAL",
        "title": "NSE Circular Digest",
        "url": "https://example.com/nse-circulars",
        "source": "NSE",
        "added_by": "owner",
        "date_added": "2026-07-01",
    }])
    service = DecisionsService(provider, config_dir=config_dir)
    ctx = service.get_decision_context("dec-ctx-1")
    assert len(ctx.external_links) == 1
    assert ctx.external_links[0].title == "NSE Circular Digest"


def test_external_links_match_bare_symbol(config_dir, provider):
    _seed_links(config_dir, [{
        "instrument_id": "RELIANCE",
        "title": "Reliance FY26 Investor Day",
        "url": "https://example.com/reliance",
        "source": "Company IR",
        "added_by": "owner",
        "date_added": "2026-07-01",
    }])
    service = DecisionsService(provider, config_dir=config_dir)
    ctx = service.get_decision_context("dec-ctx-1")
    assert len(ctx.external_links) == 1
    assert ctx.external_links[0].source == "Company IR"


def test_external_links_exclude_other_instruments(config_dir, provider):
    _seed_links(config_dir, [{
        "instrument_id": "NSE:TCS",
        "title": "TCS earnings call",
        "url": "https://example.com/tcs",
        "source": "Company IR",
        "added_by": "owner",
        "date_added": "2026-07-01",
    }])
    service = DecisionsService(provider, config_dir=config_dir)
    ctx = service.get_decision_context("dec-ctx-1")
    assert ctx.external_links == []
