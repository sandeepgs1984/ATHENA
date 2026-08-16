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

Two corrections found when the master was first materialised against production
(2026-08-16), both of which put non-equities into equity universes or kept real
equities out of them:

1. **Not every hyphen introduces a series.** ``BAJAJ-AUTO`` — a NIFTY 50
   constituent — was read as series ``AUTO``, and six other real equities
   likewise. Real NSE series codes are two characters, so a longer or shorter
   suffix is part of the company's name.
2. **Symbol shape alone cannot identify an index.** ``NIFTY 50`` has no suffix
   and so took the plain-``EQ`` default, which put it and 131 other index rows
   inside ``darvax_discovery``. Indices are distinguished by having **no tick
   size** — see ``tradable`` below.

On the tick size specifically: the NSE dump reports both ``lot_size`` and
``tick_size`` as ``0`` for all 136 index rows and for none of the 10,061 others,
so either would separate them. Only the tick size survives to this module.
``Instrument`` requires ``lot_size >= 1``, so ``KiteProvider`` clamps it with
``max(lot, 1)`` — meaning the lot-size signal is destroyed at the provider
boundary and a rule built on it would silently never fire.

Rule 1 alone would have been wrong: it would have promoted
``BHARATBOND-APR30`` and ``HANGSENG BEES-NAV`` into the equity universe. The two
rules are only correct together.
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

#: Every real NSE series code is two characters (``EQ``, ``BE``, ``SG``, ``N1``
#: …) — 10,185 of the 10,197 rows on the 2026-08-16 dump. A hyphen followed by
#: anything else is therefore part of the *company name*, not a series: the
#: twelve exceptions are names like ``BAJAJ-AUTO`` and ``NAM-INDIA``.
SERIES_CODE_LENGTH = 2


def classify_symbol(
    trading_symbol: str,
    *,
    tradable: bool | None = None,
) -> tuple[str, SeriesSource, Board, str]:
    """Infer ``(series, source, board, reason)`` from a trading symbol.

    A symbol with no recognised suffix is treated as plain ``EQ`` on the main
    board. That default is stated rather than silent: it is the assumption most
    likely to be wrong for an exotic listing, and the returned reason says so.

    Args:
        tradable: whether the instrument can actually be traded — in practice
            ``tick_size > 0``, since an instrument with no price increment is
            not quoted as a listing. **Tradability is a precondition for being
            on a board at all**, so a row known to be untradable is reported
            ``UNKNOWN`` whatever its symbol looks like. ``None`` means nobody
            established it, and classification falls back to symbol shape alone.

    Passing ``tradable`` is what keeps index rows out of the equity universe.
    ``NIFTY 50`` carries no suffix and would otherwise take the plain-``EQ``
    default; it reached ``darvax_discovery`` that way, alongside 131 other index
    rows, until this parameter existed.
    """
    symbol = trading_symbol.strip().upper()
    if not symbol:
        raise ValueError("trading symbol must not be empty")

    series, source, board, reason = _classify_by_suffix(symbol)

    if tradable is False and board is not Board.UNKNOWN:
        return (
            series,
            source,
            Board.UNKNOWN,
            f"{reason} — but the instrument has no tick size, so it is not a "
            f"tradable listing and no board is established",
        )
    return (series, source, board, reason)


def _classify_by_suffix(symbol: str) -> tuple[str, SeriesSource, Board, str]:
    """Classification from the trading symbol alone."""
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
        if len(suffix) == SERIES_CODE_LENGTH:
            # The right shape for a series code, but one this module does not
            # know. Reported as unknown rather than forced into EQ: quietly
            # promoting an unclassifiable instrument into the equity universe is
            # exactly the accident ADR-011 exists to prevent.
            return (
                suffix,
                SeriesSource.INFERRED_SUFFIX,
                Board.UNKNOWN,
                f"unrecognised suffix '-{suffix}'; series not established",
            )
        # Not the shape of a series code at all, so the hyphen belongs to the
        # company's name. Treating it as a series is what hid BAJAJ-AUTO — a
        # NIFTY 50 constituent — from every board-derived universe.
        return (
            DEFAULT_EQUITY_SERIES,
            SeriesSource.INFERRED_SUFFIX,
            Board.MAINBOARD,
            f"'-{suffix}' is not a series code (NSE codes are "
            f"{SERIES_CODE_LENGTH} characters), so it is read as part of the "
            f"company name; assumed plain EQ on the main board",
        )

    return (
        DEFAULT_EQUITY_SERIES,
        SeriesSource.INFERRED_SUFFIX,
        Board.MAINBOARD,
        "no series suffix; assumed plain EQ on the main board",
    )
