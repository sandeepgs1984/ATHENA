"""File-backed InstitutionalFlowProvider (ADR-008 / DD-11) — CI and replay."""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from athena.config.models import InstitutionalFileProviderConfig
from athena.domain.enums import HealthStatus
from athena.domain.interfaces import ProviderHealth
from athena.domain.market import InstitutionalFlowSession
from athena.errors import ProviderError


def _dec(raw: str, field: str, where: str) -> Decimal:
    try:
        return Decimal(raw.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ProviderError(f"invalid {field} at {where}: {raw!r}") from exc


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "y", "provisional"}


class FileInstitutionalFlowProvider:
    """Reads FII/DII cash rows from a CSV under data_root (deterministic)."""

    name = "institutional_file"

    def __init__(self, config: InstitutionalFileProviderConfig, data_root: Path) -> None:
        self._config = config
        self._data_root = Path(data_root)
        self._path = self._data_root / config.flows_file

    @classmethod
    def from_config_dir(
        cls, config_dir: Path, base_dir: Path | None = None
    ) -> FileInstitutionalFlowProvider:
        from athena.config.loader import load_institutional_file_provider_config

        config = load_institutional_file_provider_config(config_dir)
        base = Path(base_dir) if base_dir is not None else Path(config_dir).resolve().parent
        root = Path(config.data_root)
        data_root = root if root.is_absolute() else base / root
        return cls(config, data_root)

    def latest_session(self) -> InstitutionalFlowSession:
        rows = self._load_all()
        if not rows:
            raise ProviderError(f"no institutional flow rows in {self._path}")
        return max(rows, key=lambda s: (s.session_date, s.fetched_at))

    def sessions(self, start: date, end: date) -> list[InstitutionalFlowSession]:
        if start > end:
            raise ProviderError(f"invalid institutional flow range: {start} > {end}")
        return sorted(
            (s for s in self._load_all() if start <= s.session_date <= end),
            key=lambda s: (s.session_date, s.fetched_at),
        )

    def health(self) -> ProviderHealth:
        if not self._path.exists():
            return ProviderHealth(
                status=HealthStatus.BLOCKED,
                detail=f"institutional flow file missing: {self._path}",
            )
        try:
            latest = self.latest_session()
        except ProviderError as exc:
            return ProviderHealth(status=HealthStatus.WARN, detail=str(exc))
        return ProviderHealth(
            status=HealthStatus.OK,
            detail=f"file institutional flow from {self._path}",
            last_data_ts=latest.fetched_at,
        )

    def _load_all(self) -> list[InstitutionalFlowSession]:
        if not self._path.exists():
            raise ProviderError(f"missing institutional flow file: {self._path}")
        rows: list[InstitutionalFlowSession] = []
        with self._path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            expected = {
                "session_date", "fii_buy", "fii_sell", "fii_net",
                "dii_buy", "dii_sell", "dii_net", "provisional",
            }
            if reader.fieldnames is None or not expected.issubset(
                {c.strip() for c in reader.fieldnames}
            ):
                raise ProviderError(
                    f"invalid institutional flow CSV {self._path}: "
                    f"expected columns {sorted(expected)}, got {reader.fieldnames}"
                )
            for line_no, row in enumerate(reader, start=2):
                where = f"{self._path}:{line_no}"
                try:
                    session_date = date.fromisoformat(row["session_date"].strip())
                    fetched_raw = (row.get("fetched_at") or "").strip()
                    fetched_at = (
                        datetime.fromisoformat(fetched_raw)
                        if fetched_raw
                        else datetime(
                            session_date.year, session_date.month, session_date.day,
                            15, 30, tzinfo=timezone.utc,
                        )
                    )
                    if fetched_at.tzinfo is None:
                        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
                    rows.append(
                        InstitutionalFlowSession(
                            session_date=session_date,
                            fii_buy=_dec(row["fii_buy"], "fii_buy", where),
                            fii_sell=_dec(row["fii_sell"], "fii_sell", where),
                            fii_net=_dec(row["fii_net"], "fii_net", where),
                            dii_buy=_dec(row["dii_buy"], "dii_buy", where),
                            dii_sell=_dec(row["dii_sell"], "dii_sell", where),
                            dii_net=_dec(row["dii_net"], "dii_net", where),
                            provisional=_parse_bool(row.get("provisional", "true")),
                            source_id=row.get("source_id", "").strip() or "file",
                            fetched_at=fetched_at,
                            run_id=(row.get("run_id") or "").strip(),
                        )
                    )
                except (KeyError, ValueError) as exc:
                    raise ProviderError(f"corrupted institutional flow at {where}: {exc}") from exc
        return rows
