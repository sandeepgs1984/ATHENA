"""Strategy profiles business service (P9.5)."""

from __future__ import annotations

import os
from pathlib import Path

from athena.api.v1.dtos.strategies import StrategyProfileDTO
from athena.config.loader import load_strategy_config


class StrategyService:
    """Orchestrates strategy profiles lookup and config loading."""

    def _resolve_config_dir(self) -> Path:
        env_dir = os.environ.get("ATHENA_CONFIG_DIR")
        if env_dir:
            return Path(env_dir)
        current = Path(__file__).resolve().parent
        for _ in range(10):
            if (current / "config").is_dir() and (current / "src").is_dir():
                return current / "config"
            current = current.parent
        return Path("config")

    def list_profiles(self) -> list[StrategyProfileDTO]:
        """Loads and returns all configured strategy profiles and selection rules."""
        config_dir = self._resolve_config_dir()
        cfg = load_strategy_config(config_dir)

        profiles = []
        for name, rule in cfg.strategies.items():
            # Build DTO mapping properties
            profiles.append(
                StrategyProfileDTO(
                    name=name,
                    enabled=rule.enabled,
                    description=self._get_strategy_description(name),
                    decisions=rule.decisions,
                    direction=rule.direction,
                    watchlists_any=rule.watchlists_any,
                    min_score=rule.min_score,
                    min_confidence=rule.min_confidence,
                    max_risk=rule.max_risk,
                )
            )
        return profiles

    def _get_strategy_description(self, name: str) -> str:
        descriptions = {
            "momentum": "High-conviction or improving decisions with strong composite scores.",
            "swing": "Trade/watch decisions carried by adequate confidence.",
            "breakout": "Long trade decisions with high composite scores.",
            "mean_reversion": "Improving watch/wait decisions kept within a risk ceiling.",
            "sector_rotation": "Constructive decisions surfacing in high-conviction or improving lists.",
        }
        return descriptions.get(name, "Declarative selection policy strategy.")
