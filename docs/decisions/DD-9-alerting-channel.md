# DD-9 — Alerting channel (R5 partial resolution)

| | |
|---|---|
| Status | **ACCEPTED for R5** — webhook + local file (email SMTP deferred) |
| Date | 2026-07-23 |
| Deferred decision | ATHENA-002 §15 **DD-9** |
| Scope | Hard-failure alerts for host-scheduled ops (`athena run-due`) |

## Decision

For single-user workstation ops, R5 uses:

1. **File artifacts** under `artifacts/alerts/` (always available offline).
2. **Webhook POST** to `ATHENA_ALERT_WEBHOOK_URL` (or fallback `ATHENA_WEBHOOK_URL`) from `.env`.

**Not in R5:** SMTP email, desktop push, Telegram bot. Those remain future options without changing the `FailureAlertDispatcher` shape.

## Traceability

- Ops runbook: `docs/ops/HOST_SCHEDULE.md`
- Config: `config/host_ops.json`
- Code: `src/athena/ops/failure_alerts.py`
