# ID-9 — Position Sizing / Capital Allocation Discovery + V0 Contract

Status: **ID-9 POSITION SIZING DISCOVERY + V0 CONTRACT READY FOR OWNER /
CHIEF ARCHITECT REVIEW.** Discovery only — no contract frozen, no
implementation beyond the tiny read-only source-inspection probes cited
throughout. Zero production writes, zero schema change, zero methodology
change to ID-6/ID-7/ID-8.

## 1. Executive summary

ID-9 asks: given an opportunity that has passed `Decision.decision_type
== TRADE`, `EntryQualification.state == QUALIFIED`, and
`EntryActionability.state == ACTIONABLE`, with ID-8's frozen entry/risk
geometry, how much capital should ATHENA recommend allocating? This
discovery found the picture is **more nuanced than "build from
scratch"**:

- **The production entry/risk artifact ID-9 needs already exists and is
  already persisted** — `EntryActionability` (ID-7A, schema v18) carries
  `entry_reference.price`, `operative_invalidation.level`,
  `reward.t1_price`/`t2_price`/`reward_risk_to_t1`/`reward_risk_to_t2`,
  and `direction`, all Decimal, all immutable, all queryable via
  `SqliteRepository.get_entry_actionability`/`latest_entry_actionability_for_entry_qualification`.
  **There is no "missing EntryRisk artifact" gap** (§10) — ID-9 consumes
  `EntryActionability` directly, never a research harness.
- **A complete, tested, code-reviewed sizing/allocation/order-planning
  pipeline (P5.2–P5.6) already exists in this repository** —
  `CapitalAllocationEngine` (`allocation/engine.py`), `PositionSizingEngine`
  (`sizing/engine.py`), `OrderPlanningEngine` (`orders/engine.py`),
  `BrokerManager` (`brokers/engine.py`), `OrderLifecycleEngine`
  (`execution/engine.py`) — with matching `config/*.json` policy files
  and pydantic schemas. **But this entire pipeline is DORMANT in
  production**: it is imported by zero live code path (`cli.py`,
  `runtime/`, `ops/owner_validation.py`, `scheduling/` all have zero
  references — §5, §7), it operates on the pre-ID-track generic
  `Decision` object (never `EntryQualification`/`EntryActionability`),
  and its own capital source is the separate legacy `owner_positions`
  manual-fill ledger, never a live broker feed. This is the single most
  important architectural fact this discovery surfaces — see §5/§7/§36
  for the resulting Owner decision this creates.
- **`config/capital.json`/`CapitalConfig` and `config/risk.json`/`RiskConfig`
  are loaded but consumed by zero engines anywhere** — real Owner-
  configured-looking policy values (`total_capital`, `per_trade_risk_pct`,
  `max_capital_per_position_pct`, `max_capital_per_sector_pct`,
  `max_daily_loss_pct`) sit in the config system entirely unused (§8).
- **No live cash/available-capital or broker account state exists
  anywhere in ATHENA** — every capital/position figure in the repository
  is either a hardcoded config default or manually entered by the Owner
  (the legacy fill ledger, or My Portfolio's CSV/XLSX import). A V0
  sizing engine must therefore explicitly be a
  `THEORETICAL_POLICY_CAPITAL_SIZING` engine (§9), never implying
  brokerage synchronization.
- **NSE/BSE cash equities have no real lot-size constraint** (`lot_size`
  is always 1 for genuine equities in this codebase's data path) but
  **no tick-size rounding convention exists anywhere**, including in
  `TradePlan` (§14) — a sizing engine introduces the first real
  Decimal-quantization-to-tick-size logic in the repository.
- **SHORT sizing should be refused in V0**, not mechanically computed
  and merely labeled — see §28 for the reasoning.

## 2. Scope

Discovery and V0 contract design only, per explicit Owner authorization.
No `PositionSizing` domain object implemented. No schema migration. No
workflow-stage wiring. No API/UI. A handful of tiny, read-only source
inspections (grep/read of existing files) were performed to answer the
Owner's 12 questions (§21) with evidence, never guesses. Zero writes to
`db/athena.db`; zero provider/network calls; zero touches to ID-6, ID-7,
ID-8 methodology, EMR, or DarvaX.

## 3. Frozen upstream dependencies (restated, unchanged by this milestone)

- `Decision.decision_type == TRADE` AND exact bound
  `EntryQualification.state == QUALIFIED` AND
  `EntryActionability.state == ACTIONABLE` AND
  `entry_actionability_currentness.is_currently_usable(...)` must be
  `CURRENT` when consumed live (`src/athena/intraday/entry_actionability_currentness.py`).
- ID-8 frozen PRIMARY LONG contract (owner-frozen, `ID8_V0_ENTRY_RISK_PARTIALLY_SUPPORTED`):
  entry reference = `CHECKPOINT_CLOSE_THEORETICAL` (the completed-M5-close
  checkpoint price); operative invalidation = evolving session VWAP-loss;
  T1 ≈ +1%/−1%, T2 ≈ +1.5%/−1.5% (`GOAL_BANDS_ONLY`); RR is
  `RR_INFORMATIONAL_ONLY`, never a gate; no validated extension gate; OR15
  and D1-ATR are context/level geometry only
  (`OR15_LEVEL_GEOMETRY_RECONSTRUCTED_EVENT_SEMANTICS_NOT_RECOVERABLE`,
  `D1_ATR_LEVEL_GEOMETRY_RECONSTRUCTED_EVENT_SEMANTICS_NOT_RECOVERABLE`).
  `LONG_VALIDATED_SHORT_UNVALIDATED` remains frozen — no SHORT sizing
  methodology is invented from this unsupported upstream evidence (§28).
- None of the above is reopened, re-derived, or re-validated by this
  milestone.

## 4. Source files inspected

`src/athena/intraday/entry_actionability_models.py`,
`entry_actionability_currentness.py`; `src/athena/data/store/repository.py`
(entry_actionability read methods, `owner_positions` methods);
`src/athena/data/store/schema.py` (portfolio_*, owner_positions,
symbol_master, entry_actionabilities tables); `src/athena/domain/decision.py`
(`Decision`, `TradePlan`, `Portfolio`, `CapitalState`, `RiskEvaluation`);
`src/athena/domain/market.py` (`Instrument`, `Candle`); `src/athena/config/models.py`
(`CapitalConfig`, `RiskConfig`, `PortfolioConfig`, `AllocationConfig`,
`SizingConfig`, `OrderPlanningConfig`, `BrokerConfig`, `ExecutionConfig`,
`PortfolioAnalyticsConfig`, `ProfileSizingConfig`); `config/capital.json`,
`config/risk.json`, `config/portfolio.json`, `config/allocation.json`,
`config/sizing.json`, `config/orders.json`, `config/brokers.json`,
`config/portfolio_analytics.json`, `config/darvax.json`;
`src/athena/allocation/engine.py`, `src/athena/sizing/engine.py`,
`src/athena/orders/engine.py`, `src/athena/brokers/engine.py`,
`src/athena/execution/engine.py`, `src/athena/risk/engine.py`;
`src/athena/orchestration/pipelines/execution.py`, `orchestration/stages/`
(allocation.py, sizing.py, order_planning.py, broker_translation.py);
`src/athena/portfolio/my_portfolio_contracts.py`, `sync.py`,
`interpretation.py`, `structural_review.py`, `models.py`, `engine.py`;
`src/athena/api/v1/providers/sqlite_providers.py`
(`SqlitePortfolioProvider`); `src/athena/symbols/models.py`,
`symbols/catalog.py`, `symbols/classify.py`; `src/athena/data/providers/kite_provider.py`;
`src/athena/intraday/relative_volume_models.py`; `src/athena/ops/owner_validation.py`
(the live per-instrument `WorkflowStage` DAG); `src/athena/cli.py` (every
subcommand); `docs/design/SYMBOL-UNIVERSE-INVESTIGATION.md`;
`docs/ATHENA-WORKFLOW-METHODOLOGY.md`;
`docs/research/ID-7-INTRADAY-ENTRY-TRADEPLAN-DISCOVERY.md`.

## 5. Existing capital concepts

Two disjoint capital-tracking subsystems exist, both manual-entry-based
— **neither is a live broker feed** (confirmed: `grep -rn "balance\|margin\|Protocol\|account" src/athena/brokers/` returns zero matches; no `.env`-driven capital figure exists):

| Concept | Class | Evidence |
|---|---|---|
| `CapitalConfig` (`total_capital`, `reserved_pct`, `max_capital_per_position_pct`, `max_capital_per_sector_pct`) | **EXISTING_BUT_UNUSED** — loaded by `config/loader.py`, consumed by **zero** engine anywhere (`grep -rln "CapitalConfig\b" src/athena --include=*.py` outside `config/`: no hits) | `config/models.py:123`, `config/capital.json` |
| `RiskConfig` (`per_trade_risk_pct=0.5`, `max_daily_loss_pct=2.0`, `max_consecutive_losses`, `max_decisions_per_day`) | **EXISTING_BUT_UNUSED** — same pattern, zero consumers (`grep -rn "per_trade_risk_pct\|max_daily_loss_pct" src/athena --include=*.py` outside `config/models.py`: no hits) | `config/models.py:105`, `config/risk.json` |
| `PortfolioConfig.initial_cash` (₹10,00,000 default) | **EXISTING_BUT_PARTIAL** — genuinely consumed, but only as the starting-cash baseline for the legacy manual `owner_positions` ledger (§5 continued below), never a live balance | `config/models.py:1326-1340`, `config/portfolio.json` |
| `CashBalance` (`total_cash`/`available_cash`/`allocated_cash`/`reserved_cash`) domain object | **CANONICAL for the legacy ledger only** — computed by `SqlitePortfolioProvider._compute_cash` (`src/athena/api/v1/providers/sqlite_providers.py:335-347`) as `initial_cash` minus manually-entered position costs plus manually-entered exit proceeds | `src/athena/portfolio/models.py:136-151` |
| `AllocationConfig` (`FIXED_AMOUNT`/`FIXED_PERCENTAGE`/`EQUAL_WEIGHT`, `min_cash_reserve_pct`, `max_opportunities`) | **EXISTING_BUT_UNUSED IN PRODUCTION** — a real consuming class exists (`CapitalAllocationEngine`) but that class is never invoked anywhere reachable from `cli.py`/`runtime/`/`ops/` (verified: zero `AllocationEngine`/`CapitalAllocationEngine` references in those three trees) | `config/models.py:1349-1365`, `src/athena/allocation/engine.py:32-52` |
| Per-position/per-sector caps described in `docs/ATHENA-WORKFLOW-METHODOLOGY.md:395` | **DOCUMENTED BUT NOT_AVAILABLE IN CODE** — `AllocationConfig` itself has no per-position/per-sector cap field; only `CapitalConfig` (itself unused, above) has those fields | `docs/ATHENA-WORKFLOW-METHODOLOGY.md:395` vs. `config/models.py:1349-1365` |

**No live broker cash/margin/account-balance capability exists at all** —
confirmed by direct grep of `brokers/`.

## 6. Existing position/exposure concepts

Two entirely separate "portfolio" subsystems live under `src/athena/portfolio/` — **do not conflate them**:

1. **"My Portfolio" (Portfolio Sync, frozen/closed track)** —
   `my_portfolio_contracts.py`: `CanonicalPortfolioHolding`
   (`instrument_id`, `quantity`, `avg_price`, provenance — **no sector
   field, no cash field**); `PortfolioSnapshotSummary` aggregates
   `total_investment`/`total_current_value`/`total_pnl` **over imported
   holdings only** — no cash/available-capital dimension. 100%
   owner-uploaded CSV/XLSX, reconciled diff-only
   (`portfolio/sync.py`) — never a live broker feed.
2. **The legacy Portfolio Engine (P5.1) + `owner_positions` manual fill
   ledger** — `domain/decision.py:164-169` `Portfolio` dataclass has
   `cash: Decimal` and `exposure_by_sector: Mapping[str, Decimal]`;
   backing table `owner_positions`
   (`src/athena/data/store/schema.py:276-292`: `position_id,
   instrument_id, opened_ts, quantity, avg_price, closed_ts, exit_price,
   decision_ref, broker, notes, sector, meta_json`). Populated by
   `SqlitePortfolioProvider` (`api/v1/providers/sqlite_providers.py:184-360`)
   — genuinely live/wired into `dashboard/engine.py`,
   `explainability/engine.py`, `reporting/engine.py`,
   `monitoring/engine.py`, `timeline/engine.py`,
   `analytics/portfolio/engine.py` for **display purposes**. This is the
   **only place `exposure_by_sector` is computed anywhere in ATHENA**,
   and it depends entirely on the Owner having typed a free-text
   `sector` string into each manually-entered fill row.

**Classification:**

| Concept | Class | Source |
|---|---|---|
| Current holdings/quantity | **CANONICAL** (two disjoint, unreconciled sources) | `portfolio_holdings` (My Portfolio import) OR `owner_positions` (manual fill entry) |
| Cash / available capital | **EXISTING_BUT_PARTIAL** | Legacy `owner_positions`/`CashBalance` only; absent from My Portfolio entirely |
| Total portfolio value | **EXISTING_BUT_PARTIAL** | `PortfolioSnapshotSummary.total_current_value` (holdings only, no cash) vs. legacy `CashBalance` (cash only, no holdings) — no single number combines both today |
| Sector exposure aggregate | **EXISTING_BUT_PARTIAL** | Only via legacy `owner_positions.sector` (free text) → `_compute_exposure` (`sqlite_providers.py:349-358`); My Portfolio has no sector field at all |

`structural_review.py` is confirmed price-level-only (swing-point/support/
target zones) — no capital or exposure concept.

## 7. Existing sizing/risk concepts

A complete, tested P5.2→P5.6 pipeline exists — **but is entirely
dormant in production** (never imported by `cli.py`, `runtime/`,
`ops/owner_validation.py`, or `scheduling/`; the whole `orchestration`
package that declaratively registers these stages is itself never
imported from any of those trees either):

| Stage | Engine | Consumes | Produces | Reachable from live serve? |
|---|---|---|---|---|
| Capital Allocation (P5.2) | `CapitalAllocationEngine.allocate()` (`allocation/engine.py:46`) | `PortfolioSnapshot` + `Sequence[Decision]` (the **generic** `domain.decision.Decision`, never `EntryQualification`/`EntryActionability`) | `AllocationPlan`/`CapitalAllocation` (rupee amounts only) | **No** |
| Position Sizing (P5.3) | `PositionSizingEngine.size_plan()` (`sizing/engine.py:45,118,245`) | `AllocationPlan` + instrument price | `PositionSize.quantity` (`raw_qty = allocated_amount / price`, WHOLE_SHARE/FRACTIONAL rounding) | **No** |
| Order Planning (P5.4) | `OrderPlanningEngine.plan_execution()` (`orders/engine.py:47`) | `PositionSizingPlan` | `PlannedOrder`/`ExecutionPlan` | **No** |
| Broker Translation (P5.5) | `BrokerManager.translate_plan()` (`brokers/engine.py:75`) | `ExecutionPlan` | `BrokerRequest` against `paper_broker` only | **No** |
| Order Lifecycle (P5.6) | `OrderLifecycleEngine` (`execution/engine.py:61`) | — | State machine only, no broker I/O | **No** |

Separately, `RiskEngine.assess()` (`risk/engine.py:81`) computes a
0-100 **trade-level** exposure/uncertainty score (volatility, liquidity,
gap, event, market-environment, universe-breadth concentration) feeding
Decision Confidence — explicitly "never a recommendation or position
size" per its own header (`risk/engine.py:3-5`). This is the live
per-cycle `risk` `WorkflowStage` seen in `owner_validation.py`
(`depends_on=("indicators","regime")`, `produces=("risk",)`) — **it is
not position sizing and must not be confused with it.**

`TradePlan.position_size`/`risk_amount` (`domain/decision.py:14-36`)
exist as fields but are **STUB_ONLY**:
`decision/engine.py:262-266` constructs
`position_size=cfg.default_units` (a hardcoded config int, default `1`)
and `risk_amount=stop_dist * Decimal(cfg.default_units)` — never
capital-derived, never connected to `sizing/`/`allocation/`.
`docs/research/ID-7-INTRADAY-ENTRY-TRADEPLAN-DISCOVERY.md:167` itself
documents this as "a provisional unit, NOT a capital-based size."

Two dead domain types sit unused in the same file:
`CapitalState` (`decision.py:56-74`: daily/allocated/reserved capital,
max-per-sector, max-per-position) and `RiskEvaluation`
(`decision.py:39-53`) — never constructed anywhere except their own
definitions. These read as an earlier, superseded design sketch.

**Bottom line:** the sizing MATH (capital → quantity, with
WHOLE_SHARE/ROUND_DOWN rounding) is already written, unit-tested, and
architecturally sound — but it has never been fed a real opportunity,
never fed real capital state, and predates `EntryQualification`/
`EntryActionability` entirely. See §36 for the resulting recommendation.

## 8. Existing configuration/policy concepts

Every `config/*.json` file relevant to capital/sizing was read in full:

- `config/capital.json` (`CapitalConfig`): `total_capital`,
  `reserved_pct`, `max_capital_per_position_pct`,
  `max_capital_per_sector_pct`, with a validator enforcing
  per-position% ≤ per-sector%. **Zero consumers.**
- `config/risk.json` (`RiskConfig`): `max_daily_loss_pct: 2.0`,
  `per_trade_risk_pct: 0.5`, `max_consecutive_losses: 3`,
  `max_decisions_per_day: 5`, `no_trade{min_market_health, block_on_stale_data}`.
  Its own `_meta.description`: "Risk EVALUATION rules (F-4). Sizing/
  capital live in capital.json." **Zero consumers.**
- `config/portfolio.json` (`PortfolioConfig`): `initial_cash:
  "1000000.00"`, `currency: "INR"`, `allow_short: false`. Its own
  `_meta.description`: "Portfolio Engine + owner fill ledger cash
  baseline (P5.1). initial_cash is the cash starting point before
  logged Kite/Groww fills. ATHENA never places orders." **Consumed** —
  by the legacy `owner_positions` cash computation (§6).
- `config/allocation.json` (`AllocationConfig`): `default_model:
  FIXED_PERCENTAGE`, `fixed_amount: 100000.00`, `fixed_percentage:
  10.0`, `max_opportunities: 5`, `min_cash_reserve_pct: 20.0`. Has a
  consuming class but that class is dormant (§7).
- `config/sizing.json` (`SizingConfig`): `default_model: WHOLE_SHARE`,
  `default_rounding: ROUND_DOWN`, `decimal_precision: 4`. Same status.
- `config/orders.json`/`config/brokers.json`: order-planning/broker-
  abstraction policy, same dormant-consumer status.
- `ProfileSizingConfig` (`config/models.py:203`, in `profiles/*.json`)
  is a **strategy profile's own declared** `method`+`risk_per_trade_pct`
  — its own docstring explicitly warns this is a *different* concept
  from the Sizing Engine's config, a naming collision an ID-9 design
  must not repeat.
- `config/darvax.json`/`darvax/positions/models.py`: `DarvaxPosition`
  tracks quantity/entry/stop for DarvaX's own advisory HOLD/EXIT logic
  only — its own docstring states "nothing here sizes a trade, allocates
  capital, or places an order"; `config/darvax.json` explicitly forbids
  adding DarvaX fields to any `athena.config` model (ADR-010 isolation).
  **Not a sizing precedent to reuse.**

## 9. Upstream entry/risk production availability

**Fully production-available today**, via `EntryActionability`
(`intraday/entry_actionability_models.py`) — when
`state == ACTIONABLE`:

- `entry_reference.price: Decimal` (the M5-close checkpoint entry
  trigger, always positive).
- `operative_invalidation.level: Decimal` (VWAP-loss level; the
  domain's own `_validate_risk_geometry` already guarantees this is
  strictly on the correct side of `entry_reference.price` for the
  declared `direction` — a structurally-invalid geometry can never
  reach `ACTIONABLE` in the first place, per
  `entry_actionability_models.py:523-549`).
- `reward.t1_price`/`t2_price: Decimal`, `reward.reward_risk_to_t1`/
  `reward_risk_to_t2: Decimal | None` (informational only).
- `direction: Direction` (LONG/SHORT/NONE).
- `evidence_as_of`, `entry_actionability_as_of`, full upstream
  EntryQualification identity — everything `is_currently_usable(...)`
  needs.

Read via `SqliteRepository.latest_entry_actionability_for_entry_qualification(...)`
(exact-EQ-identity) or `.get_entry_actionability(...)` (exact full
identity) — both already exist, zero new repository method required.

**This is genuinely production data, not a research-only artifact.**
ID-8's own forward-outcome study (MFE/MAE, T1/T2 hit rates,
VWAP-loss-timing) is research-only and must never be consumed by ID-9 —
but the *inputs* to that study (entry price, invalidation level, T1/T2
prices) are the same fields `EntryActionability` already persists in
production, per real cycle, today.

## 10. EntryRisk artifact gap assessment

**No gap exists.** `EntryActionability` already IS the production
entry/risk artifact ID-9 needs (§9) — per-share risk distance, T1/T2,
and direction are all present, Decimal, immutable, and queryable by
exact identity. **Do not invent a new `EntryRisk` domain object.** ID-9
should consume `EntryActionability` (state == ACTIONABLE) directly, the
same way `EntryActionabilityEngine` consumed `EntryQualification` and
`EntryQualificationEngine` consumed `Decision` (ADR-013/ADR-015's own
established layering pattern) — ID-9 becomes ADR-013's next downstream
layer, not a sibling requiring its own new upstream contract.

## 11. Portfolio/holdings dependency assessment

Two disjoint, non-reconciled sources exist (§6): My Portfolio
(`portfolio_holdings`, no cash/sector) and the legacy `owner_positions`
ledger (`Portfolio`/`CashBalance`/`exposure_by_sector`, manual entry).
**ID-9 should not hard-couple to either for V0.** Recommendation:
V0 sizing operates against an explicit, Owner-supplied
`CapitalPolicy.total_deployable_capital` figure (§9's
`THEORETICAL_POLICY_CAPITAL_SIZING` mode) and exposes
concentration/available-capital constraints as
`CONCENTRATION_CHECK_NOT_AVAILABLE`/`AVAILABLE_CAPITAL_POLICY_ONLY`
rather than silently reading either ledger. A future milestone can
decide whether and how to reconcile the two ledgers into one
authoritative exposure source — not ID-9's problem to solve.

## 12. Liquidity-data availability

Absolute traded volume is available on every persisted candle
(`Candle.volume: int`, `domain/market.py:49`) at D1 and M5 granularity —
a coarse `recent_traded_value ≈ D1.volume × D1.close` capacity metric is
directly computable with zero new data. `RelativeVolumeContext`
(`intraday/relative_volume_models.py`, ID-5D, owner-approved) already
computes a same-time-of-day cumulative RVOL ratio against a real
baseline-session window — genuinely canonical, but it measures *relative*
volume (today vs. typical), not an absolute capacity bound; it is
context, not a capacity constraint, without further design work. No
provider-level bid/ask/depth/spread/market-impact data exists anywhere
(confirmed by the ID-8 discovery's own full 30-table schema scan,
carried forward here) — a liquidity constraint beyond a coarse
volume-fraction cap is **NOT_AVAILABLE**.

## 13. Sector/concentration-data availability

`Instrument.sector: str | None` exists on the canonical instrument model
(`domain/market.py`) — sector *classification* is available per
instrument. **Aggregate current sector exposure is not reliably
available** (§6/§11): the only computed aggregate today
(`_compute_exposure`, legacy `owner_positions`) depends on free-text
manual data entry, not a canonical source ID-9 should silently trust.
V0 must classify this `CONCENTRATION_CHECK_NOT_AVAILABLE` rather than
compute a number from an unreliable source.

## 14. Instrument lot-size/quantity rules

`Instrument.lot_size: int = 1` and `Instrument.tick_size: Decimal =
Decimal("0.05")` are real fields (`domain/market.py`), also mirrored in
`symbol_master` (`symbols/models.py`, `data/store/schema.py:29-42`).
Confirmed empirically: zero real NSE/BSE cash-equity rows in this
codebase's data path ever carry `lot_size != 1`
(`docs/design/SYMBOL-UNIVERSE-INVESTIGATION.md:133`; pinned by
`tests/symbols/test_su1_symbol_master.py:198`,
`test_lot_size_cannot_carry_the_tradability_signal`) — consistent with
real-world NSE/BSE cash-equity behavior (unlike F&O). **Minimum
tradable quantity is effectively always 1 share today**, but a sizing
engine should still divide/floor by `instrument.lot_size` for
correctness rather than hardcoding `1`, since the field is real and
genuinely part of the domain model.

**No tick-size rounding convention exists anywhere in the repository**
— confirmed by inspecting `TradePlan._build_plan`
(`decision/engine.py:232-266`): `stop`/`target` are raw, unquantized
`Decimal` arithmetic. A sizing engine introduces the first genuine
`Decimal.quantize(instrument.tick_size, ...)` price-rounding logic in
ATHENA — this needs its own explicit design decision (§16), not an
assumption borrowed from elsewhere.

## 15. Money/Decimal conventions

All monetary/price arithmetic elsewhere in the repo uses `Decimal`
(never binary float) — confirmed convention, e.g. `_quantize` helpers
in `brokers/engine.py:30-31` (`ROUND_HALF_UP`, 2 decimal places for
rupee totals) and `darvax/signals/stops.py:37-40` (2-place price
quantization). `SizingConfig.default_rounding = ROUND_DOWN`
(`config/models.py:1373-1383`) is the one existing convention
specifically for *quantity* flooring — reusable directly. No existing
convention rounds a *price* to a tick size (§14) — ID-9 must define
this itself if tick-size-aware pricing is wanted, or explicitly declare
V0 skips tick rounding (prices come pre-rounded from `EntryActionability`
already, since M5-close/VWAP-loss levels are real observed trade prices,
not synthetic ones — tick-size rounding is arguably only relevant to
`OperativeInvalidation`-implied stop-order prices, an ID-11 concern, not
ID-9's).

## 16. Proposed observation/identity

A `PositionSizing` V0 identity should mirror ADR-013/ADR-015's own
established pattern: the entire upstream `EntryActionability` identity,
copied verbatim (`instrument_id, session_date,
entry_qualification_as_of, decision_id,
entry_qualification_methodology_version, entry_actionability_as_of,
entry_actionability_methodology_version`), plus this artifact's own
`position_sizing_as_of` and `sizing_methodology_version`. No surrogate
id, consistent with EQ/EntryActionability precedent. Proposed only —
not frozen by this discovery (§13 of the Owner's authorization).

## 17. Proposed timestamps/currentness

`position_sizing_as_of` (this artifact's own evaluation instant),
`evidence_as_of` (copied from the bound `EntryActionability`, never
re-derived), `evaluated_at` (wall-clock diagnostic only, mirroring
`EntryActionability.evaluated_at`'s own precedent), `methodology_version`
(sizing math identity), `capital_policy_version` (separate from
methodology — a policy-value change, e.g. the Owner raising
`risk_budget_per_trade_pct`, must not silently masquerade as a
methodology change, and vice versa). Currentness must require **exact
identity** of the upstream `EntryActionability` (full composite key,
never `decision_id` alone) — reusing
`entry_actionability_currentness.is_currently_usable`'s own established
exact-identity pattern rather than inventing a new one. A sized result
must never remain "usable" once its underlying actionable opportunity is
superseded — no sticky state, mirroring ID-7A0.1's own frozen dimension-A/
dimension-B separation.

## 18. Proposed state model

Smallest deterministic set, distinguishing methodology result from
read-time currentness from policy availability from direction-validation
status (never conflated, per the Owner's own instruction):

- `SIZED` — a valid, positive, capital-constrained quantity was
  produced.
- `ZERO_QUANTITY_UNDER_POLICY` — geometry and policy were both valid,
  but the binding constraint's own arithmetic floors to less than one
  tradable unit (§27 — never silently rounded up to a forced minimum).
- `NOT_SIZED` — upstream not `ACTIONABLE`, risk geometry unavailable, or
  capital policy unavailable (each with its own reason code, never
  collapsed into one vague label).
- `UNKNOWN` — reserved only if a genuine methodology-evidence gap exists
  distinct from `NOT_SIZED`'s upstream-ineligibility family (mirroring
  `EntryActionabilityState`'s own dimension-A discipline) — likely
  unnecessary for V0 given `EntryActionability` already resolves
  eligibility upstream; propose omitting a separate `UNKNOWN` state
  unless a genuine V0 case is found requiring it (avoid state
  proliferation the Owner explicitly warned against).

Read-time currentness (dimension B) is never a persisted state, per
§17. Direction-validation status (`UNVALIDATED_DIRECTION` for SHORT, if
Option B of §28 is chosen) is a third, independent dimension, never
merged into the methodology-state enum itself.

## 19. Proposed reason model

Mirroring `EntryActionabilityReasonCode`'s own family-separated
discipline: an `UPSTREAM_NOT_ACTIONABLE` family (upstream
`EntryActionability.state != ACTIONABLE`, or superseded/stale per
currentness), a `RISK_GEOMETRY` family (`RISK_REFERENCE_UNAVAILABLE` —
should be structurally unreachable given §9's finding that ACTIONABLE
already guarantees valid geometry, but defensively checked rather than
assumed), and a `CAPITAL_POLICY` family
(`CAPITAL_POLICY_UNAVAILABLE`, `ZERO_QUANTITY_UNDER_POLICY`). Every
`NOT_SIZED`/`ZERO_QUANTITY_UNDER_POLICY` result must carry at least one
reason code — never silently empty, per ADR-005's explainability
mandate.

## 20. Per-share-risk semantics

LONG: `per_share_risk = entry_reference.price - operative_invalidation.level`.
SHORT: `per_share_risk = operative_invalidation.level - entry_reference.price`.
Must be `> 0` before any sizing proceeds. As found in §9,
`EntryActionability`'s own `_validate_risk_geometry` invariant already
makes a zero/wrong-side result structurally unreachable whenever
`state == ACTIONABLE` for the declared direction — so in practice this
reduces to a defensive re-check (`VALID_GEOMETRY` is the expected
99.9%+ case), never a fabricated absolute-value fallback that would hide
a genuine upstream defect. `RISK_REFERENCE_UNAVAILABLE` is reserved for
the case where `operative_invalidation` itself is `None` (only possible
if `state != ACTIONABLE`, at which point sizing should never have been
attempted in the first place — an upstream-gating bug, not a sizing
concern).

## 21. Risk-based quantity

`risk_amount = deployable_capital × configured_risk_pct` (Decimal
throughout); `risk_quantity = floor(risk_amount / per_share_risk /
instrument.lot_size) × instrument.lot_size` (floor to whole lots, which
for cash equities per §14 collapses to `floor(risk_amount /
per_share_risk)`, whole shares). `configured_risk_pct` must come from
an explicit Owner `CapitalPolicy`, never invented (§28 of the
authorization) — no candidate default value is proposed here.

## 22. Max-value quantity

`value_quantity = floor(max_position_value / entry_reference.price /
instrument.lot_size) × instrument.lot_size`, a separate, independently
computed constraint — never combined with the risk-percentage
calculation into one formula, per the Owner's explicit instruction.
`max_position_value` must come from Owner policy (e.g. a configured
`max_position_value_pct × total_deployable_capital`); no number is
proposed here.

## 23. Available-capital quantity

Given §11's finding (no reliable live "available capital minus
committed" signal exists), V0's only honest option is
`THEORETICAL_POLICY_CAPITAL_SIZING`: `available_capital_quantity =
floor(total_deployable_capital / entry_reference.price /
instrument.lot_size) × instrument.lot_size`, explicitly labeled as
policy-capital-based, never implying brokerage-account synchronization.
A future milestone that reconciles §6's two ledgers could tighten this
to a genuine "capital minus open positions" figure — out of scope here.

## 24. Liquidity constraint

Given §12, V0 can expose `recent_traded_value` (D1 volume × D1 close, a
real, already-available metric) as **context only** — no binding
liquidity gate is proposed, since no Owner-configured
fraction-of-volume policy exists yet (§8: no such field in any config
schema). If the Owner later configures e.g. `max_position_pct_of_adv`,
`liquidity_quantity` becomes computable with zero new data-acquisition
work; until then, classify `LIQUIDITY_CONTEXT_AVAILABLE_GATE_NOT_CONFIGURED`.

## 25. Concentration constraint

Given §13, no reliable current-exposure aggregate exists. Classify
`CONCENTRATION_CHECK_NOT_AVAILABLE` for V0 — expose the instrument's own
`sector` as context (it is real, canonical data), but do not compute or
gate on an aggregate-exposure number sourced from the unreliable legacy
ledger.

## 26. Binding-constraint semantics

Final `recommended_quantity = min(every APPLICABLE valid candidate
quantity)` — `risk_quantity` and `value_quantity` are always applicable
once policy exists; `available_capital_quantity` is applicable under
`THEORETICAL_POLICY_CAPITAL_SIZING`; `liquidity_quantity`/
`concentration_quantity` are applicable only once/if their respective
gates become configured (§24-25) — an unconfigured, non-mandatory
constraint must never silently participate in the `min()` as if it were
zero or infinite; it is simply absent from the candidate set, with its
own unavailability explicitly reported. `binding_constraint` names
whichever candidate(s) achieved the minimum (co-binding ties reported as
a list, never arbitrarily resolved to one). No hidden arithmetic — every
candidate quantity that was computed is echoed in the result (§15 of the
Owner's authorization).

## 27. Zero-quantity behavior

If the binding constraint's own floor produces `quantity < 1` (or
`< instrument.lot_size`), the result is `ZERO_QUANTITY_UNDER_POLICY` —
`recommended_quantity = 0`, never forced up to 1 share. This is a
truthful methodology result (the risk budget or capital policy
genuinely cannot support a position in this instrument at its current
price/risk-distance), not an error.

## 28. SHORT-direction handling

**Recommendation: refuse SHORT sizing in V0 (Option A), not compute-and-
label (Option B).** Reasoning: `LONG_VALIDATED_SHORT_UNVALIDATED` is not
a cosmetic caveat — ID-8's entire empirical evidence base (MFE/MAE, T1/T2
reachability, VWAP-loss timing, terminal ordering) that justifies
sizing a LONG position at all has **zero SHORT observations** in the
frozen PRIMARY analysis (SHORT was diagnostic-only throughout ID-8, with
100% invalid geometry in the episode-replay population). Computing a
mechanically-correct SHORT quantity would present a *number* with the
same visual authority as a LONG recommendation while resting on zero
validated outcome evidence — the exact "silent mixing of validated and
unvalidated evidence" pattern ADR-015/ID-7B.2 have repeatedly corrected
elsewhere in this codebase. A `NOT_SIZED`/`UNVALIDATED_DIRECTION` refusal
is the safer, more honest architecture, fully consistent with every
prior ID-6/ID-7/ID-8 precedent of refusing to extend a validated result
past its own evidence boundary.

## 29. T1/T2/RR role

Preserved exactly, per explicit instruction: `GOAL_BANDS_ONLY`,
`RR_INFORMATIONAL_ONLY`. ID-9 must not size larger because RR or T1/T2
distance is favorable — no Kelly criterion, no confidence-weighted
sizing, no score-weighted sizing, no conviction multiplier, no
martingale, no Decision-score-based scaling. V0 sizing is a pure
risk/capital-constraint minimum (§26), full stop.

## 30. Proposed V0 `PositionSizing` contract

An immutable dataclass (name TBD by the Owner — `PositionSizing` used as
a placeholder, not frozen) with, at minimum: the identity fields of §16;
`direction`; `entry_reference_price`, `operative_invalidation_level`,
`per_share_risk` (all copied/derived from the bound
`EntryActionability`, never re-fetched independently); candidate
quantities (`risk_quantity`, `value_quantity`,
`available_capital_quantity`, and the two context-only fields of §24-25
when present); `recommended_quantity`, `recommended_position_value`,
`capital_at_risk`; `binding_constraint` (one or more); `sizing_status`
(§18); `sizing_reasons` (§19); `capital_policy_version`,
`sizing_methodology_version`; the timestamps of §17; `explanation`
(ADR-005 mandatory). This is a proposal for Owner review, not a frozen
contract (per the authorization's own explicit instruction not to
freeze it here).

## 31. Persistence recommendation

**Not required to prove the V0 contract during a future design
milestone** (pure functions can be tested against synthetic
`EntryActionability`+`CapitalPolicy` inputs, mirroring
`EntryActionabilityEngine`'s own ID-7C precedent of shipping the pure
evaluator before persistence). If persistence is wanted for audit/
history, it should mirror the exact `entry_actionabilities` table
pattern (`data/store/schema.py`) — composite-key primary key, FK to the
bound Decision, nested-JSON value-object columns, append-only,
idempotent `save_*` with dual binding validation. Recommend deferring
the actual `CREATE TABLE`/schema-version bump to the implementation
milestone, not this discovery.

## 32. Workflow integration recommendation

Mirror ID-7E's own precedent exactly: a new `position_sizing`
`WorkflowStage` in `OwnerValidationPipeline._scan_eligible`'s per-
instrument DAG, `depends_on=("entry_actionability",)`,
`produces=("position_sizing",)`. Reuse the same same-cycle-context
closure pattern `entry_qualification_stage`/`entry_actionability_stage`
already use (read the exact `EntryActionability` this cycle's own
upstream stage produced — never a repository "latest" query at
write-time, mirroring ID-7E's own established discipline). Gate
evaluation to `state == ACTIONABLE` only (mirroring ID-7E.1's own
narrow-scope-gate correction) — a non-ACTIONABLE artifact should never
even reach sizing composition, exactly as a non-eligible EQ never
reaches EntryActionability's layer-3 evidence composition.

## 33. API/read-model implications

Out of scope for this discovery (no API/UI authorized). Noted for a
future milestone: any dashboard surface would need a clear, honest
label distinguishing `THEORETICAL_POLICY_CAPITAL_SIZING` (§9/§23) from
a genuine live-capital figure — this labeling requirement should be
carried into that future milestone's own design review, not decided
here.

## 34. Unsupported/deferred constraints

Liquidity binding gate (§24, context-only until policy configured),
concentration/sector binding gate (§25, not available), daily/portfolio
aggregate risk (§19 of the authorization — see the table below), Kelly/
confidence/score-weighted sizing (§29, explicitly forbidden), tick-size
price rounding (§14/§16, deferred to a future ID-11 concern if needed),
live broker cash/margin sync (§5, `NOT_AVAILABLE`, no Protocol exists
even abstractly).

| Daily/portfolio risk concept | Classification |
|---|---|
| Aggregate open risk across positions | `REQUIRES_PORTFOLIO_STATE` (needs a reconciled ledger, §6/§11) |
| Same-sector open risk | `REQUIRES_PORTFOLIO_STATE` |
| Same-direction exposure | `REQUIRES_PORTFOLIO_STATE` |
| Daily loss budget | `POLICY_ONLY` — `RiskConfig.max_daily_loss_pct` exists as an unused config value (§8); could inform a future policy field, but no live "today's realized loss" tracking exists to check it against |

Recommend all four remain `OUT_OF_V0` — the smallest useful, honest V0
is single-opportunity risk/capital-constraint sizing (§20-27) only.

## 35. Owner-configurable policy requirements

A `CapitalPolicy`/`RiskPolicy` (naming per Owner preference — inspect-
before-freezing per the authorization) distinct from `SizingMethodology`
is required for V0 to produce any non-trivial result at all. Candidate
fields (examples only, none frozen, none invented as defaults):
`total_deployable_capital`, `risk_budget_per_trade_pct`,
`max_position_value_pct`, `cash_reserve_pct`. `max_sector_exposure_pct`/
`max_instrument_exposure_pct` are meaningful only once §11's ledger
question is resolved — proposing them now would create policy fields
with no data to check them against. Existing `CapitalConfig`/
`AllocationConfig`/`RiskConfig` field names (§5/§8) are candidates for
direct reuse rather than reinvention, since they already carry very
similar semantics (`total_capital`, `min_cash_reserve_pct`,
`per_trade_risk_pct`) — an Owner decision, not decided here.

## 36. Owner decisions A-L

**A. What canonical capital/account state exists today?** None live —
only manually-entered ledgers (§5/§6), zero broker sync.
**B. What position/exposure information exists today?** Two disjoint,
unreconciled manual ledgers (§6); no live broker feed.
**C. What exact upstream entry/risk artifact can ID-9 consume in
production?** `EntryActionability` (state == ACTIONABLE) directly (§9).
**D. Is a canonical EntryRisk artifact missing after ID-8?** No (§10).
**E. What risk-budget policy values already exist?** `CapitalConfig`/
`RiskConfig` exist but have zero consumers (§8) — real values, unused.
**F. Which sizing constraints are implementable now without invented
numbers?** Risk-quantity and max-value-quantity (§21-22), *given* an
Owner-supplied policy value — the math needs no invention, only the
Owner's own numbers.
**G. Which constraints require Owner-configurable policy values?**
All of them (§21-23, §35) — V0 produces nothing without at least a
`total_deployable_capital` and a risk-or-value policy figure.
**H. Which constraints require future Portfolio Sync/account state?**
Available-capital-minus-committed (§23), concentration (§25), and all
four daily/portfolio-risk concepts (§34).
**I. Should SHORT sizing be blocked in V0?** Yes (§28).
**J. What is the smallest useful deterministic PositionSizing V0?**
Single-opportunity, `EntryActionability`-consuming, policy-driven
risk-quantity + max-value-quantity + theoretical-available-capital
minimum, LONG-only, zero liquidity/concentration/portfolio-risk gates
(§20-27, §34).
**K. Does it require persistence?** Not for the design/proof stage
(§31); recommended for a production-facing implementation, mirroring
`entry_actionabilities`' own schema pattern.
**L. Where should it integrate into the canonical workflow?** A new
`position_sizing` `WorkflowStage`, `depends_on=("entry_actionability",)`
(§32).

## 37. Recommended implementation sequence

A future, separately-authorized milestone should: (1) have the Owner
resolve §35's policy-field names/values and §11's ledger-reconciliation
question (or explicitly defer it, accepting `THEORETICAL_POLICY_CAPITAL_SIZING`
for V0); (2) implement the pure `PositionSizing` domain contract (§30)
and a pure sizing evaluator consuming `EntryActionability` +
`CapitalPolicy`, mirroring `EntryActionabilityEngine`'s own ID-7C
precedent exactly (no persistence yet); (3) add focused tests proving
every constraint/reason-code/zero-quantity/SHORT-refusal case; (4) only
then decide persistence (§31) and workflow wiring (§32) as a follow-on
slice, mirroring ID-7A→ID-7E's own staged sequence. Do not attempt all
of this in one milestone — the Owner's own "do not proliferate
sub-milestones unless a genuine correctness blocker is found" applies to
the *discovery* phase; a multi-slice *implementation* sequence is
standard practice here and mirrors every prior ID-7/ID-8 precedent.

## 38. Production safety

Strictly read-only throughout this discovery. No `db/athena.db` write,
no schema migration, no schema/repository/engine code change. All
"inspections" in this report were `grep`/`Read` of already-committed
source files and `config/*.json` — zero provider/network calls, zero
new files other than this report. `schema_version` and PID 2453 were
not touched or queried this milestone (no runtime state needed
inspecting for a pure source-discovery pass).

## 39. EMR isolation

Not referenced, not touched. `explosive_move/` package untouched.

## 40. DarvaX isolation

Not touched. `darvax/positions/models.py` was read only to confirm it
is NOT a sizing precedent (§8) — its own docstring already states this;
`config/darvax.json`'s explicit prohibition on adding DarvaX fields to
any `athena.config` model was read and is preserved, unmodified.

## 41. Files changed

Created: `docs/research/ID-9-POSITION-SIZING-DISCOVERY-AND-V0-CONTRACT.md`
(this report). No other files created or modified. No code change of
any kind.

## 42. `git diff --check`

Clean (only this new, untracked report file exists; no tracked file was
modified).

---

**ID-9 POSITION SIZING DISCOVERY + V0 CONTRACT READY FOR OWNER / CHIEF
ARCHITECT REVIEW**
