"""Default observability-backed provider implementations (P8.1).

ObservabilityHealthProvider: Returns platform health from basic system checks.
ObservabilityMetricsProvider: Returns scaffold metric values.

Per PE architecture decision Q2: real metric aggregation (PipelineHistory,
ScheduleHistory) belongs to the future observability platform. P8.1 provides
scaffold counters through the provider abstraction only.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from athena.api.v1.dtos.common import (
    ComponentHealth,
    HealthResponse,
    LastCycleHealthDTO,
    MetricsResponse,
)
from athena.ops.serve_runtime import get_serve_runtime, kite_token_status_from_env

# Module-level start time for uptime calculation
_START_TIME = time.monotonic()


class ObservabilityHealthProvider:
    """Default HealthProvider.

    Returns a self-reported healthy status for the API platform layer.
    When ``athena serve`` is running, includes cycle-worker and kite token fields.
    """

    def get_health(self) -> HealthResponse:
        now = datetime.now(tz=timezone.utc)
        runtime = get_serve_runtime()
        last_cycle = None
        cycles_enabled = False
        serve_error = None
        if runtime is not None:
            snap = runtime.snapshot()
            cycles_enabled = bool(snap["cycles_enabled"])
            serve_error = snap["last_error"]  # type: ignore[assignment]
            last = snap["last_cycle"]
            if last is not None:
                last_cycle = LastCycleHealthDTO(
                    as_of=last.as_of,
                    idle=last.idle,
                    due=last.due,
                    status=last.status,
                    run_id=last.run_id,
                    trigger=last.trigger,
                    detail=last.detail,
                )

        return HealthResponse(
            status="healthy",
            version="0.1.0",
            components=[
                ComponentHealth(name="api", status="healthy", detail="Platform API layer operational"),
                ComponentHealth(name="orchestration", status="healthy", detail="Orchestration runtime available"),
                ComponentHealth(name="workspace", status="healthy", detail="Intelligence Workspace available"),
                ComponentHealth(
                    name="scheduler",
                    status="healthy",
                    detail=(
                        "Interactive cycle worker enabled"
                        if cycles_enabled
                        else "Scheduling bridge available (use --with-cycles for in-process due ticks)"
                    ),
                ),
            ],
            as_of=now,
            kite_token_status=kite_token_status_from_env(),
            cycles_enabled=cycles_enabled,
            last_cycle=last_cycle,
            serve_error=serve_error,
        )


class ObservabilityMetricsProvider:
    """Default MetricsProvider returning scaffold metric values.

    Counters are zero-value scaffolds in P8.1. Real aggregation from
    PipelineHistory and PipelineScheduleHistory is deferred to the
    future observability platform milestone.
    """

    def get_metrics(self) -> MetricsResponse:
        now = datetime.now(tz=timezone.utc)
        uptime = round(time.monotonic() - _START_TIME, 2)
        return MetricsResponse(
            pipeline_runs_total=0,
            pipeline_runs_succeeded=0,
            pipeline_runs_failed=0,
            schedule_runs_total=0,
            schedule_runs_succeeded=0,
            schedule_runs_failed=0,
            uptime_seconds=uptime,
            as_of=now,
        )
