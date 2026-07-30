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
    EligibilityRuleDTO,
    FullValidationProgressDTO,
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
from athena.errors import AthenaError, DataValidationError
from athena.ops.owner_candidates import CandidateStore, normalize_candidate_symbol
from athena.ops.symbol_validate import resolve_against_catalog, validate_symbols

_RUN_SCAN_LIMIT = 50
_DECISION_SCAN_LIMIT = 2000


class CandidateNotFoundError(ResourceNotFoundError):
    """Owner candidate symbol not found."""


@dataclass(frozen=True, slots=True)
class _UniverseVerdict:
    """One symbol's outcome from the newest run that covered it."""

    status: str
    eligibility_summary: str | None
    eligibility_evidence: tuple[EligibilityRuleDTO, ...]
    validated_ts: datetime


def _bare_symbol(value: str) -> str:
    return value.upper().replace("NSE:", "").replace("BSE:", "")


def _from_detail(detail: object, key: str) -> object:
    """Read one key from a run detail, whether nested under ``pipeline`` or flat."""
    if not isinstance(detail, dict):
        return None
    pipeline = detail.get("pipeline")
    if isinstance(pipeline, dict) and key in pipeline:
        return pipeline[key]
    return detail.get(key)


def _members_from_detail(detail: object) -> dict[str, dict[str, Any]]:
    """Extract ``universe_members`` keyed by bare symbol from one run detail."""
    members_raw = _from_detail(detail, "universe_members")
    if not isinstance(members_raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, val in members_raw.items():
        if not isinstance(val, dict):
            continue
        out[_bare_symbol(str(val.get("symbol") or key))] = val
    return out


def _unresolved_from_detail(detail: object) -> dict[str, str]:
    """Extract ``unresolved_candidates`` as bare symbol → reason."""
    rows = _from_detail(detail, "unresolved_candidates")
    if not isinstance(rows, list):
        return {}
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or row.get("instrument_id") or "")
        if not symbol:
            continue
        out[_bare_symbol(symbol)] = str(row.get("reason") or "unresolved symbol")
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
        verdicts: dict[str, _UniverseVerdict] | None = None
        last_validated: dict[str, datetime] | None = None
        sectors: dict[str, str] | None = None
        if self._repo is not None:
            try:
                verdicts = self._universe_verdicts({_bare_symbol(c.symbol) for c in rows})
                last_validated = self._latest_decision_ts_by_symbol()
                sectors = self._sector_by_symbol()
            except AthenaError:
                verdicts = None
                last_validated = None
                sectors = None
        dtos = tuple(
            self._to_dto(
                c.symbol,
                c.added_ts,
                c.notes,
                c.active,
                verdicts=verdicts,
                last_validated=last_validated,
                sectors=sectors,
            )
            for c in rows
        )
        return OwnerCandidateListDTO(candidates=dtos, count=len(dtos))

    def upsert_candidate(self, body: UpsertCandidateRequest) -> OwnerCandidateDTO:
        self._reject_unlisted_symbol(body.symbol)
        row = self._store.upsert_candidate(
            symbol=body.symbol,
            notes=body.notes,
            active=body.active,
        )
        return self._to_dto(row.symbol, row.added_ts, row.notes, row.active)

    def _reject_unlisted_symbol(self, symbol: str) -> None:
        """Refuse to store a symbol the exchange does not list.

        A typo used to survive its own failed validation and stay in the
        universe, where it then aborted every later cycle. Best effort by
        design: when the catalog cannot be consulted (no credentials, offline,
        non-kite provider) the add proceeds and the symbol shows up as
        Unresolved after the next run instead of being silently trusted.
        """
        bare = normalize_candidate_symbol(symbol)
        try:
            _provider, _resolved, unresolved = resolve_against_catalog(
                self._config_dir, [bare], repo_root=self._repo_root
            )
        except Exception:
            # Any failure to consult the catalog (config, credentials, network)
            # leaves the symbol unproven, not proven wrong: allow the add.
            return
        if unresolved:
            raise DataValidationError(
                f"{bare} is not listed on the exchange — check the trading symbol "
                "(nothing was added to the universe)"
            )

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

    def start_full_validation(self) -> FullValidationProgressDTO:
        """ADR-007: kick off owner-triggered full-universe validation in the host."""
        from athena.ops.full_validation import start_full_validation

        if self._repo is None:
            raise AthenaError(
                "Full validation requires the live SQLite ledger "
                "(restart the API so wire_sqlite_providers attaches the DB)"
            )
        progress = start_full_validation(
            repo_root=self._repo_root,
            config_dir=self._config_dir,
            db_path=Path(self._repo.path),
        )
        return self._progress_dto(progress)

    def full_validation_status(self) -> FullValidationProgressDTO:
        from athena.ops.full_validation import get_full_validation_progress

        return self._progress_dto(get_full_validation_progress())

    @staticmethod
    def _progress_dto(progress) -> FullValidationProgressDTO:
        return FullValidationProgressDTO(
            state=progress.state,
            stage=progress.stage,
            symbols_total=progress.symbols_total,
            symbols_completed=progress.symbols_completed,
            started_at=progress.started_at,
            finished_at=progress.finished_at,
            run_id=progress.run_id,
            detail=progress.detail,
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
        eligibility_evidence: tuple[EligibilityRuleDTO, ...] = ()
        validated = None if last_validated is None else last_validated.get(bare)
        if verdicts is not None:
            verdict = verdicts.get(bare)
            if verdict is None:
                status = "PENDING"
            else:
                status = verdict.status
                eligibility_summary = verdict.eligibility_summary
                eligibility_evidence = verdict.eligibility_evidence
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
            eligibility_evidence=eligibility_evidence,
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
            detail = self._repo.get_run_detail(run.run_id)
            for sym, member in _members_from_detail(detail).items():
                if sym not in symbols or sym in out:
                    continue
                summary = member.get("eligibility_summary")
                evidence_raw = member.get("evidence")
                evidence = tuple(
                    EligibilityRuleDTO(
                        rule=str(item.get("rule") or "unknown"),
                        passed=bool(item.get("passed")),
                        explanation=str(item.get("explanation") or ""),
                    )
                    for item in evidence_raw
                    if isinstance(item, dict)
                ) if isinstance(evidence_raw, list) else ()
                out[sym] = _UniverseVerdict(
                    status="ELIGIBLE" if bool(member.get("included")) else "EXCLUDED",
                    eligibility_summary=str(summary) if summary else None,
                    eligibility_evidence=evidence,
                    validated_ts=run.started_ts,
                )
            for sym, reason in _unresolved_from_detail(detail).items():
                if sym not in symbols or sym in out:
                    continue
                out[sym] = _UniverseVerdict(
                    status="UNRESOLVED",
                    eligibility_summary=reason,
                    eligibility_evidence=(),
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
