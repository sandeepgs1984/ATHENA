"""SQLite-backed API providers for live dashboard data.

Reads decisions, owner-entered positions, and cycle runs from the same
ATHENA_DB_PATH ledger used by CLI ingest/cycle/brief. No demo seed data.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from athena.api.v1.dtos import (
    CollectionResult,
    DecisionFilterParams,
    PipelineRunFilterParams,
    QuerySpecification,
)
from athena.api.v1.providers.in_memory import apply_query_spec
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision, DecisionTrace, Portfolio, Position
from athena.domain.enums import RunStatus, Timeframe
from athena.domain.market import Candle
from athena.orchestration.models import (
    PipelineContext,
    PipelineMetadata,
    PipelineResult,
    PipelineStatus,
    StageResult,
    StageStatus,
    SystemPipelineResult,
)


def _resolve_repo_root() -> Path:
    current = Path(__file__).resolve().parent
    for _ in range(12):
        if (current / "pyproject.toml").is_file() and (current / "src").is_dir():
            return current
        current = current.parent
    return Path.cwd()


def default_db_path() -> Path:
    env = os.environ.get("ATHENA_DB_PATH")
    if env:
        return Path(env)
    return _resolve_repo_root() / "db" / "athena.db"


def load_starting_cash(config_dir: Path | None = None) -> Decimal:
    """Load owner starting cash from config/portfolio.json (PortfolioConfig.initial_cash)."""
    root = config_dir or (_resolve_repo_root() / "config")
    path = Path(root) / "portfolio.json"
    if not path.is_file():
        return Decimal("0.00")
    try:
        from athena.config.loader import load_portfolio_config

        return load_portfolio_config(root).initial_cash
    except Exception:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Decimal(str(raw.get("initial_cash", raw.get("starting_cash", "0"))))


def load_configured_universe_symbols(config_dir: Path | None = None) -> list[str]:
    """Ingest-scope symbols from kite.json (or empty). Used when run has no universe."""
    root = config_dir or (_resolve_repo_root() / "config")
    kite_path = Path(root) / "providers" / "kite.json"
    if not kite_path.is_file():
        return []
    raw = json.loads(kite_path.read_text(encoding="utf-8"))
    symbols = raw.get("symbols") or []
    out: list[str] = []
    for sym in symbols:
        text = str(sym).strip()
        if not text:
            continue
        # Normalize NSE:INFY → INFY for dashboard display
        if ":" in text:
            text = text.split(":", 1)[1]
        out.append(text)
    return out


class SqliteCandleHistoryProvider:
    """Read-only candle history from the live ATHENA ledger."""

    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo

    def list_recent_candles(
        self,
        instrument_id: str,
        timeframe: Timeframe,
        *,
        limit: int,
    ) -> list[Candle]:
        return self._repo.list_candles_recent(
            instrument_id,
            timeframe,
            limit=limit,
        )


class SqliteDecisionProvider:
    """DecisionProvider backed by SqliteRepository."""

    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo

    def get_decisions(
        self, spec: QuerySpecification[DecisionFilterParams]
    ) -> CollectionResult[Decision]:
        # Pull a generous window then apply API filters/sort/page in-memory.
        # Dashboard walks pages (page_size<=100) and dedupes latest-per-instrument;
        # keep this window large enough for Nifty-scale validate runs.
        decisions = self._repo.list_decisions(limit=5000)

        def filter_func(d: Decision) -> bool:
            f = spec.filters
            if f.instrument_id and d.instrument_id != f.instrument_id:
                return False
            if f.decision_type and d.decision_type != f.decision_type:
                return False
            if f.direction and d.direction != f.direction:
                return False
            if f.from_date and d.ts < f.from_date:
                return False
            return not (f.to_date and d.ts > f.to_date)

        def sort_func(d: Decision) -> Any:
            sort_by = spec.sort.sort_by
            if sort_by == "ts":
                return d.ts
            if sort_by == "instrument_id":
                return d.instrument_id or ""
            return d.decision_id

        return apply_query_spec(list(decisions), spec, filter_func, sort_func)

    def get_decision(self, decision_id: str) -> Decision | None:
        return self._repo.get_decision(decision_id)

    def get_trace(self, decision_id: str) -> DecisionTrace | None:
        return self._repo.get_trace(decision_id)


class SqlitePortfolioProvider:
    """Owner-entered fill ledger → domain Portfolio (+ open/close writes)."""

    def __init__(
        self,
        repo: SqliteRepository,
        *,
        starting_cash: Decimal | None = None,
    ) -> None:
        self._repo = repo
        self._starting_cash = (
            starting_cash if starting_cash is not None else load_starting_cash()
        )

    def get_portfolio(self) -> Portfolio:
        positions = tuple(self._repo.list_owner_positions(limit=2000))
        cash = self._compute_cash(positions)
        exposure = self._compute_exposure(positions)
        now = datetime.now(tz=timezone.utc)
        # Enrich open positions with latest quote mark when available
        enriched: list[Position] = []
        for pos in positions:
            if pos.closed_ts is not None:
                enriched.append(pos)
                continue
            mark = self._latest_mark(pos.instrument_id)
            if mark is None:
                meta = dict(pos.meta)
                meta["mark_status"] = "no_mark"
                enriched.append(
                    Position(
                        position_id=pos.position_id,
                        instrument_id=pos.instrument_id,
                        opened_ts=pos.opened_ts,
                        quantity=pos.quantity,
                        avg_price=pos.avg_price,
                        closed_ts=pos.closed_ts,
                        meta=meta,
                    )
                )
                continue
            meta = dict(pos.meta)
            meta["current_price"] = str(mark)
            meta["mark_status"] = "quoted"
            enriched.append(
                Position(
                    position_id=pos.position_id,
                    instrument_id=pos.instrument_id,
                    opened_ts=pos.opened_ts,
                    quantity=pos.quantity,
                    avg_price=pos.avg_price,
                    closed_ts=pos.closed_ts,
                    meta=meta,
                )
            )
        return Portfolio(
            ts=now,
            positions=tuple(enriched),
            cash=cash,
            exposure_by_sector=exposure,
        )

    def open_position(
        self,
        *,
        instrument_id: str,
        quantity: int,
        avg_price: Decimal,
        opened_ts: datetime | None = None,
        decision_ref: str | None = None,
        broker: str = "",
        notes: str = "",
        sector: str = "",
    ) -> Position:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if avg_price <= 0:
            raise ValueError("avg_price (entry) must be positive")
        symbol = instrument_id.strip().upper()
        if not symbol:
            raise ValueError("instrument_id is required")
        opened = opened_ts or datetime.now(tz=timezone.utc)
        if opened.tzinfo is None:
            raise ValueError("opened_ts must be timezone-aware")
        position_id = f"pos-{uuid4().hex[:12]}"
        self._repo.save_owner_position(
            position_id=position_id,
            instrument_id=symbol,
            opened_ts=opened,
            quantity=quantity,
            avg_price=avg_price,
            decision_ref=decision_ref,
            broker=broker.strip().lower(),
            notes=notes,
            sector=sector,
            meta={},
        )
        pos = self._repo.get_owner_position(position_id)
        assert pos is not None
        return pos

    def close_position(
        self,
        position_id: str,
        *,
        exit_price: Decimal,
        closed_ts: datetime | None = None,
    ) -> Position:
        if exit_price <= 0:
            raise ValueError("exit_price must be positive")
        existing = self._repo.get_owner_position(position_id)
        if existing is None:
            raise KeyError(f"position '{position_id}' not found")
        if existing.closed_ts is not None:
            raise ValueError(f"position '{position_id}' is already closed")
        closed = closed_ts or datetime.now(tz=timezone.utc)
        if closed.tzinfo is None:
            raise ValueError("closed_ts must be timezone-aware")
        meta = dict(existing.meta)
        broker = str(meta.get("broker", ""))
        notes = str(meta.get("notes", ""))
        sector = str(meta.get("sector", ""))
        decision_ref = meta.get("decision_ref")
        self._repo.save_owner_position(
            position_id=existing.position_id,
            instrument_id=existing.instrument_id,
            opened_ts=existing.opened_ts,
            quantity=existing.quantity,
            avg_price=existing.avg_price,
            closed_ts=closed,
            exit_price=exit_price,
            decision_ref=str(decision_ref) if decision_ref else None,
            broker=broker,
            notes=notes,
            sector=sector,
            meta={
                k: v
                for k, v in meta.items()
                if k
                not in ("broker", "notes", "sector", "decision_ref", "exit_price")
            },
        )
        pos = self._repo.get_owner_position(position_id)
        assert pos is not None
        return pos

    def reset_positions(self, *, scope: str) -> int:
        if scope not in ("open", "all"):
            raise ValueError(f"invalid reset scope: {scope}")
        return self._repo.delete_owner_positions(scope=scope)

    def _compute_cash(self, positions: tuple[Position, ...] | list[Position]) -> Decimal:
        cash = self._starting_cash
        for pos in positions:
            cost = Decimal(pos.quantity) * pos.avg_price
            if pos.closed_ts is None:
                cash -= cost
            else:
                exit_raw = pos.meta.get("exit_price")
                if exit_raw is None:
                    continue
                proceeds = Decimal(pos.quantity) * Decimal(str(exit_raw))
                cash = cash - cost + proceeds
        return cash

    def _compute_exposure(
        self, positions: tuple[Position, ...] | list[Position]
    ) -> dict[str, Decimal]:
        exposure: dict[str, Decimal] = {}
        for pos in positions:
            if pos.closed_ts is not None:
                continue
            sector = str(pos.meta.get("sector") or "Unspecified")
            value = Decimal(pos.quantity) * pos.avg_price
            exposure[sector] = exposure.get(sector, Decimal("0")) + value
        return exposure

    def _latest_mark(self, instrument_id: str) -> Decimal | None:
        """Best-effort last quote; returns None when no mark (never fabricates)."""
        candidates = [instrument_id]
        if ":" not in instrument_id:
            candidates.append(f"NSE:{instrument_id}")
        try:
            for iid in candidates:
                quotes = self._repo.get_quotes(iid)
                if quotes:
                    return quotes[-1].last_price
        except Exception:
            return None
        return None


class SqlitePipelineRunProvider:
    """Map SQLite RunRecord (+ detail_json) into SystemPipelineResult for the API."""

    def __init__(
        self,
        repo: SqliteRepository,
        *,
        config_dir: Path | None = None,
    ) -> None:
        self._repo = repo
        self._config_dir = config_dir

    def get_runs(
        self, spec: QuerySpecification[PipelineRunFilterParams]
    ) -> CollectionResult[SystemPipelineResult]:
        runs = [
            self._to_system_result(r)
            for r in self._repo.list_runs(limit=500)
        ]

        def filter_func(item: SystemPipelineResult) -> bool:
            f = spec.filters
            return not (
                f.overall_status
                and item.overall_status.value != f.overall_status
            )

        def sort_func(item: SystemPipelineResult) -> Any:
            sort_by = spec.sort.sort_by
            if sort_by in ("as_of", "started_ts", None, ""):
                return item.as_of
            return item.run_id

        return apply_query_spec(runs, spec, filter_func, sort_func)

    def get_run(self, run_id: str) -> SystemPipelineResult | None:
        record = self._repo.get_run(run_id)
        if record is None:
            return None
        return self._to_system_result(record)

    def _to_system_result(self, record) -> SystemPipelineResult:
        detail = self._repo.get_run_detail(record.run_id)
        data = self._extract_context_data(detail)
        status = (
            PipelineStatus.SUCCESS
            if record.status == RunStatus.COMPLETED
            else PipelineStatus.FAILED
        )
        ctx = PipelineContext(
            run_id=record.run_id,
            as_of=record.started_ts,
            data=data,
        )
        meta = PipelineMetadata(
            definition_id="athena-cycle",
            version=record.blueprint_version,
            name="Dry-run cycle",
            description=f"trigger={record.trigger.value}",
        )
        stage = StageResult(
            stage_id="cycle",
            status=StageStatus.SUCCESS if status == PipelineStatus.SUCCESS else StageStatus.FAILED,
            message=str(detail.get("phase") or record.status.value),
        )
        pipeline_run = PipelineResult(
            pipeline_run_id=f"{record.run_id}-cycle",
            metadata=meta,
            as_of=record.started_ts,
            stages=(stage,),
            overall_status=status,
            final_context=ctx,
        )
        return SystemPipelineResult(
            run_id=record.run_id,
            as_of=record.started_ts,
            pipeline_runs=(pipeline_run,),
            workspace_snapshot=None,
            overall_status=status,
            final_context=ctx,
        )

    def _extract_context_data(self, detail: dict) -> dict[str, object]:
        """Pull regime/universe from run detail, else configured ingest symbols."""
        data: dict[str, object] = {}
        pipeline = detail.get("pipeline")
        if isinstance(pipeline, dict):
            for key in (
                "regime_assessment",
                "universe_members",
                "qualified_today",
                "universe_source",
                "universe_summary",
                "validation_summary",
                "final_context",
            ):
                if key in pipeline:
                    val = pipeline[key]
                    if key == "final_context" and isinstance(val, dict):
                        nested = val.get("data") if isinstance(val.get("data"), dict) else val
                        if isinstance(nested, dict):
                            data.update(nested)
                    else:
                        data[key] = val
            # Nested paper pipeline payloads may stash assessments under other keys
            if "regime_assessment" not in data and "regime" in pipeline:
                data["regime_assessment"] = pipeline["regime"]

        if "regime_assessment" in detail and "regime_assessment" not in data:
            data["regime_assessment"] = detail["regime_assessment"]
        if "universe_members" in detail and "universe_members" not in data:
            data["universe_members"] = detail["universe_members"]
        if "qualified_today" in detail and "qualified_today" not in data:
            data["qualified_today"] = detail["qualified_today"]
        if "universe_members" not in data:
            # No eligibility payload in this run — do not pretend kite.json symbols are Eligible.
            data["universe_members"] = {}
            data["universe_source"] = "no_validation_run"
            data["universe_note"] = (
                "No UniverseEngine validation in this run. "
                "Add candidates on Market Intelligence and run athena cycle / ./athena-run-due."
            )
            # Optional: surface configured ingest symbols as unvalidated reference only
            symbols = load_configured_universe_symbols(self._config_dir)
            if symbols:
                data["configured_ingest_symbols"] = symbols
        return data
