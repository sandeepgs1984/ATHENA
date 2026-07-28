# DD-11 — Institutional Flow (FII/DII) Data Source

| | |
|---|---|
| Status | **ACCEPTED** — Owner approved 2026-07-28 (proceed MH-1) |
| Date | 2026-07-28 |
| Trigger | Market Metrics Completion — F-5 `institutional_strength` cannot be computed from Kite price/volume data |
| ADR context | [ADR-008](../adr/ADR-008-institutional-flow-provider.md) (Accepted) — separate Protocol from ADR-002 `MarketDataProvider` |
| Code impact | MH-1 — InstitutionalFlowProvider + append-only persistence + universe breadth inputs |

---

## 1. Decision question

Which **external FII/DII cash-market flow source** should ATHENA ingest so the frozen F-5 component `institutional_strength` is real, explainable, and replayable — without fabricating a price-volume proxy?

Owner already rejected: price-volume participation proxy; keeping the aggregate score unavailable forever.

---

## 2. Decision criteria

| # | Criterion | Bar |
|---|---|---|
| C1 | Provenance | Traceable to NSE / NSDL (or another official Indian market publication), not a silent synthetic estimate |
| C2 | Replay | Same inputs → same score; historical rows persisted append-only with source timestamp and run provenance |
| C3 | Freshness | Usable for daily swing advisory (same-day or prior-session cash net flows) |
| C4 | Honesty | Provisional vs final figures labelled; missing/stale data → `INSTITUTIONAL_UNKNOWN`, never a default “neutral” score |
| C5 | Ops burden | Single-user workstation; no paid dependency required for v1 if an official free path exists |
| C6 | Provider isolation | Business logic depends on a Protocol / domain object, never a concrete HTTP client (ADR-002 family) |
| C7 | Failure mode | Fetch/parse failure fails loudly into unknown; never aborts the entire daily cycle the way an unlisted symbol once did |

---

## 3. Candidates evaluated

### A. Official NSE FII/FPI & DII Capital Market report (recommended primary)

| Criterion | Assessment |
|---|---|
| C1 | **Pass** — published by NSE (`nseindia.com/reports/fii-dii`); buy/sell/net ₹ Cr by category |
| C2 | **Pass** — downloadable CSV / table rows can be snapshotted into SQLite |
| C3 | **Partial** — same-day figures exist but are **provisional** until custodian confirmation |
| C4 | **Pass** — NSE itself documents provisional status; ATHENA must persist `provisional=true/false` |
| C5 | **Pass** — free for personal use; HTML/CSV shape can change (ops risk) |
| C6 | **Pass** — behind InstitutionalFlowProvider adapter |
| C7 | **Pass** if MH-1 treats missing flow as unknown component, not cycle abort |

**Fit:** Canonical source of truth for cash-market FII/DII. Best ATHENA default.

### B. NSDL / CDSL final FPI publications

| Criterion | Assessment |
|---|---|
| C1 | **Pass** — final FPI figures |
| C2 | **Pass** |
| C3 | **Fail for same-day** — typically lag the trading session |
| C4 | **Pass** — preferred for historical corrections |

**Fit:** Secondary **finalization** path: when a final row supersedes a provisional NSE row, append a superseding flow record (append-only), never UPDATE.

### C. Third-party aggregators (e.g. Mr. Chartist FII/DII JSON API)

| Criterion | Assessment |
|---|---|
| C1 | **Partial** — claims NSE/NSDL origin, but ATHENA would depend on a non-exchange middleman |
| C2 | **Partial** — convenient history endpoints; provenance weaker than storing NSE CSV ourselves |
| C3 | **Pass** |
| C4 | **Partial** — must trust `_source` flags; not under ATHENA control |
| C5 | **Pass** (currently free) but supply-chain / ToS / rate-limit risk |
| C6 | **Pass** as an alternate adapter only |
| C7 | **Partial** |

**Fit:** Optional convenience adapter **after** File + NSE official paths exist. Never the sole production source.

### D. Broker APIs (Kite / Upstox institutional endpoints)

| Criterion | Assessment |
|---|---|
| C1–C6 | **Fail / Unknown** for Kite Connect retail — no FII/DII cash report in the current ATHENA Kite adapter surface |

**Fit:** Rejected for MH-1. Revisit only if a broker later exposes a stable, documented institutional-flow endpoint that passes the contract suite.

### E. Owner-supplied CSV (FileProvider-style)

| Criterion | Assessment |
|---|---|
| C1 | **Pass** when the file is the NSE download the owner saved |
| C2 | **Pass** — gold for CI / replay |
| C3 | Manual |
| C5 | **Pass** |

**Fit:** **Mandatory** first adapter for deterministic tests and offline days (mirrors FileProvider for prices).

---

## 4. Recommendation (for owner acceptance)

**Select:**

1. **Primary live source:** Official NSE FII/FPI & DII Capital Market segment report (cash buy/sell/net ₹ Cr for FII/FPI and DII).
2. **Mandatory offline/replay source:** File-backed institutional-flow adapter consuming the same schema (CI, golden tests, offline workstation).
3. **Finalization:** When NSDL/CDSL (or a later NSE final) supersedes a provisional day, **append** a superseding row; engines prefer the newest non-provisional row for that session date, else the newest provisional with `provisional=true` in evidence.
4. **Optional later:** Third-party JSON aggregator as a *second* live adapter selected by config — never the only path.

### Acceptance notes

1. **Scope of MH-1:** cash-market FII and DII buy/sell/net only. F&O participant OI / PCR / sentiment scores are **out of scope** for F-5 v1 (can be a later DD if needed).
2. **Unit:** ₹ Crore, `Decimal`, session date in Asia/Kolkata.
3. **Secrets:** none required for NSE public report / file path; any future API key stays in `.env` only.
4. **Config:** `ingestion.institutional_flow_provider` = `file` | `nse` (default `file` until owner flips).
5. **Cycle resilience:** flow fetch failure → component unknown + loud log; daily cycle continues (unlike strict symbol-filter aborts).
6. **Revisit:** if NSE scrape breaks repeatedly within 30 trading days of MH-1 live use, owner may authorize a temporary third-party adapter without changing F-5 formulas.

---

## 5. Explicit non-goals

- Fabricating institutional strength from volume/price proxies.
- Binding `MarketDataProvider` / Kite to institutional flow (see ADR-008).
- Showing mock “84/100” until a persisted `MarketHealthScore` exists with all six components scoreable or an honest unavailable state (F-5 spec).

---

## 6. Traceability

- F-5 contract: `docs/design/F5-MARKET-HEALTH-SCORE.md`
- Provider ADR: `docs/adr/ADR-008-institutional-flow-provider.md`
- Blueprint type: `MarketHealthScore.components.institutional_strength` (ATHENA-002 §4 / F-5)
- Milestone track: `docs/MILESTONES.md` → Market Metrics Completion
