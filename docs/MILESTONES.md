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
| **M1.5** SQLite Repository | Schema, WAL, foreign keys, repository layer, append-only storage, integrity verification | In review |
| M1.6 Backup & Restore | Backup, restore, recovery validation, repository recovery tests | Blocked on M1.5 |

## Phase 2 — Market Intelligence

M2.1 Regime Engine · M2.2 Market Health · M2.3 Sector Health · M2.4 Universe Engine

## Phase 3 — Decision Intelligence

M3.1 Evidence Collection · M3.2 Indicator Engine · M3.3 Scoring Engine ·
M3.4 Confidence Engine · M3.5 Risk Engine · M3.6 Capital Allocation ·
M3.7 Decision Engine · M3.8 Decision Trace · M3.9 Decision Report

## Phases 4–7

Phase 4 (AI Intelligence), Phase 5 (Simulation & Replay), Phase 6 (Reporting &
Dashboard), Phase 7 (Production Readiness): each will be split into reviewable
milestones before its first implementation, at authorization time.

---

*Status legend: a milestone is "In review" after its Milestone Review Summary is
delivered, "Approved" only when the owner says so. Never two milestones in flight.*
