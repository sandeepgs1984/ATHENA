"""On-demand symbol validation (ingest + eligibility + decisions) for dashboard/CLI."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.loader import (
    load_config,
    load_ingestion_config,
    load_kite_provider_config,
    load_validation_config,
)
from athena.data.ingestion import LiveIngestionEngine, build_ingest_validator
from athena.data.providers import build_market_data_provider
from athena.data.store.repository import SqliteRepository
from athena.data.validation import QuarantineRegistry
from athena.domain.enums import RunTrigger
from athena.domain.interfaces import MarketDataProvider
from athena.errors import AthenaError, ConfigError, DataValidationError
from athena.ops.owner_candidates import (
    SqliteCandidateStore,
    display_symbol,
    normalize_candidate_symbol,
)
from athena.ops.owner_validation import OwnerValidationPipeline
from athena.scheduling import DryRunCycleOrchestrator


@dataclass(frozen=True, slots=True)
class SymbolValidateResult:
    run_id: str
    status: str
    symbols: tuple[str, ...]
    eligible: int
    excluded: int
    decisions: int
    qualified: int
    detail: str = ""
    as_of: datetime | None = None
    as_of_mode: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "symbols": list(self.symbols),
            "eligible": self.eligible,
            "excluded": self.excluded,
            "decisions": self.decisions,
            "qualified": self.qualified,
            "detail": self.detail,
            "as_of": self.as_of.isoformat() if self.as_of is not None else None,
            "as_of_mode": self.as_of_mode,
        }


def resolve_against_catalog(
    config_dir: Path,
    symbols: Sequence[str],
    *,
    repo_root: Path | None = None,
) -> tuple[MarketDataProvider, dict[str, str], list[str]]:
    """Resolve bare symbols against the Kite catalog.

    Returns the scoped provider (so callers reuse one catalog fetch), a
    bare-symbol → instrument_id map for the symbols that exist, and the symbols
    the exchange does not list. Raises ``ConfigError`` when the configured
    provider has no catalog to consult.
    """
    ingest_cfg = load_ingestion_config(config_dir)
    if ingest_cfg.provider != "kite":
        raise ConfigError(
            f"symbol catalog lookup requires ingestion.provider=kite, "
            f"got {ingest_cfg.provider!r}"
        )
    bare = [normalize_candidate_symbol(s) for s in symbols]
    provider = build_market_data_provider(
        config_dir,
        base_dir=Path(repo_root) if repo_root else Path.cwd(),
        provider_name="kite",
        kite_symbols=bare,
    )
    catalog = provider.instruments()
    by_symbol = {display_symbol(i.instrument_id): i.instrument_id for i in catalog}
    by_symbol.update({i.symbol.upper(): i.instrument_id for i in catalog})
    resolved = {sym: by_symbol[sym] for sym in bare if sym in by_symbol}
    unresolved = [sym for sym in bare if sym not in by_symbol]
    return provider, resolved, unresolved


def validate_symbols(
    repo: SqliteRepository,
    config_dir: Path,
    *,
    symbols: list[str],
    as_of: datetime,
    repo_root: Path | None = None,
) -> SymbolValidateResult:
    """Ingest + UniverseEngine + scan for the given symbols only (must already be candidates)."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    bare = [normalize_candidate_symbol(s) for s in symbols]
    if not bare:
        raise ConfigError("validate_symbols requires at least one symbol")

    store = SqliteCandidateStore(repo)
    known = {c.symbol for c in store.list_candidates(active_only=False)}
    missing = [s for s in bare if s not in known]
    if missing:
        raise DataValidationError(
            "add symbols to the validation list first: " + ", ".join(missing)
        )

    root = Path(repo_root) if repo_root else Path.cwd()
    cfg = load_config(config_dir)
    tz = ZoneInfo(cfg.market.timezone)
    ingest_cfg = load_ingestion_config(config_dir)
    if ingest_cfg.provider != "kite":
        raise ConfigError(
            f"symbol validate requires ingestion.provider=kite, got {ingest_cfg.provider!r}"
        )

    provider, by_symbol, unresolved = resolve_against_catalog(
        config_dir, bare, repo_root=root
    )
    if unresolved:
        raise DataValidationError(
            "symbols not in Kite catalog: " + ", ".join(unresolved)
        )
    resolved = [by_symbol[sym] for sym in bare]
    catalog = provider.instruments()

    try:
        kite_cfg = load_kite_provider_config(config_dir)
        catalog_ids = {i.instrument_id for i in catalog}
        for extra in list(kite_cfg.index_instruments) + [kite_cfg.india_vix_instrument]:
            if extra and extra in catalog_ids and extra not in resolved:
                resolved.append(extra)
    except Exception:
        pass

    ingest_cfg = ingest_cfg.model_copy(update={"instrument_ids": resolved})
    calendar = CalendarEngine.from_config_dir(config_dir, cfg.market)
    validation = load_validation_config(config_dir)
    validator = build_ingest_validator(calendar, validation, ingest_cfg, tz)
    institutional = None
    try:
        from athena.data.providers import build_institutional_flow_provider

        institutional = build_institutional_flow_provider(
            config_dir, base_dir=config_dir.resolve().parent
        )
    except Exception:
        institutional = None
    engine = LiveIngestionEngine(
        provider,
        repo,
        validator,
        QuarantineRegistry(),
        ingest_cfg,
        validation,
        tzinfo=tz,
        institutional_provider=institutional,
    )
    pipeline = OwnerValidationPipeline(
        repo, config_dir, symbols_filter=bare
    )
    orchestrator = DryRunCycleOrchestrator(
        engine,
        repo,
        pipeline=pipeline,
        strategy_profile=cfg.base.active_profile,
        config_snapshot_id="cfg-symbol-validate",
    )
    try:
        result = orchestrator.run_cycle(RunTrigger.REFRESH, as_of=as_of)
    except AthenaError:
        # Run is still persisted as FAILED; re-raise for API mapping
        raise

    pipe = dict(result.pipeline_detail)
    summary = pipe.get("universe_summary") or {}
    qualified = pipe.get("qualified_today") or []
    bare_set = set(bare)
    return SymbolValidateResult(
        run_id=result.run.run_id,
        status=result.run.status.value,
        symbols=tuple(bare),
        eligible=int(summary.get("included", 0)),
        excluded=int(summary.get("excluded", 0)),
        decisions=sum(
            1
            for d in repo.list_decisions(limit=500)
            if display_symbol(d.instrument_id) in bare_set
            and d.ts.date() == as_of.date()
        ),
        qualified=len(qualified) if isinstance(qualified, list) else 0,
        detail=str(pipe.get("mode") or ""),
        as_of=as_of,
        as_of_mode=None,
    )
