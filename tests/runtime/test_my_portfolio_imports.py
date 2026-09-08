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


def test_csv_parser_accepts_broker_export_headers_with_periods_and_extra_columns() -> None:
    # Owner-reported: a real Zerodha/Kite holdings export ("Instrument,Qty.,
    # Avg. cost,LTP,Invested,Cur. val,P&L,Net chg.,Day chg.") previously
    # failed with MISSING_REQUIRED_COLUMN for all three required fields —
    # "Instrument" wasn't a recognized symbol alias, and the trailing/
    # embedded periods in "Qty."/"Avg. cost" broke the exact-match against
    # the already-existing period-free "qty"/"avg cost" aliases. The extra
    # broker-computed columns (LTP, Invested, P&L, ...) are ATHENA's own
    # server-owned math and must stay ignored, never required or parsed.
    parsed = parse_holdings_file(
        "holdings.csv",
        b"Instrument,Qty.,Avg. cost,LTP,Invested,Cur. val,P&L,Net chg.,Day chg.\n"
        b"ACMESOLAR,418,408.35,418.00,170690.30,174724.00,4033.70,2.36,4.01\n"
        b"BALKRISIND,46,2153.57,2284.60,99064.00,105091.60,6027.60,6.08,-1.83\n",
    )

    assert parsed.errors == ()
    assert len(parsed.rows) == 2
    assert parsed.rows[0].normalized_symbol == "ACMESOLAR"
    assert parsed.rows[0].quantity == 418
    assert parsed.rows[0].avg_price == Decimal("408.35")
    assert parsed.rows[0].is_valid
    assert parsed.rows[1].normalized_symbol == "BALKRISIND"
    assert parsed.rows[1].quantity == 46
    assert parsed.rows[1].avg_price == Decimal("2153.57")


def test_csv_parser_rejects_zero_avg_price_row_without_failing_whole_import() -> None:
    # A real broker export can carry a genuine ₹0.00 avg cost (e.g. a bonus/
    # demerger share with no cost basis) — ATHENA's own domain invariant
    # requires avg_price > 0, so that one row is rejected on its own; it
    # must never abort parsing the rest of a otherwise-valid file.
    parsed = parse_holdings_file(
        "holdings.csv",
        b"Instrument,Qty.,Avg. cost\nRATNA-RE,74,0.00\nINFY,10,1500\n",
    )

    assert parsed.errors == ()
    assert len(parsed.rows) == 2
    assert parsed.rows[0].normalized_symbol == "RATNA-RE"
    assert not parsed.rows[0].is_valid
    assert "INVALID_AVG_PRICE" in parsed.rows[0].errors
    assert parsed.rows[1].is_valid


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
        b"Symbol,Qty,Avg Price\nINFY,10,1500\nMISSING,1,1\nTRIPLE,1,1\nINFY,2,1600\n",
    )
    index = build_symbol_resolver_index(
        (),
        (
            _instrument("NSE:INFY", "INFY"),
            _instrument("NSE:TRIPLE", "TRIPLE", exchange="NSE"),
            _instrument("BSE:TRIPLE", "TRIPLE", exchange="BSE"),
            _instrument("MSE:TRIPLE", "TRIPLE", exchange="MSE"),
        ),
    )

    rows = resolve_preview_rows(parsed.rows, index)

    assert rows[0].mapping_state is SymbolMappingState.RESOLVED
    assert rows[1].mapping_state is SymbolMappingState.UNRESOLVED
    assert rows[2].mapping_state is SymbolMappingState.AMBIGUOUS
    assert "DUPLICATE_CANONICAL_INSTRUMENT" in rows[0].errors
    assert "DUPLICATE_CANONICAL_INSTRUMENT" in rows[3].errors


def test_symbol_resolution_matches_equity_series_suffix() -> None:
    parsed = parse_holdings_file(
        "holdings.csv",
        b"Symbol,Qty,Avg Price\nRAJESHEXPO,10,200\n",
    )
    master = _instrument("NSE:RAJESHEXPO-BZ", "RAJESHEXPO-BZ", exchange="NSE")
    index = build_symbol_resolver_index((master,), ())

    rows = resolve_preview_rows(parsed.rows, index)

    assert rows[0].mapping_state is SymbolMappingState.RESOLVED
    assert rows[0].resolved_instrument_id == "NSE:RAJESHEXPO-BZ"
    assert "SERIES_SUFFIX_FALLBACK" in rows[0].warnings


def test_symbol_resolution_prefers_bse_when_nse_and_bse_both_match() -> None:
    parsed = parse_holdings_file(
        "holdings.csv",
        b"Symbol,Qty,Avg Price\nHFCL,10,226\nABC,1,1\n",
    )
    index = build_symbol_resolver_index(
        (),
        (
            _instrument("NSE:HFCL", "HFCL", exchange="NSE"),
            _instrument("BSE:HFCL", "HFCL", exchange="BSE"),
            _instrument("NSE:ABC", "ABC", exchange="NSE"),
            _instrument("BSE:ABC", "ABC", exchange="BSE"),
        ),
    )

    rows = resolve_preview_rows(parsed.rows, index)

    assert rows[0].mapping_state is SymbolMappingState.RESOLVED
    assert rows[0].resolved_instrument_id == "BSE:HFCL"
    assert rows[0].warnings == ("BSE_EXCHANGE_FALLBACK",)
    assert rows[1].resolved_instrument_id == "BSE:ABC"
