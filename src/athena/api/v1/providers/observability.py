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

from athena.api.v1.dtos.common import ComponentHealth, HealthResponse, MetricsResponse

# Module-level start time for uptime calculation
_START_TIME = time.monotonic()


class ObservabilityHealthProvider:
    """Default HealthProvider.

    Returns a self-reported healthy status for the API platform layer.
    Future implementations may integrate with athena.observability.health.run_system_checks().
    """

    def get_health(self) -> HealthResponse:
        now = datetime.now(tz=timezone.utc)
        return HealthResponse(
            status="healthy",
            version="0.1.0",
            components=[
                ComponentHealth(name="api", status="healthy", detail="Platform API layer operational"),
                ComponentHealth(name="orchestration", status="healthy", detail="Orchestration runtime available"),
                ComponentHealth(name="workspace", status="healthy", detail="Intelligence Workspace available"),
                ComponentHealth(name="scheduler", status="healthy", detail="Scheduling bridge available"),
            ],
            as_of=now,
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
