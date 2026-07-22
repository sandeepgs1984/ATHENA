"""Platform metadata discovery providers (P8.5)."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class CapabilityMetadataDTO(BaseModel):
    """Structured operational capability metadata representation."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    category: str
    description: str
    enabled: bool
    experimental: bool


class FeaturesDTO(BaseModel):
    """Platform feature flags wrapper."""

    model_config = ConfigDict(frozen=True)

    features: dict[str, bool]


class PlatformMetadataDTO(BaseModel):
    """Consolidated platform metadata mapping."""

    model_config = ConfigDict(frozen=True)

    app_name: str
    active_profile: str
    modules: list[str]
    api_version_compatibility: list[str]
    ai: dict[str, Any]


class MetadataProvider(Protocol):
    """Abstract protocol interface defining metadata/capability discovery queries."""

    def get_metadata(self) -> PlatformMetadataDTO:
        """Query consolidated platform meta."""
        ...

    def get_features(self) -> FeaturesDTO:
        """Query active platform feature flags status."""
        ...

    def get_capabilities(self) -> list[CapabilityMetadataDTO]:
        """Query registered capabilities metadata details."""
        ...


class DefaultMetadataProvider:
    """Standard provider reading active settings and capability registry."""

    def __init__(self, active_profile: str = "production", features: dict[str, bool] | None = None) -> None:
        self._active_profile = active_profile
        self._features = features or {
            "auth": True,
            "backtest": True,
            "scanner": True,
            "strategy": True,
            "portfolio": True,
            "execution": True,
            "reporting": True,
        }
        self._capabilities = [
            CapabilityMetadataDTO(
                name="MarketDataScanning",
                version="1.0.0",
                category="INGESTION",
                description="NSE/BSE daily scanner capability",
                enabled=True,
                experimental=False,
            ),
            CapabilityMetadataDTO(
                name="WatchlistManagement",
                version="1.0.0",
                category="ORCHESTRATION",
                description="Trend watchlists tracking",
                enabled=True,
                experimental=False,
            ),
            CapabilityMetadataDTO(
                name="StrategyExecutionEngine",
                version="1.0.0",
                category="INTELLIGENCE",
                description="Rules-based swing trading decision engine",
                enabled=True,
                experimental=False,
            ),
            CapabilityMetadataDTO(
                name="BacktestingReplay",
                version="1.0.0",
                category="SIMULATION",
                description="Chronological historical replay simulation",
                enabled=True,
                experimental=False,
            ),
            CapabilityMetadataDTO(
                name="BrokerExecutionAdaptation",
                version="0.8.0",
                category="EXECUTION",
                description="External brokerage API integrations",
                enabled=False,
                experimental=True,
            ),
        ]

    def get_metadata(self) -> PlatformMetadataDTO:
        """Return platform operational metadata."""
        return PlatformMetadataDTO(
            app_name="ATHENA",
            active_profile=self._active_profile,
            modules=[
                "data",
                "evidence",
                "scoring",
                "risk",
                "decision",
                "report",
                "security",
                "analytics",
                "exports",
            ],
            api_version_compatibility=["v1"],
            ai={"enabled": False},
        )

    def get_features(self) -> FeaturesDTO:
        """Return active features flags map."""
        return FeaturesDTO(features=self._features)

    def get_capabilities(self) -> list[CapabilityMetadataDTO]:
        """Return registered capability definitions."""
        return list(self._capabilities)
