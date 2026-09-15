"""SI-P2E persisted ATHENA Decision presentation contracts."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

JS = Path("src/athena/api/static/js/08c-symbol-intelligence.js")
CSS = Path("src/athena/api/static/css/15-symbol-intelligence.css")
HTML = Path("src/athena/api/static/index.html")
DASHBOARD_CSS = Path("src/athena/api/static/dashboard.css")


def _render(bundle: dict[str, Any]) -> str:
    js = JS.read_text(encoding="utf-8")
    helpers = js[js.index("function siEscape") : js.index("function siAthenaView")]
    node = shutil.which("node")
    assert node is not None
    script = helpers + f"\nprocess.stdout.write(siDecisionCard({json.dumps(bundle)}));"
    return subprocess.run(
        [node, "-e", script], check=True, capture_output=True, text=True
    ).stdout


def _bundle() -> dict[str, Any]:
    return {
        "identity": {
            "resolved": True,
            "instrument_id": "NSE:WIPRO",
            "symbol": "WIPRO",
        },
        "sources": [
            {
                "source": "D1_CANDLES",
                "status": "CURRENT",
                "explanation": "Current D1",
            },
            {
                "source": "ATHENA_DECISION",
                "status": "CURRENT",
                "explanation": "Current persisted Decision",
            },
        ],
        "decision": {
            "present": True,
            "decision_id": "decision-wipro-1",
            "decision_type": "WATCH",
            "direction": "NONE",
            "ts": "2026-09-11T15:30:00+05:30",
            "explanation": "Hold / watch — persisted explanation.",
            "confidence_level": "MEDIUM",
            "depth": {"score": {"value": 68.25}},
            "gates": [
                {"gate": "DATA", "passed": True, "detail": "bundle complete"},
                {
                    "gate": "CONFIDENCE",
                    "passed": False,
                    "detail": "confidence 58.0 vs min 60",
                },
            ],
            "trade_plan": None,
            "plan_freshness": {"status": "NO_PLAN"},
        },
    }


def test_si_p2e_present_decision_uses_persisted_evidence_hierarchy() -> None:
    html = _render(_bundle())
    assert "Persisted ATHENA Decision" in html
    assert "<h2><span>Watch</span></h2>" in html
    assert "Decision as of 11 Sep 2026" in html
    assert "Medium" in html
    assert "68.3" in html
    assert "1 of 2 gates passed" in html
    assert "Hold / watch — persisted explanation." in html
    assert "Decision Evidence" in html
    assert "Why ATHENA decided this" not in html
    assert "Data quality" in html and "Confidence quality" in html
    assert "bundle complete" in html
    assert "confidence 58.0 vs min 60" in html
    assert 'class="si-decision-gate is-fail" open' in html
    assert "No persisted trade plan for this Decision." in html
    assert "/dashboard/decisions?decision=decision-wipro-1" in html
    assert 'data-si-jump="audit"' in html


def test_si_p2e_all_passed_does_not_invent_trade_causality() -> None:
    bundle = _bundle()
    bundle["decision"]["decision_type"] = "NO_TRADE"
    bundle["decision"]["explanation"] = "Persisted no-trade explanation."
    bundle["decision"]["gates"] = [
        {"gate": gate, "passed": True, "detail": f"{gate.lower()} persisted"}
        for gate in ("DATA", "EVIDENCE", "RISK", "EXPLAINABILITY", "CONFIDENCE", "MARKET")
    ]
    html = _render(bundle)
    assert "6 of 6 gates passed" in html
    assert "All passed" in html
    assert "Persisted no-trade explanation." in html
    assert "rejected because" not in html.lower()
    assert "gates caused" not in html.lower()


def test_si_p2e_trade_plan_renders_only_authoritative_targets_and_fields() -> None:
    bundle = _bundle()
    bundle["decision"].update(
        decision_type="TRADE",
        direction="LONG",
        trade_plan={
            "entry_low": 100,
            "entry_high": 102,
            "stop_loss": 96,
            "targets": [110],
            "position_size": 25,
            "risk_amount": 150,
            "risk_reward": 2.5,
            "valid_from": "2026-09-11T10:00:00+05:30",
            "valid_until": "2026-09-12T10:00:00+05:30",
        },
        plan_freshness={
            "status": "AGING",
            "summary": "Persisted plan is approaching its validity boundary.",
        },
    )
    html = _render(bundle)
    assert "<span>Trade</span>" in html
    assert 'class="si-decision-direction"' in html
    assert '<b aria-hidden="true">·</b> Long</span>' in html
    assert "Entry band" in html
    assert "₹100.00 \u2013 ₹102.00" in html
    assert "Stop loss" in html and "₹96.00" in html
    assert "Target 1" in html and "₹110.00" in html
    assert "Target 2" not in html and "Target 3" not in html
    assert "Support" not in html
    assert "2.50 : 1" in html
    assert "Position size" in html and ">25<" in html
    assert "Risk amount" in html and "₹150.00" in html
    assert "Persisted plan is approaching its validity boundary." in html


def test_si_p2e_missing_optional_numbers_and_gate_outcomes_fail_closed() -> None:
    bundle = _bundle()
    bundle["decision"].update(
        depth={"score": {"value": None}},
        gates=[
            {"gate": "DATA", "passed": True, "detail": "bundle complete"},
            {"gate": "MARKET", "detail": "outcome was not persisted"},
        ],
        trade_plan={
            "entry_low": 100,
            "entry_high": None,
            "stop_loss": None,
            "targets": [110, None],
            "position_size": None,
            "risk_amount": None,
            "risk_reward": None,
            "valid_from": "2026-09-11T10:00:00+05:30",
            "valid_until": None,
        },
    )
    html = _render(bundle)
    assert "Persisted score" not in html
    assert "1 unavailable" in html
    assert 'class="si-decision-gate is-unavailable"' in html
    assert ">Unavailable<" in html
    assert "outcome was not persisted" in html
    assert "Entry band" not in html
    assert "Stop loss" not in html
    assert "Target 1" in html and "₹110.00" in html
    assert "Target 2" not in html
    assert "Risk / reward" not in html
    assert "Position size" not in html
    assert "Risk amount" not in html
    assert "Valid from" in html and "11 Sep 2026" in html
    assert "Valid until" not in html
    assert "0.00 : 1" not in html


def test_si_p2e_no_decision_and_invalid_symbol_are_distinct() -> None:
    missing = _bundle()
    missing["decision"] = {
        "present": False,
        "null_reason": "NO_DECISION / NOT_ANALYZED",
    }
    html = _render(missing)
    assert "No persisted decision" in html
    assert "Stock 360 research remains available" in html
    assert 'data-si-jump="stock-360"' in html
    assert "Generate Decision" not in html and "Validate Decision" not in html

    invalid = _bundle()
    invalid["identity"] = {"resolved": False, "query": "BAD"}
    invalid["decision"] = {"present": False}
    invalid_html = _render(invalid)
    assert "Symbol unavailable" in invalid_html
    assert "No persisted decision" not in invalid_html
    assert "decision-wipro-1" not in invalid_html


def test_si_p2e_direction_is_rendered_only_from_persisted_evidence() -> None:
    none_direction = _bundle()
    none_direction["decision"]["direction"] = "NONE"
    none_html = _render(none_direction)
    assert "si-decision-direction" not in none_html
    assert "Long" not in none_html and "Short" not in none_html

    missing_direction = _bundle()
    missing_direction["decision"].pop("direction")
    missing_html = _render(missing_direction)
    assert "si-decision-direction" not in missing_html
    assert "Long" not in missing_html and "Short" not in missing_html


def test_si_p2e_stale_decision_and_stale_d1_are_independent() -> None:
    bundle = _bundle()
    bundle["sources"][0].update(status="STALE", explanation="D1 is old")
    bundle["sources"][1].update(
        status="STALE",
        explanation="Latest Decision is dated 2026-09-10; expected 2026-09-11.",
    )
    html = _render(bundle)
    assert "Decision is stale." in html
    assert "Latest Decision is dated 2026-09-10; expected 2026-09-11." in html
    assert "Completed-D1 evidence is stale." in html
    assert "historical evidence" in html


def test_si_p2e_keeps_stock360_portfolio_darvax_and_request_boundaries() -> None:
    js = JS.read_text(encoding="utf-8")
    decision_fn = js[js.index("function siDecisionCard") : js.index("function siAthenaView")]
    for forbidden in (
        "SMA20",
        "SMA50",
        "SuperTrend",
        "RSI",
        "Volume",
        "Portfolio",
        "DarvaX",
    ):
        assert forbidden not in decision_fn
    assert 'method: "POST"' in js
    assert 'siSetInFlight(analyze ? "ANALYZE" : "GET", needle)' in js
    assert "DecisionEngine" not in js
    assert '${siDecisionCard(bundle)}' in js
    assert "siDecisionCard(bundle.decision)" not in js


def test_si_p2e_responsive_contract_and_asset_pin() -> None:
    css = CSS.read_text(encoding="utf-8")
    assert ".si-decision-experience" in css
    assert ".si-decision-layout" in css
    assert ".si-decision-gates" in css
    assert "@media (max-width: 720px)" in css
    assert "grid-template-columns: minmax(0, 1fr);" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in css
    assert "#app:has(#tab-symbol-intelligence.active) .workspace-viewport" in css
    assert "overflow-x: hidden;" in css
    assert ".si-id-session strong" in css
    assert "width: 100%;" in css

    html = HTML.read_text(encoding="utf-8")
    dashboard_css = DASHBOARD_CSS.read_text(encoding="utf-8")
    assert "dashboard.css?v=9.277.0" in html
    assert "dashboard.js?v=9.277.0" in html
    assert "css/15-symbol-intelligence.css?v=9.277.0" in dashboard_css
