# ATHENA

Personal AI Decision Intelligence Platform for trading Indian equities (NSE/BSE).

ATHENA is not a screener, not a bot, and never executes trades. It exists to improve one trader's decision quality through explainable intelligence, disciplined risk management, evidence-based scoring, and human-approved learning.

## Documents

| Doc | Title | Status |
|---|---|---|
| [ATHENA-000](ATHENA-000-Master-Architecture.md) | Master Architecture & Product Foundation (Constitution) | Draft v0.1 |
| [ATHENA-001](ATHENA-001-Engineering-Review.md) | Engineering Review — 7 roles, 8 disagreements resolved, 12 amendments | Approved with amendments |
| ATHENA-002 | Folder structure, module definitions, config architecture, phase plan, risk register | Pending |

## Core decisions (from ATHENA-001)

Modular monolith, six Phase-1 modules: `data`, `evidence`, `scoring`, `risk`, `decision`, `report`. v1 scope: EOD-driven swing trading on NSE cash equities. Stack: Python, pandas, NumPy, SQLite, static HTML + vanilla JS, Lightweight Charts; in-house indicators; JSON config validated by pydantic; FastAPI (localhost-only) deferred to the journal phase. Explainability is carried as data through the pipeline. The learning engine proposes; the trader approves.

## Safety invariants

No order-placement code exists anywhere in this repo. Broker credentials live in `.env` (gitignored), never in config. The trade journal and local database are gitignored — this repo holds code and documents, not personal financial data.
