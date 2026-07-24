# ATHENA

Personal AI Decision Intelligence Platform for trading Indian equities (NSE/BSE).

ATHENA is not a screener, not a bot, and never executes trades. It exists to improve one trader's decision quality through explainable intelligence, disciplined risk management, evidence-based scoring, and human-approved learning.

## Documents

| Doc | Title | Status |
|---|---|---|
| [ATHENA-000](docs/ATHENA-000-Master-Architecture.md) | Master Architecture & Product Foundation (Constitution) | Ratified v0.2 |
| [ATHENA-001](docs/ATHENA-001-Engineering-Review.md) | Engineering Review — 7 roles, 8 disagreements resolved, 12 amendments | Approved |
| [ATHENA-001R](docs/ATHENA-001R-Owner-Review.md) | Owner Review — 15 amendments + 4 directions | Accepted |
| [ATHENA-002](docs/ATHENA-002-System-Blueprint.md) | System Blueprint — single source of truth for implementation | **Approved v1.1 — FROZEN** |
| [ATHENA-002R](docs/ATHENA-002R-Owner-Review.md) | Owner Review — 17 final refinements + architecture freeze | Accepted |
| [MILESTONES](docs/MILESTONES.md) | Phase/milestone roadmap | Active |
| [Production readiness](docs/PRODUCTION_READINESS_ROADMAP.md) | Daily advisory readiness (R1–R6) | Active |
| [File-backed daily ops](docs/ops/FILE_BACKED_DAILY_OPS.md) | R1 SOP for FileProvider daily use | Approved |
| [Kite live data ops](docs/ops/KITE_LIVE_DATA.md) | R4 Kite token + ingest runbook | **Approved** |
| [Host schedule + alerts](docs/ops/HOST_SCHEDULE.md) | R5 launchd/cron + failure alerts | **Approved** |
| [Professional live entry](docs/ops/LIVE_ENTRY.md) | Dock/URL → unlock → Kite → LIVE runbook | **Approved** |
| [QA verification](docs/ops/QA_VERIFICATION.md) | Regression, targeted suites, acceptance evidence, and failure triage | Active |
| [DD-9 alerting](docs/decisions/DD-9-alerting-channel.md) | R5 webhook+file alert choice | Accepted (email deferred) |
| [DD-1 live vendor](docs/decisions/DD-1-broker-live-data-vendor.md) | R3 broker/data vendor decision | **Accepted** — Zerodha Kite Connect |
| [ADRs](docs/adr/) | Architecture Decision Records (ADR-001…005 seeded) | Active |

## Workstation entry

```bash
# Browser-first localhost workstation
./athena-serve --with-cycles --open

# macOS: install the thin Dock launcher once
./install-athena-app
```

The morning path is: **Dock/URL → ATHENA unlock → Kite gate when needed → LIVE**.
See [Professional live entry](docs/ops/LIVE_ENTRY.md).

## Core decisions

Modular monolith, 17 modules behind Protocol interfaces (see ATHENA-002 §2); architecture frozen — changes require an ADR. **v1 scope: intraday trading on NSE cash equities** (pre-market plan + periodic refresh; swing later; options/positional in expansion). Broker kept abstract behind a `MarketDataProvider` interface — no broker binding in Phase 1. Stack: Python, pandas, NumPy, SQLite, static HTML + vanilla JS, Lightweight Charts; in-house indicators; JSON config validated by pydantic; FastAPI (localhost-only) from Phase 4. Explainability is carried as data through the pipeline; every recommendation is replayable. The learning engine proposes; the trader approves.

## Safety invariants

No order-placement code exists anywhere in this repo. Broker credentials live in `.env` (gitignored), never in config. The trade journal and local database are gitignored — this repo holds code and documents, not personal financial data.
