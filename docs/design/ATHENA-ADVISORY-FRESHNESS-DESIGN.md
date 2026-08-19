# AUX-1 — Persistent Advisory Data Freshness

**Status:** Design review pending  
**Active milestone:** AUX-1a — ATHENA freshness contract and persistent header indicator  
**Follow-on milestone:** AUX-1b — DarvaX daily-sweep freshness indicator  
**Selected:** 2026-08-19, priority 1 in the owner-approved advisory UX sequence

## Objective

Give the owner one always-visible, truthful answer to: **“How current is the
data behind what I am looking at?”** The answer must name the observation time,
use the trading calendar and configured freshness limits, and remain useful
during market hours, after close, on weekends, and when data is unavailable.

## Why this is two milestones

ATHENA and DarvaX do not have the same freshness meaning:

- ATHENA presents intraday quotes, candles, decisions, and scheduled cycle
  output. Its state can age materially during an open session.
- DarvaX screens daily bars. Its latest sweep already persists both `as_of`
  (market-data date) and `finished_at` (sweep completion), and being hours old
  after market close is not automatically stale.

Combining both in one implementation would either create a large cross-module
review or force a false shared rule. AUX-1a establishes the contract and ships
ATHENA. AUX-1b reuses the semantics but applies DarvaX's daily/calendar policy.

## Existing behavior confirmed

### ATHENA

- The shared Decisions/Market header refreshes its market ticker every 60
  seconds while either tab is active.
- Session status comes from `/api/v1/dashboard/session-status`; market-open
  state is already calendar-backed.
- Individual panels expose several different timestamps and freshness states,
  but there is no persistent workspace-level answer.
- TradePlan validity and chart-candle freshness are separate concepts and must
  not be reused as general data freshness.

### DarvaX

- `/api/v1/darvax/screen/latest` returns a persisted sweep with `as_of`,
  `started_at`, `finished_at`, state, coverage, partial status, and methodology
  digest.
- The current UI compares the daily `as_of` date with the browser's local date
  and may show “not the latest session.” It deliberately does not use ATHENA's
  calendar, so it cannot distinguish a valid Friday sweep on Saturday from a
  genuinely missed session.
- Sweep metadata is visible inside the screener, but it is not persistent when
  the owner moves through the page.

## Frozen-boundary alignment

- **ADR-005:** the server computes and explains the freshness classification;
  JavaScript renders the returned fields and may update only a neutral elapsed
  time display from the authoritative timestamp.
- **Provider independence:** freshness consumes persisted timestamps and the
  Calendar Engine, never Kite-specific fields.
- **Determinism and replayability:** classification accepts an injected `as_of`
  reference time. No business rule reads the wall clock directly.
- **No methodology change:** freshness informs whether output is current. It
  does not alter scores, confidence, risk, ATHENA decisions, or DAR-CARD tiers.
- **No order placement:** the indicator is read-only and advisory.

No ADR is required for the proposed presentation/API extension. An ADR would
be required if implementation introduced shared mutable state between ATHENA
and DarvaX; this design does not.

## Shared freshness semantics

The engine-facing result is an immutable presentation DTO with these states:

| State | Meaning | Owner wording |
|---|---|---|
| `CURRENT` | Observation is inside its authoritative freshness budget | Current · as of {time} |
| `AGING` | Still usable, but approaching the configured limit | Aging · as of {time} |
| `STALE` | Outside the applicable session/calendar budget | Stale · last observed {time} |
| `UNAVAILABLE` | No authoritative observation can be established | Freshness unavailable |

The DTO must contain:

- `status`
- `observed_at` (timezone-aware ISO timestamp, or null)
- `age_seconds` (or null)
- `freshness_limit_seconds` (or null where daily-session semantics apply)
- `source` (plain identifier such as `market_snapshot` or `darvax_sweep`)
- `headline` (short owner-facing wording)
- `explanation` (why the state was assigned)
- `market_session` and `next_live_at` when relevant

The UI must not infer `CURRENT`, `AGING`, or `STALE` from colour, elapsed time,
or a hard-coded number.

## AUX-1a — ATHENA design

### Authority

Add a read-only dashboard freshness endpoint backed by a pure service that:

1. selects the latest authoritative persisted market observation used by the
   active dashboard surface;
2. resolves the market session through `CalendarEngine`;
3. applies configured intraday freshness thresholds only while that observation
   is expected to advance;
4. returns a closed-market explanation instead of allowing age alone to turn a
   valid session-close snapshot red overnight; and
5. fails honestly to `UNAVAILABLE` when no timestamp exists.

The first implementation covers the shared Decisions and Market Intelligence
header. Other tabs keep their existing panel-specific timestamps and are not
silently assigned a market-data freshness they do not consume.

### Presentation

- Place one compact status control in the existing header status group, close
  to the market ticker and advisor pulse.
- Show status plus a concise observed time; expose the full explanation in an
  accessible popover/tooltip on click or keyboard activation.
- Use green only for `CURRENT`, amber for `AGING`, red for `STALE`, and neutral
  grey for `UNAVAILABLE` or a valid closed-market review state.
- Keep a stable width so minute-by-minute wording cannot shift the header.
- Refresh with the existing 60-second ticker cycle and on explicit workspace
  refresh. Preserve the last successful value during a transient request
  failure, while visibly marking that the refresh attempt failed.

### Non-goals

- This does not display the last successful pipeline cycle; that is AUX-2.
- This does not replace TradePlan validity, chart freshness, Kite connectivity,
  platform health, or market-open status.
- This does not calculate a blended “overall system freshness” score.

## AUX-1b — DarvaX design boundary

AUX-1b will classify the persisted sweep against the latest expected trading
session, using Calendar Engine output supplied by the server. Its persistent
header wording must distinguish:

- **Data through {session date}** — market-data coverage;
- **Screened {elapsed time} ago** — computation time;
- partial/cancelled sweep and methodology-digest mismatch; and
- no sweep yet.

It will replace the browser-local date comparison in `renderMeta()` with the
authoritative DTO. It will not make DarvaX depend on ATHENA dashboard state or
write to ATHENA's database.

## AUX-1a acceptance criteria

1. The Decisions and Market Intelligence header always shows one of the four
   freshness states after its first successful load.
2. The classification is computed server-side from persisted data, configured
   limits, an injected reference time, and Calendar Engine context.
3. Open-session current, aging, stale, unavailable, post-close, weekend, and
   holiday cases have deterministic tests.
4. Closed-market wording names the observation and next live session without
   falsely reporting an overnight session-close snapshot as intraday-stale.
5. A failed refresh preserves the last good timestamp and visibly states that
   it could not be refreshed.
6. Keyboard focus, tooltip/popover dismissal, narrow desktop layout, and text
   wrapping are browser-verified.
7. Existing ticker, advisor pulse, TradePlan, chart, and health states remain
   unchanged.
8. Full test suite passes, contracts remain additive, and no order-placement
   surface is introduced.

## Planned test layers

- Pure unit tests for all state transitions and session types.
- API tests for the DTO shape, timezone awareness, missing data, and stable
  explanations.
- Static/dashboard regression tests ensuring the UI renders returned state and
  contains no duplicate threshold/classification logic.
- Browser verification at desktop and constrained widths, including click,
  keyboard, loading, error, and closed-market states.

## Design gate

Implementation begins only after owner approval of AUX-1a's authority,
placement, wording model, and explicit separation from AUX-2. AUX-1b remains
planned until AUX-1a is reviewed and approved.
