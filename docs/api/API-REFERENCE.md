# ATHENA Platform API — Reference

**81 operations across 17 resource groups**, generated from the live OpenAPI schema served by the running platform (`GET /api/openapi.json`) — so this document, `openapi.yaml`, and `postman_collection.json` in this same directory are guaranteed to match every registered route, with nothing missed.

- **`openapi.yaml`** — the full OpenAPI 3.1 spec. Import into Swagger UI, Redoc, Insomnia, or any OpenAPI-aware tool.
- **`postman_collection.json`** — a ready-to-import Postman v2.1 collection, organized into the same 17 folders as this document, with a synthesized example request body for every endpoint that takes one.
- **This file** — the human-readable walkthrough: auth flow, envelope/error conventions, and every endpoint grouped by resource with the detail worth reading rather than just re-stating the schema.

> ATHENA is a **single-user, advisory-only** platform. This API never places or executes a trade — the only write paths that exist are the owner's own record-keeping (journal responses, manually-logged fills) and configuration/operational actions (candidates, saved symbols, backups). See [`docs/ATHENA-WORKFLOW-METHODOLOGY.md`](../ATHENA-WORKFLOW-METHODOLOGY.md) for what the data returned by these endpoints actually *means*.

---

## Base URL

```
http://127.0.0.1:8000
```

ATHENA is bound to `localhost` only, by design (ADR-004) — it is never deployed to a remote host. All `/api/v1/*` paths below are relative to this base URL; a handful of platform-level endpoints (`/health`, `/api/info`, `/api/version`, etc.) live outside the `/api/v1` prefix — see [Platform Health & Discovery](#platform-health--discovery) below.

---

## Authentication

Two schemes are registered (`components.securitySchemes` in `openapi.yaml`):

| Scheme | Type | Used for |
|---|---|---|
| `HTTPBearer` | `Authorization: Bearer <token>` | every authenticated request (the normal path) |
| `APIKeyHeader` | `X-API-Key: <key>` | an alternative header-based credential, where configured |

### The unlock flow

```
1. POST /api/v1/auth/login   { "username": "owner", "password": "..." }
   → 200 { data: { access_token, refresh_token, token_type: "bearer", expires_in_seconds } }

2. Every subsequent request:
   Authorization: Bearer <access_token>

3. When the access token expires:
   POST /api/v1/auth/refresh   (send the refresh_token)
   → a new access_token + refresh_token pair (rotated, not reused)

4. POST /api/v1/auth/logout    → revokes the current session
```

`GET /api/v1/auth/status` and `GET /api/v1/auth/me` are the two read-only checks: `status` is **public** (no token needed — it's how the dashboard's unlock screen knows whether auth is even required) and reports the current mode; `me` requires a valid Bearer token and returns the authenticated principal.

**Endpoints that require no authentication at all**, verified against the actual route definitions: `POST /api/v1/auth/login`, `GET /api/v1/auth/status`, `GET /health`, `GET /health/live`, `GET /health/ready`, and the Platform Discovery group (`/api/info`, `/api/meta`, `/api/version`, `/api/capabilities`, `/api/features`). Every other endpoint requires a Bearer token; the Postman collection's collection-level auth is set to Bearer with `{{access_token}}`, and each no-auth endpoint above is individually marked `noauth` so importing the collection "just works" once you run the login request and paste the returned token into the `access_token` collection variable.

---

## Response envelope

Every successful collection/detail response shares one shape:

```json
{
  "status": "success",
  "data": { /* or [...] for a list endpoint */ },
  "meta": {
    "request_id": "80041c2f-...",
    "api_version": "v1",
    "as_of": "2026-08-04T10:15:00+05:30"
  },
  "pagination": {
    "total": 142, "page": 1, "page_size": 20, "total_pages": 8,
    "has_next": true, "has_previous": false,
    "next_cursor": null, "previous_cursor": null
  }
}
```

`pagination` is present only on list endpoints; `meta.request_id` and the `X-Request-ID`/`X-Correlation-ID` response headers are the two identifiers to quote back if you need to trace a specific call.

### Errors — RFC 7807 Problem Details

Every error response, including validation failures and 404s, follows the same shape (not a bespoke ATHENA format):

```json
{
  "type": "https://athena.internal/errors/http-404",
  "title": "Not Found",
  "status": 404,
  "detail": "Not Found",
  "instance": "/api/v1/decisions/dec-does-not-exist",
  "request_id": "80041c2f-7d96-4e72-90e9-fe42018ba38c",
  "correlation_id": "80041c2f-7d96-4e72-90e9-fe42018ba38c",
  "timestamp": "2026-08-07T06:45:33.938670+00:00"
}
```

A `422` validation failure carries the same envelope but with `detail` as an array of `{loc, msg, type}` objects (FastAPI/Pydantic's native validation-error shape — see `HTTPValidationError`/`ValidationError` in `openapi.yaml`'s schema components).

### Pagination parameters (every list endpoint)

`page` (default 1), `page_size` (default 20, max 100), plus endpoint-specific filters and `sort_by`/`sort_dir` (`asc`/`desc`) where sorting makes sense. `next_cursor`/`previous_cursor` are reserved fields for a future cursor-based mode — every collection endpoint today uses page/page_size.

---

## Resource groups

### Auth
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/login` | Unlock with owner credentials — issues the token pair |
| POST | `/api/v1/auth/refresh` | Rotate refresh token, issue a new access token |
| POST | `/api/v1/auth/logout` | Revoke the current session |
| GET | `/api/v1/auth/me` | Current authenticated principal |
| GET | `/api/v1/auth/status` | Public — is auth required, what mode (no token needed) |

### Decisions — the core decision-intelligence surface
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/decisions` | List decisions — filter by `instrument_id`, `decision_type`, `direction`, `from_date`/`to_date`, free-text `q`; sort by any field |
| GET | `/api/v1/decisions/{decision_id}` | Full decision detail: metadata, analysis (score/confidence/risk references), trade plan, gate results |
| GET | `/api/v1/decisions/{decision_id}/trace` | The execution trace DAG — one stage per contributing pipeline engine |
| GET | `/api/v1/decisions/{decision_id}/depth` | Persisted analytical depth (component-level breakdowns) |
| GET | `/api/v1/decisions/{decision_id}/context` | Session/calendar state, regime/market-health snapshot, curated links, at the time of the decision |
| GET | `/api/v1/decisions/{decision_id}/analogs` | Historical decisions with a similar score/confidence/risk fingerprint |
| GET | `/api/v1/decisions/{decision_id}/counterfactual` | The exact quantified distance from this decision to the TRADE gate |
| GET | `/api/v1/decisions/{decision_id}/plan-freshness` | The TradePlan freshness decay clock (see §14 of the methodology doc) — `FRESH`/`AGING`/`STALE`/`EXPIRED`/`NO_PLAN` |
| GET / POST | `/api/v1/decisions/{decision_id}/journal` | Get/record the owner's response (`ACCEPTED`/`REJECTED`/`IGNORED` + notes) |
| GET / POST | `/api/v1/decisions/{decision_id}/outcome` | Get/record a realized entry/exit fill for an accepted decision — PnL computed server-side from the persisted TradePlan, never client-supplied |
| POST | `/api/v1/decisions/reset` | **CONFIRM-gated** — wipes the Decisions & Trace domain |

**Example — recording a journal response:**
```http
POST /api/v1/decisions/dec-abc123/journal
Authorization: Bearer <token>
Content-Type: application/json

{ "user_action": "ACCEPTED", "notes": "Confirmed with own chart review" }
```

**Example — logging a realized outcome:**
```json
{ "entry_price": "150.25", "exit_price": "162.80", "quantity": 100 }
```
`pnl` and plan adherence are computed server-side from the TradePlan that was actually persisted for that decision — this endpoint never accepts a client-supplied PnL.

### Market — market-wide intelligence and Kite-backed live data
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/market/summary` | The Market Summary hero: regime, F-5 health score, universe breadth, sparklines |
| GET | `/api/v1/market/ticker` | Header ticker: NIFTY 50 / BANK NIFTY / INDIA VIX |
| GET | `/api/v1/market/index-intelligence` | Every configured broad-market and sector index's level/change, from persisted data |
| GET | `/api/v1/market/index-intelligence/{index_key}/members` | Per-symbol membership + current board bucket for one index |
| GET | `/api/v1/market/opportunities` | Top Opportunities Today — sector-ranked, highest-conviction qualified symbols |
| GET | `/api/v1/market/instruments/{instrument_id}/quote` | Current last price — live Kite quote if fresh, else the last persisted one |
| GET | `/api/v1/market/instruments/{instrument_id}/candles` | Recent persisted candles for one instrument |
| GET | `/api/v1/market/instruments/{instrument_id}/index-backdrop` | Official index memberships for one symbol (informational only) |
| GET / PUT / POST / DELETE | `/api/v1/market/candidates` | Manage the owner's validation candidate list |
| POST | `/api/v1/market/validate` | Validate 1–20 candidates now (scoped ingest + score, synchronous) |
| GET / POST | `/api/v1/market/validate-all` | Poll / start a full-universe background validation (owner-triggered, single-flight) |

**Example — scoped revalidate (the dashboard's "Revalidate" button):**
```json
POST /api/v1/market/validate
{ "symbols": ["RELIANCE", "INFY"] }
```
Capped at 20 symbols per call by the schema (`maxItems: 20`) — this is the synchronous, small-batch path; `validate-all` is the separate, larger, background-job path for the whole universe.

### Pipelines
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/pipelines/runs` | List execution runs (PREMARKET/REFRESH/CLOSING/FAST/...) |
| GET | `/api/v1/pipelines/runs/{run_id}` | One run's full detail, including ingestion counts and any quarantined datasets |
| GET | `/api/v1/pipelines/validation-funnel` | Universe → Eligible → Filtered → Watch → Trade counts for the day |

### Portfolio
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/portfolio` | Cash, positions, NAV trend, day change |
| POST | `/api/v1/portfolio/positions` | Log an owner-entered **open fill** (record-keeping — not an order) |
| POST | `/api/v1/portfolio/positions/{position_id}/close` | Log an owner-entered **exit fill** |
| POST | `/api/v1/portfolio/positions/reset` | **CONFIRM-gated** — reset the owner's fill ledger |

### Saved Symbols
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/saved-symbols` | The owner's personal watch list |
| POST | `/api/v1/saved-symbols` | Save a symbol |
| DELETE | `/api/v1/saved-symbols/{symbol}` | Remove a saved symbol |

### Strategies
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/strategies/profiles` | List strategy profiles and their selection rules |

### Backtests
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/backtests/runs` | Backtest run history |
| GET | `/api/v1/backtests/runs/{run_id}` | One backtest run's detail |

### Analytics
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/analytics/performance/snapshots` | List performance snapshots |
| GET | `/api/v1/analytics/performance/snapshots/{snapshot_id}` | One snapshot's detail |

### Reports
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/reports` | List generic reports |
| GET | `/api/v1/reports/{report_id}` | One report's detail |

### Workspace
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/workspace/snapshots` | List workspace snapshot summaries |
| GET | `/api/v1/workspace/snapshots/{snapshot_id}` | One snapshot's detail |

### Exports
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/exports` | Create an export artifact |
| GET | `/api/v1/exports/snapshots` | List export snapshots |
| GET | `/api/v1/exports/snapshots/{snapshot_id}` | One export snapshot's detail |
| GET | `/api/v1/exports/artifacts/{export_id}` | One export artifact's detail |

### Scheduler
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/scheduler/history` | List scheduled pipeline runs |
| GET | `/api/v1/scheduler/history/{schedule_run_id}` | One scheduled run's detail |

### Operations — Kite session, backups, server control
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/ops/kite/status` | Verify the read-only Kite market-data session |
| POST | `/api/v1/ops/kite/start-auth` | Start the interactive Kite login flow |
| POST | `/api/v1/ops/kite/complete-auth` | Exchange the Kite request token, verify the session |
| POST | `/api/v1/ops/kite/disconnect` | Clear the daily Kite access token, require reconnect |
| GET / POST | `/api/v1/ops/backups` | List / create a database backup |
| POST | `/api/v1/ops/backups/{backup_id}/restore` | Restore the database from a backup |
| POST | `/api/v1/ops/restart` | Restart the ATHENA server process |
| GET | `/api/v1/ops/stream` | Server-Sent Events stream of live operations warnings |
| GET | `/api/v1/ops/telemetry` | Stage-by-stage telemetry for the latest pipeline run |

**The Kite auth flow, precisely** (this is the one piece worth walking through — it's a three-step interactive handshake, not a single call):
```
1. POST /api/v1/ops/kite/start-auth
   → returns the Kite login URL to open in a browser

2. (owner logs into Kite in their browser, Kite redirects back with a request_token)

3. POST /api/v1/ops/kite/complete-auth
   { "request_token": "..." }
   → exchanges it for a Kite access token, verifies the session is live, persists it for the day

4. GET /api/v1/ops/kite/status  → confirms the session is connected
```
Kite access tokens are day-scoped by Kite itself — `disconnect` clears ATHENA's copy early if needed, but the token expires on Kite's side regardless at end of day, requiring this flow again the next trading day.

### Dashboard
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/dashboard/summary` | Aggregated dashboard summary |
| GET | `/api/v1/dashboard/session-status` | Current exchange session status |
| GET | `/api/v1/dashboard/calendar` | Trading calendar configuration (holidays, expiries, sessions) |

### Platform Health & Discovery
| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/health` | Aggregated platform health | none |
| GET | `/health/live` | Liveness probe | none |
| GET | `/health/ready` | Readiness probe | none |
| GET | `/api/v1/health` | Platform health (v1-namespaced) | required |
| GET | `/api/v1/metrics` | Platform telemetry and metrics | required |
| GET | `/api/info` | Consolidated platform information | none |
| GET | `/api/meta` | Platform metadata | none |
| GET | `/api/version` | Application version | none |
| GET | `/api/capabilities` | Capability registry | none |
| GET | `/api/features` | Feature flags | none |

---

## Using the Postman collection

1. Import `postman_collection.json`.
2. Run **Auth → Unlock with owner credentials** with your real owner username/password.
3. Copy the returned `access_token` into the collection's `access_token` variable (Collection → Variables tab) — every other request already inherits Bearer auth from the collection level and will pick it up automatically.
4. `base_url` defaults to `http://127.0.0.1:8000` — change it if your instance runs on a different port.

## Using the OpenAPI file

```bash
# Swagger UI, locally
docker run -p 8080:8080 -e SWAGGER_JSON=/spec/openapi.yaml -v "$(pwd)/docs/api:/spec" swaggerapi/swagger-ui

# Or point any OpenAPI-aware client/codegen tool directly at docs/api/openapi.yaml
```
The running platform also serves its own live equivalents directly, useful for confirming this file hasn't drifted from a newer deployment: `GET /api/openapi.json`, and interactive docs at `/api/docs` (Swagger UI) and `/api/redoc` (Redoc).

---

*Generated from the live schema on 2026-08-07. Regenerate `openapi.yaml`/`postman_collection.json` from `GET /api/openapi.json` whenever routes change, and re-check this file's tables against the new route list.*
</content>
