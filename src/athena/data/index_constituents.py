"""Versioned, checksum-verified index constituent snapshots (IX-3)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from athena.errors import ConfigError
from athena.ops.constituents import ConstituentFetchError, parse_nifty_constituent_rows

_OVERLAP_POLICY = "COUNT_ONCE_PER_INDEX_INDEPENDENT_ACROSS_INDICES"


@dataclass(frozen=True, slots=True)
class IndexConstituentSet:
    key: str
    symbols: tuple[str, ...]
    source_url: str
    sha256: str


@dataclass(frozen=True, slots=True)
class IndexConstituentSnapshot:
    schema_version: int
    provider: str
    effective_date: date
    retrieved_at: datetime
    overlap_policy: str
    indices: tuple[IndexConstituentSet, ...]

    def by_key(self) -> dict[str, IndexConstituentSet]:
        return {item.key: item for item in self.indices}


def load_index_constituent_snapshot(
    manifest_path: Path,
    *,
    expected_index_keys: set[str],
) -> IndexConstituentSnapshot:
    """Load one immutable constituent snapshot and fail on provenance drift."""
    path = Path(manifest_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"invalid index constituent manifest {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"index constituent manifest {path} must be an object")

    schema_version = raw.get("schema_version")
    if schema_version != 1:
        raise ConfigError(f"unsupported constituent schema_version: {schema_version}")
    provider = _required_text(raw, "provider", path)
    effective_date = _parse_date(raw.get("effective_date"), "effective_date", path)
    retrieved_at = _parse_datetime(raw.get("retrieved_at"), "retrieved_at", path)
    overlap_policy = _required_text(raw, "overlap_policy", path)
    if overlap_policy != _OVERLAP_POLICY:
        raise ConfigError(f"unsupported constituent overlap_policy: {overlap_policy}")

    entries = raw.get("indices")
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"index constituent manifest {path} has no indices")
    loaded: list[IndexConstituentSet] = []
    seen_keys: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigError(f"index constituent manifest {path} contains a non-object entry")
        key = _required_text(entry, "key", path)
        if key in seen_keys:
            raise ConfigError(f"duplicate constituent index key: {key}")
        seen_keys.add(key)
        file_name = _required_text(entry, "file", path)
        source_url = _required_text(entry, "source_url", path)
        expected_sha = _required_text(entry, "sha256", path).lower()
        expected_count = entry.get("member_count")
        if not isinstance(expected_count, int) or expected_count < 1:
            raise ConfigError(f"invalid member_count for constituent index {key}")
        member_file = path.parent / file_name
        if member_file.parent.resolve() != path.parent.resolve():
            raise ConfigError(f"constituent file must stay beside manifest: {file_name}")
        try:
            payload = member_file.read_bytes()
        except OSError as exc:
            raise ConfigError(f"cannot read constituent file {member_file}: {exc}") from exc
        actual_sha = hashlib.sha256(payload).hexdigest()
        if actual_sha != expected_sha:
            raise ConfigError(
                f"constituent checksum mismatch for {key}: expected {expected_sha}, got {actual_sha}"
            )
        try:
            rows = parse_nifty_constituent_rows(payload.decode("utf-8-sig"))
        except (UnicodeDecodeError, ConstituentFetchError) as exc:
            raise ConfigError(f"invalid constituent file for {key}: {exc}") from exc
        symbols = tuple(sorted(row.symbol for row in rows))
        if len(symbols) != expected_count:
            raise ConfigError(
                f"constituent member_count mismatch for {key}: expected {expected_count}, got {len(symbols)}"
            )
        loaded.append(
            IndexConstituentSet(
                key=key,
                symbols=symbols,
                source_url=source_url,
                sha256=actual_sha,
            )
        )

    if seen_keys != expected_index_keys:
        missing = sorted(expected_index_keys - seen_keys)
        unknown = sorted(seen_keys - expected_index_keys)
        raise ConfigError(
            f"constituent catalog keys differ from tracked indices; missing={missing}, unknown={unknown}"
        )
    return IndexConstituentSnapshot(
        schema_version=schema_version,
        provider=provider,
        effective_date=effective_date,
        retrieved_at=retrieved_at,
        overlap_policy=overlap_policy,
        indices=tuple(loaded),
    )


def _required_text(raw: dict[str, object], key: str, path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"index constituent manifest {path} requires {key}")
    return value.strip()


def _parse_date(value: object, field: str, path: Path) -> date:
    if not isinstance(value, str):
        raise ConfigError(f"index constituent manifest {path} requires {field}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(f"invalid {field} in index constituent manifest {path}") from exc


def _parse_datetime(value: object, field: str, path: Path) -> datetime:
    if not isinstance(value, str):
        raise ConfigError(f"index constituent manifest {path} requires {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConfigError(f"invalid {field} in index constituent manifest {path}") from exc
    if parsed.tzinfo is None:
        raise ConfigError(f"{field} in index constituent manifest {path} must be timezone-aware")
    return parsed
