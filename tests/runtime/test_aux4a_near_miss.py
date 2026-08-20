"""AUX-4a: daily near-miss digest for WATCH decisions close to the trade
threshold.

Requested via the owner-approved UX roadmap sequence. Reframed from the
roadmap's original "symbols close to their buy trigger" wording after tracing
the domain model: ``Decision.trade_plan`` is ``None`` for anything short of a
TRADE, so there is no persisted entry-price level to measure distance
against. What is already computed and persisted is the composite score a
WATCH decision fell short with -- the same arithmetic already shipped for the
decision counterfactual endpoint (M-X2). These tests pin that reuse and the
one correctness-critical exclusion: a WATCH blocked by a failed gate is not a
near-miss, regardless of how small its score gap happens to be.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from tests.runtime.test_daily_briefing import MemoryDecisions, _run, _seed_run

from athena.config.models import DecisionThresholdsCfg, NotificationsConfig
from athena.data.store import SqliteRepository
from athena.domain.decision import Decision, GateResult, TradePlan
from athena.domain.enums import DecisionType, Direction, QualityGate
from athena.notifications.builder import DailyBriefingBuilder
from athena.notifications.near_miss import NearMissReading, is_near_miss, near_miss_reading

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 2, 13, 16, 0, tzinfo=IST)
THRESHOLDS = DecisionThresholdsCfg(
    min_composite_for_trade=70, watch_composite=50,
    min_confidence_for_trade=50, max_risk_for_trade=50,
    min_evidence_completeness=0.5, market_floor=50,
)


def _decision(
    decision_id: str = "d-1",
    *,
    decision_type: DecisionType = DecisionType.WATCH,
    gates_pass: bool = True,
) -> Decision:
    gate = GateResult(gate=QualityGate.RISK, passed=gates_pass, detail="checked")
    return Decision(
        decision_id=decision_id, ts=AS_OF, run_id="run-1", cycle_id="c-1",
        decision_type=decision_type, explanation="setup forming",
        instrument_id="SYN-AAA", direction=Direction.NONE,
        gate_results=(gate,),
    )


def _seed_score(repo: SqliteRepository, run_id: str, decision_id: str, composite) -> None:
    repo.save_run(_run(run_id), detail={
        "pipeline": {
            "decision_reports": {
                decision_id: {"score": {"status": "OK", "composite": str(composite)}},
            },
        },
    })


# --------------------------------------------------------------------------- #
# 1. near_miss_reading / is_near_miss — pure arithmetic
# --------------------------------------------------------------------------- #


def test_near_miss_reading_extracts_composite_and_gap(tmp_path):
    repo = SqliteRepository(tmp_path / "a.db")
    repo.initialize()
    _seed_score(repo, "run-1", "d-1", composite="66")
    reading = near_miss_reading(repo, _decision(), THRESHOLDS)
    assert reading.composite == Decimal("66")
    assert reading.score_gap == Decimal("4")  # 70 - 66
    repo.close()


def test_near_miss_reading_is_absent_not_zero_when_report_missing(tmp_path):
    repo = SqliteRepository(tmp_path / "a.db")
    repo.initialize()
    repo.save_run(_run("run-1"), detail={})  # no pipeline/decision_reports at all
    reading = near_miss_reading(repo, _decision(), THRESHOLDS)
    assert reading.composite is None
    assert reading.score_gap is None
    repo.close()


def test_near_miss_reading_is_absent_when_score_status_not_ok(tmp_path):
    repo = SqliteRepository(tmp_path / "a.db")
    repo.initialize()
    repo.save_run(_run("run-1"), detail={
        "pipeline": {"decision_reports": {"d-1": {"score": {"status": "MISSING"}}}},
    })
    reading = near_miss_reading(repo, _decision(), THRESHOLDS)
    assert reading.composite is None
    assert reading.score_gap is None
    repo.close()


def test_gap_never_goes_negative_for_a_score_above_the_threshold(tmp_path):
    """A WATCH decision cannot exceed the trade threshold by classification
    (decision/engine.py routes it to TRADE if it did), but the real function
    must not report a negative gap if this ever changed upstream."""
    repo = SqliteRepository(tmp_path / "a.db")
    repo.initialize()
    _seed_score(repo, "run-1", "d-1", composite="95")  # above THRESHOLDS's 70
    reading = near_miss_reading(repo, _decision(), THRESHOLDS)
    assert reading.composite == Decimal("95")
    assert reading.score_gap == Decimal("0")
    repo.close()


def test_is_near_miss_true_for_a_watch_within_margin():
    d = _decision(gates_pass=True)
    reading = NearMissReading(composite=Decimal("66"), score_gap=Decimal("4"))
    assert is_near_miss(d, reading, max_gap=Decimal("5")) is True


def test_is_near_miss_false_when_gap_exceeds_the_margin():
    d = _decision(gates_pass=True)
    reading = NearMissReading(composite=Decimal("40"), score_gap=Decimal("30"))
    assert is_near_miss(d, reading, max_gap=Decimal("5")) is False


def test_is_near_miss_false_for_a_trade_decision():
    plan = TradePlan(
        entry_low=Decimal("100"), entry_high=Decimal("101"),
        stop_loss=Decimal("95"), targets=(Decimal("110"),),
        position_size=10, risk_amount=Decimal("50"), risk_reward=Decimal("2"),
        valid_from=AS_OF, valid_until=AS_OF + timedelta(days=1),
    )
    d = Decision(
        decision_id="d-1", ts=AS_OF, run_id="run-1", cycle_id="c-1",
        decision_type=DecisionType.TRADE, explanation="setup ready",
        instrument_id="SYN-AAA", direction=Direction.LONG,
        gate_results=(GateResult(gate=QualityGate.RISK, passed=True, detail="ok"),),
        trade_plan=plan,
    )
    reading = NearMissReading(composite=Decimal("80"), score_gap=Decimal("0"))
    assert is_near_miss(d, reading, max_gap=Decimal("5")) is False


def test_is_near_miss_false_when_a_gate_failed_even_with_a_tiny_gap():
    """The correctness-critical exclusion: a WATCH blocked by a failed gate
    (liquidity, risk, etc.) is not "almost tradeable" by score proximity --
    it is blocked by something this metric does not describe at all."""
    d = _decision(gates_pass=False)
    reading = NearMissReading(composite=Decimal("69"), score_gap=Decimal("1"))
    assert is_near_miss(d, reading, max_gap=Decimal("5")) is False


# --------------------------------------------------------------------------- #
# 2. Config
# --------------------------------------------------------------------------- #


def test_near_miss_score_gap_max_has_a_sane_default_and_bounds():
    cfg = NotificationsConfig()
    assert cfg.near_miss_score_gap_max == 5
    assert 0 <= cfg.near_miss_score_gap_max <= 100


# --------------------------------------------------------------------------- #
# 3. Builder integration
# --------------------------------------------------------------------------- #


def test_briefing_lists_a_genuine_near_miss(tmp_path):
    repo = SqliteRepository(tmp_path / "a.db")
    repo.initialize()
    _seed_run(repo, _run("run-1"))
    _seed_score(repo, "run-1", "d-1", composite="66")
    cfg = NotificationsConfig()
    builder = DailyBriefingBuilder(
        repo, cfg, tzinfo=IST,
        decision_source=MemoryDecisions([_decision("d-1", gates_pass=True)]),
        decision_thresholds=THRESHOLDS,
    )
    briefing = builder.build(as_of=AS_OF)
    assert len(briefing.near_misses) == 1
    nm = briefing.near_misses[0]
    assert nm.decision_id == "d-1"
    assert nm.composite == "66.00"
    assert nm.score_gap == "4.00"
    assert briefing.day_summary["near_miss_count"] == 1
    assert briefing.machine["near_misses"][0]["decision_id"] == "d-1"
    assert "Near misses (1)" in briefing.text_summary
    assert "SYN-AAA" in briefing.text_summary
    repo.close()


def test_near_miss_figures_are_quantized_for_a_human_reader(tmp_path):
    """Caught via live verification against real production data: an
    unrounded composite score read as "0.20875703116003326572919967 points
    short" in the actual rendered digest -- a reader has to visually filter
    past 20+ noise digits to find the number that matters. Quantized to two
    decimal places at the point of rendering."""
    repo = SqliteRepository(tmp_path / "a.db")
    repo.initialize()
    _seed_run(repo, _run("run-1"))
    _seed_score(repo, "run-1", "d-1", composite="59.79124296883996673427080033")
    cfg = NotificationsConfig(near_miss_score_gap_max=15)  # gap here is ~10.21
    builder = DailyBriefingBuilder(
        repo, cfg, tzinfo=IST,
        decision_source=MemoryDecisions([_decision("d-1", gates_pass=True)]),
        decision_thresholds=THRESHOLDS,
    )
    briefing = builder.build(as_of=AS_OF)
    assert len(briefing.near_misses) == 1
    nm = briefing.near_misses[0]
    assert nm.composite == "59.79"
    assert nm.score_gap == "10.21"
    for value in (nm.composite, nm.score_gap):
        assert len(value.split(".")[-1]) == 2, f"{value!r} is not 2 decimal places"
    repo.close()


def test_briefing_excludes_a_gate_failed_watch_from_near_misses(tmp_path):
    repo = SqliteRepository(tmp_path / "a.db")
    repo.initialize()
    _seed_run(repo, _run("run-1"))
    _seed_score(repo, "run-1", "d-1", composite="69")  # gap of 1 -- tiny
    cfg = NotificationsConfig()
    builder = DailyBriefingBuilder(
        repo, cfg, tzinfo=IST,
        decision_source=MemoryDecisions([_decision("d-1", gates_pass=False)]),
        decision_thresholds=THRESHOLDS,
    )
    briefing = builder.build(as_of=AS_OF)
    assert briefing.near_misses == ()
    assert briefing.day_summary["near_miss_count"] == 0
    assert "Near misses (0)" in briefing.text_summary
    repo.close()


def test_briefing_degrades_to_no_near_misses_without_thresholds(tmp_path):
    """decision_thresholds is optional (mirrors decision_source's own
    optionality) -- a briefing must still assemble, not crash, for a caller
    that has not wired it through."""
    repo = SqliteRepository(tmp_path / "a.db")
    repo.initialize()
    _seed_run(repo, _run("run-1"))
    cfg = NotificationsConfig()
    builder = DailyBriefingBuilder(
        repo, cfg, tzinfo=IST,
        decision_source=MemoryDecisions([_decision("d-1")]),
        decision_thresholds=None,
    )
    briefing = builder.build(as_of=AS_OF)
    assert briefing.near_misses == ()
    repo.close()


def test_list_for_day_is_called_exactly_once_per_build(tmp_path):
    """Two independent reads of the same source risked the near-miss list
    disagreeing with the decisions list about which decisions the day
    contains -- confirm the source is consulted once."""
    repo = SqliteRepository(tmp_path / "a.db")
    repo.initialize()
    _seed_run(repo, _run("run-1"))
    _seed_score(repo, "run-1", "d-1", composite="66")

    calls = []

    class CountingSource(MemoryDecisions):
        def list_for_day(self, as_of):
            calls.append(as_of)
            return super().list_for_day(as_of)

    cfg = NotificationsConfig()
    builder = DailyBriefingBuilder(
        repo, cfg, tzinfo=IST,
        decision_source=CountingSource([_decision("d-1")]),
        decision_thresholds=THRESHOLDS,
    )
    builder.build(as_of=AS_OF)
    assert len(calls) == 1
    repo.close()
