# ADR-002 — Broker Abstraction via MarketDataProvider

| | |
|---|---|
| Status | Accepted |
| Date | 2026-07-20 |
| Deciders | sandeep (owner, ATHENA-001R direction 1) |

## Context

Intraday v1 requires real-time-capable market data, but binding business logic to one broker (e.g., Zerodha) couples strategy code to a vendor's API shape, pricing, and auth quirks. Broker choice is deferred (DD-1).

## Decision

All market data flows through the `MarketDataProvider` Protocol (ATHENA-002 §7.2). Brokers are adapters in `data/providers/`, selected by config, conformance-tested by a shared contract suite. **No order-placement methods exist in the Protocol or any adapter — order placement is structurally impossible.**

## Alternatives considered

Direct Kite Connect integration — rejected: vendor lock-in before requirements are proven, violates deferred-decision discipline. Multi-broker facade library (third-party) — rejected: supply-chain surface, uncontrolled abstractions.

## Consequences

Phase 1 ships on FileProvider (free, deterministic, CI-friendly); broker selection waits for evidence against DD-1 criteria. Cost: one adapter to write per broker, and the Protocol must stay conservative (lowest-common-denominator capabilities, declared via `capabilities()`).
