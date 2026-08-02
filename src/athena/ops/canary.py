"""Synthetic canary decision (M-X8).

A fixed, deterministic synthetic instrument run through the real
``OwnerValidationPipeline`` each due cycle, to catch silent engine
regressions. Runs against a fresh, throwaway in-memory ``SqliteRepository``
created for this call alone — never the live repository, never a real
owner candidate, never a persisted decision the owner would see. Reuses the
exact pipeline real trading decisions go through (rather than a parallel,
simplified re-implementation) so a regression caught here is a regression
in the real code path, not in a copy that could itself drift out of sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from athena.confidence.models import ConfidenceStatus
from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import DecisionType, RunTrigger, Timeframe
from athena.domain.market import Candle, Instrument
from athena.ops.owner_candidates import DEFAULT_EXCHANGE, SqliteCandidateStore
from athena.ops.owner_validation import OwnerValidationPipeline
from athena.risk.models import RiskStatus
from athena.scoring.models import ScoreStatus

CANARY_SYMBOL = "ATHENACANARY"
CANARY_INSTRUMENT_ID = f"{DEFAULT_EXCHANGE}:{CANARY_SYMBOL}"
_DAILY_BARS = 80
_SEED_PRICE = 1000


@dataclass(frozen=True, slots=True)
class CanaryResult:
    """Outcome of one canary run. Diagnostic only — never persisted."""

    ok: bool
    reasons: tuple[str, ...]
    decision_type: str | None
    composite_value: str | None


def _synthetic_daily_candles(as_of: datetime, n: int = _DAILY_BARS) -> list[Candle]:
    """Fixed, deterministic, steadily-rising daily series ending the day
    before ``as_of`` — same shape as the test fixtures used across
    tests/decision/test_scoring.py, but as a production diagnostic input,
    never real market data and never shown to the owner as such."""
    out: list[Candle] = []
    start_date = as_of.date() - timedelta(days=n)
    for i in range(n):
        px = Decimal(_SEED_PRICE + i)
        ts = datetime.combine(
            start_date + timedelta(days=i), datetime.min.time(), tzinfo=as_of.tzinfo
        ).replace(hour=9, minute=15)
        out.append(
            Candle(
                instrument_id=CANARY_INSTRUMENT_ID, timeframe=Timeframe.D1, ts_open=ts,
                open=px, high=px + Decimal("2"), low=px - Decimal("1"), close=px + Decimal("1"),
                volume=1_000_000, source="canary",
            )
        )
    return out


def run_canary(config_dir: Path, *, as_of: datetime, run_id: str) -> CanaryResult:
    """Run the fixed synthetic instrument through the real
    ``OwnerValidationPipeline`` against a fresh, throwaway in-memory repo.

    A "regression" is defined loosely on purpose — not an exact expected
    decision, since concentration risk on a single-instrument universe is a
    real, legitimate risk-engine outcome, not a bug. Instead this checks
    that the pipeline completes without raising and produces a fully
    explained (status OK) score/confidence/risk for a synthetic instrument
    that always has complete daily history by construction, plus a
    recognized decision type. Any exception, or an UNKNOWN score/confidence/
    risk status, or INSUFFICIENT_DATA for this always-complete synthetic
    input, is the regression signal.
    """
    repo = SqliteRepository(":memory:")
    try:
        repo.initialize()
        store = SqliteCandidateStore(repo)
        store.upsert_candidate(symbol=CANARY_SYMBOL)
        repo.upsert_instrument(
            Instrument(
                instrument_id=CANARY_INSTRUMENT_ID, symbol=CANARY_SYMBOL,
                exchange=DEFAULT_EXCHANGE, series="EQ", status="ACTIVE",
            )
        )
        repo.add_candles(_synthetic_daily_candles(as_of))

        pipe = OwnerValidationPipeline(repo, config_dir)
        ingestion = IngestionResult(
            as_of=as_of, instruments_upserted=1, candles_fetched=_DAILY_BARS,
            candles_written=_DAILY_BARS, quotes_fetched=0, quotes_written=0,
            datasets_validated=1, datasets_skipped_empty=0,
        )
        try:
            detail = pipe.run(RunTrigger.REFRESH, as_of=as_of, ingestion=ingestion, run_id=run_id)
        except Exception as exc:  # any pipeline exception IS the regression signal
            return CanaryResult(
                ok=False, reasons=(f"pipeline raised: {exc!r}",),
                decision_type=None, composite_value=None,
            )
    finally:
        repo.close()

    reports = detail.get("decision_reports") if isinstance(detail, dict) else None
    if not reports:
        return CanaryResult(
            ok=False, reasons=(f"no decision_reports produced (mode={detail.get('mode')!r})",),
            decision_type=None, composite_value=None,
        )
    report = next(iter(reports.values()))
    score = report.get("score", {})
    confidence = report.get("confidence", {})
    risk = report.get("risk", {})
    decision_type = report.get("decision", {}).get("type")

    reasons: list[str] = []
    if score.get("status") != ScoreStatus.OK.value:
        reasons.append(f"score status {score.get('status')!r} (expected OK)")
    if confidence.get("status") != ConfidenceStatus.OK.value:
        reasons.append(f"confidence status {confidence.get('status')!r} (expected OK)")
    if risk.get("status") != RiskStatus.OK.value:
        reasons.append(f"risk status {risk.get('status')!r} (expected OK)")
    if decision_type not in {t.value for t in DecisionType}:
        reasons.append(f"unrecognized decision_type {decision_type!r}")
    elif decision_type == DecisionType.INSUFFICIENT_DATA.value:
        reasons.append("decision_type INSUFFICIENT_DATA for an always-complete synthetic instrument")

    return CanaryResult(
        ok=not reasons, reasons=tuple(reasons),
        decision_type=decision_type, composite_value=score.get("composite"),
    )
