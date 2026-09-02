"""Generic My Portfolio holdings import parsing and symbol resolution."""

from __future__ import annotations

import csv
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from types import MappingProxyType
from xml.etree import ElementTree

from athena.portfolio.my_portfolio_contracts import (
    ImportedHoldingRow,
    ResolvedImportedHoldingRow,
    SymbolMappingState,
)

MAX_IMPORT_BYTES = 2_000_000
MAX_IMPORT_ROWS = 2_000

_SYMBOL_ALIASES = frozenset({"symbol", "ticker", "trading symbol", "tradingsymbol"})
_QTY_ALIASES = frozenset({"qty", "quantity", "shares"})
_AVG_PRICE_ALIASES = frozenset(
    {"avg price", "average price", "avg_price", "average_price", "buy price", "avg cost"}
)


@dataclass(frozen=True, slots=True)
class ParsedHoldingRow:
    """One normalized source row, valid or invalid."""

    source_row_id: str
    source_row_number: int
    original_values: Mapping[str, str]
    raw_symbol: str
    normalized_symbol: str
    quantity: int | None
    avg_price: Decimal | None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "original_values", MappingProxyType(dict(self.original_values)))

    @property
    def is_valid(self) -> bool:
        return not self.errors and self.quantity is not None and self.avg_price is not None

    def to_imported(self) -> ImportedHoldingRow:
        if self.quantity is None or self.avg_price is None:
            raise ValueError("invalid parsed row cannot become ImportedHoldingRow")
        return ImportedHoldingRow(
            source_row_id=self.source_row_id,
            raw_symbol=self.raw_symbol,
            quantity=self.quantity,
            avg_price=self.avg_price,
            source_metadata={
                "source_row_number": self.source_row_number,
                "original_values": dict(self.original_values),
            },
        )


@dataclass(frozen=True, slots=True)
class ParsedHoldingsFile:
    """Normalized holdings file parse result."""

    filename: str
    rows: tuple[ParsedHoldingRow, ...]
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    parser_version: str = "generic-holdings-v1"

    @property
    def is_valid_file(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class SymbolResolutionCandidate:
    """One candidate canonical instrument for a source symbol."""

    instrument_id: str
    symbol: str
    exchange: str
    source: str


@dataclass(frozen=True, slots=True)
class ResolvedHoldingPreviewRow:
    """Parsed row after symbol resolution and duplicate detection."""

    parsed: ParsedHoldingRow
    mapping_state: SymbolMappingState
    resolved_instrument_id: str | None = None
    candidates: tuple[SymbolResolutionCandidate, ...] = ()
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def is_confirmable(self) -> bool:
        return (
            self.parsed.is_valid
            and self.mapping_state is SymbolMappingState.RESOLVED
            and self.resolved_instrument_id is not None
            and not self.errors
        )

    def to_resolved_imported(self) -> ResolvedImportedHoldingRow:
        return ResolvedImportedHoldingRow(
            imported=self.parsed.to_imported(),
            mapping_state=self.mapping_state,
            normalized_symbol=self.parsed.normalized_symbol,
            instrument_id=self.resolved_instrument_id,
            errors=tuple(self.parsed.errors) + self.errors,
            warnings=tuple(self.parsed.warnings) + self.warnings,
        )


@dataclass(frozen=True, slots=True)
class SymbolResolverIndex:
    """In-memory index over existing ATHENA instruments and symbol_master rows."""

    by_instrument_id: Mapping[str, tuple[SymbolResolutionCandidate, ...]]
    by_symbol: Mapping[str, tuple[SymbolResolutionCandidate, ...]]


def parse_holdings_file(filename: str, content: bytes) -> ParsedHoldingsFile:
    """Parse a generic CSV/XLSX holdings file into normalized rows."""

    if len(content) > MAX_IMPORT_BYTES:
        return ParsedHoldingsFile(filename=filename, rows=(), errors=("FILE_TOO_LARGE",))
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if suffix == "csv":
            return _parse_csv(filename, content)
        if suffix == "xlsx":
            return _parse_xlsx(filename, content)
    except UnicodeDecodeError:
        return ParsedHoldingsFile(filename=filename, rows=(), errors=("UNREADABLE_CSV",))
    except zipfile.BadZipFile:
        return ParsedHoldingsFile(filename=filename, rows=(), errors=("MALFORMED_XLSX",))
    except ElementTree.ParseError:
        return ParsedHoldingsFile(filename=filename, rows=(), errors=("MALFORMED_XLSX",))
    except csv.Error:
        return ParsedHoldingsFile(filename=filename, rows=(), errors=("UNREADABLE_CSV",))
    return ParsedHoldingsFile(filename=filename, rows=(), errors=("UNSUPPORTED_FILE_TYPE",))


def resolve_preview_rows(
    rows: Iterable[ParsedHoldingRow],
    index: SymbolResolverIndex,
) -> tuple[ResolvedHoldingPreviewRow, ...]:
    """Resolve parsed rows and mark duplicate canonical instruments as errors."""

    resolved: list[ResolvedHoldingPreviewRow] = []
    counts: dict[str, int] = {}
    for row in rows:
        preview = _resolve_one(row, index)
        resolved.append(preview)
        if preview.resolved_instrument_id is not None:
            counts[preview.resolved_instrument_id] = counts.get(preview.resolved_instrument_id, 0) + 1

    final: list[ResolvedHoldingPreviewRow] = []
    for preview in resolved:
        if (
            preview.resolved_instrument_id is not None
            and counts.get(preview.resolved_instrument_id, 0) > 1
        ):
            final.append(
                ResolvedHoldingPreviewRow(
                    parsed=preview.parsed,
                    mapping_state=preview.mapping_state,
                    resolved_instrument_id=preview.resolved_instrument_id,
                    candidates=preview.candidates,
                    errors=(*preview.errors, "DUPLICATE_CANONICAL_INSTRUMENT"),
                    warnings=preview.warnings,
                )
            )
        else:
            final.append(preview)
    return tuple(final)


def build_symbol_resolver_index(records: Iterable[object], instruments: Iterable[object]) -> SymbolResolverIndex:
    """Build a resolver index from existing symbol_master and instruments rows."""

    candidates_by_id: dict[str, SymbolResolutionCandidate] = {}
    for source, items in (("symbol_master", records), ("instruments", instruments)):
        for item in items:
            instrument_id = str(item.instrument_id)
            symbol = str(item.symbol).upper()
            exchange = str(item.exchange).upper()
            candidates_by_id.setdefault(
                instrument_id.upper(),
                SymbolResolutionCandidate(
                    instrument_id=instrument_id,
                    symbol=symbol,
                    exchange=exchange,
                    source=source,
                ),
            )

    by_instrument_id: dict[str, list[SymbolResolutionCandidate]] = {}
    by_symbol: dict[str, list[SymbolResolutionCandidate]] = {}
    for candidate in candidates_by_id.values():
        by_instrument_id.setdefault(candidate.instrument_id.upper(), []).append(candidate)
        by_symbol.setdefault(candidate.symbol.upper(), []).append(candidate)

    return SymbolResolverIndex(
        by_instrument_id=MappingProxyType({k: tuple(v) for k, v in by_instrument_id.items()}),
        by_symbol=MappingProxyType({k: tuple(v) for k, v in by_symbol.items()}),
    )


def _parse_csv(filename: str, content: bytes) -> ParsedHoldingsFile:
    if not content.strip():
        return ParsedHoldingsFile(filename=filename, rows=(), errors=("EMPTY_FILE",))
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        return ParsedHoldingsFile(filename=filename, rows=(), errors=("MISSING_HEADER_ROW",))
    return _rows_from_dicts(filename, reader.fieldnames, list(reader))


def _parse_xlsx(filename: str, content: bytes) -> ParsedHoldingsFile:
    if not content.strip():
        return ParsedHoldingsFile(filename=filename, rows=(), errors=("EMPTY_FILE",))
    with zipfile.ZipFile(BytesIO(content)) as workbook:
        shared_strings = _xlsx_shared_strings(workbook)
        sheet_names = sorted(
            name
            for name in workbook.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        if not sheet_names:
            return ParsedHoldingsFile(filename=filename, rows=(), errors=("XLSX_NO_USABLE_SHEET",))
        for sheet_name in sheet_names:
            table = _xlsx_sheet_table(workbook, sheet_name, shared_strings)
            non_empty = [[cell for cell in row] for row in table if any(cell.strip() for cell in row)]
            if not non_empty:
                continue
            header = non_empty[0]
            dict_rows = [
                {header[index]: value for index, value in enumerate(row) if index < len(header)}
                for row in non_empty[1:]
            ]
            parsed = _rows_from_dicts(filename, header, dict_rows)
            if parsed.rows or parsed.errors:
                warnings = (*parsed.warnings, f"XLSX_SHEET_USED:{sheet_name}")
                return ParsedHoldingsFile(
                    filename=filename,
                    rows=parsed.rows,
                    warnings=warnings,
                    errors=parsed.errors,
                    parser_version=parsed.parser_version,
                )
    return ParsedHoldingsFile(filename=filename, rows=(), errors=("XLSX_NO_USABLE_SHEET",))


def _rows_from_dicts(
    filename: str,
    headers: Iterable[str],
    dict_rows: list[Mapping[str, object]],
) -> ParsedHoldingsFile:
    mapping, errors = _logical_column_mapping(headers)
    if errors:
        return ParsedHoldingsFile(filename=filename, rows=(), errors=tuple(errors))
    rows: list[ParsedHoldingRow] = []
    for row_number, row in enumerate(dict_rows, start=2):
        original = {str(k): "" if v is None else str(v) for k, v in row.items()}
        if not any(value.strip() for value in original.values()):
            continue
        if len(rows) >= MAX_IMPORT_ROWS:
            return ParsedHoldingsFile(filename=filename, rows=tuple(rows), errors=("ROW_LIMIT_EXCEEDED",))
        rows.append(_normalize_row(str(row_number - 1), row_number, original, mapping))
    if not rows:
        return ParsedHoldingsFile(filename=filename, rows=(), errors=("NO_DATA_ROWS",))
    return ParsedHoldingsFile(filename=filename, rows=tuple(rows))


def _logical_column_mapping(headers: Iterable[str]) -> tuple[dict[str, str], list[str]]:
    seen: dict[str, list[str]] = {"symbol": [], "quantity": [], "avg_price": []}
    for header in headers:
        normalized = _normalize_header(header)
        if normalized in _SYMBOL_ALIASES:
            seen["symbol"].append(header)
        if normalized in _QTY_ALIASES:
            seen["quantity"].append(header)
        if normalized in _AVG_PRICE_ALIASES:
            seen["avg_price"].append(header)

    errors: list[str] = []
    mapping: dict[str, str] = {}
    for logical, matches in seen.items():
        if not matches:
            errors.append(f"MISSING_REQUIRED_COLUMN:{logical}")
        elif len(matches) > 1:
            errors.append(f"DUPLICATE_LOGICAL_COLUMN:{logical}")
        else:
            mapping[logical] = matches[0]
    return mapping, errors


def _normalize_row(
    source_row_id: str,
    source_row_number: int,
    original: Mapping[str, str],
    mapping: Mapping[str, str],
) -> ParsedHoldingRow:
    raw_symbol = original.get(mapping["symbol"], "").strip()
    normalized_symbol = _normalize_symbol(raw_symbol)
    errors: list[str] = []
    if not normalized_symbol:
        errors.append("BLANK_SYMBOL")
    quantity = _parse_quantity(original.get(mapping["quantity"], ""))
    if quantity is None:
        errors.append("INVALID_QTY")
    avg_price = _parse_decimal(original.get(mapping["avg_price"], ""))
    if avg_price is None:
        errors.append("INVALID_AVG_PRICE")
    return ParsedHoldingRow(
        source_row_id=source_row_id,
        source_row_number=source_row_number,
        original_values=original,
        raw_symbol=raw_symbol,
        normalized_symbol=normalized_symbol,
        quantity=quantity,
        avg_price=avg_price,
        errors=tuple(errors),
    )


def _resolve_one(row: ParsedHoldingRow, index: SymbolResolverIndex) -> ResolvedHoldingPreviewRow:
    if row.errors:
        return ResolvedHoldingPreviewRow(
            parsed=row,
            mapping_state=SymbolMappingState.UNRESOLVED,
            errors=row.errors,
        )
    lookup = row.normalized_symbol.upper()
    candidates = index.by_instrument_id.get(lookup, ())
    if not candidates and ":" in lookup:
        candidates = index.by_instrument_id.get(lookup.replace(" ", ""), ())
    if not candidates:
        bare = lookup.split(":", 1)[1] if ":" in lookup else lookup
        candidates = index.by_symbol.get(bare, ())
    if len(candidates) == 1:
        return ResolvedHoldingPreviewRow(
            parsed=row,
            mapping_state=SymbolMappingState.RESOLVED,
            resolved_instrument_id=candidates[0].instrument_id,
            candidates=candidates,
        )
    if len(candidates) > 1:
        return ResolvedHoldingPreviewRow(
            parsed=row,
            mapping_state=SymbolMappingState.AMBIGUOUS,
            candidates=candidates,
            errors=("AMBIGUOUS_SYMBOL",),
        )
    return ResolvedHoldingPreviewRow(
        parsed=row,
        mapping_state=SymbolMappingState.UNRESOLVED,
        errors=("UNRESOLVED_SYMBOL",),
    )


def _normalize_header(value: str) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def _normalize_symbol(value: str) -> str:
    return " ".join(str(value).strip().upper().split())


def _parse_quantity(value: object) -> int | None:
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        dec = Decimal(text)
    except InvalidOperation:
        return None
    if not dec.is_finite():
        return None
    if dec <= 0 or dec != dec.to_integral_value():
        return None
    return int(dec)


def _parse_decimal(value: object) -> Decimal | None:
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        dec = Decimal(text)
    except InvalidOperation:
        return None
    if not dec.is_finite():
        return None
    if dec <= 0:
        return None
    return dec


def _xlsx_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: list[str] = []
    for item in root.findall("x:si", ns):
        parts = [node.text or "" for node in item.findall(".//x:t", ns)]
        strings.append("".join(parts))
    return strings


def _xlsx_sheet_table(
    workbook: zipfile.ZipFile,
    sheet_name: str,
    shared_strings: list[str],
) -> list[list[str]]:
    root = ElementTree.fromstring(workbook.read(sheet_name))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: list[list[str]] = []
    for row in root.findall(".//x:sheetData/x:row", ns):
        values: list[str] = []
        for cell in row.findall("x:c", ns):
            column_index = _xlsx_column_index(cell.attrib.get("r", "A1"))
            while len(values) < column_index:
                values.append("")
            values.append(_xlsx_cell_value(cell, shared_strings, ns))
        rows.append(values)
    return rows


def _xlsx_column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return max(index - 1, 0)


def _xlsx_cell_value(
    cell: ElementTree.Element,
    shared_strings: list[str],
    ns: Mapping[str, str],
) -> str:
    value_node = cell.find("x:v", ns)
    if value_node is None or value_node.text is None:
        inline = cell.find(".//x:t", ns)
        return inline.text if inline is not None and inline.text is not None else ""
    if cell.attrib.get("t") == "s":
        index = int(value_node.text)
        return shared_strings[index] if 0 <= index < len(shared_strings) else ""
    return value_node.text
