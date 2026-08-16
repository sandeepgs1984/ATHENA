"""Series and board classification (SU-1, ADR-011).

Pure functions over a trading symbol. No IO, no clock, no config — the same
symbol always classifies the same way, so a catalogue rebuild is reproducible.

**This is inference, not authority.** NSE encodes the series in the trading
symbol's suffix (``NAME-SG`` for a state government loan, ``NAME-SM`` for an SME
scrip), and that convention is reliable enough to separate ~7,000 non-equity
rows from ~3,000 equity ones. It is still a convention rather than a published
contract, which is why every result carries a :class:`SeriesSource` and a reason
in words, and why ADR-011 §2.3 forbids treating the resulting count as the
definition of anything.

Observed on the NSE dump (2026-08-15, 10,061 NSE-segment rows):

===========  =====  ==========================================
Suffix       Count  Almost certainly
===========  =====  ==========================================
``-SG``      4,298  State government loans (debt)
``-SM``        439  SME board
``-BE``        230  Trade-for-trade equity
``-GS``        130  Government securities
``-ST``        120  State development loans
``-TB``         84  Treasury bills
``-SF``         50  Other government paper
``-GB``         45  Government bonds
(none)      ~3,000  Plain ``EQ`` equity
===========  =====  ==========================================
"""

from __future__ import annotations

from athena.symbols.models import Board, SeriesSource

#: Suffixes that denote a genuinely different series from plain equity. Values
#: are ``(series, board, human explanation)``. Kept as data rather than a chain
#: of conditionals so the whole convention is reviewable in one place.
_SUFFIX_SERIES: dict[str, tuple[str, Board, str]] = {
    "SM": ("SM", Board.SME, "SME board scrip"),
    "ST": ("ST", Board.UNKNOWN, "state development loan (debt)"),
    "SG": ("SG", Board.UNKNOWN, "state government loan (debt)"),
    "GS": ("GS", Board.UNKNOWN, "government security (debt)"),
    "TB": ("TB", Board.UNKNOWN, "treasury bill (debt)"),
    "GB": ("GB", Board.UNKNOWN, "government bond (debt)"),
    "SF": ("SF", Board.UNKNOWN, "government paper (debt)"),
    "BE": ("BE", Board.MAINBOARD, "trade-for-trade equity"),
    "BZ": ("BZ", Board.MAINBOARD, "trade-for-trade surveillance equity"),
    "IV": ("IV", Board.MAINBOARD, "equity with an unpaid-call variant"),
}

#: Series that are equity on the main board when no suffix is present.
DEFAULT_EQUITY_SERIES = "EQ"


def classify_symbol(
    trading_symbol: str,
) -> tuple[str, SeriesSource, Board, str]:
    """Infer ``(series, source, board, reason)`` from a trading symbol.

    A symbol with no recognised suffix is treated as plain ``EQ`` on the main
    board. That default is stated rather than silent: it is the assumption most
    likely to be wrong for an exotic listing, and the returned reason says so.
    """
    symbol = trading_symbol.strip().upper()
    if not symbol:
        raise ValueError("trading symbol must not be empty")

    if "-" in symbol:
        _base, _, suffix = symbol.rpartition("-")
        known = _SUFFIX_SERIES.get(suffix)
        if known is not None:
            series, board, description = known
            return (
                series,
                SeriesSource.INFERRED_SUFFIX,
                board,
                f"suffix '-{suffix}' indicates {description}",
            )
        # An unrecognised suffix is reported as unknown rather than forced into
        # EQ: quietly promoting an unclassifiable instrument into the equity
        # universe is exactly the accident ADR-011 exists to prevent.
        return (
            suffix,
            SeriesSource.INFERRED_SUFFIX,
            Board.UNKNOWN,
            f"unrecognised suffix '-{suffix}'; series not established",
        )

    return (
        DEFAULT_EQUITY_SERIES,
        SeriesSource.INFERRED_SUFFIX,
        Board.MAINBOARD,
        "no series suffix; assumed plain EQ on the main board",
    )
