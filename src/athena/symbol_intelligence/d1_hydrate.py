"""Symbol-scoped D1 hydration for Symbol Intelligence (SI-P1).

Reuses ``LiveIngestionEngine`` + ``KiteProvider`` for one canonical
instrument. Does not call DecisionEngine, UniverseEngine, Portfolio Sync,
or DarvaX scan.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config, load_ingestion_config, load_validation_config
from athena.data.ingestion import LiveIngestionEngine, build_ingest_validator
from athena.data.providers import build_market_data_provider
from athena.data.store.repository import SqliteRepository
from athena.data.validation import QuarantineRegistry
from athena.domain.enums import Timeframe
from athena.errors import AthenaError, ConfigError, DataValidationError, ProviderError, RepositoryError


@dataclass(frozen=True, slots=True)
class SiHydrationOutcome:
    status: str
    detail: str
    candles_written: int = 0


class SymbolIntelligenceD1Hydrator:
    """Fetch and persist D1 (and configured companion frames) for one symbol."""

    def __init__(
        self,
        repo: SqliteRepository | None,
        *,
        config_dir: Path,
        ingest_fn: Callable[..., object] | None = None,
    ) -> None:
        self._repo = repo
        self._config_dir = Path(config_dir)
        self._ingest_fn = ingest_fn

    def needs_refresh(
        self,
        instrument_id: str,
        *,
        expected_session: date | None,
        as_of: datetime,
        market_tz: ZoneInfo,
    ) -> bool:
        if self._repo is None:
            return False
        candles = self._repo.list_candles_recent(
            instrument_id, Timeframe.D1, limit=1, as_of=as_of
        )
        if not candles:
            return True
        if expected_session is None:
            return False
        latest = candles[0].ts_open.astimezone(market_tz).date()
        return bool(latest < expected_session)

    def hydrate(
        self,
        instrument_id: str,
        *,
        as_of: datetime,
    ) -> SiHydrationOutcome:
        if self._repo is None:
            return SiHydrationOutcome(
                status="FAILED",
                detail="No repository is wired for D1 hydration.",
            )
        try:
            if self._ingest_fn is not None:
                result = self._ingest_fn(instrument_id=instrument_id, as_of=as_of)
                written = int(getattr(result, "candles_written", 0) or 0)
                return SiHydrationOutcome(
                    status="HYDRATED",
                    detail=f"Symbol-scoped ingest wrote {written} candle rows.",
                    candles_written=written,
                )
            written = self._run_live_ingest(instrument_id, as_of)
            return SiHydrationOutcome(
                status="HYDRATED",
                detail=f"Symbol-scoped LiveIngestionEngine wrote {written} candle rows.",
                candles_written=written,
            )
        except (ProviderError, DataValidationError, ConfigError, RepositoryError, AthenaError) as exc:
            return SiHydrationOutcome(
                status="FAILED",
                detail=f"D1 hydration failed: {exc}",
            )

    def _run_live_ingest(self, instrument_id: str, as_of: datetime) -> int:
        if self._repo is None:
            raise RepositoryError("No repository is wired for D1 hydration.")
        cfg = load_config(self._config_dir)
        tz = ZoneInfo(cfg.market.timezone)
        ingest_cfg = load_ingestion_config(self._config_dir)
        validation = load_validation_config(self._config_dir)
        calendar = CalendarEngine.from_config_dir(self._config_dir, cfg.market)
        bare = instrument_id.split(":", 1)[-1]
        exchange = instrument_id.split(":", 1)[0] if ":" in instrument_id else None
        provider = build_market_data_provider(
            self._config_dir,
            provider_name=ingest_cfg.provider,
            kite_symbols=[bare],
            kite_exchange=exchange,
        )
        scoped = ingest_cfg.model_copy(
            update={
                "instrument_ids": [instrument_id],
                "include_daily": True,
                "include_quotes": False,
            }
        )
        engine = LiveIngestionEngine(
            provider,
            self._repo,
            build_ingest_validator(calendar, validation, scoped, tz),
            QuarantineRegistry(),
            scoped,
            validation,
            tzinfo=tz,
        )
        result = engine.run_cycle(as_of=as_of)
        return int(result.candles_written)
