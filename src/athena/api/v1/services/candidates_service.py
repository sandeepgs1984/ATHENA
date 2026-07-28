"""Owner candidate list service (Market Intelligence validation pool)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from athena.api.exceptions import ResourceNotFoundError
from athena.api.v1.dtos.market import (
    DeleteCandidateResultDTO,
    OwnerCandidateDTO,
    OwnerCandidateListDTO,
    UpsertCandidateRequest,
    ValidateSymbolsRequest,
    ValidateSymbolsResultDTO,
)
from athena.calendar.engine import CalendarEngine
from athena.calendar.resolve_as_of import resolve_validate_as_of
from athena.config.loader import load_config
from athena.data.store.repository import SqliteRepository
from athena.errors import AthenaError
from athena.ops.owner_candidates import CandidateStore, normalize_candidate_symbol
from athena.ops.symbol_validate import validate_symbols

_RUN_SCAN_LIMIT = 50
_DECISION_SCAN_LIMIT = 2000


class CandidateNotFoundError(ResourceNotFoundError):
    """Owner candidate symbol not found."""


@dataclass(frozen=True, slots=True)
class _UniverseVerdict:
    """One symbol's eligibility outcome from the newest run that covered it."""

    included: bool
    eligibility_summary: str | None
    validated_ts: datetime


def _bare_symbol(value: str) -> str:
    return value.upper().replace("NSE:", "").replace("BSE:", "")


def _members_from_detail(detail: object) -> dict[str, dict[str, Any]]:
    """Extract ``universe_members`` keyed by bare symbol from one run detail."""
    if not isinstance(detail, dict):
        return {}
    pipeline = detail.get("pipeline")
    members_raw = pipeline.get("universe_members") if isinstance(pipeline, dict) else None
    if members_raw is None:
        members_raw = detail.get("universe_members")
    if not isinstance(members_raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, val in members_raw.items():
        if not isinstance(val, dict):
            continue
        out[_bare_symbol(str(val.get("symbol") or key))] = val
    return out


class CandidatesService:
    def __init__(
        self,
        store: CandidateStore,
        *,
        repo: SqliteRepository | None = None,
        config_dir: Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._store = store
        self._repo = repo
        self._config_dir = Path(config_dir) if config_dir else Path("config")
        self._repo_root = Path(repo_root) if repo_root else Path.cwd()

    def list_candidates(self, *, active_only: bool = True) -> OwnerCandidateListDTO:
        rows = self._store.list_candidates(active_only=active_only)
        enrich = self._repo is not None
        verdicts = self._universe_verdicts({_bare_symbol(c.symbol) for c in rows})
        last_validated = self._latest_decision_ts_by_symbol()
        sectors = self._sector_by_symbol()
        dtos = tuple(
            self._to_dto(
                c.symbol,
                c.added_ts,
                c.notes,
                c.active,
                verdicts=verdicts if enrich else None,
                last_validated=last_validated,
                sectors=sectors,
            )
            for c in rows
        )
        return OwnerCandidateListDTO(candidates=dtos, count=len(dtos))

    def upsert_candidate(self, body: UpsertCandidateRequest) -> OwnerCandidateDTO:
        row = self._store.upsert_candidate(
            symbol=body.symbol,
            notes=body.notes,
            active=body.active,
        )
        return self._to_dto(row.symbol, row.added_ts, row.notes, row.active)

    def delete_candidate(self, symbol: str) -> DeleteCandidateResultDTO:
        bare = normalize_candidate_symbol(symbol)
        deleted = self._store.delete_candidate(bare)
        if not deleted:
            raise CandidateNotFoundError(f"Candidate '{bare}' not found")
        return DeleteCandidateResultDTO(symbol=bare, deleted=True)

    def validate_candidates(self, body: ValidateSymbolsRequest) -> ValidateSymbolsResultDTO:
        if self._repo is None:
            raise AthenaError(
                "Symbol validate requires the live SQLite ledger "
                "(restart the API so wire_sqlite_providers attaches the DB)"
            )
        cfg = load_config(self._config_dir)
        tz = ZoneInfo(cfg.market.timezone)
        calendar = CalendarEngine.from_config_dir(self._config_dir, cfg.market)
        as_of, as_of_mode = resolve_validate_as_of(datetime.now(tz), calendar, tz)
        result = validate_symbols(
            self._repo,
            self._config_dir,
            symbols=list(body.symbols),
            as_of=as_of,
            repo_root=self._repo_root,
        )
        return ValidateSymbolsResultDTO(
            run_id=result.run_id,
            status=result.status,
            symbols=result.symbols,
            eligible=result.eligible,
            excluded=result.excluded,
            decisions=result.decisions,
            qualified=result.qualified,
            detail=result.detail,
            as_of=as_of,
            as_of_mode=as_of_mode,
        )

    def _to_dto(
        self,
        symbol: str,
        added_ts: datetime,
        notes: str,
        active: bool,
        *,
        verdicts: dict[str, _UniverseVerdict] | None = None,
        last_validated: dict[str, datetime] | None = None,
        sectors: dict[str, str] | None = None,
    ) -> OwnerCandidateDTO:
        bare = _bare_symbol(symbol)
        sector = None if sectors is None else sectors.get(bare)
        status = None
        eligibility_summary = None
        validated = None if last_validated is None else last_validated.get(bare)
        if verdicts is not None:
            verdict = verdicts.get(bare)
            if verdict is None:
                status = "PENDING"
            else:
                status = "ELIGIBLE" if verdict.included else "EXCLUDED"
                eligibility_summary = verdict.eligibility_summary
                # Excluded symbols never produce a Decision, so the run that
                # judged them is the only real "last validated" evidence.
                validated = verdict.validated_ts
        return OwnerCandidateDTO(
            symbol=bare,
            added_ts=added_ts,
            notes=notes,
            active=active,
            sector=sector,
            status=status,
            eligibility_summary=eligibility_summary,
            last_validated_ts=validated,
        )

    def _sector_by_symbol(self) -> dict[str, str]:
        if self._repo is None:
            return {}
        out: dict[str, str] = {}
        for inst in self._repo.list_instruments():
            if not inst.sector:
                continue
            bare = inst.symbol.upper()
            # Prefer NSE when duplicates exist across exchanges.
            if bare in out and inst.exchange.upper() != "NSE":
                continue
            out[bare] = inst.sector
        return out

    def _universe_verdicts(self, symbols: set[str]) -> dict[str, _UniverseVerdict]:
        """Newest validation verdict per symbol, merged across recent runs.

        A scoped validate writes a run whose ``universe_members`` holds only the
        symbols it was asked about, so reading a single run flipped every other
        symbol back to PENDING. Each symbol keeps the verdict of the newest run
        that actually covered it; ``validated_ts`` is that run's start.
        """
        if self._repo is None or not symbols:
            return {}
        out: dict[str, _UniverseVerdict] = {}
        for run in self._repo.list_runs(limit=_RUN_SCAN_LIMIT):
            status = run.status.value if hasattr(run.status, "value") else str(run.status)
            if str(status).upper() not in {"COMPLETED", "SUCCESS"}:
                continue
            for sym, member in _members_from_detail(
                self._repo.get_run_detail(run.run_id)
            ).items():
                if sym not in symbols or sym in out:
                    continue
                summary = member.get("eligibility_summary")
                out[sym] = _UniverseVerdict(
                    included=bool(member.get("included")),
                    eligibility_summary=str(summary) if summary else None,
                    validated_ts=run.started_ts,
                )
            if len(out) >= len(symbols):
                break
        return out

    def _latest_decision_ts_by_symbol(self) -> dict[str, datetime]:
        if self._repo is None:
            return {}
        out: dict[str, datetime] = {}
        for decision in self._repo.list_decisions(limit=_DECISION_SCAN_LIMIT):
            bare = _bare_symbol(decision.instrument_id or "")
            if not bare or bare in out:
                continue
            out[bare] = decision.ts
        return out
