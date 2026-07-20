# ATHENA-001 — Engineering Review of the Constitution

| | |
|---|---|
| Version | 1.0 |
| Reviews | ATHENA-000 v0.1 |
| Market context | Indian equities (NSE/BSE), single trader, local machine |
| Verdict | **APPROVED WITH AMENDMENTS** — 12 amendments listed in §3 |

This document records the review of ATHENA-000 by seven engineering roles, the disagreements between them, and one consolidated recommendation with documented trade-offs.

---

## 1. Role Reviews

### 1.1 Principal Software Architect

**What the constitution gets right.** The evidence-before-AI pipeline, explainability as a first-class requirement, config-over-hardcoding, and the explicit non-objectives are unusually disciplined for a personal project. The single-user constraint is the most valuable sentence in the document — it eliminates entire categories of complexity.

**Findings.**

- **A-1 (critical): 13 engines is over-decomposition.** "Independent engines" is service-oriented thinking applied to a single-user Python app. Thirteen independently replaceable engines means thirteen interfaces, thirteen test harnesses, and a dependency graph you'll maintain alone. The correct shape is a **modular monolith**: one process, one repo, engines as Python packages behind `Protocol` interfaces. Replaceability comes from interfaces and a shared domain model, not from process boundaries. Start with ~6 modules; let the remaining "engines" exist as submodules that graduate only when they earn independent complexity.
- **A-2 (critical): Explainability cannot be a terminal engine.** The data flow puts the Explainability Engine second-to-last. An engine at the end of a pipeline cannot reconstruct *why* upstream stages decided anything — it can only decorate. Explanation must be a **data structure carried through the pipeline**: every Evidence, Signal, and Decision object carries its own rationale (rule fired, values observed, config threshold used). The final "engine" is then just a renderer. This is an architectural invariant, not a module.
- **A-3 (high): The real coupling point is the domain model, not the engines.** The document specifies engine boundaries but not the canonical objects they exchange (Candle, Instrument, Evidence, Signal, Score, Decision, TradePlan). Nail these first; they are harder to change later than any engine.
- **A-4 (high): No orchestration story.** When do engines run? EOD batch? On-demand? The document implies a pipeline but never states the trigger model. Recommend: an idempotent, resumable **daily pipeline run** (fetch → validate → analyze → decide → publish), identified by run-ID, with every run producing an immutable audit record. Determinism requirement: re-running the same day with the same inputs must produce byte-identical decisions.
- **A-5 (medium): Missing storage architecture.** SQLite is named but no schema philosophy. Recommend: append-only tables for market data and decisions (never mutate history), config snapshots stored per run so every past decision can be re-explained under the config that produced it.

### 1.2 Senior Python Engineer

- **P-1 (high): Pandas AND Polars is one dependency too many.** Two dataframe libraries means two idioms, conversion overhead, and doubled test surface. For an EOD scan of a few hundred NSE symbols, pandas + NumPy is comfortably fast. Pick **pandas only**; add Polars later behind the data-access layer *only if* a measured scan exceeds the performance budget. Set that budget now (proposal: full watchlist scan < 60 s, dashboard generation < 5 s).
- **P-2 (high): Implement core indicators in-house.** TA-Lib is a C build headache; pandas-ta has maintenance risk. ATHENA needs perhaps 15–20 indicators, all with published formulas. Writing them in NumPy with golden-value unit tests directly serves Principles 1 and 6 — you can explain and trust every number. Verify each against a reference implementation once, in tests.
- **P-3 (medium): JSON config is under-powered for Principle 4.** JSON has no comments and no validation. Keep JSON if you must, but validate every file through **pydantic models** at startup — fail fast with a human-readable error on any invalid or contradictory config. (YAML/TOML would allow comments; see disagreement D-7.)
- **P-4 (medium): Defer FastAPI.** A "dashboard" that is a **generated static HTML file** needs no server, no ports, no auth, and works offline — it satisfies the UI philosophy for Phases 1–2. Introduce FastAPI only when interactivity (journal entry, config editing) demands it.
- **P-5 (low): Standards to adopt from day one.** Type hints everywhere, `mypy --strict` on core modules, dataclasses/pydantic for domain objects, structured logging (JSON lines) with run-ID correlation, `uv` for dependency locking.

### 1.3 Quantitative Research Engineer

- **Q-1 (critical): The time horizon is undefined.** Swing (days–weeks), positional (weeks–months), and intraday are different systems: different indicators, different risk rules, different data needs. Everything downstream — scoring weights, backtest design, "no-trade" logic — depends on this. **The constitution must pin the horizon.** (Assumed for this review: EOD-driven swing trading; intraday is out of scope for v1.)
- **Q-2 (critical): Additive scoring assumes factor independence — it isn't true.** Momentum, volume, and pattern evidence are correlated; an additive score double-counts the same underlying move and produces confident scores in exactly the regimes where all factors align and then reverse. Keep the additive model for v1 (it is the most explainable option) but treat weights as **hypotheses to be validated by walk-forward backtest**, never intuition, and log every score → outcome pair from the first day so calibration data accumulates before you need it.
- **Q-3 (critical): "Continuous learning" is an overfitting machine at retail sample sizes.** A single swing trader generates perhaps 100–300 closed trades a year. Auto-tuning weights on that sample chases noise. Amend Principle 7: the Learning engine **measures and proposes; the human approves**. Hard gates: no weight-change proposal below a minimum sample (e.g., 30 trades per factor bucket), and report confidence via calibration curves ("scores 80+ historically won 62% of the time, n=41"), not parametric confidence intervals, which would be false precision here.
- **Q-4 (high): Backtesting must be point-in-time or it will lie.** Indian-market specifics that will silently corrupt results: frequent splits/bonuses (prices must be back-adjusted), symbol renames, delistings (survivorship bias in any watchlist built today), and corporate-action-heavy indices. The data layer needs a corporate-actions table and point-in-time universe from Phase 1, even if backtesting itself comes later.
- **Q-5 (high): The Risk engine must encode NSE market structure.** Circuit limits (5/10/20% bands — a stock locked at lower circuit **cannot be exited**, which breaks naive stop-loss assumptions), the F&O ban list, lot sizes for derivatives, expiry-day behavior, and SEBI margin rules. These belong in config (they change) with the risk logic reading them. Position sizing must assume exits can gap or lock.
- **Q-6 (medium): Defer Options Intelligence.** Reliable NSE option-chain data effectively requires a broker API (e.g., Kite Connect); scraping the NSE site is fragile and against its terms. Shipping options analytics on unreliable data violates Principle 6. Defer to a late phase, gated on a proper data source.
- **Q-7 (medium): Define "no trade today" quantitatively.** Proposal: a market-regime gate combining index trend vs. its own moving averages, breadth (% of watchlist above 50-DMA), and India VIX bands — all thresholds in config, all decisions carrying the regime evidence that triggered them.

### 1.4 UI/UX Engineer

- **U-1 (high): One briefing page, not thirteen engine views.** The dashboard's eight questions are exactly right — answer them **in that order, on one page**: verdict banner first (TRADE / NO TRADE + one-line why), then top-N ranked opportunities as cards with expandable evidence, then capital/risk state, then "what next". Engine-per-tab dashboards die of neglect.
- **U-2 (high): Journal friction decides whether learning happens.** If logging a trade takes more than ~30 seconds, the journal — and therefore the entire Learning engine — starves. Pre-fill journal entries from the recommendation the trader acted on; outcome entry should be a couple of fields. This makes the journal an early, non-negotiable deliverable (Phase 3), not a nice-to-have.
- **U-3 (medium): Render score decomposition visually.** A stacked horizontal bar per stock (segment = factor contribution) communicates the 84 = 18+20+8+15+12+11 breakdown instantly. Show confidence as empirical history ("62% of 80+ scores were profitable, n=41"), never as an unexplained percentage.
- **U-4 (low): Lightweight Charts over Plotly for candlesticks** — smaller, faster, purpose-built; Plotly acceptable for analytics/performance charts. Both fit the static-HTML approach.

### 1.5 QA / Test Engineer

- **T-1 (critical): The mission has no measurable acceptance criterion.** "Higher quality decisions than a discretionary retail trader" cannot be tested. Define KPIs now: adherence rate (% of trades that followed the system), expectancy per trade, max drawdown vs. a baseline, calibration error. The baseline is the trader's own pre-ATHENA journal, or a simple index-following rule.
- **T-2 (critical): Stale data must fail loudly.** The most dangerous failure mode is a recommendation computed on yesterday's prices presented as today's. Every pipeline run must verify data freshness per symbol and refuse to emit decisions (surfacing "DATA INCOMPLETE — NO VERDICT") when validation fails. Silent degradation is forbidden.
- **T-3 (high): Golden-dataset regression tests.** Freeze a reference dataset (e.g., 50 symbols × 2 years, including a split, a bonus, a circuit-locked day, an F&O-ban entry, a symbol rename, and a Muhurat trading session). Every indicator, score, and decision has expected outputs against it; any diff must be an intentional, reviewed change.
- **T-4 (high): Determinism as a test.** Run the pipeline twice on identical inputs; assert byte-identical decisions and explanations. This catches hidden state, dict-ordering, and time-of-day dependencies.
- **T-5 (medium): Edge-case inventory for the NSE data layer.** Exchange holidays and half-days, missing candles, duplicate rows, zero-volume sessions, symbols moving between series (EQ/BE/T2T), IPO listings with short history, and API rate-limit/outage behavior (retry with backoff, then fail loudly per T-2).
- **T-6 (medium): Config contradiction tests.** Cross-field invariants validated at startup: per-trade risk ≤ daily loss limit ≤ max drawdown budget; position size cap ≤ max exposure; watchlist symbols exist in the instrument master.

### 1.6 DevOps / Platform Engineer

- **O-1 (high): Keep the platform boring.** One machine, one repo, `uv`-locked venv, a `justfile`/`Makefile` with `run-eod`, `dashboard`, `test`, `backup` targets. No Docker, no services, no cloud — Docker adds reproducibility ATHENA doesn't need at the cost of the simplicity it demands.
- **O-2 (high): Scheduling + idempotency.** EOD pipeline via cron/launchd after market close (with a buffer for the exchange to finalize EOD data). The pipeline must be **idempotent** (re-run safely overwrites nothing, appends a new run) and **resumable** (a failed fetch doesn't require redoing validation of what succeeded). On failure: local notification, and the dashboard clearly shows "last successful run: <date>".
- **O-3 (medium): Backups are part of risk management.** The SQLite file *is* the trade history and learning corpus. Nightly `sqlite3 .backup` copy with rotation; configs and code in git; the DB backup tested by actually restoring it in CI/test.
- **O-4 (low): SQLite settings.** WAL mode, single-writer discipline (only the pipeline writes; dashboard reads), `PRAGMA foreign_keys=ON`.

### 1.7 Security Reviewer

- **S-1 (critical): Broker credentials never touch JSON config or git.** Kite Connect (or any broker) API keys and daily access tokens go in `.env`/OS keychain, `.gitignore`d from day one, and scrubbed from logs. Note: broker API keys are often **trade-capable** — there is no read-only tier on some brokers. ATHENA must never wire any order-placement endpoint; enforce this with a client wrapper that simply does not implement order methods, making Non-Objective #1 structural rather than a promise.
- **S-2 (high): Localhost only.** If/when FastAPI arrives, bind `127.0.0.1` exclusively. No LAN exposure, no reverse proxies, no auth complexity needed as long as that holds.
- **S-3 (medium): Dependency hygiene.** The minimal-stack preference is also the security posture: few dependencies, pinned via lockfile, `pip-audit`/`uv audit` in the test target. In-house indicators (P-2) remove a whole class of supply-chain surface.
- **S-4 (low): Data sourcing legality.** Prefer official/broker APIs and NSE's published EOD files (bhavcopy) over scraping HTML endpoints, which violates NSE terms and breaks without notice — aligning with Q-6.

---

## 2. Disagreements and Resolutions

**D-1: Engine granularity.** *Constitution:* 13 independent engines. *Architect:* 6-module monolith. — **Resolution: modular monolith with 6 Phase-1 modules** (data, evidence, scoring, risk, decision, report); the 13 engines survive as the conceptual taxonomy and as submodules that graduate when they earn it. *Trade-off:* less impressive org chart, faster working software; graduating a submodule later costs a small refactor, which the Protocol interfaces (A-1) keep cheap.

**D-2: Dataframe library.** *Constitution:* pandas and Polars. *Python:* pandas only. *Quant:* neutral, wants correctness. — **Resolution: pandas only**, behind a data-access layer, with a measured performance budget; Polars is the pre-approved escape hatch if the budget is breached. *Trade-off:* sacrifices performance headroom that current scale doesn't need for a single idiom and smaller test surface.

**D-3: Dashboard delivery.** *UI/UX:* wants interactivity eventually. *DevOps/Security:* no server. *Constitution:* "FastAPI only if required". — **Resolution: generated static HTML through Phase 2; FastAPI (localhost-only) arrives with the journal**, which is the first feature that writes data from the UI. *Trade-off:* no live intraday refresh early — acceptable because v1 is EOD swing trading (Q-1); the journal deadline forces the server decision at a concrete need, not speculatively.

**D-4: Learning autonomy.** *Constitution:* "continuously improve". *Quant + QA:* human-in-the-loop with sample-size gates. — **Resolution: Learning engine measures, diagnoses, and proposes; the trader approves every parameter change; proposals blocked below minimum sample sizes.** *Trade-off:* slower adaptation and manual overhead, in exchange for not letting 30 noisy trades rewrite the scoring weights. This amends Principle 7's wording, not its intent.

**D-5: Options Intelligence timing.** *Constitution:* lists it as a peer engine. *Quant/QA/Security:* data source isn't reliably available without a broker API. — **Resolution: deferred to a late phase, gated on a broker-API data source.** The constitution's own Principle 6 (data integrity first) decides this. *Trade-off:* F&O traders lose options analytics for several phases; the alternative is analytics built on scraped, unreliable chains — worse than nothing.

**D-6: What "AI Scoring" means in v1.** *Constitution:* AI Scoring as a pipeline stage. *Quant/Architect:* v1 scoring must be a transparent, config-weighted evidence sum; LLM/ML may **annotate** (news summarization, natural-language explanations) but never mutate a score it can't decompose. — **Resolution: rule-based transparent scoring in v1; AI as annotator; any future ML scorer must emit per-factor attributions or it doesn't ship.** *Trade-off:* less "AI" in the AI platform initially — but Principle 2 says exactly this, and a black-box scorer would violate Principle 1 outright.

**D-7: Config format.** *Constitution:* JSON. *Python:* wants comments and validation. *QA:* wants invariant checks. — **Resolution: keep JSON (constitution's choice) but every file loads through pydantic with cross-field invariant validation (T-6); revisit TOML only if comment-less config becomes a real pain.** *Trade-off:* no inline comments; mitigated by a documented config reference and `description` fields in schemas.

**D-8: Docker.** *DevOps (initially split):* reproducibility vs. simplicity. — **Resolution: no Docker.** `uv` lockfiles give reproducibility; a single-user local app gains nothing from containers. *Trade-off:* a future machine migration takes an hour of setup instead of `docker run` — acceptable.

---

## 3. Consolidated Recommendation

The constitution is sound. Its principles survive review intact — every resolution above was decided *by* the principles, which is evidence they're the right ones. The amendments below tighten it into something buildable.

### Amendments to ATHENA-000

1. **Pin the trading horizon: EOD-driven swing trading** on NSE cash equities for v1. Intraday and options are explicitly future phases. (Q-1)
2. **Architecture is a modular monolith**, not independent engines: one process, six Phase-1 modules behind Protocol interfaces — `data`, `evidence`, `scoring`, `risk`, `decision`, `report`. The 13-engine taxonomy is retained as the conceptual map. (A-1, D-1)
3. **Explainability is an invariant, not an engine**: every Evidence/Signal/Decision object carries its rationale (rule, observed values, config threshold). The report module renders; it never reconstructs. (A-2)
4. **Define the canonical domain model before any engine**: Instrument, Candle, CorporateAction, Evidence, Signal, Score, Decision, TradePlan, JournalEntry, RunRecord. (A-3)
5. **Deterministic, auditable runs**: idempotent daily pipeline, run-ID on everything, config snapshot stored per run, append-only history, re-run ⇒ identical output. (A-4, A-5, T-4, O-2)
6. **Stack trimmed**: Python + pandas + NumPy + SQLite + static HTML/vanilla JS + Lightweight Charts; indicators implemented in-house with golden tests; FastAPI deferred until the journal; JSON config validated by pydantic. (P-1..P-4, D-2, D-3, D-7)
7. **Principle 7 amended**: the Learning engine *proposes*, the trader *disposes*; minimum-sample gates on every proposal; confidence reported as empirical calibration, not confidence intervals. (Q-3, D-4)
8. **Risk engine encodes NSE structure** from config: circuit bands, F&O ban list, lot sizes, margin rules; sizing assumes exits can gap or lock. (Q-5)
9. **NSE-aware data layer from Phase 1**: corporate-actions handling, point-in-time universe, freshness validation that blocks verdicts on stale data. (Q-4, T-2, T-5)
10. **Measurable mission**: KPIs are adherence rate, expectancy, max drawdown vs. baseline, and calibration error, tracked from the first journaled trade. (T-1)
11. **Structural safety**: the broker client wrapper implements no order-placement methods; secrets in `.env`/keychain, never in config or logs; any server binds localhost only. (S-1, S-2)
12. **Golden-dataset regression suite** is a Phase-1 deliverable, including the NSE edge cases (split, bonus, circuit lock, ban list, rename, Muhurat session). (T-3)

### Recommended phase shape (to be detailed in ATHENA-002)

- **Phase 0 — Foundations:** repo, domain model, config framework + validation, logging, golden dataset skeleton.
- **Phase 1 — Data:** NSE EOD ingestion (bhavcopy/broker API), corporate actions, validation, SQLite store. *Exit: a trustworthy, tested price history.*
- **Phase 2 — Evidence → Verdict:** in-house indicators, evidence generation, transparent scoring, risk gates, static HTML morning briefing. *Exit: a daily TRADE/NO-TRADE verdict with full explanations.*
- **Phase 3 — Journal + server:** FastAPI (localhost), low-friction journal pre-filled from recommendations, KPI tracking.
- **Phase 4 — Backtest + calibration:** point-in-time backtester, walk-forward weight validation, calibration curves.
- **Phase 5 — Learning diagnostics:** propose-and-approve loop over accumulated journal + calibration data.
- **Phase 6 — Expansion:** options intelligence (broker-API gated), news intelligence, AI assistant as annotator.

### Top risks carried forward (for the ATHENA-002 risk register)

1. Data quality of free NSE sources (corporate actions especially) — mitigated by validation layer + broker API fallback.
2. Journal abandonment starving the learning loop — mitigated by U-2's friction budget.
3. Overfitting via premature weight tuning — mitigated by amendment 7's gates.
4. Scope creep toward the 13-engine enterprise platform the non-objectives forbid — mitigated by phase exit criteria and this document.

---

*Next step: on acceptance of these amendments, produce ATHENA-002 (folder structure, module definitions, config architecture, coding standards, detailed phase plan, full risk register).*
