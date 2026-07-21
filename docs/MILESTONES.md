# ATHENA — Milestone Roadmap

Official milestone breakdown per the milestone-based workflow (CLAUDE.md).
One milestone at a time; owner approval gates every transition. A milestone
too large for a single-sitting review is split BEFORE implementation.

## Phase 0 — Foundations ✅ APPROVED (2026-07-20)

Delivered as one batch before this workflow existed; retroactive milestone map:
M0.1 Repository & Project Setup · M0.2 Canonical Domain Model · M0.3 Configuration
Framework · M0.4 Trading Calendar · M0.5 Observability & CLI.

## Phase 1 — Data Foundation (AUTHORIZED)

| Milestone | Scope | Status |
|---|---|---|
| **M1.1** MarketDataProvider Contracts | Provider Protocol hardening, ProviderCapabilities, ProviderHealth, behavioral contract, reusable contract test suite | ✅ Approved |
| **M1.2** FileProvider | FileProvider; daily/intraday/instrument/quote loaders; provider health | ✅ Approved |
| **M1.3** Validation Layer | Freshness, OHLC, duplicate, gap validation; validation reports; quarantine handling | ✅ Approved |
| **M1.4** Corporate Actions Engine | Splits, bonuses, dividends, renames; historical adjustment strategy | ✅ Approved |
| **M1.5** SQLite Repository | Schema, WAL, foreign keys, repository layer, append-only storage, integrity verification | ✅ Approved |
| **M1.6** Backup & Restore | Backup, restore, recovery validation, repository recovery tests | ✅ Approved |

## Phase 2 — Market Intelligence (AUTHORIZED)

| Milestone | Scope | Status |
|---|---|---|
| **M2.1** Regime Engine | Deterministic regime (trend/volatility/gap) with evidence | ✅ Approved |
| **M2.2** Market Health | Breadth, trend quality, participation, momentum, volatility health | ✅ Approved |
| **M2.3** Sector Health | Sector-level strength, deterministic + explainable | ✅ Approved |
| **M2.4** Universe Engine | Investable universe construction with explainable inclusion | In review |

## Phase 3 — Decision Intelligence (AUTHORIZED)

Per the Phase 3 authorization the milestone set is:

| Milestone | Scope | Status |
|---|---|---|
| **M3.1** Evidence Aggregation | Single immutable evidence graph with provenance + missing detection | ✅ Approved |
| **M3.2** Indicator Engine | Deterministic technical indicators (SMA/EMA/RSI/ATR/MACD/ADX/vol avgs) | ✅ Approved |
| **M3.3** Scoring Engine | Transparent component scores from approved evidence/indicators | ✅ Approved |
| **M3.4** Confidence Engine | Evidence reliability (completeness, agreement, freshness, contradictions) | ✅ Approved |
| **M3.5** Risk Engine | Descriptive trading-risk assessment (volatility/liquidity/gap/event/concentration) | ✅ Approved |
| **M3.6** Decision Engine | First explainable decisions from bundle+indicators+scores+confidence+risk | In review |
| M3.7 Decision Trace & Reporting | Human + machine-readable decision reports | Blocked on M3.6 |

## Phases 4–7

Phase 4 (AI Intelligence), Phase 5 (Simulation & Replay), Phase 6 (Reporting &
Dashboard), Phase 7 (Production Readiness): each will be split into reviewable
milestones before its first implementation, at authorization time.

---

*Status legend: a milestone is "In review" after its Milestone Review Summary is
delivered, "Approved" only when the owner says so. Never two milestones in flight.*
