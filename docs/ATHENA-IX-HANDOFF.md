# ATHENA IX Track Handoff

**Snapshot date:** 2026-08-01  
**Branch observed:** `feature/live-dashboard`  
**Latest committed IX milestone:** IX-3 (`b86d5ea`)  
**Current working milestone:** IX-4a (ready for review) — owner resumed and
authorized IX-4 on 2026-08-01; IX-4 is split into IX-4a/IX-4b/IX-4c (design in
`docs/design/ATHENA-INDEX-SECTOR-INTELLIGENCE-ROADMAP.md`), one at a time.
IX-4a is implemented, tested (1,147 full suite), and live-verified via the
DOM-bypass technique; awaiting owner review/approval.  
**Next milestone:** IX-4b, only after IX-4a is reviewed and approved

This document is a continuity aid for the IX track. It is not the authority for
milestone status. Before acting, read `ATHENA_BRIEFING.md`, then verify
`docs/MILESTONES.md`, the newest entry in `IMPLEMENTATION_SUMMARY.md`, and the
current git log/status. Those sources override this snapshot if they differ.

## 1. Product and Safety Context

ATHENA is a single-user, advisory-only NSE/BSE decision-intelligence platform.
It never places orders. The IX track adds broad-market and sector-index context
to Market Intelligence and Decisions & Trace.

Index movement and index breadth are presentation context only. They do not
change score, confidence, risk, decisions, TradePlan values, or eligibility.
Any analytical influence is deferred to IX-6 and requires replay evidence, an
ADR, and owner approval. SD-2 is not silently resolved by this track.

## 2. Current IX Status

| Milestone | State on 2026-07-31 | Result |
|---|---|---|
| IX-1 | Approved | Twelve-index quote-only catalog, persisted observations, and read-only API |
| IX-2 | Approved | Session-aware Index Leadership ribbon and detail modal |
| IX-3 | Approved | Official versioned constituents, exact resolution, and fail-closed current-board breadth |
| IX-4 | Planned | Index-aware discovery across Universe, Workbench, and Decisions |
| IX-5 | Planned | Informational index backdrop in the selected-symbol brief |
| IX-6 | Planned and ADR-gated | Replay study and decision on analytical influence |

IX-3 was explicitly approved by the owner on 2026-07-31. The IX track is now
paused. Do not begin IX-4 merely because IX-3 is approved; wait for a separate
owner instruction to resume and authorize IX-4.

## 3. Implemented Data Flow

1. `config/index_intelligence.json` owns the enabled index catalog, provider
   identity, family, ordering, and constituent-manifest path.
2. Kite snapshots quote the display catalog in a bounded request. The larger
   display set is not added to scoped historical symbol ingestion.
3. `GET /api/v1/market/index-intelligence` exposes persisted index levels,
   trustworthy prior-session changes when available, session context, and IX-3
   constituent context.
4. `data/index_constituents/2026-07-31/` contains immutable official NSE CSVs
   and a manifest with effective date, retrieval time, source URL, member count,
   SHA-256 checksum, and overlap policy.
5. `src/athena/data/index_constituents.py` validates and loads that snapshot.
   It fails loudly on catalog drift, checksum drift, malformed data, duplicate
   keys, path traversal, or member-count mismatch.
6. Constituents resolve only to exactly one active NSE EQ instrument with the
   same symbol. ATHENA does not infer membership from names, aliases, sectors,
   or partial matches.
7. `SqliteRepository.list_latest_decisions_by_instrument()` selects one latest
   persisted decision per instrument using timestamp and decision-id
   tie-breaking.
8. The service publishes Trade, Watch, No trade, and Trade breadth only when
   every constituent resolves and every resolved member has a current-board
   decision. Trade additionally requires a current TradePlan. Incomplete
   coverage suppresses all breadth values and lists the affected symbols.

## 4. IX-3 Runtime Contract

Each index row reports membership provenance and one constituent-context state:

- `AVAILABLE`: instrument and current-decision coverage are complete; board
  composition and Trade breadth may be shown.
- `INCOMPLETE_INSTRUMENTS`: one or more official symbols did not resolve
  exactly; breadth must remain unavailable.
- `INCOMPLETE_DECISIONS`: membership resolved, but one or more constituents do
  not have a current-board decision; breadth must remain unavailable.

“Breadth” in IX-3 means the composition of ATHENA's current Decision board for
the official index membership. It is not exchange advance/decline breadth and
is not a trade signal.

## 5. Owner Visual QA Evidence

The owner-supplied desktop screenshots from 2026-07-31 verify the expected
IX-3 behavior:

- the compact ribbon reports all 12 index levels available;
- the closed-session copy gives the next live session as 03 Aug, 09:15 AM IST;
- NIFTY BANK has complete coverage (`14 resolved`, `14 covered`) and therefore
  publishes `64.3% Trade breadth` from Trade 9, Watch 5, No trade 0;
- NIFTY 50, NIFTY NEXT 50, NIFTY MIDCAP 100, and shown sector indices withhold
  breadth and disclose their missing current-decision counts;
- affected-symbol disclosure and official-membership links are present;
- the modal uses the available width without visible horizontal clipping.

The screenshots therefore pass the IX-3 desktop owner-QA gate. Automated
authenticated browser interaction was unavailable because the browser stopped
at Workstation Unlock. Narrow-layout and overflow behavior remain covered by
dashboard regression assertions; an authenticated interaction pass can still
be repeated when the workstation session is available.

## 6. Expected Unavailable States

- `Change unavailable` is expected when no trusted prior-session baseline has
  yet been persisted. IX-2 never substitutes a same-day observation or zero.
- A level may be available while change is unavailable; these are separate
  evidence fields.
- Breadth is unavailable whenever even one official constituent lacks exact
  instrument resolution or a current-board decision. Partial percentages are
  prohibited.
- Official memberships are point-in-time evidence. Add a new effective-date
  directory when NSE membership changes; never overwrite an existing snapshot.

## 7. Separate Runtime Issue Visible in QA

The Market Intelligence screenshot shows a later `run-closing` validation
failure at 03:45 PM and correctly changes the Validation Pipeline card to
`Failed` with guidance to inspect Runs. This is not an IX-3 constituent or
breadth failure. Treat existing rows as prior persisted results until the run
failure is investigated and a successful validation refresh completes.

Do not weaken the fail-loud run state or relabel old decisions as fresh to hide
that operational failure.

## 8. Key Files

Data and configuration:

- `config/index_intelligence.json`
- `data/index_constituents/2026-07-31/manifest.json`
- `data/index_constituents/2026-07-31/*.csv`
- `src/athena/data/index_constituents.py`
- `src/athena/data/store/repository.py`

API and service:

- `src/athena/api/v1/dtos/market.py`
- `src/athena/api/v1/services/market_history_service.py`
- `src/athena/api/v1/routers/market.py`

Dashboard:

- `src/athena/api/static/index.html`
- `src/athena/api/static/js/09-market-intelligence.js`
- `src/athena/api/static/css/06-market-intelligence.css`

Tests and tracking:

- `tests/data/test_index_constituents.py`
- `tests/data_layer/test_decision_journal.py`
- `tests/api/v1/test_market_history.py`
- `tests/api/platform/test_dashboard_hosting.py`
- `tests/api/platform/test_decision_chart_release_gate.py`
- `docs/design/ATHENA-INDEX-SECTOR-INTELLIGENCE-ROADMAP.md`
- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`

## 9. IX-4 Pickup Contract

Start IX-4 only after the owner explicitly resumes the paused IX track and
authorizes IX-4. Complete its Design step before editing code and confirm
alignment with the relevant ATHENA-002 sections.

Approved roadmap scope:

- add official index filters to Universe, Validation Workbench Results, and
  Decisions;
- provide a selected-index view of current Trade, Watch, and No trade symbols;
- rank only with existing ATHENA fields such as current-plan validity, entry
  readiness, score, confidence, risk, and freshness;
- preserve strict selected-symbol handoff into Decisions & Trace;
- provide immediate progress feedback while filtering or sorting large lists.

IX-4 safety rules:

- “Best” means best current ATHENA-qualified setup inside the selected official
  membership, never the symbol with the largest index or day move.
- Expired, stale, unavailable, or no-plan rows cannot appear actionable.
- Filtering changes presentation only; it must not recompute or mutate a
  validation result.
- Reuse IX-3's exact membership map. Do not create a second inferred mapping.
- Keep unavailable and incomplete states visible; do not silently drop them.
- Do not change scoring, confidence, risk, decision policy, TradePlan values,
  provider protocols, frozen domain objects, or broker behavior.

## 10. IX-5 and IX-6 Remaining Scope

IX-5 is a plain-language, informational Decision Brief section showing the
selected symbol's official index memberships, index direction, relative move,
and available board breadth. It must stay visually separate from ATHENA's
recommendation and must not crowd the actionable TradePlan fold.

IX-6 is an evidence milestone, not permission to alter scoring. It must replay
historical decisions with index context, measure coverage and outcome impact,
and produce an ADR proposal. No analytical influence may be implemented unless
the evidence, ADR, and owner approval all support it. Keeping index context
presentation-only is an acceptable IX-6 outcome.

## 11. Verification Baseline

IX-3 completed with:

- focused IX-3 suite: 43 passed;
- full suite: 1,140 passed with one existing Starlette/httpx warning;
- IX-3-owned Ruff checks: passed;
- MyPy: no issues;
- JavaScript parse and final diff whitespace checks: passed.

Future IX work must rerun focused tests for touched contracts and the full suite,
then update `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`, and this handoff.

## 12. Agent Pickup Checklist

1. Read `ATHENA_BRIEFING.md` and the mandatory project rules.
2. Read the IX table and latest IX notes in `docs/MILESTONES.md`.
3. Read only the newest entry in `IMPLEMENTATION_SUMMARY.md`.
4. Inspect git log and working-tree status; documentation may be ahead of the
   owner's commit.
5. Read the IX roadmap and this handoff.
6. Confirm the owner has explicitly approved the next milestone.
7. Work on exactly one IX milestone through Design, Implement, Test,
   Self-Validate, and Milestone Review Summary.
8. Stop at the next owner-approval gate.
