"""Official NSE corporate-action retrieval and parser boundary (EM-1r2)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from athena.errors import ProviderError
from athena.explosive_move.corporate_action_coverage import (
    CorporateActionExclusion,
    CorporateActionExclusionReason,
    OfficialCorporateActionRow,
)


@dataclass(frozen=True, slots=True)
class ParsedCorporateActionPayload:
    rows: tuple[OfficialCorporateActionRow, ...]
    exclusions: tuple[CorporateActionExclusion, ...]
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class RetrievedCorporateActionPayload:
    requested_start: date
    requested_end: date
    retrieved_at: datetime
    source_url: str
    content_type: str
    body: bytes
    parsed: ParsedCorporateActionPayload
    complete: bool
    completeness_basis: str


class NseCorporateActionsProvider:
    """Retrieve an exact inclusive date interval from the official NSE API."""

    FILINGS_URL = "https://www.nseindia.com/companies-listing/corporate-filings-actions"
    API_URL = "https://www.nseindia.com/api/corporates-corporateActions"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    )

    def __init__(
        self,
        *,
        urlopen_fn: Callable[..., object] | None = None,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        self._urlopen = (
            urlopen_fn or build_opener(HTTPCookieProcessor(CookieJar())).open
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout_seconds = timeout_seconds

    def retrieve(self, start: date, end: date) -> RetrievedCorporateActionPayload:
        if start > end:
            raise ProviderError(f"invalid corporate-action range: {start} > {end}")
        query = urlencode(
            {
                "index": "equities",
                "from_date": start.strftime("%d-%m-%Y"),
                "to_date": end.strftime("%d-%m-%Y"),
            }
        )
        source_url = f"{self.API_URL}?{query}"
        self._get(self.FILINGS_URL, accept="text/html")
        body, content_type = self._get(source_url, accept="application/json")
        if "json" not in content_type.lower():
            raise ProviderError(
                f"official NSE corporate-action response is not JSON: {content_type!r}"
            )
        try:
            root = json.loads(body.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError(f"invalid official NSE corporate-action JSON: {exc}") from exc
        if not isinstance(root, list):
            raise ProviderError("official NSE corporate-action response must be a JSON array")
        try:
            parsed = parse_official_nse_payload(
                body, source_url=source_url, content_type=content_type
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ProviderError(f"invalid official NSE corporate-action payload: {exc}") from exc
        outside = [row for row in parsed.rows if not start <= row.ex_date <= end]
        complete = not outside
        basis = (
            "Official NSE equities endpoint returned a structurally valid JSON array for the "
            "exact inclusive requested interval; all parsed ex-dates fall inside that interval."
            if complete
            else "Official NSE response contained ex-dates outside the exact requested interval."
        )
        return RetrievedCorporateActionPayload(
            requested_start=start,
            requested_end=end,
            retrieved_at=self._clock(),
            source_url=source_url,
            content_type=content_type,
            body=body,
            parsed=parsed,
            complete=complete,
            completeness_basis=basis,
        )

    def _get(self, url: str, *, accept: str) -> tuple[bytes, str]:
        request = Request(
            url,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": accept,
                "Referer": self.FILINGS_URL,
            },
            method="GET",
        )
        try:
            with self._urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read()
                headers = getattr(response, "headers", None)
                content_type = headers.get("Content-Type", "") if headers else ""
        except HTTPError as exc:
            raise ProviderError(f"NSE HTTP {exc.code} for {url}") from exc
        except URLError as exc:
            raise ProviderError(f"NSE network error for {url}: {exc.reason}") from exc
        if not isinstance(body, bytes):
            body = str(body).encode("utf-8")
        return body, content_type


class CapturedNseCorporateActionsProvider:
    """Replay exact NSE payloads referenced by an immutable EM-1r2 manifest."""

    def __init__(self, *, source_manifest: Path, evidence_root: Path) -> None:
        try:
            manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderError(f"cannot load captured NSE manifest: {source_manifest}") from exc
        raw_slices = manifest.get("retrieval_slices")
        if not isinstance(raw_slices, list) or not raw_slices:
            raise ProviderError("captured NSE manifest has no retrieval slices")
        self._evidence_root = evidence_root.resolve()
        self._slices: dict[tuple[date, date], dict[str, Any]] = {}
        for raw_slice in raw_slices:
            if not isinstance(raw_slice, dict):
                raise ProviderError("captured NSE manifest contains an invalid retrieval slice")
            try:
                key = (
                    date.fromisoformat(str(raw_slice["requested_start"])),
                    date.fromisoformat(str(raw_slice["requested_end"])),
                )
            except (KeyError, ValueError) as exc:
                raise ProviderError("captured NSE retrieval slice has invalid bounds") from exc
            if key in self._slices:
                raise ProviderError(f"duplicate captured NSE retrieval interval: {key}")
            self._slices[key] = raw_slice

    def retrieve(self, start: date, end: date) -> RetrievedCorporateActionPayload:
        raw_slice = self._slices.get((start, end))
        if raw_slice is None:
            raise ProviderError(f"captured NSE evidence has no exact interval {start} to {end}")
        try:
            artifact = (self._evidence_root / str(raw_slice["raw_artifact"])).resolve()
            artifact.relative_to(self._evidence_root)
            body = artifact.read_bytes()
            expected_digest = str(raw_slice["payload_sha256"])
            actual_digest = hashlib.sha256(body).hexdigest()
            if actual_digest != expected_digest:
                raise ProviderError(
                    f"captured NSE payload checksum mismatch: {artifact}"
                )
            source_url = str(raw_slice["source_url"])
            parsed = parse_official_nse_payload(
                body,
                source_url=source_url,
                content_type="application/json",
            )
            return RetrievedCorporateActionPayload(
                requested_start=start,
                requested_end=end,
                retrieved_at=datetime.fromisoformat(str(raw_slice["retrieved_at"])),
                source_url=source_url,
                content_type="application/json",
                body=body,
                parsed=parsed,
                complete=bool(raw_slice["complete"]),
                completeness_basis=str(raw_slice["completeness_basis"]),
            )
        except ProviderError:
            raise
        except (KeyError, OSError, ValueError) as exc:
            raise ProviderError(f"captured NSE evidence is invalid for {start} to {end}") from exc


def parse_official_nse_payload(
    payload: bytes,
    *,
    source_url: str,
    content_type: str,
) -> ParsedCorporateActionPayload:
    """Parse a captured payload without performing network I/O or guessing fields."""

    payload_sha256 = hashlib.sha256(payload).hexdigest()
    raw_rows = _raw_rows(payload, content_type)
    rows: list[OfficialCorporateActionRow] = []
    exclusions: list[CorporateActionExclusion] = []
    for position, raw in enumerate(raw_rows, start=1):
        normalized = {_key(key): value for key, value in raw.items()}
        record_id = _first(normalized, "id", "recordid", "srno") or f"row-{position}"
        symbol = _first(normalized, "symbol", "companysymbol")
        series = _first(normalized, "series")
        subject = _first(normalized, "subject", "purpose", "corporateaction")
        isin = _first(normalized, "isin") or None
        ex_date_text = _first(normalized, "exdate", "exdt")
        try:
            ex_date = _parse_date(ex_date_text)
        except ValueError:
            exclusions.append(
                CorporateActionExclusion(
                    source_record_id=record_id,
                    symbol=symbol,
                    ex_date=None,
                    reason=CorporateActionExclusionReason.MALFORMED_SOURCE_ROW,
                    detail=f"invalid or missing ex-date at source row {position}",
                    source_url=source_url,
                    payload_sha256=payload_sha256,
                )
            )
            continue
        if not symbol or not series or not subject:
            exclusions.append(
                CorporateActionExclusion(
                    source_record_id=record_id,
                    symbol=symbol,
                    ex_date=ex_date,
                    reason=CorporateActionExclusionReason.MALFORMED_SOURCE_ROW,
                    detail=f"missing symbol, series, or subject at source row {position}",
                    source_url=source_url,
                    payload_sha256=payload_sha256,
                )
            )
            continue
        rows.append(
            OfficialCorporateActionRow(
                source_record_id=record_id,
                symbol=symbol.upper(),
                series=series.upper(),
                ex_date=ex_date,
                subject=subject.strip(),
                source_url=source_url,
                payload_sha256=payload_sha256,
                isin=isin.upper() if isin else None,
            )
        )
    return ParsedCorporateActionPayload(
        rows=tuple(sorted(rows, key=lambda row: (row.ex_date, row.symbol, row.source_record_id))),
        exclusions=tuple(exclusions),
        payload_sha256=payload_sha256,
    )


def _raw_rows(payload: bytes, content_type: str) -> list[dict[str, Any]]:
    text = payload.decode("utf-8-sig")
    if "json" in content_type.lower():
        decoded = json.loads(text)
        if isinstance(decoded, list):
            return [row for row in decoded if isinstance(row, dict)]
        if isinstance(decoded, dict):
            data = decoded.get("data")
            if isinstance(data, list):
                return [row for row in data if isinstance(row, dict)]
        raise ValueError("official NSE JSON payload has no row list")
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def _key(value: str) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _first(values: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = values.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _parse_date(value: str) -> date:
    for format_string in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            from datetime import datetime

            return datetime.strptime(value, format_string).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported NSE date: {value}")
