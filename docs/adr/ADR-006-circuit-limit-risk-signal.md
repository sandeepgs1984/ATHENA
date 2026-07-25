# ADR-006 — Circuit-limit / price-band proximity as a risk signal

| | |
|---|---|
| Status | Proposed |
| Date | 2026-07-25 |
| Deciders | sandeep (owner) |

## Context

Zerodha Kite Connect's live quote response already includes per-symbol
`lower_circuit_limit` / `upper_circuit_limit` fields (the exchange-computed
price band for that instrument, that day). `KiteProvider.quotes()`
(`src/athena/data/providers/kite_provider.py`) reads `last_price`/`volume`/
`timestamp` from the same raw response row and silently discards these two
fields — they are fetched from the provider and thrown away today.

This is a real intraday risk gap: a stock trading 2% from its lower circuit
behaves very differently (halted-trading risk, liquidity air-pockets,
gap-continuation risk) than the same score/confidence/risk profile on a
symbol with room to move, and nothing in the Risk Engine (M3.5) currently
sees this.

The per-symbol band (5% / 10% / 20% / no-band, per NSE's periodic
category review) is **not** derivable from data ATHENA already holds —
`config/market.nse.json`'s `circuit_bands_pct: [5, 10, 20]` is only the
*set* of possible band percentages used for config validation, not a
per-symbol assignment. The live circuit-limit values from Kite are the only
source of the actual assignment.

Constraints: the frozen domain model (§4) and provider contracts (§7) may
not change without an ADR (§19). `MarketSnapshot.india_vix: Decimal | None`
already establishes precedent for an optional, provider-dependent field
that degrades honestly to `None`/UNKNOWN rather than being faked — this
extension follows that exact pattern, not a new one.

## Decision

Extend the frozen `Quote` domain object (`src/athena/domain/market.py`) with
two optional fields:

```python
lower_circuit_limit: Decimal | None = None
upper_circuit_limit: Decimal | None = None
```

`KiteProvider.quotes()` populates them from the already-fetched raw response
(no new API call, no new vendor, no new external dependency — DD-1 is
unaffected). `FileProvider` and any other provider that cannot supply them
leave them `None`; this is a live-only, current-session risk input, honestly
absent in historical/backtest data — same posture as `india_vix`.

Add a new Risk Engine (`src/athena/risk/engine.py`) dimension,
`circuit_proximity_risk`: when both limits are known, compute proximity of
`last_price` to whichever band is nearer, on a config-driven point scale
(new `risk_assessment.json` thresholds, no magic numbers); when unknown,
degrade to the existing `RiskStatus.UNKNOWN` pattern used by every other
dimension — never silently assume "no circuit risk."

## Alternatives considered

- **Derive circuit limits purely from previous close × configured band %.**
  Rejected — ATHENA has no per-symbol mapping of which band (5/10/20/none)
  applies; guessing would silently fabricate a risk input, which the
  constitution forbids (no invented values).
- **New standalone `PriceBand` domain object instead of extending `Quote`.**
  Considered for a smaller blast radius, but rejected: a circuit limit is
  intrinsically a property of a point-in-time quote, not a separate
  artifact with its own lifecycle/provenance; two optional fields on `Quote`
  is the smaller, more honest change and mirrors the `MarketSnapshot`
  precedent directly.
- **Do nothing (accept the gap).** Rejected per the owner's explicit
  "no compromise on any factors" direction — this is a live, low-effort,
  zero-new-dependency fix to a real risk blind spot.

## Consequences

- `Quote` gains two optional fields — additive, backward compatible, no
  existing consumer breaks (both default `None`).
- Risk Engine gains one new dimension; existing dimensions/weights/contracts
  untouched.
- FileProvider-driven backtests will always show this dimension as UNKNOWN —
  documented, honest, and expected; no fabricated circuit data ever enters
  a replay.
- Establishes the pattern for any *future* Kite-only live risk input: extend
  `Quote`/`MarketSnapshot` with an optional field degrading to `None`,
  never a required field, never silently defaulted.
- Must be revisited if a second live data vendor (DD-1 successor) is ever
  chosen and lacks equivalent fields — the optional/UNKNOWN degradation
  already covers that case without further changes.
