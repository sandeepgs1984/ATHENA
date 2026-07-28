# ADR-008 — Institutional Flow Provider (separate from MarketDataProvider)

| | |
|---|---|
| Status | **Accepted** |
| Date | 2026-07-28 |
| Deciders | sandeep (owner) — accepted with MH-0 / DD-11; gate cleared for MH-1 |
| Related | [ADR-002](ADR-002-broker-abstraction.md), [DD-11](../decisions/DD-11-institutional-flow-fii-dii.md), [F-5 spec](../design/F5-MARKET-HEALTH-SCORE.md) |

## Context

Frozen F-5 requires an `institutional_strength` component on `MarketHealthScore`. Owner chose an **external FII/DII cash-flow** source (DD-11). That data is not quotes, candles, or instruments — it is a daily category-level flow report. Extending `MarketDataProvider` (ADR-002) with institutional methods would:

- Couple every price-data adapter (File, Kite, future brokers) to an unrelated capability.
- Force false `capabilities()` declarations or optional no-ops that weaken the contract suite.
- Mix auth/rate-limit/failure semantics of brokers with public NSE report scraping.

ATHENA also needs FileProvider-parity for institutional rows so CI and replay stay deterministic.

## Decision

Introduce a dedicated **`InstitutionalFlowProvider` Protocol** (name exact in MH-1 code) under `data/providers/`, selected by config, with:

- Read-only methods returning canonical domain/institutional flow objects (session date, FII buy/sell/net, DII buy/sell/net, provisional flag, source id, fetched_at).
- At least two adapters: **file** (mandatory) and **nse** (live, per DD-11).
- Conformance tests analogous to the market-data contract suite.
- **No order methods.** No dependency from business logic on a concrete adapter.

`MarketHealthEngine` (and any MH-2 score factory) consumes only persisted/canonical flow objects passed in — never HTTP.

Persistence is append-only (new table or typed payload under an existing intelligence store — exact schema chosen in MH-1 with `SCHEMA_VERSION` bump). Engines never scrape at score time; ingestion writes, scoring reads.

## Alternatives considered

1. **Extend `MarketDataProvider`** — rejected: pollutes ADR-002 lowest-common-denominator contract; Kite cannot implement it honestly.
2. **Hardcode NSE fetch inside `market_health/`** — rejected: breaks provider independence and replay (hidden I/O).
3. **Price-volume proxy instead of FII/DII** — rejected by owner for MH-0.
4. **Third-party aggregator as sole source** — rejected as primary (DD-11); optional later adapter only.

## Consequences

**Easier:** clear boundary; File + NSE adapters; scoring stays pure; DD-11 source swaps without engine changes.

**Harder:** one more Protocol + contract suite + schema; NSE HTML/CSV fragility becomes an ops concern (mitigated by file fallback + unknown-component policy).

**Debt accepted:** provisional same-day figures until finalization supersedes them.

**Must revisit when:** a broker exposes a stable institutional-flow API that should become a third adapter, or NSE repeatedly breaks the live adapter (temporary third-party adapter under DD-11 §4 note 6).

## Gate

Cleared 2026-07-28 — ADR Accepted and DD-11 Accepted; MH-1 authorized.
