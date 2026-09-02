"""My Portfolio Sync orchestration (PS-P4).

Composes confirmed My Portfolio holdings with already-persisted ATHENA market
data and decisions. This module deliberately does not introduce trading
methodology; nullable snapshot fields stay nullable unless an approved persisted
artifact directly supplies them.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import Timeframe
from athena.portfolio.my_portfolio_contracts import (
    PORTFOLIO_ANALYSIS_VERSION,
    CanonicalPortfolioHolding,
    PortfolioAnalysisProvenance,
    PortfolioFreshness,
    PortfolioSnapshotRow,
    SyncRunStatus,
)


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class PortfolioSyncOrchestrator:
    """Build durable Portfolio Snapshot rows from confirmed holdings."""

    def __init__(
        self,
        repo: SqliteRepository,
        *,
        validation_runner: Callable[[Sequence[str]], str | None] | None = None,
    ) -> None:
        self._repo = repo
        self._validation_runner = validation_runner

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
                provenance=dict(run.get("provenance") or {}),
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

        refresh_run_id, refresh_error = self._refresh_missing_daily_data(
            sync_run_id,
            holdings,
        )
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
            )
            snapshot_records.append(record)
            row_failures = record["failures"]
            if row_failures:
                failed += 1
                per_symbol[symbol] = {
                    "status": "FAILED",
                    "instrument_id": holding.instrument_id,
                    "errors": row_failures,
                    "unavailable": record["unavailable"],
                }
            else:
                succeeded += 1
                per_symbol[symbol] = {
                    "status": "SUCCESS",
                    "instrument_id": holding.instrument_id,
                    "price_as_of": record.get("price_as_of"),
                    "decision_id": record["provenance"].get("decision_id"),
                    "unavailable": record["unavailable"],
                }
            if isinstance(record.get("price_as_of_dt"), datetime):
                price_as_of_values.append(record["price_as_of_dt"])
            validation_run_id = record["provenance"].get("validation_run_id")
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
            row = dict(record["row"])
            freshness = dict(record["freshness"])
            row["freshness"]["market_data_through"] = record["market_data_through"]
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
                **dict(run.get("provenance") or {}),
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

        target_1 = None
        if decision is not None and decision.trade_plan is not None:
            target_1 = decision.trade_plan.targets[0]
        else:
            unavailable.append("target_1")
        unavailable.extend(
            [
                "status",
                "conviction",
                "trend_setup",
                "key_trigger",
                "support_1",
                "major_support_exit",
                "target_2",
                "target_3",
                "next_action",
            ]
        )
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
            validation_run_id=decision.run_id if decision is not None else None,
            analyzed_at=analyzed_at,
            unavailable_fields=tuple(dict.fromkeys(unavailable)),
            failed_components=tuple(dict.fromkeys(failures)),
        )
        row = PortfolioSnapshotRow.from_holding(
            symbol=symbol,
            holding=holding,
            last_price=last_price,
            price_as_of=price_as_of,
            target_1=target_1,
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
            "unavailable": tuple(dict.fromkeys(unavailable)),
            "failures": tuple(dict.fromkeys(failures)),
        }

    def _latest_decisions_by_instrument(self) -> dict[str, Decision]:
        out: dict[str, Decision] = {}
        for decision in self._repo.list_decisions(limit=5000):
            if decision.instrument_id and decision.instrument_id not in out:
                out[decision.instrument_id] = decision
        return out

    def _refresh_missing_daily_data(
        self,
        sync_run_id: str,
        holdings: Sequence[CanonicalPortfolioHolding],
    ) -> tuple[str | None, str | None]:
        missing = [
            self._display_symbol(holding.instrument_id)
            for holding in holdings
            if self._latest_daily_candle(holding.instrument_id) is None
        ]
        if not missing or self._validation_runner is None:
            return None, None
        self._repo.update_portfolio_sync_run(
            sync_run_id,
            status=SyncRunStatus.RUNNING,
            progress={
                "processed_holdings": 0,
                "stage": "refreshing_market_data",
                "message": f"Refreshing persisted ATHENA data for {len(missing)} holdings",
                "symbols": list(missing),
            },
        )
        try:
            return self._validation_runner(missing), None
        except Exception as exc:
            return None, str(exc)

    def _latest_daily_candle(self, instrument_id: str):
        candles = self._repo.list_candles_recent(instrument_id, Timeframe.D1, limit=1)
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
