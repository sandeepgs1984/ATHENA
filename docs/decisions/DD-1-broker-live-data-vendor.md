# DD-1 — Broker / Live Market Data Vendor (R3 Decision Record)

| | |
|---|---|
| Status | **ACCEPTED** — Owner approved 2026-07-23 |
| Date | 2026-07-23 |
| Deferred decision | ATHENA-002 §15 **DD-1** |
| ADR context | [ADR-002](../adr/ADR-002-broker-abstraction.md) — adapters behind `MarketDataProvider`; no order methods |
| Code impact | **None in R3.** Adapter implementation is **R4** only — still unauthorized until owner gates R4 |
| Owner note | Existing Zerodha Kite account; Groww retained for manual execution only (ATHENA never places orders) |

---

## 1. Decision question

Which **live market-data vendor** should ATHENA bind as the first non-FileProvider `MarketDataProvider` for NSE cash equities (quotes + daily/intraday candles), selected by config, secrets in `.env` only?

ATHENA remains advisory-only: the Protocol and adapters **must not** place orders (constitution + ADR-002).

---

## 2. Decision criteria (ATHENA-002 §15, verbatim gist)

| # | Criterion | Bar |
|---|---|---|
| C1 | Contract | Passes `tests/contract/provider_contract.py` unchanged |
| C2 | History depth | Intraday history depth ≥ **2 years at 5m** (ideal); gaps documented if partial |
| C3 | Rate limits | Quote polling viable at **~15 min cadence for ~100 symbols** |
| C4 | Cost | Acceptable for single-user workstation (prefer known, bounded fees) |
| C5 | Auth ergonomics | Daily re-auth / token burden manageable for one operator |
| C6 | API stability | Mature public docs + track record |

Additional ATHENA constraints (not in §15 table but binding):

- Read-only market data path (no execute APIs in adapter)
- Secrets only in `.env`
- Config selects provider (`ingestion.provider` / providers config) — FileProvider remains fallback
- Localhost / single-machine posture unchanged (DD-8)

---

## 3. Candidates evaluated

Scores: **Pass / Partial / Fail / Unknown** against each criterion. “Partial” means usable for live poll with documented gap (usually deep history → DD-10).

### A. Zerodha Kite Connect (recommended)

| Criterion | Assessment |
|---|---|
| C1 Contract | **Pass** — can implement Protocol: instruments, daily/intraday candles, quotes, capabilities/health |
| C2 History ≥2y@5m | **Partial** — live + limited historical windows; multi-year 5m often needs paid historical / accumulation (DD-10). Does **not** block live daily ops |
| C3 Rate limits | **Pass** — 15-min refresh for ~100 symbols is well within typical retail quote/candle quotas when batched |
| C4 Cost | **Pass** — Connect API access tied to Zerodha account; predictable for single user |
| C5 Auth | **Partial** — daily login/token refresh is the main ops burden; document in R4/R5 SOP |
| C6 Stability | **Pass** — longest-lived retail NSE API surface; widespread docs/community |

**Fit:** Strong default for Indian NSE cash advisory workstation. Matches ADR-002’s original “e.g. Zerodha” example without baking Kite into business logic.

### B. Upstox API

| Criterion | Assessment |
|---|---|
| C1 | **Pass** (feasible) |
| C2 | **Partial** (similar history limits) |
| C3 | **Pass** for 15-min / ~100 symbols (verify current quotas in R4) |
| C4 | **Pass** |
| C5 | **Partial** (OAuth/token cadence) |
| C6 | **Pass** (mature v2) |

**Fit:** Viable alternate. Prefer if owner already banks with Upstox and wants one login surface.

### C. Angel One SmartAPI

| Criterion | Assessment |
|---|---|
| C1 | **Pass** (feasible) |
| C2 | **Partial / Unknown** — confirm historical depth in R4 spike |
| C3 | **Pass** with careful batching |
| C4 | **Pass** |
| C5 | **Partial** |
| C6 | **Pass** |

**Fit:** Viable alternate; same architecture as A/B.

### D. Pure data vendors (e.g. TrueData, Global Datafeeds) — no brokerage

| Criterion | Assessment |
|---|---|
| C1 | **Pass** if REST/poll available |
| C2 | **Pass / Partial** — often stronger on history (aligns DD-10) |
| C3 | **Pass** (product-dependent) |
| C4 | **Partial** — usually subscription cost |
| C5 | **Pass** (API keys, less daily login theatre) |
| C6 | **Partial** — vendor-specific |

**Fit:** Attractive if deep history is more important than broker-portal convenience. Can be a **second** provider later without changing domain logic.

### E. Stay FileProvider-only (reject live bind)

| Criterion | Assessment |
|---|---|
| — | Defers live readiness; R1/R2 already support disciplined file ops |

**Fit:** Not a DD-1 resolution — leaves production roadmap Track B open.

---

## 4. Recommendation (for owner acceptance)

**Select: Zerodha Kite Connect** as the **first** live `MarketDataProvider` target for **R4**.

### Acceptance notes

1. **Scope of R4:** Read-only adapter — `instruments`, `daily_candles`, `intraday_candles`, `quotes`, `capabilities`, `health`. **No** order/trade/GTT methods in the adapter or Protocol.
2. **History gap (C2):** Treat multi-year 5m history as **DD-10 / live accumulation**, not a R4 blocker. R4 must fail loudly when requested history exceeds vendor capability.
3. **Auth (C5):** R4 + ops SOP must document daily token refresh; secrets (`KITE_API_KEY`, `KITE_ACCESS_TOKEN`, etc.) in `.env` only.
4. **Config:** `ingestion.provider` (or equivalent) selects `kite` vs `file`; default remains `file` until owner flips config.
5. **Fallback:** FileProvider stays supported forever for CI, replay, and offline days.
6. **Revisit:** If rate limits, auth burden, or cost prove unacceptable within 30 trading days of R4 use, owner may reopen DD-1 and switch to Upstox/Angel/data vendor without domain changes (new adapter only).

### Explicit non-choices in this record

- Not selecting Upstox/Angel as primary (remain documented alternates)
- Not binding a paid pure-data vendor yet (revisit with DD-10)
- Not authorizing streaming websockets (DD-2)
- Not authorizing any order placement path

---

## 5. Owner sign-off

| Field | Value |
|---|---|
| Chosen vendor | **Zerodha Kite Connect** |
| Owner | sandeep |
| Accepted | **2026-07-23** (`approve R3`) — existing Kite account; Groww for manual execution only |
| Next | **`authorize R4`** to implement read-only Kite `MarketDataProvider` (FileProvider remains default/fallback) |

**R4 remains unauthorized** until R3 is approved with a chosen vendor.

---

## 6. Traceability

| Doc | Link |
|---|---|
| Blueprint deferred decisions | ATHENA-002 §15 DD-1 |
| Broker abstraction | ADR-002 |
| Production track | `docs/PRODUCTION_READINESS_ROADMAP.md` R3→R4 |
| Contract suite | `tests/contract/provider_contract.py` |
| Current ingest lock | `config/ingestion.json` → `provider: "file"` |
