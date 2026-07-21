# ATHENA — Implementation Summary

Permanent implementation log. One section per completed phase, newest first,
in the 7-part format mandated by CLAUDE.md. Written before owner review;
status updated on approval.

---

## Phase 1 — Data Foundation (in progress)

### M1.6 — Backup & Restore  (completes Phase 1)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic backup + restore with integrity verification, schema-compat enforcement, recovery validation |
| Tests | 182 passed / 0 failed (11 new) |
| Status | **APPROVED** — closes Phase 1 (Principal Engineer review passed) |
| Branch | main |

Built the backup/restore layer. `create_backup` integrity-verifies the source, snapshots it via SQLite's online backup API written atomically (temp + `os.replace`, so a backup file is always complete), and writes a JSON metadata sidecar (schema version, per-table counts, provenance). `restore_backup` validates the backup first (integrity + schema-version compatibility — no silent repair, no automatic migration), replaces the target atomically, clears stale WAL sidecars, then re-verifies the restored repository (integrity, foreign keys, schema version, record counts vs metadata) and reports the outcome. Every failure mode raises `RepositoryError` with an actionable message and never leaves the target inconsistent. Repository-focused; no business/provider/intelligence logic.

Files created: `src/athena/data/store/backup.py`, `tests/data_layer/test_backup_restore.py`. Files modified: `src/athena/data/store/{__init__,repository}.py` (exports; repo `path`/`connection`/`record_counts` accessors). Public APIs added: `create_backup`, `restore_backup`, `BackupResult`, `RestoreResult`. 11 new tests: successful backup/restore, overwrite behavior, read-only destination, recovery of every entity, restored==original, deterministic repeated cycles, missing/corrupted backup, incompatible schema refusal (+ target untouched), unhealthy-source refusal.

**Codebase-wide quality pass (this milestone):** ran `ruff` for the first time (not previously available in the sandbox). Applied safe modernizations tree-wide — `typing.List/Dict/Tuple/Optional/Union` → builtin generics and `X | None` (verified against the 3.10 floor; all tests green), raw-string regex patterns in tests, and minor nits. Set ruff `target-version = py310` and `line-length = 120` (a deliberate project-standard width suited to this explainability-heavy code, avoiding low-value wrapping churn). `ruff check src tests` now passes clean. `mypy` could not run — v2.3.0 in the sandbox crashes with an INTERNAL ERROR on any input (tooling bug); strict typing remains configured for `domain`/`config` and should be verified on the owner's machine.

Validation checklist 1–10 passed; frozen contracts unchanged; no ADR; no drift; no tech debt.

---

## Phase 4 — Orchestration & Operational Intelligence (in progress)

### M4.5 — Backtesting Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic chronological replay of the existing operational pipeline across historical points, with no alternate analytical logic |
| Tests | 459 passed / 0 failed (19 new) |
| Status | **Awaiting owner approval** — M4.6 (Reporting & Analytics) blocked until approved |
| Branch | main |

Built the Backtesting Engine (`src/athena/backtest/`), which answers one question: "How would ATHENA's completed analytical pipeline and strategy framework have behaved across historical market snapshots?" `BacktestingEngine.run(points, *, run_id=None)` replays a chronological sequence of caller-supplied `ReplayPoint`s (each a timezone-aware `as_of`, a universe, and the per-instrument pipeline builder for that date — identical in shape to what the live scanner consumes) through the **existing** operational components: the M4.2 `DailyMarketScanner`, M4.3 `WatchlistManager`, and M4.4 `StrategyFramework` (which in turn run the M4.1 `WorkflowEngine` and the analytical core). It **orchestrates only** — it introduces no alternate analytical logic, computes no market values, and replays the same deterministic pipeline used live; the analytical core stays the single source of truth. Out-of-scope items (portfolio valuation, P&L, sizing, brokerage/slippage/cost simulation, order execution) are deliberately absent.

Each replay point produces an immutable `BacktestStep` referencing the artifacts the real pipeline emitted — scan id, watchlist snapshot id, strategy execution id, replay date, and execution timestamp — and retaining the full `DailyScanReport`, `WatchlistSnapshot`, and `StrategyExecution` for complete history preservation. Watchlist state **threads forward** chronologically (per `carry_watchlist` config) so trend-based watchlists and strategies observe prior scans exactly as they would live. Steps run in strict chronological order (sorted by `as_of`; duplicate timestamps fail loudly). **Failure isolation**: any step whose scan/apply/execute raises is recorded `FAILED` with a diagnostic note; with `continue_on_error` the replay proceeds (and a failed step does not advance carried state), otherwise it stops. Results aggregate into a `BacktestRun` (run identity + period + `BacktestSession`) carrying a `BacktestSummary` with sum-checked step counts and per-strategy `StrategyPerformance` (total matches, steps with matches, distinct instruments) across the whole period. Determinism verified: with `as_of` injected and no clock read, the same dataset yields an identical `to_dict()` on rerun (internal per-stage timings are excluded from serialization).

Files created: `src/athena/backtest/{__init__,models,engine}.py`, `config/backtest.json`, `tests/runtime/test_backtest.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `BacktestConfig`, `load_backtest_config`, exports). No analytical engine, scanner, watchlist manager, strategy framework, workflow engine, or frozen-domain type touched. Public APIs added: `BacktestingEngine`, `ReplayPoint`, `BacktestStep`, `BacktestSession`, `BacktestRun`, `BacktestSummary`, `StrategyPerformance`, `BacktestConfig`, `load_backtest_config`. 19 new tests: chronological ordering (incl. out-of-order input), all-steps-completed, step references, watchlist carry-forward (and disabled), multi-strategy performance aggregation, partial-failure isolation, stop-on-error, failed-step-doesn't-advance-state, deterministic rerun, empty dataset, immutable run, duplicate-replay-point rejection, history preservation, config validation (defaults, unknown-key rejection, production config loads, missing fails loudly), and a three-day **end-to-end replay** through the real workflow → scanner → watchlist → strategy chain. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; workflow engine, scanner, watchlist manager, strategy framework, and analytical engines all unchanged.

### M4.4 — Strategy Framework

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic framework for multiple strategies to select completed decision artifacts by policy, without any analytical calculation |
| Tests | 440 passed / 0 failed (19 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Strategy Framework (`src/athena/strategy/`), which answers one question: "Which completed ATHENA decisions satisfy each strategy's deterministic selection policy?" `StrategyFramework.execute(scan_report, watchlist, *, as_of)` runs every registered strategy over the immutable outputs of the M4.2 scanner (`DailyScanReport` → `DecisionReport`) and M4.3 watchlist manager (`WatchlistSnapshot`), producing an immutable `StrategyExecution`. It **coordinates strategy evaluation only** — it parses completed decision artifacts into read-only views, invokes each strategy, and aggregates; it never invokes an analytical engine, computes an indicator, or reinterprets a decision. Strategies express *selection*, not intelligence.

The `Strategy` contract (`base.py`) is a small ABC declaring `name`, `version`, `description`, and a pure `select(views) -> tuple[MatchProposal, ...]`. Each strategy sees only `InstrumentView`s — a pre-parsed, read-only lens bundling one instrument's completed decision facts (type, direction, and the score/confidence/risk values *already produced* by the core, read as-is, UNKNOWN preserved as `None`) with its current watchlist memberships. Five reference strategies (Momentum, Swing, Breakout, Mean Reversion, Sector Rotation) share a `ConfigurableStrategy` base that applies declarative `StrategyRuleCfg` filters (decision set, direction, watchlist overlap, min score, min confidence, max risk). A threshold set against an UNKNOWN value never matches — missing analytical values exclude an instrument rather than being defaulted (no fabrication). Multiple strategies may select the same instrument; overlaps are surfaced in the summary.

Determinism: instruments are viewed in stable sorted order, strategies run in registration order (and `from_config` registers enabled reference strategies in id-sorted order), and matches are ordered by instrument — with `as_of` injected and no clock read, identical inputs yield an identical `StrategyExecution` (verified via `to_dict` replay equality). Each `StrategyMatch` records the instrument, originating decision id, originating watchlist memberships, a strategy-specific explanation, and supporting references (decision id, scan id, watchlist snapshot id, and the score/confidence/risk refs lifted faithfully from the decision report). Duplicate strategy registration and unknown reference-strategy ids fail loudly; failed/skipped scan results are ignored.

Files created: `src/athena/strategy/{__init__,models,base,strategies,framework}.py`, `config/strategy.json`, `tests/runtime/test_strategy.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `StrategyConfig` + `StrategyRuleCfg`, `load_strategy_config`, exports). No analytical engine, scanner, watchlist manager, workflow engine, or frozen-domain type touched. Public APIs added: `StrategyFramework`, `Strategy`, `InstrumentView`, `MatchProposal`, `StrategyMatch`, `StrategyResult`, `StrategySummary`, `StrategyExecution`, the five reference strategies + `ConfigurableStrategy` + `REFERENCE_STRATEGIES`, `StrategyConfig`, `load_strategy_config`. 19 new tests: multiple strategies, overlapping matches, no matches, UNKNOWN-value exclusion, failed-results ignored, explanation + references preservation, registration, duplicate-registration rejection, `from_config` enabled-only + unknown-id rejection, deterministic replay, immutable output, empty universe, config validation (unknown decision, unknown direction, empty strategies, production config loads, missing config fails loudly), and a **real chain** consuming a scanner-produced `DailyScanReport` and a watchlist-manager-produced `WatchlistSnapshot`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; scanner, watchlist manager, workflow engine, and analytical engines all unchanged.

### M4.3 — Watchlist Manager

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Maintain deterministic, explainable named watchlists derived exclusively from completed scan/decision artifacts |
| Tests | 421 passed / 0 failed (21 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Watchlist Manager (`src/athena/watchlist/`), which answers one question: "Which instruments deserve ongoing attention based on ATHENA's completed decisions?" `WatchlistManager.apply(scan_report, *, as_of, previous=None)` folds an immutable `DailyScanReport` (M4.2) into a new immutable `WatchlistSnapshot`. It **coordinates state only** — it never executes an analytical engine, never recalculates a decision, and never invents a conclusion; it reads only the completed decision outcomes already produced by the pipeline and scanner, and organises them into named watchlists.

Classification is entirely **configuration-driven** (`config/watchlist.json`, validated by `WatchlistConfig`). Two rule kinds cover the initial five watchlists: a `decision_in` rule (membership when the instrument's current decision type is in a configured set — **High Conviction** ← TRADE/INCREASE_POSITION, **Watch** ← WATCH/WAIT, **Rejected** ← NO_TRADE/AVOID_SECTOR) and a `trend` rule (membership by change in decision *strength* versus the previous scan, using a configurable `decision_rank` map — **Improving** when the rank rose, **Weakening** when it fell). An instrument may belong to several watchlists at once (e.g. both High Conviction and Improving).

`apply` is a **pure function** of `(config, previous, scan_report, as_of)`: no hidden state, no clock read (`as_of` injected), instruments processed in stable sorted order — so replaying the same scan sequence yields bit-identical snapshots (verified). Every membership change is recorded as an explained `WatchlistChange` (ADDED / RETAINED / REMOVED) stating *why the instrument entered, why it remained, or why it exited* (rule no longer satisfied, or absent from the current scan). `entered_as_of` is preserved across retentions so an entry's original entry time is never lost. `WatchlistHistory` is **append-only** — `record()` returns a new, extended history and never overwrites prior state. Failed/skipped scan results are ignored (only completed decisions classify); a scan report containing a duplicate instrument fails loudly.

Files created: `src/athena/watchlist/{__init__,models,manager}.py`, `config/watchlist.json`, `tests/runtime/test_watchlist.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `WatchlistConfig` + rule models, `load_watchlist_config`, exports). No analytical engine, scanner, workflow engine, or frozen-domain type touched. Public APIs added: `WatchlistManager`, `WatchlistSnapshot`, `WatchlistEntry`, `WatchlistChange`, `WatchlistChangeType`, `WatchlistHistory`, `WatchlistSummary`, `WatchlistConfig`, `load_watchlist_config`. 21 new tests: decision-in classification, multi-watchlist membership, additions/retention/removal (rule-lapse and absence), improving/weakening trends, no-trend-without-prior, append-only history + entry/exit explanation, deterministic replay, immutable snapshots, empty scan (and empty-scan removals), duplicate-instrument protection, failed/skipped results ignored, config validation (duplicate names, unknown decision, production config loads, missing config fails loudly), and a **real DailyScanReport** produced by the M4.2 scanner classified across two cycles. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; scanner, workflow engine, and analytical engines all unchanged.

### M4.2 — Daily Market Scanner

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Coordinate ATHENA's full analytical workflow across the approved universe into one immutable daily scan report |
| Tests | 400 passed / 0 failed (10 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Daily Market Scanner (`src/athena/scanner/`), which answers a single question: "What does ATHENA conclude today for every eligible instrument?" `DailyMarketScanner.scan(universe, *, as_of, pipeline_builder)` iterates the universe in **stable sorted order** (`sorted(set(universe))` — deterministic, deduplicated), asks the caller-supplied `pipeline_builder` for a per-instrument `InstrumentPlan`, executes that plan's `WorkflowDefinition` through the shared `WorkflowEngine`, and — after the workflow completes — reads the captured `ScanCapture` and renders a `DecisionReport` via the existing `DecisionReportingEngine`. It **coordinates only**: it reuses M4.1's engine and M3.7's reporting engine, invokes analytical engines exclusively inside workflow stages defined by the caller, and recalculates nothing.

The design challenge was that M4.1's `WorkflowExecution` (frozen, approved) does not surface the `DecisionOutcome`. Rather than modify the approved engine (which would need an ADR), the scanner uses a **capture pattern**: `InstrumentPlan` pairs the workflow definition with a `collect()` callable; workflow stages populate a closure, and the scanner calls `collect()` after `execute()` to retrieve the outcome. No M4.1 change, no frozen-domain change.

**Failure isolation** is total — every per-instrument step (build, execute, collect, report) is wrapped so one instrument's failure produces a `FAILED` result with a diagnostic note and never aborts the scan; a builder returning `None` yields `SKIPPED`. Results aggregate into an immutable `DailyScanReport` with `ScanStatistics` (sum-checked total/successful/failed/skipped) and a `ScanSummary` (decision-type distribution, frozen via `MappingProxyType`), plus `result_for()` lookup and a JSON-safe `to_dict()`. Determinism verified: two scanners under fixed clocks produce bit-identical `to_dict()`.

Files created: `src/athena/scanner/{__init__,models,scanner.py}`, `tests/runtime/test_scanner.py`. Files modified: none (pure addition; no engine or contract touched). Public APIs added: `DailyMarketScanner`, `DailyScanReport`, `InstrumentPlan`, `InstrumentScanResult`, `ScanCapture`, `ScanStatistics`, `ScanSummary`, `PipelineBuilder`. 10 new tests: multi-instrument scan, deterministic ordering, empty universe, partial-failure isolation, skipped instrument, failed result carries no report, replay determinism, immutability, `to_dict` shape, and a **real multi-instrument pipeline** wiring indicator → regime → scoring → decision engines through workflows. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed.

### M4.1 — Workflow Orchestration Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic central orchestrator that runs analytical engines as coordinated pipeline stages |
| Tests | 390 passed / 0 failed (17 new) |
| Status | **APPROVED** — orchestration foundation for Phase 4 |
| Branch | main |

Built the runtime orchestration layer (`src/athena/runtime/`, realizing the blueprint's reserved §2 `runtime` module — building the plan, not a new module). `WorkflowEngine` executes a `WorkflowDefinition` (a validated DAG of `WorkflowStage`s) in a deterministic topological order, passing a read-only `WorkflowContext` accumulator through the stages; each stage's callable invokes an existing analytical engine and returns named outputs the engine merges (collisions rejected). It **coordinates only** — performs no analysis, duplicates no engine logic, modifies no engine. Dependency validation rejects missing dependencies, cycles, and duplicate stage names up front (`WorkflowError`). Failure isolation: a failed stage is recorded with its error and its downstream dependents are SKIPPED, while independent branches still run. Timing is captured per stage (offset + duration) via an **injected clock**, so under a fixed clock an execution is bit-identical — replay determinism verified. Produces an immutable `WorkflowExecution` (the execution report) plus a presentation-only `WorkflowReport` (`to_dict`/`to_json`/`to_text`). Verified end-to-end by wiring the real indicator → regime → scoring → decision engines as stages — the orchestrator ran the full pipeline without duplicating any engine.

Runtime types live in `src/athena/runtime/` — the blueprint's planned orchestration module — no ADR, no frozen-domain change, no analytical engine touched. Files created: `src/athena/runtime/{__init__,models,workflow,report}.py`, `tests/runtime/test_workflow.py`. Files modified: `src/athena/errors.py` (+WorkflowError). Public APIs added: `WorkflowEngine`, `WorkflowDefinition`, `WorkflowStage`, `WorkflowContext`, `WorkflowExecution`, `WorkflowReport`, `StageResult`, `ExecutionStatus`, `build_definition`. ruff clean; no drift; no tech debt.

---

## Phase 3 — Decision Intelligence (COMPLETE — pending formal review)

### M3.7 — Decision Trace & Reporting  (completes Phase 3)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Presentation-only human- and machine-readable decision reports from immutable artifacts |
| Tests | 373 passed / 0 failed (11 new) |
| Status | **Awaiting owner approval** — closes Phase 3; Phase 4 blocked pending full Phase-3 review |
| Branch | main |

Built `DecisionReportingEngine` (`src/athena/reporting/`), completing Phase 3. It consumes a `DecisionOutcome` plus the source artifacts (scoring, confidence, risk, evidence bundle, indicators) and produces an immutable `DecisionReport` offering two views derived from the same source: `to_dict()`/`to_json()` (machine-readable, JSON-safe, sorted-key deterministic) and `to_text()` (human-readable, sectioned). The report faithfully mirrors the decision — decision summary/outcome/status/direction, trade-plan summary, all six gate results, score summary with component breakdown, confidence dimensions, risk dimensions, evidence summary (provenance + missing sources), indicator summary, full reasoning-stage trace, and referenced artifact ids. Presentation only: it never modifies, reinterprets, or recalculates any artifact, and adds no new conclusions. UNKNOWN is displayed explicitly for every absent artifact (verified on the INSUFFICIENT_DATA path). Pure and deterministic: no I/O, clock, or randomness; both views reproducible.

Report types live in `src/athena/reporting/` (not frozen domain §4) — no ADR. Files created: `src/athena/reporting/{__init__,models,engine}.py`, `tests/decision/test_reporting.py`. No config needed. Public APIs added: `DecisionReportingEngine.report`, `DecisionReport` (`to_dict`, `to_json`, `to_text`). Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 3 — Decision Intelligence: COMPLETE (pending formal review)

All seven milestones implemented and individually reviewed: M3.1 Evidence Aggregation, M3.2 Indicator Engine, M3.3 Scoring, M3.4 Confidence, M3.5 Risk, M3.6 Decision, M3.7 Reporting. ATHENA now runs a complete, end-to-end, evidence-first decision pipeline: canonical data → market intelligence → aggregated evidence → objective indicators → transparent scores → confidence → risk → gated, auditable decisions → faithful human/machine reports. Every decision is deterministic, replayable, and traceable back to explicit evidence, measurements, and configuration; the frozen-domain TRADE invariant is enforced at construction. 373 tests, ruff-clean, zero technical debt. Ready for full Phase-3 review before Phase 4 is authorized.

---

### M3.6 — Decision Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | First deterministic, auditable decisions combining scores + confidence + risk via config-driven gates |
| Tests | 362 passed / 0 failed (12 new) |
| Status | **Awaiting owner approval** — M3.7 (Decision Trace & Reporting) blocked until approved |
| Branch | main |

Built `DecisionEngine` (`src/athena/decision/`), the capstone that combines the analytical pipeline into the first explainable decisions. It consumes approved artifacts only (ScoringResult, ConfidenceAssessment, RiskAssessment, EvidenceBundle, RegimeResult, indicators, optional market/sector health) and produces the **frozen-domain** `Decision` + `DecisionTrace` wrapped in a `DecisionOutcome`. It evaluates all six §8.5 quality gates (DATA, EVIDENCE, RISK, EXPLAINABILITY, CONFIDENCE, MARKET) as `GateResult`s, then applies config-driven policy: TRADE (all gates pass + composite ≥ trade threshold + directional regime + buildable plan), WATCH (composite in watch band), NO_TRADE (below watch), or INSUFFICIENT_DATA (no composite). Every frozen invariant is honored — a TRADE always carries a `TradePlan`, a direction, and zero failed gates (verified end-to-end: a strong-bull pipeline yields TRADE with all six gates green). Trade plans use analytical levels only (last close ± ATR multiples for stop/target, constant risk-reward); `position_size` is a provisional unit — **no capital-based sizing** (deferred to the capital layer). The `DecisionTrace` records the full reasoning path (regime → market/sector health → evidence → score → confidence → risk → decision → trade_plan) with references. Pure and replayable: injected `as_of`, Decimal math, thresholds from `decision.json`; consumes approved artifacts, never recalculates lower layers or touches providers/repositories.

Engine + `DecisionOutcome` live in `src/athena/decision/` (the frozen `Decision`/`DecisionTrace` come from `athena.domain.decision` — no §4 change) — no ADR. Files created: `src/athena/decision/{__init__,models,engine}.py`, `config/decision.json`, `tests/decision/test_decision.py`. Files modified: `config/models.py` (+DecisionConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_decision_config). Public APIs added: `DecisionEngine.decide`, `DecisionOutcome`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.5 — Risk Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic descriptive exposure assessment across six independent risk dimensions |
| Tests | 350 passed / 0 failed (16 new) |
| Status | **Awaiting owner approval** — M3.6 (Decision Engine) blocked until approved |
| Branch | main |

Built `RiskEngine` (`src/athena/risk/`). It consumes approved artifacts only and produces an immutable `RiskAssessment` of six independently explainable dimensions (higher value = more risk), each degrading to explicit `UNKNOWN`: volatility risk (regime volatility label), liquidity risk (Volume MA vs configured minimum), gap risk (regime gap label), event risk (CalendarContext expiries/scheduled events), market-environment risk (market-health labels mapped to risk points, averaged), and a concentration indicator (investable-universe breadth). Each dimension carries `RiskContribution` traces and a LOW/MEDIUM/HIGH level; the overall risk is a config-weighted mean over known dimensions with a `completeness` ratio and `unknown_stats`. Risk measures exposure only — independent of opportunity, and never a recommendation or position size. Missing artifacts produce transparent UNKNOWN; nothing is fabricated. Pure and replayable: injected `as_of`, Decimal math, all point maps from `risk_assessment.json` (a new file, kept separate from the F-4 no-trade rules in `risk.json`). Consumes approved artifacts, never providers/repositories.

Result types in `src/athena/risk/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/risk/{__init__,models,engine}.py`, `config/risk_assessment.json`, `tests/decision/test_risk.py`. Files modified: `config/models.py` (+RiskAssessmentConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_risk_assessment_config). Public APIs added: `RiskEngine.assess`, `RiskAssessment`, `RiskDimension`, `RiskContribution`, `RiskLevel`, `RiskStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.4 — Confidence Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic evaluation-reliability assessment across six independent confidence dimensions |
| Tests | 334 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — M3.5 (Risk Engine) blocked until approved |
| Branch | main |

Built `ConfidenceEngine` (`src/athena/confidence/`). It consumes approved artifacts only — EvidenceBundle, ScoringResult, IndicatorResults — and produces an immutable `ConfidenceAssessment` of six independently explainable dimensions, each degrading to explicit `UNKNOWN`: evidence completeness (present vs required sources), data freshness (validation reports passed vs total), indicator availability (OK vs total), cross-engine agreement (dispersion of known component scores), unknown ratio (share of known artifacts), and consistency (absence of contradictory signals among known scores, config divergence gap). Each dimension carries `ConfidenceContribution` traces and a LOW/MEDIUM/HIGH level; the overall confidence is a config-weighted mean over known dimensions with a `completeness` ratio and `unknown_stats`. Confidence measures evaluation reliability only — never market direction, attractiveness, or risk. Missing artifacts transparently reduce confidence; nothing is fabricated or inferred. Pure and replayable: injected `as_of`, Decimal math, thresholds/weights from `confidence.json`; consumes approved artifacts, never providers/repositories.

Result types in `src/athena/confidence/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/confidence/{__init__,models,engine}.py`, `config/confidence.json`, `tests/decision/test_confidence.py`. Files modified: `config/models.py` (+ConfidenceConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_confidence_config). Public APIs added: `ConfidenceEngine.assess`, `ConfidenceAssessment`, `ConfidenceDimension`, `ConfidenceContribution`, `ConfidenceLevel`, `ConfidenceStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.3 — Scoring Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Transparent, config-driven component + composite scores from approved evidence and indicators |
| Tests | 317 passed / 0 failed (18 new) |
| Status | **Awaiting owner approval** — M3.4 (Confidence Engine) blocked until approved |
| Branch | main |

Built `ScoringEngine` (`src/athena/scoring/`). It consumes approved artifacts only — regime, market-health, sector-health assessments and `IndicatorResult`s — and produces six independent `ComponentScore`s (trend, momentum, market quality, sector quality, liquidity, technical structure), each 0–100 with a full `Contribution` trace referencing the exact regime/health dimension, indicator, and configured point value behind it, plus a plain-language explanation. A `CompositeScore` weights the known components (config weights sum to 100) and retains a complete `CompositeBreakdownItem` breakdown including each component's weight, value, and weighted contribution, with a `completeness` ratio. UNKNOWN propagation is strict: any missing evidence/indicator yields an explicit UNKNOWN component (no value, no fabricated default), unscoreable dimensions are excluded from averages, and the composite is UNKNOWN only when nothing is scoreable. Scores are intermediate artifacts — no buy/sell/hold, sizing, risk, or portfolio logic. Pure and replayable: injected `as_of`, Decimal math, all point maps from `scoring.json`; consumes approved artifacts, never raw providers/repositories.

Result types in `src/athena/scoring/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/scoring/{__init__,models,engine}.py`, `config/scoring.json`, `tests/decision/test_scoring.py`. Files modified: `config/models.py` (+ScoringConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_scoring_config). Public APIs added: `ScoringEngine.score`, `ScoringResult`, `ComponentScore`, `CompositeScore`, `CompositeBreakdownItem`, `Contribution`, `ScoreStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.2 — Indicator Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic technical-indicator measurement layer over canonical candles |
| Tests | 299 passed / 0 failed (26 new) |
| Status | **Awaiting owner approval** — M3.3 (Scoring Engine) blocked until approved |
| Branch | main |

Built `IndicatorEngine` (`src/athena/indicators/`) computing SMA, EMA, RSI (Wilder), ATR (Wilder), MACD, ADX (Wilder), and Volume MA from canonical candle data. Parameters are configuration-driven (`indicators.json`, extended with sma/macd/adx/volume_ma); calculations are pure Decimal functions in `calculations.py`; each result is an immutable `IndicatorResult` carrying name, status, parameters, window used, value(s), `IndicatorEvidence` (formula + inputs + explanation), and tz-aware ts. Insufficient history yields an explicit `UNKNOWN` result with no values (never a fabricated number). Strictly measurement-only — no signals, crossovers-as-events, composites, scoring, or interpretation; results never imply bullish/bearish/strength/weakness. Pure and replayable: injected `as_of`, deterministic Decimal math (fixed 28-digit context), candles sorted; provider/repository/intelligence-independent.

Result types in `src/athena/indicators/models.py` (measurement types, not frozen domain §4) — no ADR. Files created: `src/athena/indicators/{__init__,models,calculations,engine}.py`, `tests/decision/test_indicators.py`. Files modified: `config/indicators.json` (added sma/macd/adx/volume_ma params + versions; ema now single-period). Public APIs added: `IndicatorEngine.compute` / `compute_all`, `IndicatorName`, `IndicatorStatus`, `IndicatorResult`, `IndicatorEvidence`. Tests validate exact SMA/Volume-MA values, RSI boundaries (all-gains→100, all-losses→0, alternating≈50), ATR/MACD zero on flat/constant series, ADX range, Decimal precision, UNKNOWN handling, determinism, and immutability. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.1 — Evidence Aggregation Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Gather all approved intelligence into a single immutable, provenance-tagged evidence graph |
| Tests | 273 passed / 0 failed (10 new) |
| Status | **Awaiting owner approval** — M3.2 (Indicator Engine) blocked until approved |
| Branch | main |

Built `EvidenceAggregationEngine` (`src/athena/evidence/`), the first Decision Intelligence module. It gathers approved intelligence — regime, market health, sector health, universe, corporate-action evidence, and validation reports — into a single immutable `EvidenceBundle` of provenance-tagged `EvidenceItem`s. Each item records its `source`, `kind`, `reference_id`, timezone-aware `ts`, explanation, and the original (frozen) intelligence object as `payload` — so nothing is transformed or lost; provenance is preserved verbatim. The engine detects missing required sources (`required_sources` → `missing_sources`, `is_complete`) and publishes a per-source provenance count. Aggregation only — no scoring, signals, decisions, or transformation. Pure and replayable: injected `as_of`, deterministic fixed source ordering (sectors sorted), no I/O/clock/randomness; `EvidenceBundle` exposes `by_source`, `has_source`, `present_sources`.

Result types in `src/athena/evidence/models.py` (decision-intelligence types, not frozen domain §4) — no ADR. Files created: `src/athena/evidence/{__init__,models,engine}.py`, `tests/decision/test_evidence_aggregation.py`. Public APIs added: `EvidenceAggregationEngine.aggregate`, `EvidenceBundle`, `EvidenceItem`, `EvidenceSource`. All prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 2 — Market Intelligence (COMPLETE — pending formal review)

### M2.4 — Universe Engine  (completes Phase 2)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic investable-universe construction via config-driven eligibility rules + constituent-breadth export |
| Tests | 263 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — closes Phase 2; Phase 3 blocked pending full Phase-2 review |
| Branch | main |

Built `UniverseEngine` (`src/athena/universe/`). It evaluates each instrument independently against configuration-driven eligibility rules — active status, supported series, eligible exchange, data present, minimum trading history, minimum liquidity, and (when a calendar + window are supplied) data completeness — producing an immutable per-instrument `UniverseAssessment` (inclusion status, exclusion reasons, per-rule `RuleEvidence`, eligibility summary) and the frozen-domain `Universe` of included members (each with a full inclusion trace). Missing datasets produce explicit evidence, never silent exclusion. It also publishes **constituent advances/declines per sector** as a canonical output (`constituent_breadth`), completing the data dependency anticipated by Sector Health (M2.3) — computed from included instruments' latest vs prior close, and never by calling the Sector Health Engine. `max_universe_size` is advisory only (a hard cap would require ranking, which is out of scope) — all eligible instruments are included and the cap is surfaced in the summary. Pure and replayable (injected `as_of`, Decimal math, thresholds from `universe.json`); eligibility-focused, no ranking/scoring/selection.

Result types in `src/athena/universe/models.py` + `UniverseResult` in engine (not frozen domain §4; the canonical included set uses the frozen `Universe`/`UniverseMember`) — no ADR. Files created: `src/athena/universe/{__init__,models,engine}.py`, `tests/market_intel/test_universe.py`. Files modified: `config/models.py` (UniverseConfig +eligibility fields), `config/universe.json`. Public APIs added: `UniverseEngine.build`, `UniverseResult`, `UniverseAssessment`, `RuleEvidence`. Regime, Market Health, Sector Health, and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 2 — Market Intelligence: COMPLETE (pending formal review)

All four milestones implemented and individually reviewed: M2.1 Regime Engine, M2.2 Market Health, M2.3 Sector Health, M2.4 Universe Engine. The Market Intelligence layer now describes market conditions (regime, market health), sector conditions (sector health), and constructs a trustworthy investable universe — all deterministic, explainable, replayable, and strictly descriptive/eligibility-focused (no scoring, ranking, or decisions). Engines consume canonical data + approved intelligence and are aware-but-not-dependent on one another. 263 tests, ruff-clean, zero technical debt. Ready for full Phase-2 review before Phase 3 (Decision Intelligence) is authorized.

---

### M2.3 — Sector Health Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Descriptive per-sector condition across four independently explainable dimensions |
| Tests | 246 passed / 0 failed (23 new) |
| Status | **Awaiting owner approval** — M2.4 (Universe Engine) blocked until approved |
| Branch | main |

Built `SectorHealthEngine` (`src/athena/sector_health/`). Per sector it consumes canonical sector-index `Candle` history (plus optional constituent breadth) and produces an immutable `SectorHealthAssessment` of four independently explainable dimensions, each degrading to explicit `*_UNKNOWN`: **trend** (fast/slow SMA → UPTREND/DOWNTREND/SIDEWAYS), **breadth** (constituent participation — reported `SECTOR_BREADTH_UNKNOWN` unless constituent advances/declines are supplied; never inferred, since constituent data arrives with M2.4), **momentum** (period ROC), and **volatility** (realized volatility = stdev of returns, a sector-specific context that complements — not duplicates — Market Health). `assess_many` evaluates multiple sectors deterministically. Every dimension emits `SectorHealthEvidence` with inputs, thresholds, outcome, and explanation. Pure and replayable (injected `as_of`, Decimal math incl. `Decimal.sqrt`, thresholds from `sector_health.json`); descriptive only — no ranking, rotation, selection, or signals. Regime-aware and Market-Health-aware but dependent on neither (optional, explanation-only).

Result types in `src/athena/sector_health/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/sector_health/{__init__,models,engine}.py`, `config/sector_health.json`, `tests/market_intel/test_sector_health.py`. Files modified: `config/models.py` (+SectorHealthConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_sector_health_config). Public APIs added: `SectorHealthEngine.assess` / `assess_many`, `SectorHealthResult`, `SectorHealthAssessment`, `SectorHealthEvidence`, `SectorHealthLabel`, `SectorHealthConfig`, `load_sector_health_config`. Regime, Market Health, and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M2.2 — Market Health Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Descriptive assessment of overall market condition across four independently explainable dimensions |
| Tests | 223 passed / 0 failed (24 new) |
| Status | **Awaiting owner approval** — M2.3 (Sector Health) blocked until approved |
| Branch | main |

Built `MarketHealthEngine` (`src/athena/market_health/`). It consumes canonical `Candle` history + optional `MarketSnapshot`, and produces an immutable `MarketHealthAssessment` composed of four independently explainable dimensions, each always labelled (explicit `*_UNKNOWN` on insufficient data): **breadth** (advance ratio from snapshot advances/declines), **trend quality** (one-directional consistency of recent index returns — complements the Regime Engine's direction, does not replace it), **momentum** (period rate-of-change of the index), and **volatility** (contextual read of India VIX on market stability, framed as health not re-classification). Every dimension emits `HealthEvidence` carrying inputs, the thresholds that produced the label (owner suggestion #3), the outcome, and a human explanation. Pure and replayable (injected `as_of`, Decimal math, thresholds from `market_health.json`); descriptive only — no scores, rankings, or recommendations. Regime-aware but not regime-dependent: an optional `RegimeResult` enriches the trend-quality explanation only; labels are identical with or without it (verified by test).

Result types live in `src/athena/market_health/models.py` (market-intelligence types, not frozen domain §4) — no ADR. Files created: `src/athena/market_health/{__init__,models,engine}.py`, `config/market_health.json`, `tests/market_intel/test_market_health.py`. Files modified: `config/models.py` (+MarketHealthConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_market_health_config). Public APIs added: `MarketHealthEngine.assess`, `MarketHealthResult`, `MarketHealthAssessment`, `HealthEvidence`, `MarketHealthLabel`, `MarketHealthConfig`, `load_market_health_config`. Regime Engine and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M2.1 — Regime Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic market-regime classification from canonical market data; descriptive, not prescriptive |
| Tests | 199 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — M2.2 (Market Health) blocked until approved |
| Branch | main |

Built `RegimeEngine` (`src/athena/regime/`), the first Market Intelligence module. It consumes canonical `Candle` history (an index) plus an optional `MarketSnapshot` (India VIX) and produces the frozen-domain `RegimeAssessment` plus a supporting `RegimeEvidence` chain. Three orthogonal, deterministic dimensions, each always labelled (explicit `*_UNKNOWN` when data is insufficient — never a silent omission): **trend** (BULL/BEAR/SIDEWAYS via fast-vs-slow SMA and last close), **volatility** (HIGH/LOW/NORMAL via India VIX against configured bands), and **gap** (UP/DOWN/NONE via latest open vs prior close against the gap threshold). Pure and replayable: no I/O, no clock reads (time injected as `as_of`), no randomness; Decimal math throughout; thresholds from the existing `regime.json`. Output is strictly descriptive — labels, evidence, and explanation only; no scoring, ranking, or recommendation.

Regime result types live in `src/athena/regime/models.py` (market-intelligence types, not additions to frozen domain §4, which already provides `RegimeAssessment`) — no ADR required. Files created: `src/athena/regime/{__init__,models,engine}.py`, `tests/market_intel/test_regime.py`. Public APIs added: `RegimeEngine.assess`, `RegimeResult`, `RegimeEvidence`, `RegimeLabel`. Validation checklist passed; frozen contracts unchanged; ruff clean; no drift; no tech debt.

---

## Phase 1 — Data Foundation: COMPLETE ✅ (approved 2026-07-20)

All six milestones implemented and individually reviewed: M1.1 provider contracts, M1.2 FileProvider, M1.3 validation layer, M1.4 corporate actions, M1.5 SQLite repository, M1.6 backup & restore. The data foundation now ingests (via an abstract, order-incapable provider), validates, historically adjusts, persists, and recovers canonical market data — deterministically, explainably, and replayably. 182 tests, ruff-clean. **Phase 1 approved; Phase 2 (Market Intelligence) authorized.**

---

### M1.5 — SQLite Repository

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Persistent storage layer: schema, repository, WAL/FK config, integrity verification, quarantine + corporate-action persistence |
| Tests | 171 passed / 0 failed (23 new) |
| Status | **Awaiting owner approval** — M1.6 (backup & restore) blocked until approved |
| Branch | main |

Built `SqliteRepository`, ATHENA's persistent ledger. Deterministic schema (ATHENA-002 §5) with a single `candles` table keyed by (instrument_id, timeframe, ts_open) serving both daily and intraday, plus `instruments`, `quotes`, `market_snapshots`, `corporate_actions`, `quarantine_records`, and a `schema_version` table for future migrations. Explicit primary keys, foreign keys, and a range index; all decimals/timestamps stored as TEXT (ISO-8601, tz-aware) to preserve exact precision. SQLite configured with WAL mode and enforced foreign keys per connection; writes wrapped in transactions with a public `transaction()` context manager (commit on success, rollback on exception). Repository returns canonical domain objects, never rows — no provider, validation, or intelligence logic lives here. Append-only history (duplicate primary keys rejected as `RepositoryError`); instruments and quarantine support idempotent upsert. `verify_integrity()` runs `PRAGMA integrity_check` + `PRAGMA foreign_key_check` + schema-version check and returns an immutable `IntegrityReport`; corrupt/non-SQLite files fail loudly. Quarantine persistence serializes/restores `QuarantineRecord`s with full validation evidence, timestamps, types, severities, and explanations.

Storage types live in `src/athena/data/store/` — §5 schema is not among the §19-frozen items, and the milestone checklist confirms no ADR — so schema evolution is allowed within the data module. Files created: `src/athena/data/store/{__init__,schema,serialization,repository}.py`, `tests/data_layer/test_repository.py`. Files modified: `src/athena/errors.py` (+RepositoryError), `.gitignore` (WAL sidecars + db/). Public APIs added: `SqliteRepository` (initialize, upsert_instrument, get_instrument, list_instruments, add_candles, get_candles, add_quotes, get_quotes, add_snapshot, get_latest_snapshot, add_corporate_action, get_corporate_actions, save_quarantine, get_quarantine, list_quarantine, verify_integrity, transaction, close), `IntegrityReport`, `SCHEMA_VERSION`. Validation checklist 1–10 passed; provider contract, Validation Layer, and Corporate Actions Engine untouched; no drift; no tech debt.

### M1.4 — Corporate Actions Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider/storage-independent modeling + deterministic back-adjustment for splits, bonuses, dividends, renames |
| Tests | 148 passed / 0 failed (19 new) |
| Status | **Awaiting owner approval** — M1.5 (SQLite repository) blocked until approved |
| Branch | main |

Built a Corporate Actions Engine that interprets the canonical (frozen) `CorporateAction` domain object into validated typed actions (`Split`, `Bonus`, `Dividend`, `Rename`) and applies deterministic back-adjustment to candle datasets, producing **adjusted copies** with full evidence — originals are never mutated (and `Candle` is frozen regardless). Standard model: an action with ex_date D adjusts only candles strictly before D; split from→to scales price by from/to and volume by to/from; bonus b:h scales price by h/(h+b); dividend scales price by (prev_close − amount)/prev_close using the raw close before D; factors are cumulative across sequential actions; renames map identifiers (with chain resolution A→B→C) and never touch candle values. Four explicit, traceable strategies (RAW, SPLIT_ADJUSTED, SPLIT_BONUS_ADJUSTED, FULLY_ADJUSTED) — no hidden behavior. Every adjustment emits immutable `AdjustmentEvidence` (action, ex_date, price/volume factor, affected record count, explanation, metadata); the whole run returns an immutable `AdjustmentResult`. Deterministic Decimal math (fixed context) and injected `as_of` make it fully replayable. Optional Calendar Engine only annotates whether an ex_date is a trading session — effective dates are never inferred. No fetching, no persistence, no provider/file/SQLite awareness.

Engine types live in `src/athena/data/corporate_actions/` — not additions to the frozen domain §4 — so no ADR was required. Files created: `src/athena/data/corporate_actions/{__init__,models,evidence,engine}.py`, `tests/data_layer/test_corporate_actions.py`. Files modified: `src/athena/errors.py` (+CorporateActionError). Public APIs added: `CorporateActionsEngine` (`adjust`, `build_symbol_map`, `resolve_symbol`), `parse_action`, `Split`/`Bonus`/`Dividend`/`Rename`, `CorporateActionType`, `AdjustmentStrategy`, `AdjustmentEvidence`, `AdjustmentResult`. Validation checklist 1–10 passed; provider contract and Validation Layer untouched; no drift; no tech debt.

### M1.3 — Validation Layer

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider-independent data-quality framework: freshness, OHLC, duplicate, gap validation; immutable reports; quarantine |
| Tests | 129 passed / 0 failed (25 new) |
| Status | **Awaiting owner approval** — M1.4 (corporate actions) blocked until approved |
| Branch | main |

Built a reusable validation framework that operates exclusively on canonical `Candle` objects and the Phase-0 Calendar Engine — no file/SQLite/broker/provider awareness. Validators are pure functions with an injected `as_of` (no clock reads → deterministic and replayable). Freshness compares daily data against the calendar's expected latest trading day and intraday data against the reference time, with configurable thresholds. OHLC validation checks the one business rule the Candle contract does NOT guarantee — strictly positive prices — and explicitly does not re-check H/L ordering (structurally enforced by the domain object) to avoid duplicating provider responsibility. Duplicate detection targets cross-dataset/ingestion-boundary duplicates (provider within-request dedup untouched). Gap detection uses the Calendar Engine for both missing trading sessions (weekends/holidays never counted) and missing intraday intervals; sessions are never inferred manually. Every check produces an immutable `ValidationReport` (type, result, severity, explanation, evidence, statistics, tz-aware timestamp); `DatasetValidator` aggregates into an immutable `ValidationSummary`; `QuarantineRegistry` records invalid datasets with preserved failure evidence and never auto-repairs.

Validation types live in `src/athena/data/validation/` — data-layer result types, NOT additions to the frozen canonical domain model (§4) — so no ADR was required. Files created: `src/athena/data/validation/{__init__,reports,validators,dataset_validator,quarantine,calendar_expectations}.py`, `config/validation.json`, `tests/data_layer/test_validation.py`. Files modified: `config/models.py` (+ValidationConfig/FreshnessConfig/GapConfig), `config/loader.py` + `config/__init__.py` (+load_validation_config). Public APIs added: `DatasetValidator`, `ValidationReport`, `ValidationSummary`, `ValidationType`, `ValidationResult`, `Severity`, `QuarantineRegistry`, `QuarantineRecord`, the five `validate_*` functions, `load_validation_config`, `ValidationConfig`. Validation checklist 1–10 passed; provider contract untouched; no drift; no tech debt.

### M1.2 — FileProvider

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | First production `MarketDataProvider`, backed by local CSV/JSON files; reference implementation for all future providers |
| Tests | 104 passed / 0 failed (37 new) |
| Status | **Awaiting owner approval** — M1.3 (validation layer) blocked until approved |
| Branch | main |

Implemented `FileProvider` conforming 100% to the frozen contract (passes the M1.1 suite unchanged). Loads daily candles, intraday candles, instrument metadata, market snapshots, and quotes from configurable file locations (`config/providers/file.json`, loaded via a new `load_file_provider_config` + `FileProviderConfig` model — `AthenaConfig` untouched, so config compatibility is preserved). Deterministic: no caching, no mutable global state, no clock reads, no concurrency; candles sorted ascending and deduplicated to honor the contract. Decimal precision and tz-aware timestamps preserved end to end. Error taxonomy differentiates missing files, invalid format (wrong header), unsupported instrument/timeframe/capability, and corrupted data (non-numeric values, impossible OHLC, naive timestamps, duplicate timestamps) — all `ProviderError` with file:line context. Validation is limited to what loading correctness requires; freshness/gap/cross-dataset validation deferred to M1.3 as instructed.

Files created: `src/athena/data/__init__.py`, `src/athena/data/providers/__init__.py`, `src/athena/data/providers/file_provider.py`, `config/providers/file.json`, two deterministic fixture datasets (`tests/data/fileprovider/` synthetic, `tests/data/fileprovider_sample/` sanitized-realistic with real symbols/ISINs but fictional prices), `tests/contract/test_file_provider_contract.py`, `tests/data_layer/test_file_provider.py`, dataset READMEs. Files modified: `config/models.py` (+FileProviderConfig, ProviderCapabilitiesConfig), `config/loader.py` + `config/__init__.py` (+loader). Public APIs added: `FileProvider`, `FileProvider.from_config_dir`, `load_file_provider_config`, `FileProviderConfig`. Validation checklist 1–10 passed; contract unchanged; no ADR; no drift; no tech debt.

### M1.1 — MarketDataProvider Contracts

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider Protocol behavioral contract, ProviderCapabilities/ProviderHealth invariants, reusable contract test suite |
| Tests | 67 passed / 0 failed (16 new) |
| Status | **Awaiting owner approval** — M1.2 (FileProvider) blocked until approved |
| Branch | main |

Frozen Protocol signatures untouched (contract compatibility preserved). Added: constructor invariants on `ProviderCapabilities` (non-empty unique timeframes, history ≥ 1 day) and `ProviderHealth` (mandatory detail, tz-aware timestamps); a documented behavioral contract on the Protocol (capability honesty, candle ordering/uniqueness/range, emptiness-is-not-error, determinism, unknown-id failures, structurally-forbidden order methods); `tests/contract/provider_contract.py` — the conformance suite every provider (M1.2 FileProvider, future broker adapters per DD-1) must pass unchanged, including a `test_no_order_methods_exist` structural-safety check; proven against a deterministic in-memory `StubProvider` (test infrastructure only, arithmetic data, no randomness/clock reads) plus negative tests showing the suite catches rogue order methods and invalid capabilities. Validation checklist 1–10 passed; no ADR needed; no config changes.

---

## Phase 0 — Foundations

| | |
|---|---|
| Completed | 2026-07-20 |
| Blueprint scope | ATHENA-002 §14, Phase 0 |
| Tests | 51 passed / 0 failed |
| Status | **APPROVED** (owner + principal engineer review passed, 2026-07-20) |
| Branch | main |
| Lessons learned | Phase-sized batches are too large to review well — milestone-based workflow adopted from Phase 1 (see CLAUDE.md, docs/MILESTONES.md) |

### 1. Summary of completed work

Project scaffolding (`pyproject.toml`, `justfile`, `.env.example`); complete canonical domain model; layered configuration framework with strategy profiles, feature flags, and cross-file invariants; JSONL logging with secret redaction and run/cycle correlation; observability skeleton (metric timers, performance-budget violations, system-health pre-flight); Trading Calendar Engine loaded with the real NSE 2026 holiday calendar (16 weekday holidays + Muhurat on 2026-11-08); CLI commands `athena today`, `athena health`, `athena version`.

### 2. Architectural compliance review

All Phase 0 exit criteria pass: CalendarContext correct for the 10 acceptance dates including Republic Day (holiday) and Muhurat (special session overriding a Sunday, timings honestly "TBD" until NSE notifies); config invariant violations fail with readable errors naming field and rule; full suite green. Contracts match the blueprint exactly: PipelineContext enforces consumes/produces discipline (re-producing a key raises, F-1/ADR-003); `MarketDataProvider` Protocol contains no order methods (ADR-002); explanations are constructor-mandatory — a TRADE decision without a TradePlan, without a direction, or with a failed quality gate cannot be instantiated (F-12, ADR-005); prices are Decimal; timestamps are timezone-aware; clocks are injected. No architectural deviations; no ADR was needed.

### 3. Files created

- `src/athena/domain/` — enums, market, evidence, decision, run, health, context, interfaces (8 files)
- `src/athena/config/` — models (pydantic), loader + snapshot hashing (2 files)
- `src/athena/observability/` — logging, metrics, health (3 files)
- `src/athena/calendar/engine.py`, `src/athena/cli.py`, `src/athena/errors.py`
- `config/` — base, market.nse, risk, capital, regime, universe, indicators, profiles/intraday-momentum, calendar/{holidays,expiries,events} (10 files)
- `tests/` — conftest + 5 test modules + golden-dataset skeleton README
- Scaffolding: `pyproject.toml`, `justfile`, `.env.example`

### 4. Tests added (51)

Calendar acceptance (10 parametrized dates, timings, trading-session semantics, budget event, fail-loud on uncovered year, determinism); config (11 cases: invariants, typo rejection, missing file, unknown profile, unversioned indicator, out-of-session trading window, snapshot hash determinism and change-sensitivity); domain invariants (immutability, impossible OHLC, naive timestamps, mandatory explanations, score-breakdown sum, decision contract, context discipline, read-only context data); observability (JSON-line shape, run/cycle correlation, secret redaction, budget violation detection, health pre-flight honest WARNs, calendar-coverage BLOCKED); CLI (5 commands/paths).

### 5. Remaining work

Phase 1 (Data): `MarketDataProvider` contract test suite, FileProvider (EOD bhavcopy + intraday files), validation layer (freshness, OHLC sanity, gaps, duplicates), corporate-actions handling, SQLite store with backup/restore. Owner actions before relying on calendar-aware features: verify `config/calendar/holidays.json` against the NSE circular and set `verified_by_owner: true`; populate `config/calendar/expiries.json` from the current derivatives circular (left empty by design — expiry weekdays change by circular and were not guessed).

### 6. Risks discovered

The AI sandbox cannot delete files, so `athena health` reports storage/logs BLOCKED when run there — the check is working as designed and passes on the owner's machine. The blueprint pins Python ≥ 3.12 but verification ran on 3.10; `pyproject.toml` currently declares ≥ 3.10 — tighten to 3.12 once the production interpreter is confirmed.

### 7. Suggested improvements (implementation-only)

A `just verify-calendar` target that diffs `holidays.json` against the NSE circular each January; a minimal GitHub Actions workflow (ruff + mypy + pytest) once the owner wants CI on pushes.
