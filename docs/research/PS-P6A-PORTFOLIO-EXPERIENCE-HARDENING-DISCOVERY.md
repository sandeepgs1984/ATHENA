# PS-P6A Portfolio Experience Hardening Discovery

Status: Discovery complete; ready for Owner/Chief Architect review
Date: 2026-09-03
Scope: Product/operational hardening discovery only
Boundary: No production behavior, schema, API, dashboard, methodology, provider,
broker, execution, or trading-rule changes

## 1. Executive Summary

My Portfolio now has a coherent end-to-end path from uploaded CSV/XLSX holdings
through immutable interpreted snapshots. The remaining production-readiness gaps
are mostly state-truthfulness and operability, not trading methodology.

The most important gap is P0: the system can create and persist a snapshot for
holdings state A, then accept a later confirmed holdings state B, while the
latest snapshot endpoint and dashboard still present the old snapshot as if it
were current. A related P0 exists when Sync starts from holdings state A and an
import confirmation changes holdings to B before Sync finishes. The sync run
already stores a deterministic holdings digest, but no read path compares it
with the current canonical holdings digest.

PS-P6B should be the smallest hardening milestone that makes state freshness
truthful: holdings fingerprint comparison, stale-analysis metadata, dashboard
stale banner, import/sync concurrency policy, and clearer partial/failure
presentation. No new portfolio interpretation methodology is needed.

## 2. Current End-to-End Architecture

Current path:

CSV/XLSX upload -> preview parse -> symbol resolution -> reconciliation preview
-> explicit confirmation -> canonical `portfolio_holdings` -> manual Portfolio
Sync -> D1 freshness refresh/check -> persisted Decision/TradePlan and optional
EntryQualification evidence -> PS-P5B interpreter -> immutable
`portfolio_analysis_snapshots` -> latest snapshot dashboard table.

Primary files inspected:

- `src/athena/portfolio/imports.py`
- `src/athena/api/v1/services/my_portfolio_service.py`
- `src/athena/portfolio/sync.py`
- `src/athena/data/store/repository.py`
- `src/athena/data/store/schema.py`
- `src/athena/api/v1/routers/my_portfolio.py`
- `src/athena/api/v1/dtos/portfolio.py`
- `src/athena/api/static/index.html`
- `src/athena/api/static/js/08b-my-portfolio.js`
- `src/athena/api/static/css/05b-my-portfolio.css`

## 3. Current User Workflow

Supported today:

- Upload CSV/XLSX holdings.
- Preview normalized rows and mapping/validation errors.
- Review proposed reconciliation.
- Confirm with exact `CONFIRM` token supplied by the UI.
- View canonical holdings.
- Start manual Sync.
- Poll queued/running/terminal sync state.
- View latest successful or partial snapshot.
- View import history.

The workflow is understandable, but after a confirmed import the dashboard does
not clearly say the existing analysis is now stale and should be re-synced.

## 4. Holdings/Snapshot State Model

Current canonical state:

- `portfolio_holdings` is one row per canonical instrument.
- `portfolio_holdings_digest()` hashes sorted `instrument_id`, `quantity`, and
  `avg_price`.
- Import previews store `base_holdings_digest` in import provenance.
- Sync run creation stores `holdings_digest` in sync-run provenance.
- Snapshot rows store row/freshness/provenance JSON, but not an explicit
  snapshot-vs-current freshness verdict.

The data model has enough raw material to detect stale snapshots, but the
application does not yet expose that comparison.

## 5. Snapshot Staleness Analysis

P0: latest snapshot reads do not compare the sync-run `holdings_digest` against
the current `portfolio_holdings_digest()`.

Observed behavior from code:

- `PortfolioSyncOrchestrator.create_run()` records the current digest in
  sync-run provenance.
- `MyPortfolioService.latest_snapshot()` selects the latest SUCCESS/PARTIAL run
  with snapshots and returns its rows.
- `renderMyPortfolioHoldings()` renders snapshot rows whenever
  `myPortfolioState.snapshot?.rows?.length` exists, even if current holdings
  were changed after the snapshot.

Result: an old 20-holding snapshot can appear current after a new 21-holding
import until the owner syncs again.

## 6. Import-after-Sync Behavior

Current behavior:

- Confirming a new import atomically replaces canonical holdings and writes
  reconciliation audit rows.
- The old latest snapshot remains available.
- The dashboard reloads holdings/imports/snapshot after confirmation, but still
  prefers existing snapshot rows over current holdings rows.
- There is no stale-analysis banner or structured `portfolio_changed_since_sync`
  flag.

Classification: P0, because a dashboard can silently show analysis for a prior
holdings state.

## 7. Sync-during-Import Concurrency

Current behavior:

- Sync snapshots the holdings list at run start.
- Import confirmation can proceed independently while a sync thread is running.
- The completed sync persists rows for the holdings list it read, but the run
  may complete after canonical holdings changed.
- The run provenance digest remains the original digest, but no read path marks
  it stale.

Classification: P0. The system should either block import confirmation while
sync is active, mark the resulting snapshot stale if current holdings changed,
or both.

## 8. Holdings Fingerprint/Digest Analysis

Existing digest is suitable as the foundation:

- Deterministic and order-independent.
- Based on canonical instrument, quantity, and average price.
- Already used to reject stale import previews.
- Already stored in sync-run provenance.

Recommendation: PS-P6B should promote this into explicit read-model semantics:
`snapshot_holdings_digest`, `current_holdings_digest`,
`portfolio_changed_since_sync`, and stale reason/timestamps. No schema migration
is strictly required if sync-run/snapshot provenance remains JSON, but DTO/API
fields should make the comparison first-class.

## 9. Empty Portfolio / Clear Portfolio

Current behavior:

- Empty files and no-data files are parser errors.
- Confirmation rejects imports with no uploaded holdings.
- This correctly prevents interpreting a blank upload as "remove everything."

Recommendation: add an explicit Clear Portfolio design only if the owner wants
regular all-clear operation. It should be a separate action with strong
confirmation, audit/reconciliation rows for removals, no fabricated sale
transactions, no realized P&L, and no SELL/EXIT interpretation.

Classification: P1 if the owner needs the operation; otherwise DEFER.

## 10. Import UX Review

Strengths:

- Upload makes clear required columns are Symbol, Qty, Avg Price.
- Preview separates invalid, unresolved, ambiguous, duplicate rows.
- Reconciliation shows ADDED/UPDATED/REMOVED/UNCHANGED counts.
- REMOVED is explained as absent from the uploaded current-holdings snapshot,
  with no sale inferred.
- Confirmation note says holdings are replaced and no trades or realized P&L are
  inferred.
- Stale preview errors are handled with an upload-again prompt.

Gaps:

- P1: after confirm, the success alert does not explicitly say analysis is stale
  until Sync runs.
- P2: import history does not expose reconciliation details inline.

## 11. Sync UX Review

Strengths:

- Sync button disables while local polling says sync is active.
- API is single-flight for active sync runs.
- Progress includes processed count and current symbol.
- SUCCESS/PARTIAL/FAILED terminal states are surfaced.
- Previous completed snapshot is retained after failed sync.

Gaps:

- P0: sync result is not compared against current holdings digest.
- P1: failed-symbol details are in API `per_symbol`, but not rendered in the
  dashboard.
- P1: PARTIAL tells the owner counts, but not which symbols failed or why.
- P2: expected analysis as-of and refresh-required symbols are not visible in
  normal UI.

## 12. PARTIAL / FAILED UX

The API contains enough structured failure information for a minimal UX:

- run status
- succeeded/failed counts
- `per_symbol` with status, instrument id, errors, unavailable, refresh flags
- failed rows with `failed_components` and unavailable fields

Dashboard gap: it does not render a failed-symbol summary or row details panel.
The table may show failed rows with `UNAVAILABLE` / `WATCH`, but the reason is
not obvious without inspecting provenance.

Classification: P1.

## 13. Summary/Valuation Coverage

Server summary is authoritative. `PortfolioSnapshotSummary.from_rows()` returns
null current value / total P&L / total P&L percent if any row lacks valuation,
so it does not fabricate a complete portfolio P&L on incomplete coverage.

Dashboard fallback computes total investment from current holdings only when no
snapshot exists. That is acceptable for cost basis, but once a stale snapshot is
present the UI currently uses the stale snapshot summary instead of clearly
showing current holdings investment versus stale analysis.

Recommendation: add valuation coverage and stale-analysis state in PS-P6B.

## 14. Snapshot History

Current API has sync history and latest snapshot only:

- `GET /api/v1/my-portfolio/sync`
- `GET /api/v1/my-portfolio/sync/{sync_run_id}`
- `GET /api/v1/my-portfolio/snapshot`

There is no historical snapshot retrieval endpoint by sync id, and the
dashboard does not expose sync history.

Minimum useful capability: show recent sync runs with status/counts/timestamps
and allow viewing the latest snapshot only. Historical row-level snapshot
retrieval can be DEFER unless the owner wants audit drill-down.

## 15. Import History

Current import history shows uploaded timestamp, filename, status, row counts,
and confirmed timestamp. It does not show reconciliation changes inline, but a
reconciliation endpoint exists.

Recommendation: keep import history lightweight. Add a small "changes" affordance
only if PS-P6B adds a details panel.

Classification: P2.

## 16. Row Failure/Unavailable Semantics

The API can distinguish:

- valuation failure via null price/current value/P&L and failed components
- stale Decision evidence via unavailable fields and interpretation reasons
- intentionally-null methodology fields via unavailable fields and reason codes
- interpreted but cautionary rows via Status/Next Action

Dashboard gap: all nulls mostly render as `—` or "Not available", so Support 1
methodology-unavailable can look similar to Last Price data-failed.

Classification: P1 for a minimal explanation/details interaction.

## 17. Interpretation Explainability

PS-P5B persists deterministic reason codes and compact evidence acceptance
flags. Dumping raw codes into the table would be too noisy.

Recommendation: add a row details/tooltip pattern that translates a small
allowlist of reason codes into owner-facing explanations:

- why Status is CAUTION/AT_RISK/UNAVAILABLE
- why Next Action is WATCH/HOLD/ADD/EXIT
- why ADD is not available
- why a field is intentionally unavailable

Classification: P1.

## 18. 20-Column Table Usability

Strengths:

- Horizontal scroll exists.
- Symbol, Qty, and Avg Price are sticky.
- Numeric fields use monospace and INR formatting.
- Header row is sticky.

Gaps:

- P1: Status and Next Action are plain text in snapshot rows, not visually
  prioritized.
- P1: failed/unavailable reason details are not accessible.
- P2: 2100px minimum width is workable on desktop but heavy for narrow screens.
- P2: long text states may need width constraints once reason/details UI exists.

## 19. Sorting/Filtering

No sorting/filtering exists in the My Portfolio table.

Recommendation: for 20-50 holdings, minimum production-ready sorting is enough:
Symbol, P&L %, Status, Next Action, Last Review. Filtering can be limited to
Status, Next Action, and failed/unavailable rows.

Classification: sorting P2, filtering P2 unless owner regularly carries 50+
holdings.

## 20. Freshness UX

Dates currently visible:

- Latest Import
- Last Synced
- Market data through
- Price As Of per row
- Last Review per row

Dates not clearly surfaced:

- expected analysis as-of
- Decision as-of
- holdings digest/currentness
- snapshot holdings state vs current holdings state

Recommendation:

- Header: Latest Import, Last Synced, Market data through, stale/current badge.
- Row: Price As Of and Last Review.
- Details/provenance: Decision as-of, expected analysis as-of, interpretation
  version/reasons.

## 21. Daily Owner Workflow

Current UX supports the happy path:

- no holdings changes -> open My Portfolio -> Sync -> review
- holdings changed -> upload -> preview -> confirm -> Sync -> review

Friction: after confirm, the interface does not strongly move the owner from
"holdings updated" to "analysis stale; sync next."

Recommendation: keep Sync manual, but add a prominent stale-analysis banner and
make Sync the primary next action after confirmation.

## 22. Performance

Likely behavior:

- 20 holdings: acceptable.
- 50 holdings: acceptable, with visible progress.
- 100 holdings: operationally plausible but may reveal N+1 query costs.

Potential risks:

- `_analyze_holding()` performs per-holding instrument, candle, and
  EntryQualification lookups.
- Scoped validation may dominate cost when many symbols require refresh.
- Dashboard renders a full 20-column table in one pass; 100 holdings should
  still be manageable, but row details/sorting should stay simple.

Classification: P2 monitoring/optimization, not P0 without evidence.

## 23. Concurrency

Current protections:

- Import confirmation is atomic.
- Stale previews are rejected using base holdings digest.
- Sync start is single-flight for active sync runs.
- Interrupted sync runs are marked failed on recovery.

Missing protections:

- Import confirmation during active sync is not blocked.
- Sync run completion is not checked against current holdings digest.
- Latest snapshot read is not checked against current holdings digest.

Classification: P0 for misleading state; PS-P6B should resolve policy.

## 24. Restart/Recovery

Current behavior:

- On service reads/start, active queued/running sync runs without a live worker
  are marked FAILED/INTERRUPTED.
- Previous good SUCCESS/PARTIAL snapshot remains available.
- Browser refresh reloads holdings/imports/latest snapshot.

Gap: after restart, latest snapshot may still be stale relative to holdings and
will not be flagged.

Classification: P1 after digest P0 is solved.

## 25. API Contract Review

Current My Portfolio API surface:

- `POST /api/v1/my-portfolio/imports`
- `GET /api/v1/my-portfolio/imports`
- `GET /api/v1/my-portfolio/imports/{import_id}`
- `POST /api/v1/my-portfolio/imports/{import_id}/confirm`
- `GET /api/v1/my-portfolio/holdings`
- `GET /api/v1/my-portfolio/imports/{import_id}/reconciliations`
- `POST /api/v1/my-portfolio/sync`
- `GET /api/v1/my-portfolio/sync`
- `GET /api/v1/my-portfolio/sync/{sync_run_id}`
- `GET /api/v1/my-portfolio/snapshot`

Gaps:

- P0: latest snapshot DTO lacks current-vs-snapshot holdings state.
- P1: no active/stale analysis summary endpoint; latest snapshot must infer from
  separate holdings/import/sync calls.
- P2: no historical snapshot-by-sync endpoint.

## 26. Upload/Input Hardening

Current protections:

- 2 MB max import size.
- 2,000 max rows.
- CSV and XLSX only.
- Empty/malformed/unsupported files rejected.
- Required logical columns enforced.
- Duplicate logical columns rejected.
- Blank symbol, invalid quantity, invalid avg price rejected.
- Quantity must be positive integer.
- Avg price must be positive finite Decimal.
- Duplicate canonical instruments rejected.
- XLSX reads first usable worksheet through XML parsing, not formula execution.

Gaps:

- P1: limits are hardcoded; owner may want config-based limits.
- P1: no explicit filename sanitization policy beyond treating filename as text.
- P2: no user-facing explanation of size/row limits before upload.
- P2: extreme but valid Decimal precision is not capped beyond Decimal
  finiteness/positivity.

## 27. Auditability

Trace is mostly present:

- file hash in import provenance
- preview rows and row-level errors
- confirmed reconciliation rows
- canonical holdings source import/row
- sync run id and provenance
- validation run id
- row freshness/provenance
- Decision id
- interpretation version/reasons/evidence flags

Missing audit link: latest snapshot does not explicitly state whether its
holdings digest matches current holdings. Historical snapshot row retrieval is
also missing from API/UI, but lower priority than currentness.

## 28. Production-Readiness Gaps

P0:

- Snapshot can silently represent old holdings after a later confirmed import.
- Sync can finish for holdings state A after holdings state B is confirmed, then
  appear current.
- Latest snapshot API lacks first-class current-vs-snapshot digest/currentness.

P1:

- Dashboard does not strongly prompt Sync after holdings confirmation.
- PARTIAL/FAILED symbol reasons are not visible enough.
- Row-level unavailable/failure semantics are not explainable in normal UI.
- Status/Next Action critical states lack visual priority.
- Clear Portfolio decision remains unresolved if the owner needs it.
- Upload limits are hardcoded and not visible to the owner.

P2:

- Sorting/filtering.
- Sync history UI.
- Import history reconciliation drill-down.
- Historical snapshot retrieval.
- Valuation coverage display.
- Performance optimization for larger portfolios.

DEFER:

- Automatic scheduled Sync.
- Rich historical analytics.
- Broker integration/execution.
- Transaction ledger/lot accounting.
- New interpretation methodology.

## 29. Proposed PS-P6B Scope

Smallest coherent implementation milestone:

1. Add holdings digest/currentness read model:
   `snapshot_holdings_digest`, `current_holdings_digest`,
   `portfolio_changed_since_sync`, and stale reason/timestamps.
2. Mark latest snapshot stale when current holdings digest differs from the
   sync-run digest.
3. Add dashboard stale-analysis banner after import confirmation and on load.
4. Add import/sync concurrency policy:
   either block import confirmation during active sync or allow it while marking
   any in-flight result stale; owner decision required.
5. Render minimal PARTIAL/FAILED symbol details from `per_symbol` and row
   provenance.
6. Add minimal owner-facing explanation/details for Status/Next Action and
   unavailable/failure fields.

Do not include sorting/filtering, historical snapshots, Clear Portfolio, or
scheduled sync unless owner explicitly pulls them into PS-P6B.

## 30. Deferred Enhancements

- Clear Portfolio action.
- Historical snapshot-by-sync endpoint and UI.
- Sync history drill-down.
- Sorting/filtering beyond minimal table hardening.
- Configurable upload limits.
- Scheduled Sync.
- Rich explanation integration with Decision Brief.
- Valuation coverage card if stale/currentness banner already proves sufficient.

## 31. Owner Decisions Required

1. Stale snapshot visibility: should old snapshot remain visible but clearly
   marked stale? Recommended: yes.
2. Holdings digest/fingerprint: approve using current `portfolio_holdings_digest`
   as the canonical comparison? Recommended: yes.
3. Import while Sync is running: block confirmation or allow and mark in-flight
   sync stale? Recommended: block confirmation for PS-P6B simplicity.
4. Sync while import confirmation is occurring: rely on repository lock or add
   explicit guard? Recommended: add explicit guard/error semantics.
5. Clear Portfolio: implement explicit action now or defer? Recommended: defer
   unless operationally needed immediately.
6. PARTIAL summary semantics: keep portfolio P&L null when any valuation missing?
   Recommended: yes.
7. Snapshot history exposure: latest-only plus sync history, or historical row
   retrieval? Recommended: latest-only for PS-P6B.
8. Explanation/details UX: tooltip/details panel for reason codes? Recommended:
   minimal row details panel.
9. Sorting/filtering scope: include in PS-P6B? Recommended: defer unless table
   usability is painful with owner’s real holding count.
10. Upload limits/input hardening: keep hardcoded or make configurable?
    Recommended: document now, configure later.
11. Retry semantics: should retry use manual Sync only? Recommended: yes;
    failed/partial states should make retry obvious without auto-running.
