"""Dry-run cycle orchestration (M10.2).

One scheduled cycle: live ingest → optional paper pipeline hook → SQLite run
ledger. No order placement. No notifications (M10.3). No AI (M10.4).
"""

from __future__ import annotations

import json
import time as _time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Protocol

from athena import BLUEPRINT_VERSION, __version__
from athena.data.ingestion.engine import LiveIngestionEngine
from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import RunStatus, RunTrigger
from athena.domain.run import RunRecord
from athena.errors import AthenaError


class DryRunPipeline(Protocol):
    """Optional paper/dry-run step after successful ingest (injectable)."""

    def run(
        self, trigger: RunTrigger, *, as_of: datetime, ingestion: IngestionResult,
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class DryRunCycleResult:
    """Immutable outcome of one dry-run cycle."""

    run: RunRecord
    ingestion: IngestionResult | None
    pipeline_detail: Mapping[str, object]
    duration_seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "pipeline_detail", MappingProxyType(dict(self.pipeline_detail)))
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run.run_id,
            "cycle_id": self.run.cycle_id,
            "trigger": self.run.trigger.value,
            "status": self.run.status.value,
            "started_ts": self.run.started_ts.isoformat(),
            "finished_ts": self.run.finished_ts.isoformat() if self.run.finished_ts else None,
            "duration_seconds": self.duration_seconds,
            "ingestion": None if self.ingestion is None else {
                "candles_written": self.ingestion.candles_written,
                "quotes_written": self.ingestion.quotes_written,
                "datasets_validated": self.ingestion.datasets_validated,
            },
            "pipeline_detail": dict(self.pipeline_detail),
        }


class DryRunCycleOrchestrator:
    """Premarket/refresh cycle: ingest, optional pipeline, persist ``RunRecord``."""

    def __init__(
        self,
        ingest_engine: LiveIngestionEngine,
        repo: SqliteRepository,
        *,
        pipeline: DryRunPipeline | None = None,
        strategy_profile: str = "intraday-momentum",
        strategy_profile_version: str = "1",
        config_snapshot_id: str = "cfg-live",
        clock: Callable[[], float] = _time.monotonic,
        run_id_factory: Callable[[RunTrigger, datetime], str] | None = None,
    ) -> None:
        self._ingest = ingest_engine
        self._repo = repo
        self._pipeline = pipeline
        self._strategy_profile = strategy_profile
        self._strategy_profile_version = strategy_profile_version
        self._config_snapshot_id = config_snapshot_id
        self._clock = clock
        self._run_id_factory = run_id_factory or _default_run_id
        self._cycle_counter = 0

    def run_cycle(self, trigger: RunTrigger, *, as_of: datetime) -> DryRunCycleResult:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        if trigger not in (RunTrigger.PREMARKET, RunTrigger.REFRESH):
            raise ValueError(
                f"dry-run cycle supports PREMARKET/REFRESH only, got {trigger.value}"
            )

        self._cycle_counter += 1
        run_id = self._run_id_factory(trigger, as_of)
        cycle_id = f"{as_of.date().isoformat()}-{trigger.value.lower()}-{self._cycle_counter:04d}"
        started = as_of
        t0 = self._clock()

        running = RunRecord(
            run_id=run_id,
            cycle_id=cycle_id,
            trigger=trigger,
            started_ts=started,
            status=RunStatus.RUNNING,
            software_version=__version__,
            blueprint_version=BLUEPRINT_VERSION,
            strategy_profile=self._strategy_profile,
            strategy_profile_version=self._strategy_profile_version,
            indicator_versions={},
            config_snapshot_id=self._config_snapshot_id,
        )
        self._repo.save_run(running, detail={"phase": "started"})

        ingestion: IngestionResult | None = None
        pipeline_detail: dict[str, object] = {"mode": "ingest_only"}
        status = RunStatus.COMPLETED
        error_detail: str | None = None
        failure: BaseException | None = None

        try:
            ingestion = self._ingest.run_cycle(as_of=as_of)
            if self._pipeline is not None:
                pipeline_detail = dict(
                    self._pipeline.run(trigger, as_of=as_of, ingestion=ingestion)
                )
                pipeline_detail.setdefault("mode", "paper_pipeline")
        except AthenaError as exc:
            status = RunStatus.FAILED
            error_detail = str(exc)
            pipeline_detail = {"mode": "failed", "error": error_detail}
            failure = exc
        except Exception as exc:  # noqa: BLE001 — cycle must always persist a terminal run
            status = RunStatus.FAILED
            error_detail = f"{type(exc).__name__}: {exc}"
            pipeline_detail = {"mode": "failed", "error": error_detail}
            failure = AthenaError(error_detail)

        finished = as_of  # business time stays injected; wall duration via clock
        duration = max(0.0, self._clock() - t0)
        final = RunRecord(
            run_id=run_id,
            cycle_id=cycle_id,
            trigger=trigger,
            started_ts=started,
            status=status,
            software_version=__version__,
            blueprint_version=BLUEPRINT_VERSION,
            strategy_profile=self._strategy_profile,
            strategy_profile_version=self._strategy_profile_version,
            indicator_versions={},
            config_snapshot_id=self._config_snapshot_id,
            input_digest=_ingestion_digest(ingestion),
            finished_ts=finished,
        )
        detail = {
            "phase": "finished",
            "duration_seconds": duration,
            "pipeline": pipeline_detail,
            "ingestion": None if ingestion is None else {
                "candles_fetched": ingestion.candles_fetched,
                "candles_written": ingestion.candles_written,
                "quotes_fetched": ingestion.quotes_fetched,
                "quotes_written": ingestion.quotes_written,
                "datasets_validated": ingestion.datasets_validated,
                "datasets_skipped_empty": ingestion.datasets_skipped_empty,
            },
        }
        if error_detail:
            detail["error"] = error_detail
        self._repo.save_run(final, detail=detail)

        result = DryRunCycleResult(
            run=final,
            ingestion=ingestion,
            pipeline_detail=pipeline_detail,
            duration_seconds=duration,
        )
        if failure is not None:
            raise failure
        return result


def _default_run_id(trigger: RunTrigger, as_of: datetime) -> str:
    stamp = as_of.strftime("%Y%m%dT%H%M%S")
    return f"run-{trigger.value.lower()}-{stamp}"


def _ingestion_digest(ingestion: IngestionResult | None) -> str:
    if ingestion is None:
        return ""
    payload = {
        "as_of": ingestion.as_of.isoformat(),
        "candles_written": ingestion.candles_written,
        "quotes_written": ingestion.quotes_written,
        "datasets_validated": ingestion.datasets_validated,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
