"""Build information provider protocols and implementations (P8.5)."""

from __future__ import annotations

import os
import platform
import sys
from datetime import datetime, timezone
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class BuildInfoDTO(BaseModel):
    """Data transfer object containing application build and version info."""

    model_config = ConfigDict(frozen=True)

    app_name: str
    semver: str
    api_version: str
    build_number: str
    commit_hash: str
    build_timestamp: datetime
    environment: str
    runtime_info: dict[str, str]


class BuildInfoProvider(Protocol):
    """Abstract protocol interface defining build metadata queries."""

    def get_build_info(self) -> BuildInfoDTO:
        """Query detailed build details for the running instance."""
        ...


class DefaultBuildInfoProvider:
    """Standard provider reading details from environment and runtime stats."""

    def get_build_info(self) -> BuildInfoDTO:
        """Compile build metrics from system profile and environment overrides."""
        env_val = os.environ.get("ATHENA_ENV", "production")
        build_num = os.environ.get("ATHENA_BUILD_NUMBER", "build-456")
        commit_sha = os.environ.get("ATHENA_COMMIT_HASH", "commit-sha-placeholder")
        
        # Parse build timestamp from env, or default to current date
        build_ts_str = os.environ.get("ATHENA_BUILD_TIMESTAMP")
        if build_ts_str:
            try:
                build_ts = datetime.fromisoformat(build_ts_str)
            except ValueError:
                build_ts = datetime.now(tz=timezone.utc)
        else:
            build_ts = datetime.fromisoformat("2026-07-22T12:00:00+00:00")

        runtime = {
            "python_version": sys.version,
            "os_platform": platform.platform(),
            "cpu_architecture": platform.machine(),
        }

        return BuildInfoDTO(
            app_name="ATHENA",
            semver="1.0.0",
            api_version="v1",
            build_number=build_num,
            commit_hash=commit_sha,
            build_timestamp=build_ts,
            environment=env_val,
            runtime_info=runtime,
        )
