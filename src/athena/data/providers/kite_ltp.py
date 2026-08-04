"""Lightweight single-instrument LTP fetch via Kite /quote (no catalog load).

Used by the Decisions & Trace header price poll. Deliberately bypasses
``KiteProvider.quotes()`` which requires the full instruments CSV — loading that
on every 10s refresh would be heavy. The quote endpoint accepts
``exchange:tradingsymbol`` ids directly.
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.config.loader import load_kite_provider_config
from athena.data.providers.kite_transport import UrllibKiteTransport
from athena.domain.market import Quote
from athena.errors import ProviderError

IST = ZoneInfo("Asia/Kolkata")


def _parse_kite_ts(raw: str) -> datetime:
    s = raw.strip().replace(" ", "T")
    if len(s) >= 5 and s[-5] in "+-" and ":" not in s[-5:]:
        s = f"{s[:-2]}:{s[-2:]}"
    try:
        ts = datetime.fromisoformat(s)
    except ValueError as exc:
        raise ProviderError(f"kite timestamp unparseable: '{raw}'") from exc
    if ts.tzinfo is None:
        return ts.replace(tzinfo=IST)
    return ts


def _decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ProviderError(f"kite returned invalid {field}: {value!r}") from exc


def _build_transport(config_dir: Path) -> UrllibKiteTransport:
    api_key = (os.environ.get("KITE_API_KEY") or "").strip()
    access_token = (os.environ.get("KITE_ACCESS_TOKEN") or "").strip()
    if not api_key or not access_token:
        raise ProviderError("Kite credentials missing; cannot fetch live quote")
    kite_cfg = load_kite_provider_config(config_dir)
    return UrllibKiteTransport(
        base_url=kite_cfg.base_url,
        api_key=api_key,
        access_token=access_token,
        rate_limit=kite_cfg.rate_limit,
    )


def _parse_quote_row(iid: str, row: object) -> tuple[Quote, Decimal | None]:
    if not isinstance(row, dict):
        raise ProviderError(f"kite /quote returned no data for {iid}")

    ts_raw = row.get("timestamp") or row.get("last_trade_time")
    if not ts_raw:
        raise ProviderError(f"kite quote for {iid} missing timestamp")
    ts = _parse_kite_ts(str(ts_raw))
    last_price = _decimal(row.get("last_price"), "last_price")
    if last_price <= 0:
        raise ProviderError(f"kite quote for {iid} has non-positive last_price")

    change_pct: Decimal | None = None
    ohlc = row.get("ohlc")
    if isinstance(ohlc, dict) and ohlc.get("close") is not None:
        try:
            prior = _decimal(ohlc.get("close"), "ohlc.close")
        except ProviderError:
            prior = Decimal(0)
        if prior > 0:
            change_pct = (last_price - prior) / prior * Decimal(100)

    quote = Quote(
        instrument_id=iid,
        ts=ts,
        last_price=last_price,
        volume=int(row.get("volume") or 0),
        source="kite",
    )
    return quote, change_pct


def fetch_live_quote(
    instrument_id: str,
    *,
    config_dir: Path,
) -> tuple[Quote, Decimal | None]:
    """Return ``(quote, change_pct)`` for one instrument from Kite /quote.

    ``change_pct`` is derived from Kite's previous-close OHLC when present;
    otherwise ``None`` (never fabricated). Raises ``ProviderError`` /
    ``ConfigError`` when credentials or the response are unusable.
    """
    iid = instrument_id.strip().upper()
    if not iid:
        raise ProviderError("instrument_id must be non-empty")
    if ":" not in iid:
        iid = f"NSE:{iid}"

    transport = _build_transport(config_dir)
    payload = transport.get_json("/quote", [("i", iid)])
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise ProviderError("kite /quote returned malformed data")
    row = data.get(iid)
    if row is None:
        row = next((v for k, v in data.items() if str(k).upper() == iid), None)
    return _parse_quote_row(iid, row)


def fetch_live_quotes(
    instrument_ids: list[str],
    *,
    config_dir: Path,
) -> dict[str, tuple[Quote, Decimal | None]]:
    """Batched sibling of ``fetch_live_quote`` — ONE Kite ``/quote`` request
    for every id instead of one request per id.

    Perf fix (owner-reported, 2026-08-04): Top Opportunities Today calls this
    once per qualifying symbol (up to ~10-20 per request); each call used to
    open its own connection and make its own live round trip, measured at
    7-13s end to end in production. Kite's ``/quote`` endpoint already
    accepts multiple ``i=`` params in one call (same pattern
    ``KiteProvider.quotes()`` already uses for its own batching) — this cuts
    N sequential network round trips down to 1. A symbol Kite doesn't return
    data for is simply absent from the result dict, never fabricated.
    """
    bare_ids = [instrument_id.strip().upper() for instrument_id in instrument_ids]
    bare_ids = [iid if ":" in iid else f"NSE:{iid}" for iid in bare_ids if iid]
    unique_ids = list(dict.fromkeys(bare_ids))
    if not unique_ids:
        return {}

    transport = _build_transport(config_dir)
    payload = transport.get_json("/quote", [("i", iid) for iid in unique_ids])
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise ProviderError("kite /quote returned malformed data")

    by_upper_key = {str(k).upper(): v for k, v in data.items()}
    results: dict[str, tuple[Quote, Decimal | None]] = {}
    for iid in unique_ids:
        row = data.get(iid, by_upper_key.get(iid))
        if row is None:
            continue
        try:
            results[iid] = _parse_quote_row(iid, row)
        except ProviderError:
            continue
    return results
