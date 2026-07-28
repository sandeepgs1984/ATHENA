"""Nifty 500 (and related) constituent fetch for owner candidate seeding.

Primary source: official NSE Indices CSV (no cookie/session dance).
Injectable HTTP + optional local file for tests and offline replay.
"""

from __future__ import annotations

import csv
import io
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol

from athena.errors import AthenaError, ConfigError
from athena.ops.owner_candidates import (
    CandidateStore,
    normalize_candidate_symbol,
)

DEFAULT_NIFTY500_URL = (
    "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
)
DEFAULT_NIFTY500_FALLBACK_URL = (
    "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
)

_USER_AGENT = (
    "Mozilla/5.0 (compatible; ATHENA/1.0; +https://github.com/local/athena; "
    "decision-intelligence; no-orders)"
)


class ConstituentFetchError(AthenaError):
    """Failed to download or parse index constituents."""


class HttpGet(Protocol):
    def __call__(self, url: str, *, timeout: float) -> str: ...


def default_http_get(url: str, *, timeout: float = 30.0) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/csv,*/*"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise ConstituentFetchError(
            f"constituent HTTP {exc.code} for {url}: {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ConstituentFetchError(f"constituent network failure for {url}: {exc.reason}") from exc
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ConstituentFetchError(f"constituent CSV not UTF-8 for {url}") from exc


def parse_nifty_constituent_csv(text: str) -> tuple[str, ...]:
    """Parse NSE/niftyindices constituent CSV → unique bare trading symbols."""
    return tuple(row.symbol for row in parse_nifty_constituent_rows(text))


@dataclass(frozen=True, slots=True)
class NiftyConstituentRow:
    """One NSE index-constituent row — Symbol + Industry (MI-4 sector source)."""

    symbol: str
    industry: str | None = None


def parse_nifty_constituent_rows(text: str) -> tuple[NiftyConstituentRow, ...]:
    """Parse NSE/niftyindices constituent CSV → unique (symbol, industry) rows.

    Industry is the NSE CSV column that ATHENA labels Sector in the Universe
    table. Absent/blank Industry stays None — never fabricated.
    """
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ConstituentFetchError("constituent CSV has no header")
    fields = {f.strip().lower(): f for f in reader.fieldnames if f}
    symbol_key = fields.get("symbol")
    if symbol_key is None:
        raise ConstituentFetchError(
            f"constituent CSV missing Symbol column; got {list(reader.fieldnames)}"
        )
    industry_key = fields.get("industry")
    seen: set[str] = set()
    ordered: list[NiftyConstituentRow] = []
    for row in reader:
        raw = (row.get(symbol_key) or "").strip()
        if not raw:
            continue
        try:
            sym = normalize_candidate_symbol(raw)
        except ValueError:
            continue
        if sym in seen:
            continue
        seen.add(sym)
        industry_raw = (row.get(industry_key) or "").strip() if industry_key else ""
        ordered.append(
            NiftyConstituentRow(
                symbol=sym,
                industry=industry_raw or None,
            )
        )
    if not ordered:
        raise ConstituentFetchError("constituent CSV produced zero symbols")
    return tuple(ordered)


@dataclass(frozen=True, slots=True)
class CandidateSeedResult:
    source: str
    status: str  # seeded | skipped_already_today | disabled | failed
    as_of_date: date
    fetched: int
    added: int
    already_present: int
    url_used: str | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "status": self.status,
            "as_of_date": self.as_of_date.isoformat(),
            "fetched": self.fetched,
            "added": self.added,
            "already_present": self.already_present,
            "url_used": self.url_used,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class CandidateSeedConfig:
    """Ops settings for daily owner_candidates seeding (merge-unique)."""

    source: str = "none"  # none | NIFTY500
    merge_unique: bool = True
    once_per_day: bool = True
    url: str = DEFAULT_NIFTY500_URL
    fallback_url: str = DEFAULT_NIFTY500_FALLBACK_URL
    local_file: str | None = None
    http_timeout_seconds: float = 30.0
    notes_prefix: str = "seed:NIFTY500"

    def __post_init__(self) -> None:
        src = self.source.strip().upper()
        if src in ("", "NONE", "OFF", "DISABLED"):
            object.__setattr__(self, "source", "none")
        elif src in ("NIFTY500", "NIFTY_500", "NIFTY 500"):
            object.__setattr__(self, "source", "NIFTY500")
        else:
            raise ConfigError(
                f"candidate_seed.source '{self.source}' unsupported; "
                "allowed: none, NIFTY500"
            )
        if self.http_timeout_seconds <= 0:
            raise ConfigError("candidate_seed.http_timeout_seconds must be > 0")


def load_candidate_seed_config(config_dir: Path) -> CandidateSeedConfig:
    import json

    path = Path(config_dir) / "candidate_seed.json"
    if not path.is_file():
        return CandidateSeedConfig()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError("candidate_seed.json must be a JSON object")
    raw.pop("_meta", None)
    return CandidateSeedConfig(**{k: v for k, v in raw.items() if k in CandidateSeedConfig.__dataclass_fields__})


class CandidateSeeder:
    """Fetch constituents and merge-unique into the owner candidate store."""

    def __init__(
        self,
        store: CandidateStore,
        config: CandidateSeedConfig,
        *,
        repo_root: Path | None = None,
        http_get: HttpGet | None = None,
        meta_get: Callable[[str], str | None] | None = None,
        meta_set: Callable[[str, str], None] | None = None,
        instrument_repo: object | None = None,
    ) -> None:
        self._store = store
        self._config = config
        self._repo_root = Path(repo_root) if repo_root else Path.cwd()
        self._http_get = http_get or default_http_get
        self._meta_get = meta_get
        self._meta_set = meta_set
        # Optional SqliteRepository — used only for MI-4 sector backfill.
        self._instrument_repo = instrument_repo

    def run(self, *, as_of: datetime) -> CandidateSeedResult:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        day = as_of.date()
        cfg = self._config
        if cfg.source == "none":
            return CandidateSeedResult(
                source="none",
                status="disabled",
                as_of_date=day,
                fetched=0,
                added=0,
                already_present=0,
                detail="candidate seeding disabled",
            )

        meta_key = f"candidate_seed:{cfg.source}:last_date"
        rows, url_used = self._load_rows()
        # MI-4: Industry→instruments.sector always, even when candidate merge
        # is skipped for the day — otherwise sector stays null forever after
        # the first once-per-day seed.
        sectors_written = self._apply_sectors(rows)

        if cfg.once_per_day and self._meta_get is not None:
            last = self._meta_get(meta_key)
            if last == day.isoformat():
                return CandidateSeedResult(
                    source=cfg.source,
                    status="skipped_already_today",
                    as_of_date=day,
                    fetched=len(rows),
                    added=0,
                    already_present=0,
                    url_used=url_used,
                    detail=(
                        f"already seeded for {day.isoformat()}"
                        + (f"; sector backfill updated {sectors_written} instruments" if sectors_written else "")
                    ),
                )

        existing = {
            c.symbol for c in self._store.list_candidates(active_only=False)
        }
        added = 0
        already = 0
        ts = as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        for row in rows:
            sym = row.symbol
            if sym in existing:
                already += 1
                continue
            if not cfg.merge_unique:
                # replace mode not used for this milestone; treat as merge
                pass
            self._store.upsert_candidate(
                symbol=sym,
                notes=cfg.notes_prefix,
                active=True,
                added_ts=ts,
            )
            existing.add(sym)
            added += 1

        if self._meta_set is not None:
            self._meta_set(meta_key, day.isoformat())

        detail = f"merge-unique: added {added}, already present {already}"
        if sectors_written:
            detail = f"{detail}; sector backfill updated {sectors_written} instruments"
        return CandidateSeedResult(
            source=cfg.source,
            status="seeded",
            as_of_date=day,
            fetched=len(rows),
            added=added,
            already_present=already,
            url_used=url_used,
            detail=detail,
        )

    def _apply_sectors(self, rows: Sequence[NiftyConstituentRow]) -> int:
        repo = self._instrument_repo
        if repo is None:
            return 0
        updated = 0
        for row in rows:
            if not row.industry:
                continue
            updated += int(repo.update_instrument_sector(row.symbol, row.industry) or 0)
        return updated

    def _load_rows(self) -> tuple[Sequence[NiftyConstituentRow], str | None]:
        cfg = self._config
        if cfg.local_file:
            path = Path(cfg.local_file)
            if not path.is_absolute():
                path = self._repo_root / path
            if not path.is_file():
                raise ConstituentFetchError(f"constituents local_file missing: {path}")
            text = path.read_text(encoding="utf-8-sig")
            return parse_nifty_constituent_rows(text), str(path)

        errors: list[str] = []
        for url in (cfg.url, cfg.fallback_url):
            if not url:
                continue
            try:
                text = self._http_get(url, timeout=cfg.http_timeout_seconds)
                return parse_nifty_constituent_rows(text), url
            except ConstituentFetchError as exc:
                errors.append(str(exc))
        raise ConstituentFetchError(
            "all constituent URLs failed: " + " | ".join(errors)
        )
