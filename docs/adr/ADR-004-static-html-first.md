# ADR-004 — Static HTML First, FastAPI Later

| | |
|---|---|
| Status | Accepted |
| Date | 2026-07-20 |
| Deciders | sandeep (owner), engineering review (ATHENA-001 D-3, revised by ATHENA-001R R-1) |

## Context

The dashboard must answer the constitution's eight questions with zero operational burden. A server adds ports, auth surface, and a process to babysit — costs that buy nothing until the UI must accept input.

## Decision

Phases 0–3: the report module generates static HTML files (vanilla JS, Lightweight Charts). Phase 4 introduces FastAPI bound to 127.0.0.1 only — triggered by the first write-path feature (journal UI), not by speculation.

## Alternatives considered

FastAPI from day one — rejected: server complexity before any interactive need. Desktop GUI (Qt/Tauri) — rejected: heavier stack, violates constitution's minimal-stack preference. Terminal UI — rejected: fails the dashboard clarity philosophy.

## Consequences

Pre-market plan works offline, survives crashes, is trivially archivable per run (replayability). Intraday refresh in Phase 4 re-renders on each cycle; true live push (websocket UI) stays deferred with DD-2/DD-3.
