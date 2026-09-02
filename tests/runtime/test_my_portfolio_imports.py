"""PS-P2 generic My Portfolio import parser/resolver tests."""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO

from athena.domain.market import Instrument
from athena.portfolio.imports import (
    build_symbol_resolver_index,
    parse_holdings_file,
    resolve_preview_rows,
)
from athena.portfolio.my_portfolio_contracts import SymbolMappingState

NOW = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)


def _instrument(instrument_id: str, symbol: str, exchange: str = "NSE") -> Instrument:
    return Instrument(instrument_id=instrument_id, symbol=symbol, exchange=exchange, series="EQ")


def _xlsx(rows: list[list[str]]) -> bytes:
    shared: list[str] = []
    cells: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        parts = []
        for col_index, value in enumerate(row):
            shared.append(value)
            cell_ref = f"{chr(ord('A') + col_index)}{row_index}"
            parts.append(f'<c r="{cell_ref}" t="s"><v>{len(shared) - 1}</v></c>')
        cells.append(f'<row r="{row_index}">{"".join(parts)}</row>')
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + "".join(f"<si><t>{value}</t></si>" for value in shared)
        + "</sst>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(cells)}</sheetData></worksheet>'
    )
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as workbook:
        workbook.writestr("xl/sharedStrings.xml", shared_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return out.getvalue()


def test_csv_parser_accepts_canonical_columns_and_aliases() -> None:
    parsed = parse_holdings_file(
        "holdings.csv",
        b"ticker,shares,avg cost\n infy ,10,1500.25\n\nTCS,2,3000\n",
    )

    assert parsed.errors == ()
    assert len(parsed.rows) == 2
    assert parsed.rows[0].normalized_symbol == "INFY"
    assert parsed.rows[0].quantity == 10
    assert parsed.rows[0].avg_price == Decimal("1500.25")


def test_csv_parser_reports_missing_required_columns_and_unsupported_file() -> None:
    missing = parse_holdings_file("holdings.csv", b"Symbol,Qty\nINFY,10\n")
    unsupported = parse_holdings_file("holdings.txt", b"Symbol,Qty,Avg Price\nINFY,10,100\n")

    assert "MISSING_REQUIRED_COLUMN:avg_price" in missing.errors
    assert unsupported.errors == ("UNSUPPORTED_FILE_TYPE",)


def test_row_numeric_validation_rejects_invalid_values() -> None:
    parsed = parse_holdings_file(
        "holdings.csv",
        b"Symbol,Qty,Avg Price\nA,0,10\nB,-1,10\nC,x,10\nD,1,0\nE,1,-1\nF,1,NaN\n",
    )

    errors = [row.errors for row in parsed.rows]

    assert ("INVALID_QTY",) in errors
    assert ("INVALID_AVG_PRICE",) in errors


def test_xlsx_parser_uses_first_non_empty_sheet() -> None:
    parsed = parse_holdings_file(
        "holdings.xlsx",
        _xlsx([["Symbol", "Qty", "Avg Price"], ["INFY", "10", "1500"]]),
    )

    assert parsed.errors == ()
    assert parsed.rows[0].normalized_symbol == "INFY"
    assert any(item.startswith("XLSX_SHEET_USED:") for item in parsed.warnings)


def test_xlsx_parser_reports_malformed_and_empty_workbook() -> None:
    malformed = parse_holdings_file("holdings.xlsx", b"not-a-zip")
    empty = parse_holdings_file("holdings.xlsx", b"")

    assert malformed.errors == ("MALFORMED_XLSX",)
    assert empty.errors == ("EMPTY_FILE",)


def test_symbol_resolution_reports_resolved_unresolved_ambiguous_and_duplicate() -> None:
    parsed = parse_holdings_file(
        "holdings.csv",
        b"Symbol,Qty,Avg Price\nINFY,10,1500\nMISSING,1,1\nABC,1,1\nINFY,2,1600\n",
    )
    index = build_symbol_resolver_index(
        (),
        (
            _instrument("NSE:INFY", "INFY"),
            _instrument("NSE:ABC", "ABC", exchange="NSE"),
            _instrument("BSE:ABC", "ABC", exchange="BSE"),
        ),
    )

    rows = resolve_preview_rows(parsed.rows, index)

    assert rows[0].mapping_state is SymbolMappingState.RESOLVED
    assert rows[1].mapping_state is SymbolMappingState.UNRESOLVED
    assert rows[2].mapping_state is SymbolMappingState.AMBIGUOUS
    assert "DUPLICATE_CANONICAL_INSTRUMENT" in rows[0].errors
    assert "DUPLICATE_CANONICAL_INSTRUMENT" in rows[3].errors
