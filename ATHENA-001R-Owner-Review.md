# ATHENA-001R — Owner Review of the Foundation Documents

| | |
|---|---|
| Reviews | ATHENA-000 v0.1, ATHENA-001 v1.0 |
| Reviewer | sandeep (project owner) |
| Date | 2026-07-20 |
| Verdict | **APPROVED WITH ADDITIONAL AMENDMENTS** — 15 points below, all accepted |
| Effect | ATHENA-000 amended to v0.2; all points incorporated into ATHENA-002 |

The Constitution and Engineering Review are approved as the project baseline. Before implementation, the following improvements are incorporated.

## The 15 amendments

**R-1. Primary trading horizon is INTRADAY.** ATHENA-001's Q-1 assumption (EOD swing) is reversed. Primary strategy: intraday trading (v1). Secondary: swing trading (future). Expansion: options, positional, multi-day. Every module, scoring rule, indicator, dashboard component, and risk rule optimizes for the primary horizon. *Engineering note (accepted trade-offs): requires a real-time-capable data provider and intraday historical candles from Phase 1; supersedes ATHENA-001 D-3's "static HTML until Phase 3" — the dashboard needs periodic refresh earlier; intraday backtest data for NSE is scarcer/paid.*

**R-2. Market Regime Engine.** No stock scoring before market context is established. Regimes include: bull/bear trend, range-bound, gap up/down, high/low volatility, expiry day, budget day, election day, result season, event-driven, circuit-driven. First intelligence module executed every session.

**R-3. Trading Calendar Engine.** Dedicated market-awareness module: NSE holidays, Muhurat trading, weekly/monthly expiry, budget day, election day, RBI policy, US Fed events, IPO listings, corporate actions, trading sessions, special timings. All downstream modules consume calendar context.

**R-4. Dynamic Watchlist Engine.** Never scan the whole market. A Watchlist (Universe) Engine constructs today's trading universe from filters: index constituents, F&O list, liquidity, relative strength, sector leaders, volume, gaps, news candidates, institutional interest, custom lists. Scanners consume only this universe.

**R-5. Canonical Evidence object.** Every observation becomes Evidence: identifier, category, source, timestamp, weight, confidence, raw value, normalized value, explanation, metadata. The Decision Engine operates only on Evidence — fully independent of individual indicators.

**R-6. Canonical Decision object.** Richer than BUY/SELL: Trade, Watch, Wait, No Trade, Reduce Position, Increase Position, Partial Exit, Full Exit, Avoid Sector, Market Closed, Insufficient Data, Data Validation Failed.

**R-7. Score ≠ Confidence.** Score = opportunity quality. Confidence = historical trust in that score. Dedicated Confidence Engine, not embedded in scoring.

**R-8. Explainability Quality metric.** Every recommendation exposes Decision + Score + Confidence + Explainability quality. Poor explainability ⇒ recommendation rejected automatically. ATHENA never produces recommendations it cannot fully explain.

**R-9. Decision Journal replaces Trade Journal.** Record every recommendation, not only executed trades: timestamp, market context, evidence, score, decision, confidence, user action (ignored/accepted/rejected), trade outcome. Learning evaluates decision quality, not just trade outcomes.

**R-10. Knowledge Base.** Central store for architecture docs, reviews, trading rules, scoring rules, patterns, playbooks, failure analysis, lessons learned, release notes. ATHENA becomes self-documenting.

**R-11. Replayability as core principle.** Any recommendation reconstructable at any future date: original market data, config snapshot, evidence chain, score breakdown, decision, confidence, risk evaluation, software version, run ID. No hidden runtime state.

**R-12. From pipeline to platform.** Remain a modular monolith, but support collaborative intelligence through shared domain models: market influences risk, risk influences decision, decision influences confidence, confidence influences portfolio, portfolio influences sizing, learning influences future scoring.

**R-13. Domain model before implementation.** Minimum objects: Instrument, MarketSnapshot, SectorSnapshot, Candle, CorporateAction, Evidence, Signal, Score, Decision, TradePlan, Position, Portfolio, JournalEntry, DecisionJournalEntry, RunRecord, ConfigurationSnapshot.

**R-14. System-wide principles added to the Constitution.** Every recommendation replayable; every decision explainable; every module owns one responsibility; every configuration change versioned; every pipeline execution reproducible; every recommendation auditable; every historical decision reconstructable.

**R-15. Next deliverable is ATHENA-002 — no implementation before it is approved.** Must define: folder structure, domain model, SQLite schema, configuration architecture, module responsibilities, module interfaces, data contracts, execution lifecycle, dependency graph, logging architecture, error handling, testing strategy, risk register, coding standards, phased roadmap, definition of done, acceptance criteria, architecture diagrams.

## Additional directions (post-review)

1. **Broker stays abstract.** A `MarketDataProvider` interface; no binding to Zerodha or any broker in Phase 1. Business logic broker-independent.
2. **Pre-market planning workflow + periodic refreshes**, architected to evolve into an event-driven system where only affected intelligence modules re-evaluate.
3. **ATHENA-002 is one consolidated blueprint** — the project's single source of truth.
4. **Deferred Decisions section** in ATHENA-002: intentionally postponed choices (broker, options provider, news provider, ML framework, cloud, …) with the revisit phase and decision criteria for each.

## Verdict

ATHENA-000: APPROVED (amended to v0.2). ATHENA-001: APPROVED. Required before coding: ATHENA-002 System Blueprint. Architecture rating 9.6/10; target after ATHENA-002: 10/10.

The objective remains unchanged: ATHENA is not a stock screener and not an automated trading platform. It is a Personal AI Decision Intelligence Platform focused on improving trading decisions through explainable intelligence, disciplined risk management, evidence-driven reasoning, deterministic execution, and continuous human-supervised learning.
