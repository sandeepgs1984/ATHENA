# ATHENA Cycle Status Design (AUX-2)

## Objective

Make the last successful full ATHENA validation cycle visible outside Live Operations and warn when the next full cycle is overdue.

## Architectural boundary

- Runtime remains the owner of persisted `RunRecord` history.
- The dashboard receives a read-only projection of `REFRESH` runs; it does not schedule, retry, or mutate a cycle.
- Market-observation freshness and ATHENA cycle health remain separate server contracts. The browser only combines their presentation in the existing freshness detail popover.
- `FAST` decision-list refreshes never satisfy the full-cycle cadence.
- No scoring, risk, decision, TradePlan, replay, or provider contract changes are introduced. No ADR is required.

## Timing policy

The effective cadence is `scheduling.refresh.interval_minutes`, falling back to `base.refresh_interval_minutes`. A configured `overdue_grace_minutes` is added before an open-session cycle becomes overdue.

During an open market session:

- `CURRENT`: the latest successful cycle is inside the cadence plus grace window.
- `OVERDUE`: no successful cycle covers the current session, or the next expected cycle is late.
- `FAILED`: the latest completed attempt after the last success is failed, blocked, or degraded.

Outside an open market session:

- `CLOSED`: the latest attempt completed successfully; no overdue warning is raised while the market is closed.
- `FAILED`: the latest completed attempt failed, was blocked, or degraded.
- `UNAVAILABLE`: no full-cycle history exists.

A running attempt is reported explicitly and does not replace the last successful cycle timestamp.

## API contract

`GET /api/v1/dashboard/cycle-status`

Returns status, tone, plain-language headline and explanation, last successful run/time, latest attempt status/time, next expected time, session phase, cadence, and grace.

## UX

- Reuse the existing freshness button and anchored popover; do not add another header control.
- Add a divided `ATHENA cycle` section below market-data freshness.
- Escalate the shared header label/tone only for `OVERDUE` or `FAILED` cycle states.
- Offer `Open Live Operations` for overdue/failed states so the owner can inspect persisted run evidence.
- Show the `Expected by` deadline only during live-session cadence monitoring. In a closed session, label the last cycle factually and suppress the obsolete live deadline while retaining its API value for replay and audit.
- Endpoint failure degrades only the cycle section and never hides a valid market-freshness reading.

## Verification

- Unit-test current, overdue, failed, closed, and unavailable classifications.
- Contract-test the dashboard route.
- Hosting-test the visible DOM, independent fetch, severity composition, and Live Operations action.
- Run the complete suite before milestone review.
