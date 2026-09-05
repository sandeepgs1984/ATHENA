"""My Portfolio Sync orchestration (PS-P4).

Composes confirmed My Portfolio holdings with already-persisted ATHENA market
data and decisions. This module deliberately does not introduce trading
methodology; nullable snapshot fields stay nullable unless an approved persisted
artifact directly supplies them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4
from zoneinfo import ZoneInfo

from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.intraday.entry_qualification_models import EntryQualification
from athena.ops.symbol_validate import _index_instrument_needs_refresh
from athena.portfolio.confidence_adapter import (
    PortfolioConfidenceAdapter,
    PortfolioConfidenceEvidence,
)
from athena.portfolio.interpretation import (
    PortfolioInterpretationEvidence,
    PortfolioInterpreter,
)
from athena.portfolio.my_portfolio_contracts import (
    PORTFOLIO_ANALYSIS_VERSION,
    CanonicalPortfolioHolding,
    PortfolioAnalysisProvenance,
    PortfolioFreshness,
    PortfolioSnapshotRow,
    SyncRunStatus,
)
from athena.portfolio.setup_adapter import (
    PortfolioSetupAdapter,
    PortfolioSetupEvidence,
    PortfolioSetupWindowEvidence,
)
from athena.portfolio.trend_adapter import PortfolioTrendAdapter, PortfolioTrendEvidence

ValidationRunner = Callable[[Sequence[str], datetime], str | None]


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class PortfolioSyncOrchestrator:
    """Build durable Portfolio Snapshot rows from confirmed holdings."""

    def __init__(
        self,
        repo: SqliteRepository,
        *,
        validation_runner: ValidationRunner | None = None,
        expected_analysis_as_of: datetime | None = None,
        market_timezone: ZoneInfo | None = None,
        config_dir: Path | str = "config",
        force_ingestion: bool = False,
    ) -> None:
        self._repo = repo
        self._validation_runner = validation_runner
        self._expected_analysis_as_of = expected_analysis_as_of
        self._market_timezone = market_timezone or ZoneInfo("UTC")
        self._force_ingestion = force_ingestion
        self._interpreter = PortfolioInterpreter()
        self._confidence_adapter = PortfolioConfidenceAdapter(repo)
        self._trend_adapter = PortfolioTrendAdapter(repo, config_dir=config_dir)
        self._setup_adapter = PortfolioSetupAdapter(repo, config_dir=config_dir)

    def create_run(self) -> dict[str, object]:
        active = self._repo.get_active_portfolio_sync_run()
        if active is not None:
            return active
        holdings = self._repo.list_portfolio_holdings()
        sync_run_id = f"psync-{uuid4().hex}"
        return self._repo.create_portfolio_sync_run(
            sync_run_id=sync_run_id,
            started_at=utc_now(),
            total_holdings=len(holdings),
            analysis_version=PORTFOLIO_ANALYSIS_VERSION,
            status=SyncRunStatus.QUEUED,
            progress={
                "processed_holdings": 0,
                "stage": "queued",
                "message": "Portfolio Sync queued",
            },
            provenance={
                "holdings_digest": self._repo.portfolio_holdings_digest(),
                "source": "portfolio_holdings",
                "expected_analysis_as_of": (
                    self._expected_analysis_as_of.isoformat()
                    if self._expected_analysis_as_of is not None
                    else None
                ),
                "force_ingestion_requested": self._force_ingestion,
            },
        )

    def run(self, sync_run_id: str) -> dict[str, object]:
        run = self._repo.get_portfolio_sync_run(sync_run_id)
        if run is None:
            raise ValueError(f"Portfolio Sync run not found: {sync_run_id}")
        holdings = self._repo.list_portfolio_holdings()
        if not holdings:
            return self._repo.update_portfolio_sync_run(
                sync_run_id,
                status=SyncRunStatus.SUCCESS,
                finished_at=utc_now(),
                succeeded_holdings=0,
                failed_holdings=0,
                progress={
                    "processed_holdings": 0,
                    "stage": "completed",
                    "message": "No holdings imported yet",
                },
                per_symbol={},
                provenance=dict(cast(Mapping[str, object], run.get("provenance") or {})),
            )

        self._repo.update_portfolio_sync_run(
            sync_run_id,
            status=SyncRunStatus.RUNNING,
            progress={
                "processed_holdings": 0,
                "stage": "running",
                "message": "Analyzing confirmed My Portfolio holdings",
            },
        )

        (
            refresh_run_id,
            refresh_error,
            refresh_required_symbols,
            refreshed_symbols,
        ) = self._refresh_stale_daily_data(sync_run_id, holdings)
        # Re-read persisted decisions only after scoped validation has had a
        # chance to ingest candles and emit same-session decisions.
        decisions = self._latest_decisions_by_instrument()
        snapshot_records: list[dict[str, object]] = []
        per_symbol: dict[str, object] = {}
        succeeded = 0
        failed = 0
        price_as_of_values: list[datetime] = []
        latest_validation_run_id: str | None = refresh_run_id
        analyzed_at = utc_now()

        for index, holding in enumerate(holdings, start=1):
            symbol = self._display_symbol(holding.instrument_id)
            record = self._analyze_holding(
                sync_run_id=sync_run_id,
                row_index=index,
                holding=holding,
                symbol=symbol,
                decision=decisions.get(holding.instrument_id),
                analyzed_at=analyzed_at,
                refresh_required=symbol in refresh_required_symbols,
                refresh_performed=symbol in refreshed_symbols,
            )
            snapshot_records.append(record)
            provenance_record = cast(Mapping[str, object], record["provenance"])
            row_failures = record["failures"]
            if row_failures:
                failed += 1
                per_symbol[symbol] = {
                    "status": "FAILED",
                    "instrument_id": holding.instrument_id,
                    "errors": row_failures,
                    "unavailable": record["unavailable"],
                    "refresh_required": symbol in refresh_required_symbols,
                    "refresh_performed": symbol in refreshed_symbols,
                }
            else:
                succeeded += 1
                per_symbol[symbol] = {
                    "status": "SUCCESS",
                    "instrument_id": holding.instrument_id,
                    "price_as_of": record.get("price_as_of"),
                    "expected_analysis_as_of": (
                        self._expected_analysis_as_of.isoformat()
                        if self._expected_analysis_as_of is not None
                        else None
                    ),
                    "decision_id": provenance_record.get("decision_id"),
                    "interpretation_version": provenance_record.get(
                        "interpretation_version",
                    ),
                    "interpretation_reason_codes": provenance_record.get(
                        "interpretation_reason_codes"
                    ),
                    "unavailable": record["unavailable"],
                    "refresh_required": symbol in refresh_required_symbols,
                    "refresh_performed": symbol in refreshed_symbols,
                }
            if isinstance(record.get("price_as_of_dt"), datetime):
                price_as_of_values.append(cast(datetime, record["price_as_of_dt"]))
            validation_run_id = provenance_record.get("validation_run_id")
            if validation_run_id and latest_validation_run_id is None:
                latest_validation_run_id = str(validation_run_id)

            self._repo.update_portfolio_sync_run(
                sync_run_id,
                status=SyncRunStatus.RUNNING,
                succeeded_holdings=succeeded,
                failed_holdings=failed,
                progress={
                    "processed_holdings": index,
                    "stage": "running",
                    "message": f"Analyzed {index} of {len(holdings)} holdings",
                    "current_symbol": symbol,
                },
                per_symbol=per_symbol,
            )

        market_data_through = min(price_as_of_values) if price_as_of_values else None
        for record in snapshot_records:
            record.pop("price_as_of_dt", None)
            record["market_data_through"] = (
                market_data_through.isoformat() if market_data_through else None
            )
            row = dict(cast(Mapping[str, object], record["row"]))
            freshness = dict(cast(Mapping[str, object], record["freshness"]))
            row_freshness = dict(cast(Mapping[str, object], row["freshness"]))
            row_freshness["market_data_through"] = record["market_data_through"]
            row["freshness"] = row_freshness
            freshness["market_data_through"] = record["market_data_through"]
            record["row"] = row
            record["freshness"] = freshness

        self._repo.save_portfolio_analysis_snapshots(
            sync_run_id=sync_run_id,
            rows=snapshot_records,
        )
        status = (
            SyncRunStatus.SUCCESS
            if failed == 0
            else SyncRunStatus.FAILED
            if succeeded == 0
            else SyncRunStatus.PARTIAL
        )
        return self._repo.update_portfolio_sync_run(
            sync_run_id,
            status=status,
            finished_at=utc_now(),
            succeeded_holdings=succeeded,
            failed_holdings=failed,
            market_data_through=market_data_through,
            validation_run_id=latest_validation_run_id,
            progress={
                "processed_holdings": len(holdings),
                "stage": "completed" if status is not SyncRunStatus.FAILED else "failed",
                "message": (
                    "Portfolio Sync completed"
                    if status is SyncRunStatus.SUCCESS
                    else "Portfolio Sync completed with per-holding failures"
                    if status is SyncRunStatus.PARTIAL
                    else "Portfolio Sync found no analyzable holdings"
                ),
            },
            per_symbol=per_symbol,
            error=(
                {}
                if status is not SyncRunStatus.FAILED
                else {
                    "code": "ALL_HOLDINGS_FAILED",
                    "message": "No holdings could be analyzed from persisted ATHENA data",
                }
            ),
            provenance={
                **dict(cast(Mapping[str, object], run.get("provenance") or {})),
                "expected_analysis_as_of": (
                    self._expected_analysis_as_of.isoformat()
                    if self._expected_analysis_as_of is not None
                    else None
                ),
                "refresh_required_symbols": list(refresh_required_symbols),
                "refreshed_symbols": list(refreshed_symbols),
                **({"refresh_error": refresh_error} if refresh_error else {}),
            },
        )

    def _analyze_holding(
        self,
        *,
        sync_run_id: str,
        row_index: int,
        holding: CanonicalPortfolioHolding,
        symbol: str,
        decision: Decision | None,
        analyzed_at: datetime,
        refresh_required: bool,
        refresh_performed: bool,
    ) -> dict[str, object]:
        unavailable: list[str] = []
        failures: list[str] = []
        instrument = self._repo.get_instrument(holding.instrument_id)
        if instrument is None:
            failures.append("INVALID_CANONICAL_INSTRUMENT")

        candle = self._latest_daily_candle(holding.instrument_id)
        if candle is None:
            failures.append("NO_PERSISTED_D1_CANDLE")
            unavailable.extend(
                [
                    "last_price",
                    "price_as_of",
                    "current_value",
                    "pnl",
                    "pnl_pct",
                ]
            )
        last_price = candle.close if candle is not None else None
        price_as_of = candle.ts_open if candle is not None else None
        if price_as_of is not None:
            price_as_of = price_as_of.astimezone(timezone.utc)

        final_price_is_expected_session = self._price_is_expected_session(price_as_of)
        if price_as_of is not None and not final_price_is_expected_session:
            unavailable.append("current_price_session")

        decision_is_coherent = self._decision_matches_price_session(decision, price_as_of)
        interpretation_as_of = self._interpretation_as_of(price_as_of, analyzed_at)
        trade_plan_is_active = (
            final_price_is_expected_session
            and decision_is_coherent
            and self._trade_plan_is_active(decision, interpretation_as_of)
        )
        entry_qualification = self._latest_coherent_entry_qualification(
            decision=decision,
            instrument_id=holding.instrument_id,
            interpretation_as_of=interpretation_as_of,
            decision_is_coherent=decision_is_coherent,
        )
        confidence_evidence = self._confidence_adapter.resolve(
            decision=decision,
            instrument_id=holding.instrument_id,
            decision_is_coherent=decision_is_coherent,
        )
        trend_evidence = self._trend_adapter.resolve(
            instrument_id=holding.instrument_id,
            accepted_price_as_of=price_as_of,
            expected_analysis_as_of=self._expected_analysis_as_of,
            market_timezone=self._market_timezone,
        )
        setup_evidence = self._setup_adapter.resolve(
            instrument_id=holding.instrument_id,
            accepted_price_as_of=price_as_of,
            expected_analysis_as_of=self._expected_analysis_as_of,
            market_timezone=self._market_timezone,
        )
        interpretation = self._interpreter.interpret(
            PortfolioInterpretationEvidence(
                instrument_id=holding.instrument_id,
                as_of=interpretation_as_of,
                last_price=last_price,
                price_is_current=final_price_is_expected_session,
                decision=decision,
                decision_is_coherent=decision_is_coherent,
                trade_plan=(
                    decision.trade_plan
                    if decision is not None
                    and final_price_is_expected_session
                    and decision_is_coherent
                    else None
                ),
                trade_plan_is_active=trade_plan_is_active,
                entry_qualification=entry_qualification,
                entry_qualification_is_coherent=entry_qualification is not None,
                confidence_level=confidence_evidence.level,
                confidence_is_coherent=confidence_evidence.is_coherent,
                trend=trend_evidence.trend,
                trend_is_coherent=trend_evidence.is_coherent,
                trend_reason=trend_evidence.reason,
                setup=setup_evidence.setup,
                setup_is_coherent=setup_evidence.is_coherent,
                setup_reason=setup_evidence.reason,
            )
        )
        target_1 = None
        if decision is not None and not decision_is_coherent:
            unavailable.extend(["decision", "target_1", "decision_evidence"])
        elif decision is not None and decision.trade_plan is not None and trade_plan_is_active:
            target_1 = decision.trade_plan.targets[0]
        else:
            unavailable.append("target_1")
        if interpretation.conviction is None:
            unavailable.append("conviction")
        unavailable.extend(["support_1", "target_2", "target_3"])
        if interpretation.trend_setup is None:
            unavailable.append("trend_setup")
        if interpretation.key_trigger is None:
            unavailable.append("key_trigger")
        if interpretation.major_support_exit is None:
            unavailable.append("major_support_exit")
        if decision is None:
            unavailable.append("decision")

        freshness = PortfolioFreshness(
            portfolio_imported_at=holding.imported_at,
            holdings_as_of=None,
            last_synced_at=analyzed_at,
            market_data_through=None,
            analysis_version=PORTFOLIO_ANALYSIS_VERSION,
            decision_as_of=decision.ts if decision is not None else None,
            price_as_of=price_as_of,
        )
        provenance = PortfolioAnalysisProvenance(
            instrument_id=holding.instrument_id,
            price_source=candle.source if candle is not None else None,
            candle_ref=(
                f"{holding.instrument_id}|{Timeframe.D1.value}|{price_as_of.isoformat()}"
                if price_as_of is not None
                else None
            ),
            decision_id=decision.decision_id if decision is not None else None,
            validation_run_id=(
                decision.run_id
                if decision is not None and decision_is_coherent
                else None
            ),
            analyzed_at=analyzed_at,
            unavailable_fields=tuple(dict.fromkeys(unavailable)),
            failed_components=tuple(dict.fromkeys(failures)),
            interpretation_version=interpretation.interpretation_version,
            interpretation_reason_codes=tuple(
                reason.value for reason in interpretation.reason_codes
            ),
            interpretation_evidence=self._interpretation_evidence_to_json(
                decision=decision,
                decision_is_coherent=decision_is_coherent,
                trade_plan_is_active=trade_plan_is_active,
                entry_qualification=entry_qualification,
                confidence_evidence=confidence_evidence,
                trend_evidence=trend_evidence,
                setup_evidence=setup_evidence,
                price_is_current=final_price_is_expected_session,
                interpretation_as_of=interpretation_as_of,
            ),
        )
        row = PortfolioSnapshotRow.from_holding(
            symbol=symbol,
            holding=holding,
            last_price=last_price,
            price_as_of=price_as_of,
            status=interpretation.status.value,
            conviction=interpretation.conviction,
            trend_setup=interpretation.trend_setup,
            key_trigger=(
                str(interpretation.key_trigger)
                if interpretation.key_trigger is not None
                else None
            ),
            support_1=interpretation.support_1,
            major_support_exit=interpretation.major_support_exit,
            target_1=target_1,
            target_2=interpretation.target_2,
            target_3=interpretation.target_3,
            next_action=interpretation.next_action.value,
            last_review=analyzed_at,
            freshness=freshness,
            provenance=provenance,
        )
        return {
            "snapshot_id": f"{sync_run_id}-row-{row_index:04d}",
            "instrument_id": holding.instrument_id,
            "symbol": symbol,
            "analyzed_at": analyzed_at.isoformat(),
            "price_as_of": price_as_of.isoformat() if price_as_of else None,
            "price_as_of_dt": price_as_of,
            "decision_as_of": decision.ts.isoformat() if decision is not None else None,
            "market_data_through": None,
            "analysis_version": PORTFOLIO_ANALYSIS_VERSION,
            "row": self._row_to_json(row),
            "freshness": self._freshness_to_json(freshness),
            "provenance": self._provenance_to_json(provenance),
            "expected_analysis_as_of": (
                self._expected_analysis_as_of.isoformat()
                if self._expected_analysis_as_of is not None
                else None
            ),
            "refresh_required": refresh_required,
            "refresh_performed": refresh_performed,
            "decision_evidence_accepted": decision_is_coherent,
            "unavailable": tuple(dict.fromkeys(unavailable)),
            "failures": tuple(dict.fromkeys(failures)),
        }

    def _latest_decisions_by_instrument(self) -> dict[str, Decision]:
        return {
            decision.instrument_id: decision
            for decision in self._repo.list_latest_decisions_by_instrument()
            if decision.instrument_id is not None
        }

    def _refresh_stale_daily_data(
        self,
        sync_run_id: str,
        holdings: Sequence[CanonicalPortfolioHolding],
    ) -> tuple[str | None, str | None, tuple[str, ...], tuple[str, ...]]:
        refresh_symbols = tuple(
            self._display_symbol(holding.instrument_id)
            for holding in holdings
            if self._holding_needs_refresh(holding)
        )
        if not refresh_symbols:
            return None, None, (), ()
        if self._validation_runner is None or self._expected_analysis_as_of is None:
            return None, None, refresh_symbols, ()
        self._repo.update_portfolio_sync_run(
            sync_run_id,
            status=SyncRunStatus.RUNNING,
            progress={
                "processed_holdings": 0,
                "stage": "refreshing_market_data",
                "message": f"Refreshing persisted ATHENA data for {len(refresh_symbols)} holdings",
                "symbols": list(refresh_symbols),
                "expected_analysis_as_of": self._expected_analysis_as_of.isoformat(),
            },
        )
        try:
            return (
                self._validation_runner(refresh_symbols, self._expected_analysis_as_of),
                None,
                refresh_symbols,
                refresh_symbols,
            )
        except Exception as exc:
            return None, str(exc), refresh_symbols, ()

    def _holding_needs_refresh(self, holding: CanonicalPortfolioHolding) -> bool:
        if self._force_ingestion:
            return True
        if self._expected_analysis_as_of is None:
            return self._latest_daily_candle(holding.instrument_id) is None
        return _index_instrument_needs_refresh(
            self._repo,
            holding.instrument_id,
            self._expected_analysis_as_of,
            self._market_timezone,
        )

    def _price_is_expected_session(self, price_as_of: datetime | None) -> bool:
        if price_as_of is None or self._expected_analysis_as_of is None:
            return True
        return (
            price_as_of.astimezone(self._market_timezone).date()
            == self._expected_analysis_as_of.astimezone(self._market_timezone).date()
        )

    def _decision_matches_price_session(
        self,
        decision: Decision | None,
        price_as_of: datetime | None,
    ) -> bool:
        if decision is None:
            return False
        if price_as_of is None:
            return False
        return (
            decision.ts.astimezone(self._market_timezone).date()
            == price_as_of.astimezone(self._market_timezone).date()
        )

    def _interpretation_as_of(
        self,
        price_as_of: datetime | None,
        analyzed_at: datetime,
    ) -> datetime:
        return self._expected_analysis_as_of or price_as_of or analyzed_at

    def _trade_plan_is_active(
        self,
        decision: Decision | None,
        interpretation_as_of: datetime,
    ) -> bool:
        if decision is None or decision.trade_plan is None:
            return False
        plan = decision.trade_plan
        return plan.valid_from <= interpretation_as_of <= plan.valid_until

    def _latest_coherent_entry_qualification(
        self,
        *,
        decision: Decision | None,
        instrument_id: str,
        interpretation_as_of: datetime,
        decision_is_coherent: bool,
    ) -> EntryQualification | None:
        if decision is None or not decision_is_coherent:
            return None
        eq = self._repo.latest_entry_qualification_for_decision(decision.decision_id)
        if eq is None:
            return None
        session_date = interpretation_as_of.astimezone(self._market_timezone).date()
        if eq.instrument_id != instrument_id:
            return None
        if eq.decision_id != decision.decision_id:
            return None
        if eq.run_id != decision.run_id or eq.cycle_id != decision.cycle_id:
            return None
        if eq.decision_type is not decision.decision_type:
            return None
        if eq.session_date != session_date:
            return None
        if eq.as_of.astimezone(self._market_timezone).date() != session_date:
            return None
        if eq.as_of > interpretation_as_of:
            return None
        return eq

    def _latest_daily_candle(self, instrument_id: str) -> Candle | None:
        candles = self._repo.list_candles_recent(
            instrument_id,
            Timeframe.D1,
            limit=1,
            as_of=self._expected_analysis_as_of,
        )
        return candles[0] if candles else None

    @staticmethod
    def _display_symbol(instrument_id: str) -> str:
        return instrument_id.split(":", 1)[1] if ":" in instrument_id else instrument_id

    @staticmethod
    def _value(value: object) -> object:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @classmethod
    def _interpretation_evidence_to_json(
        cls,
        *,
        decision: Decision | None,
        decision_is_coherent: bool,
        trade_plan_is_active: bool,
        entry_qualification: EntryQualification | None,
        confidence_evidence: PortfolioConfidenceEvidence,
        trend_evidence: PortfolioTrendEvidence,
        setup_evidence: PortfolioSetupEvidence,
        price_is_current: bool,
        interpretation_as_of: datetime,
    ) -> dict[str, object]:
        return {
            "interpretation_as_of": interpretation_as_of.isoformat(),
            "price_is_current": price_is_current,
            "decision_is_coherent": decision_is_coherent,
            "trade_plan_accepted": trade_plan_is_active,
            "entry_qualification_accepted": entry_qualification is not None,
            "decision_id": decision.decision_id if decision is not None else None,
            "confidence": {
                "decision_id": confidence_evidence.decision_id,
                "run_id": confidence_evidence.run_id,
                "source": confidence_evidence.source,
                "level": (
                    confidence_evidence.level.value
                    if confidence_evidence.level is not None
                    else None
                ),
                "is_coherent": confidence_evidence.is_coherent,
                "reason": confidence_evidence.reason.value,
            },
            "entry_qualification": (
                {
                    "decision_id": entry_qualification.decision_id,
                    "as_of": entry_qualification.as_of.isoformat(),
                    "state": entry_qualification.state.value,
                    "methodology_version": entry_qualification.methodology_version,
                }
                if entry_qualification is not None
                else None
            ),
            "trend": {
                "label": (
                    trend_evidence.trend.value
                    if trend_evidence.trend is not None
                    else None
                ),
                "reason": trend_evidence.reason.value,
                "d1_session": (
                    trend_evidence.d1_session.isoformat()
                    if trend_evidence.d1_session is not None
                    else None
                ),
                "fast_period": trend_evidence.fast_period,
                "slow_period": trend_evidence.slow_period,
                "fast_sma": (
                    str(trend_evidence.fast_sma)
                    if trend_evidence.fast_sma is not None
                    else None
                ),
                "slow_sma": (
                    str(trend_evidence.slow_sma)
                    if trend_evidence.slow_sma is not None
                    else None
                ),
                "close": (
                    str(trend_evidence.close)
                    if trend_evidence.close is not None
                    else None
                ),
                "candles_used": trend_evidence.candles_used,
                "is_coherent": trend_evidence.is_coherent,
            },
            "setup": {
                "label": (
                    setup_evidence.setup.value
                    if setup_evidence.setup is not None
                    else None
                ),
                "reason": setup_evidence.reason.value,
                "session_date": (
                    setup_evidence.session_date.isoformat()
                    if setup_evidence.session_date is not None
                    else None
                ),
                "analysis_as_of": (
                    setup_evidence.analysis_as_of.isoformat()
                    if setup_evidence.analysis_as_of is not None
                    else None
                ),
                "evidence_as_of": (
                    setup_evidence.evidence_as_of.isoformat()
                    if setup_evidence.evidence_as_of is not None
                    else None
                ),
                "latest_completed_m5_slot": (
                    setup_evidence.latest_completed_m5_slot.isoformat()
                    if setup_evidence.latest_completed_m5_slot is not None
                    else None
                ),
                "is_coherent": setup_evidence.is_coherent,
                "or15": cls._setup_window_to_json(setup_evidence.or15),
                "or30": cls._setup_window_to_json(setup_evidence.or30),
            },
        }

    @staticmethod
    def _setup_window_to_json(
        window: PortfolioSetupWindowEvidence | None,
    ) -> dict[str, object] | None:
        if window is None:
            return None
        return {
            "status": window.status.value if window.status is not None else None,
            "event": window.event.value if window.event is not None else None,
            "returned_inside_range": window.returned_inside_range,
            "first_event_ts": (
                window.first_event_ts.isoformat()
                if window.first_event_ts is not None
                else None
            ),
        }

    @classmethod
    def _row_to_json(cls, row: PortfolioSnapshotRow) -> dict[str, object]:
        payload = asdict(row)
        payload["freshness"] = cls._freshness_to_json(row.freshness)
        payload["provenance"] = cls._provenance_to_json(row.provenance)
        return {key: cls._value(value) for key, value in payload.items()}

    @classmethod
    def _freshness_to_json(cls, freshness: PortfolioFreshness) -> dict[str, object]:
        return {key: cls._value(value) for key, value in asdict(freshness).items()}

    @classmethod
    def _provenance_to_json(
        cls,
        provenance: PortfolioAnalysisProvenance,
    ) -> dict[str, object]:
        return {key: cls._value(value) for key, value in asdict(provenance).items()}
