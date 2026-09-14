"""SI-P2D deterministic Written Summary presentation contracts."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

JS = Path("src/athena/api/static/js/08c-symbol-intelligence.js")
CSS = Path("src/athena/api/static/css/15-symbol-intelligence.css")
HTML = Path("src/athena/api/static/index.html")


def _js() -> str:
    return JS.read_text(encoding="utf-8")


def _base_bundle() -> dict[str, Any]:
    return {
        "identity": {"resolved": True, "instrument_id": "NSE:WIPRO", "symbol": "WIPRO"},
        "overall_freshness": {"status": "PARTIAL", "explanation": "No Decision"},
        "sources": [
            {
                "source": "D1_CANDLES",
                "status": "CURRENT",
                "as_of": "2026-09-11T00:00:00+05:30",
            }
        ],
        "d1": {
            "present": True,
            "latest_session": "2026-09-11T00:00:00+05:30",
            "close": 100,
            "symbol_trend": "UPTREND",
            "symbol_trend_is_coherent": True,
            "fast_sma": 102,
            "slow_sma": 98,
            "supertrend_direction": "BULLISH",
            "supertrend_is_coherent": True,
            "rsi14": 44.1,
            "rsi_is_coherent": True,
            "volume": 900,
            "volume_ma20": 1000,
            "volume_is_coherent": True,
            "structural_is_coherent": True,
            "support_1": {"lower": 90, "upper": 95},
            "major_support": {"lower": 85, "upper": 88},
            "review_trigger": {"lower": 101, "upper": 101},
            "target_1": {"lower": 106.5, "upper": 108},
            "target_2": {"lower": 110, "upper": 112},
            "target_3": {"lower": 115, "upper": 118},
        },
        "decision": {"present": False, "null_reason": "NO_DECISION / NOT_ANALYZED"},
        "portfolio": {"status": "NOT_HELD"},
        "fundamentals": {"status": "NOT_INGESTED"},
        "news": {"status": "NOT_INGESTED"},
        "darvax": {"status": "ENABLED_IFRAME"},
    }


def _run_summary(bundle: dict[str, Any], *, include_render: bool = False) -> dict[str, Any]:
    js = _js()
    helpers = js[js.index("function siEscape") : js.index("function siAuditTable")]
    date_key = js[js.index("function siChartDateKey") : js.index("function siChartCandle")]
    long_date = js[js.index("function siChartLongDate") : js.index("function siChartAxisZone")]
    node = shutil.which("node")
    assert node is not None
    payload = json.dumps(bundle)
    render = ", html: siCompleteReview(bundle)" if include_render else ""
    script = (
        helpers
        + date_key
        + long_date
        + f"""
const bundle = {payload};
const summary = siComposeResearchSummary(bundle);
process.stdout.write(JSON.stringify({{
  summary,
  frozen: Object.isFrozen(summary) && summary.statements.every(Object.isFrozen)
  {render}
}}));
"""
    )
    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _texts(result: dict[str, Any]) -> dict[str, str]:
    return {item["kind"]: item["text"] for item in result["summary"]["statements"]}


def test_si_p2d_golden_wipro_like_down_agreement_momentum_and_decision() -> None:
    bundle = _base_bundle()
    bundle["d1"].update(
        symbol_trend="DOWNTREND",
        supertrend_direction="BEARISH",
        rsi14=30.6,
        volume=1200,
    )
    bundle["decision"] = {
        "present": True,
        "decision_type": "NO_TRADE",
        "ts": "2026-09-11T15:30:00+05:30",
        "confidence_level": "HIGH",
        "depth": {"score": {"value": 35}},
        "gates": [{"passed": True} for _ in range(6)],
    }
    bundle["overall_freshness"]["status"] = "READY"

    result = _run_summary(bundle)
    texts = _texts(result)
    assert texts["STRUCTURE"] == (
        "Daily SMA structure and SuperTrend both indicate downward technical structure."
    )
    assert texts["MOMENTUM"] == (
        "RSI (14) is 30.6, and completed-D1 volume is above its 20-session average."
    )
    assert texts["ATHENA_DECISION"] == (
        "ATHENA has a persisted No Trade Decision as of 11 Sept 2026 with High confidence. "
        "Persisted score is 35.0 / 100, and 6 of 6 gates passed."
    )
    statements = {item["kind"]: item for item in result["summary"]["statements"]}
    assert statements["STRUCTURE"]["display_parts"] == ["SMA Down", "SuperTrend Down"]
    assert statements["MOMENTUM"]["display_parts"] == [
        "RSI 30.6",
        "Volume above 20-session average",
    ]
    assert statements["ATHENA_DECISION"]["display_parts"] == [
        "No Trade",
        "High confidence",
        "Score 35.0/100",
        "6/6 gates passed",
    ]
    assert statements["ATHENA_DECISION"]["display_meta"] == "Decision as of 11 Sept 2026"
    assert result["frozen"] is True


def test_si_p2d_up_agreement_and_ti_like_disagreement() -> None:
    up = _texts(_run_summary(_base_bundle()))
    assert up["STRUCTURE"] == (
        "Daily SMA structure and SuperTrend both indicate upward technical structure."
    )

    ti = _base_bundle()
    ti["identity"].update(instrument_id="NSE:TI", symbol="TI")
    ti["d1"].update(symbol_trend="UPTREND", supertrend_direction="BEARISH")
    disagreement = _texts(_run_summary(ti))
    assert disagreement["STRUCTURE"] == (
        "Daily SMA structure is Up, while SuperTrend is Down; the two measurements disagree."
    )
    assert "authoritative" not in disagreement["STRUCTURE"].lower()
    assert "uncertain" not in disagreement["STRUCTURE"].lower()


def test_si_p2d_unavailable_supertrend_and_rsi_are_compact_and_nonduplicative() -> None:
    bundle = _base_bundle()
    bundle["d1"].update(
        supertrend_direction=None,
        supertrend_is_coherent=False,
        rsi14=None,
        rsi_is_coherent=False,
    )
    texts = _texts(_run_summary(bundle))
    assert texts["STRUCTURE"] == "Daily SMA structure is Up; SuperTrend is unavailable."
    assert texts["MOMENTUM"] == (
        "Completed-D1 volume is below its 20-session average."
    )
    assert "RSI is unavailable." in texts["DATA_AVAILABILITY"]
    assert texts["DATA_AVAILABILITY"].count("SuperTrend") == 0


def test_si_p2d_level_rules_use_at_most_support_and_forward_observations() -> None:
    bundle = _base_bundle()
    levels = _texts(_run_summary(bundle))["LEVEL_POSITION"]
    assert levels == (
        "Completed D1 is 5.3% above Support 1 upper boundary. "
        "Review Trigger is 1.0% above completed-D1 close."
    )
    assert "Major Support" not in levels
    assert "Target 1" not in levels
    assert "Target 2" not in levels and "Target 3" not in levels

    fallback = _base_bundle()
    fallback["d1"]["support_1"] = None
    fallback["d1"]["review_trigger"] = None
    fallback_levels = _texts(_run_summary(fallback))["LEVEL_POSITION"]
    assert fallback_levels == (
        "Completed D1 is 13.6% above Major Support upper boundary. "
        "Target 1 is 6.5% above completed-D1 close."
    )


def test_si_p2d_decision_and_no_decision_variants_are_factual() -> None:
    missing = _texts(_run_summary(_base_bundle()))["ATHENA_DECISION"]
    assert missing == (
        "ATHENA has no persisted Decision for this symbol; Stock 360 technical research "
        "remains available."
    )
    missing_statement = next(
        item
        for item in _run_summary(_base_bundle())["summary"]["statements"]
        if item["kind"] == "ATHENA_DECISION"
    )
    assert missing_statement["display_parts"] == [
        "No persisted Decision",
        "Stock 360 research remains available",
    ]

    decision = _base_bundle()
    decision["decision"] = {
        "present": True,
        "decision_type": "WATCH",
        "ts": "2026-09-11T15:30:00+05:30",
        "confidence_level": "MEDIUM",
        "gates": [{"passed": True}, {"passed": False}],
    }
    text = _texts(_run_summary(decision))["ATHENA_DECISION"]
    assert text == (
        "ATHENA has a persisted Watch Decision as of 11 Sept 2026 with Medium confidence. "
        "1 of 2 gates passed."
    )
    assert "avoid" not in text.lower() and "wait" not in text.lower()


def test_si_p2d_acmesolar_like_portfolio_and_not_held_variants() -> None:
    held = _base_bundle()
    held["identity"].update(instrument_id="NSE:ACMESOLAR", symbol="ACMESOLAR")
    held["portfolio"] = {
        "status": "HELD",
        "quantity": 418,
        "avg_price": 408.35,
        "pnl_pct": -1.6,
        "interpretation_status": "HOLD",
        "next_action": "HOLD",
    }
    held_result = _run_summary(held, include_render=True)
    text = _texts(held_result)["PORTFOLIO"]
    assert text == (
        "This symbol is held in My Portfolio: 418 shares at an average price of ₹408.35. "
        "Current Portfolio P&L is -1.60%."
    )
    statement = next(
        item
        for item in held_result["summary"]["statements"]
        if item["kind"] == "PORTFOLIO"
    )
    assert statement["display_parts"] == ["418 shares", "Avg ₹408.35", "P&L -1.60%"]
    assert statement["source_refs"] == [
        "portfolio.status",
        "portfolio.quantity",
        "portfolio.avg_price",
        "portfolio.pnl_pct",
    ]
    assert "HOLD" not in text
    assert '<dt>Portfolio</dt>' in held_result["html"]
    assert "418 shares · Avg ₹408.35 · P&amp;L -1.60%" in held_result["html"]

    not_held_result = _run_summary(_base_bundle(), include_render=True)
    not_held = _texts(not_held_result)["PORTFOLIO"]
    assert not_held == "This symbol is not held in My Portfolio."
    not_held_statement = next(
        item
        for item in not_held_result["summary"]["statements"]
        if item["kind"] == "PORTFOLIO"
    )
    assert not_held_statement["source_refs"] == ["portfolio.status"]
    assert 'data-si-summary-kind="PORTFOLIO"' not in not_held_result["html"]
    assert "<dt>Portfolio</dt>" not in not_held_result["html"]


def test_si_p2d_ready_partial_stale_and_capability_availability() -> None:
    ready = _base_bundle()
    ready["overall_freshness"]["status"] = "READY"
    ready_text = _texts(_run_summary(ready))["DATA_AVAILABILITY"]
    assert ready_text == (
        "Data through 11 Sept 2026. Fundamentals and news/catalysts are not yet ingested."
    )

    partial = _base_bundle()
    partial["overall_freshness"]["status"] = "PARTIAL"
    partial_texts = _texts(_run_summary(partial))
    assert "no persisted Decision" in partial_texts["ATHENA_DECISION"]
    assert "Partial" not in partial_texts["DATA_AVAILABILITY"]

    stale = _base_bundle()
    stale["sources"][0]["status"] = "STALE"
    stale_text = _texts(_run_summary(stale))["DATA_AVAILABILITY"]
    assert stale_text.startswith("Completed-D1 evidence is stale through 11 Sept 2026.")
    assert "NOT_INGESTED" not in stale_text


def test_si_p2d_minimal_optional_evidence_uses_one_bounded_availability_note() -> None:
    bundle = _base_bundle()
    bundle["d1"].update(
        symbol_trend=None,
        symbol_trend_is_coherent=False,
        supertrend_direction=None,
        supertrend_is_coherent=False,
        rsi14=None,
        rsi_is_coherent=False,
        volume_ma20=None,
        volume_is_coherent=False,
        structural_is_coherent=False,
        support_1=None,
        major_support=None,
        review_trigger=None,
        target_1=None,
    )
    result = _run_summary(bundle)
    texts = _texts(result)
    assert "STRUCTURE" not in texts
    assert "MOMENTUM" not in texts
    assert "LEVEL_POSITION" not in texts
    assert texts["DATA_AVAILABILITY"] == (
        "Data through 11 Sept 2026. Some optional D1 measurements are unavailable. "
        "Fundamentals and news/catalysts are not yet ingested."
    )
    assert len(result["summary"]["primary"]) <= 4
    assert len(result["summary"]["supporting"]) <= 1
    assert len(result["summary"]["availability"]) <= 1


def test_si_p2d_invalid_symbol_generates_no_research_summary() -> None:
    bundle = _base_bundle()
    bundle["identity"] = {"resolved": False, "query": "NO_SUCH_TICKER"}
    result = _run_summary(bundle)
    assert result["summary"] == {
        "primary": [],
        "supporting": [],
        "availability": [],
        "statements": [],
    }


def test_si_p2d_statement_provenance_order_and_human_enum_formatting() -> None:
    result = _run_summary(_base_bundle())
    statements = result["summary"]["statements"]
    assert [item["kind"] for item in statements] == [
        "STRUCTURE",
        "MOMENTUM",
        "LEVEL_POSITION",
        "ATHENA_DECISION",
        "PORTFOLIO",
        "DATA_AVAILABILITY",
    ]
    assert all(item["source_refs"] for item in statements)
    assert all(item["display_parts"] for item in statements)
    assert statements[0]["as_of"] == "2026-09-11T00:00:00+05:30"
    assert "UPTREND" not in statements[0]["text"]
    assert "BULLISH" not in statements[0]["text"]


def test_si_p2d_generated_language_has_no_prediction_recommendation_or_mq_eq() -> None:
    cases = [_base_bundle()]
    down = _base_bundle()
    down["d1"].update(symbol_trend="DOWNTREND", supertrend_direction="BEARISH")
    cases.append(down)
    sparse = _base_bundle()
    sparse["d1"].update(rsi14=None, rsi_is_coherent=False)
    cases.append(sparse)
    corpus = " ".join(
        item["text"]
        for case in cases
        for item in _run_summary(case)["summary"]["statements"]
    )
    forbidden = (
        r"\blikely\b|\bexpected to\b|\bcould rally\b|\bmay fall\b|\blooks ready\b|"
        r"\bstrong upside\b|\bgood entry\b|\bbuy zone\b|\bsell zone\b|"
        r"\bbreakout likely\b|\breversal expected\b|\bMomentum Quality\b|"
        r"\bEntry Quality\b|\bbullish probability\b|\btrend score\b|"
        r"\bbecause\b|\btherefore\b|\brecommend(?:ation|ed)?\b"
    )
    assert re.search(forbidden, corpus, re.I) is None


def test_si_p2d_rendering_is_compact_traceable_accessible_and_responsive() -> None:
    result = _run_summary(_base_bundle(), include_render=True)
    html = result["html"]
    assert "<h3>Research brief</h3>" in html
    assert '<dl class="si-research-brief">' in html
    assert html.count('class="si-brief-row"') == 4
    assert html.count("si-review-meta") == 1
    assert "si-review-primary" not in html
    assert "si-review-support" not in html
    assert "<h4>" not in html
    labels = [html.index(f"<dt>{label}</dt>") for label in (
        "Structure", "Momentum", "Key Levels", "ATHENA"
    )]
    assert labels == sorted(labels)
    assert "SMA Up · SuperTrend Up" in html
    assert "RSI 44.1 · Volume below 20-session average" in html
    assert "D1 5.3% above Support 1 · Review Trigger 1.0% above D1 close" in html
    assert "No persisted Decision · Stock 360 research remains available" in html
    assert "<dt>Portfolio</dt>" not in html
    assert 'data-si-summary-kind="PORTFOLIO"' not in html
    assert '<span class="si-review-freshness">Data through 11 Sept 2026</span>' in html
    assert (
        '<span class="si-review-capability">Fundamentals and news/catalysts '
        "not yet ingested</span>" in html
    )
    assert "data-si-summary-sources=" in html
    assert "DarvaX" not in html
    assert "Momentum Quality" not in html and "Entry Quality" not in html
    assert "UPTREND" not in html and "BULLISH" not in html
    js = _js()
    assert '<details class="si-written-summary" open>' in js
    assert "function siComposeResearchSummary(bundle)" in js
    assert "function siSummaryFamilyLabel(kind)" in js
    css = CSS.read_text(encoding="utf-8")
    assert "grid-template-columns: 1.6rem 7rem minmax(0, 1fr)" in css
    narrow = css[css.index("@media (max-width: 720px)") :]
    assert ".si-brief-row" in narrow
    assert "grid-template-columns: minmax(0, 1fr)" in narrow
    assert ".si-review-meta" in narrow
    assert ".si-brief-secondary" in narrow
    assert ".si-review-capability" in narrow
    assert "content: none" in narrow
    assert "max-width: 100%" in narrow
    assert "overflow-wrap: break-word" in narrow


def test_si_p2d_decision_rendering_groups_primary_secondary_and_meta() -> None:
    bundle = _base_bundle()
    bundle["decision"] = {
        "present": True,
        "decision_type": "NO_TRADE",
        "ts": "2026-09-11T15:30:00+05:30",
        "confidence_level": "HIGH",
        "depth": {"score": {"value": 35}},
        "gates": [{"passed": True} for _ in range(6)],
    }
    html = _run_summary(bundle, include_render=True)["html"]
    assert (
        '<span class="si-brief-evidence">No&nbsp;Trade · High&nbsp;confidence</span>'
        in html
    )
    assert (
        '<span class="si-brief-secondary">Score&nbsp;35.0/100 · '
        "6/6&nbsp;gates&nbsp;passed</span>"
        in html
    )
    assert '<span class="si-brief-meta">Decision as of 11 Sept 2026</span>' in html
    decision_row = html[html.index('data-si-summary-kind="ATHENA_DECISION"') :]
    assert "decision.decision_type" in decision_row
    assert "decision.depth.score.value" in decision_row
    assert "decision.gates" in decision_row


def test_si_p2d_missing_family_leaves_no_empty_research_row() -> None:
    bundle = _base_bundle()
    bundle["d1"].update(
        rsi14=None,
        rsi_is_coherent=False,
        volume=None,
        volume_ma20=None,
        volume_is_coherent=False,
    )
    html = _run_summary(bundle, include_render=True)["html"]
    assert 'data-si-summary-kind="MOMENTUM"' not in html
    assert "<dt>Momentum</dt>" not in html
    assert html.count('class="si-brief-row"') == 3


def test_si_p2d_stale_footer_is_bounded_and_visually_distinct() -> None:
    bundle = _base_bundle()
    bundle["sources"][0]["status"] = "STALE"
    html = _run_summary(bundle, include_render=True)["html"]
    assert html.count('data-si-summary-kind="DATA_AVAILABILITY"') == 1
    assert 'class="si-review-meta is-stale"' in html
    assert (
        '<span class="si-review-freshness">Completed-D1 evidence stale through '
        "11 Sept 2026</span>" in html
    )
    assert '<span class="si-review-capability">' in html
    assert "sources.D1_CANDLES.status" in html


def test_si_p2d_asset_cache_pin() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = Path("src/athena/api/static/dashboard.css").read_text(encoding="utf-8")
    assert "dashboard.css?v=9.274.0" in html
    assert "dashboard.js?v=9.274.0" in html
    assert "css/15-symbol-intelligence.css?v=9.274.0" in css
