# ATHENA — Kite Connect live market data (R4)

**Audience:** Owner running ingest/cycles against Zerodha Kite after DD-1 acceptance.

**Non-goals:** Order placement, websockets (DD-2), multi-year 5m backfill (DD-10).

---

## Prerequisites

1. Zerodha account + **Kite Connect** app (paid Connect plan required for historical + quotes used here).
2. Copy `.env.example` → `.env` and set:
   - `KITE_API_KEY`
   - `KITE_ACCESS_TOKEN` (daily; typically expires around 06:00 IST)
3. Keep `config/ingestion.json` → `"provider": "file"` until you intentionally flip to `"kite"`.
4. Optionally set `config/providers/kite.json` → `symbols` to a watchlist (empty = all NSE EQ in the dump — heavy). Prefer also setting `ingestion.instrument_ids` to the same `NSE:SYMBOL` ids.

Instrument ids are **`NSE:SYMBOL`** (e.g. `NSE:INFY`).

---

## Daily access-token refresh

Kite login is out-of-band. Typical flow:

1. Open: `https://kite.zerodha.com/connect/login?v=3&api_key=YOUR_API_KEY`
2. After login, redirect URL contains `request_token=…`
3. Exchange for `access_token` (checksum = SHA256(`api_key` + `request_token` + `api_secret`)) via Kite session API — store only `KITE_ACCESS_TOKEN` in `.env`.
4. Never commit `.env`. Never put tokens in JSON config.

ATHENA does **not** call order/session-management placement endpoints; the HTTP client allowlists `/instruments*` and `/quote*` GETs only.

---

## Enable live ingest

1. Set secrets in `.env`.
2. Edit `config/providers/kite.json` — set `symbols` (recommended) and confirm index keys.
3. Edit `config/ingestion.json`:
   - `"provider": "kite"`
   - optionally `"instrument_ids": ["NSE:INFY", …]`
4. Smoke: `athena health` then `athena ingest --as-of …`
5. To go offline / CI: set `"provider": "file"` again (FileProvider remains default/fallback).

---

## Limits & honesty

| Topic | Behaviour |
|---|---|
| History depth | Declared `max_history_days` in kite.json; deep multi-year 5m is DD-10 / live accumulation |
| Rate limits | Batch quotes (≤500); chunk historical windows; ~15 min / ~100 symbols is in scope |
| Market snapshot | Index LTPs + India VIX from `/quote`; breadth fields stay `0` (not provided by this path) |
| Auth failure | `ProviderError` / health `BLOCKED` — fails loudly |

---

## Related

- DD-1: `docs/decisions/DD-1-broker-live-data-vendor.md`
- ADR-002: `docs/adr/ADR-002-broker-abstraction.md`
- File-backed interim: `docs/ops/FILE_BACKED_DAILY_OPS.md`
