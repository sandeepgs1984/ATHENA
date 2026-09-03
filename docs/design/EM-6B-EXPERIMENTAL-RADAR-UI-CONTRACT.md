# EM-6B — Experimental EMR API & Dashboard Contract

**Status:** Implementation complete; EM-6B.1 clock-coherence correction
applied. Ready for owner closure review.
**Depends on:** EM-6A (`OWNER APPROVED / CLOSED`, 2026-09-03).
**Does not:** modify the EMR scanner/model/research methodology, add
scanner scheduling, read FINAL_TEST, touch canonical ATHENA/DarvaX/
ID-track code.

**EM-6B.1 correction (2026-09-03):** owner review found the router
independently called `datetime.now(tz=timezone.utc)` for
`ResponseMeta.as_of`, separate from the service's own `request_as_of`
used for scan-age (§8 below, as originally written, described the
intended single-clock behavior but the router did not actually implement
it). Corrected: the router now captures exactly one clock read (a new
injectable `get_emr_request_clock` dependency) and passes it explicitly
into the service, reusing the identical value for `ResponseMeta.as_of` —
in both the populated-scan and no-scan branches. See
`IMPLEMENTATION_SUMMARY.md`'s EM-6B.1 entry for full detail. §8 below now
reflects the corrected, actually-implemented behavior.

## 1. Scope

Two responsibilities only: (A) an isolated, read-only HTTP endpoint
exposing EM-6A's presentation contract; (B) a permanently "Experimental"
dashboard panel consuming it. Observational research tooling — not a
trade recommendation, entry, alert, or execution system, and not a
replacement for ATHENA Decisions or EntryQualification.

## 2. Architecture audit (before writing code)

- **Isolation-mount template**: `api/darvax_mount.py` — a full opt-in
  sub-application with its own auth-delegation seam. Reused the
  *principle* (one file is the only place that knows the satellite
  exists; narrow, auditable coupling), not the sub-app mechanism itself
  — EM-6B is a single read-only endpoint, not a standalone product
  surface, so a standard `api/v1/routers/*.py` router (the convention
  every other v1 feature already uses) is the right-sized isolation unit.
- **API composition**: `api/v1/router.py` aggregates per-feature routers;
  `api/dependencies.py` provides per-request service construction from
  `request.app.state` (test-injectable); `api/v1/dtos/base.py`'s
  `AthenaResponse[T]`/`ResponseMeta` is the single response envelope
  every v1 endpoint already uses.
- **Auth**: every existing v1 GET route gates on
  `Depends(RequirePermission(Permission.READ))` — reused verbatim.
- **Dashboard structure**: `tab-market` (Market Intelligence) already
  hosts a collapsed-by-default `<details class="card ...">` secondary
  panel ("Trading Calendar & Events") — the exact precedent for a
  visually-secondary, non-primary panel. Reused directly for the EMR
  panel rather than inventing new UI chrome.
- **Refresh/fetch pattern**: `apiRequest(url, options)` (returns the
  parsed `AthenaResponse` envelope or throws `{status, data}`);
  `formatDecisionTime`/`formatDecisionPrice` (`05-utils.js`) for
  IST-timezone timestamp and ₹-formatted price rendering — reused
  verbatim, no new date/currency formatting invented.
- **JS/CSS assembly**: `DASHBOARD_JS_PARTS` (app.py) concatenates
  numbered `js/*.js` files in order; `dashboard.css` `@import`s numbered
  `css/*.css` files. New files follow the existing `NNb-*` naming
  precedent (`08b-my-portfolio.js` after `08-portfolio.js`) →
  `09b-emr-experimental.js`/`06b-emr-experimental.css`.

## 3. Isolation-mount decision

A dedicated router (`api/v1/routers/emr.py`) + DTO module
(`api/v1/dtos/emr.py`) + service (`api/v1/services/emr_presentation_service.py`)
— the only three files in the entire ATHENA API layer that import from
`athena.explosive_move`, and only from `athena.explosive_move.live.presentation`
(EM-6A). None imports `athena.decision`/`athena.risk`/`athena.portfolio`/
`athena.scoring`/`athena.intraday`/`athena.darvax`/ATHENA's own
`SqliteRepository` — verified by AST import-scan tests
(`test_router_and_service_import_nothing_canonical_or_darvax`), not just
grep, so a legitimate docstring mention of a forbidden module's name
never false-positives the check.

## 4. Files created/modified

**Created**: `src/athena/api/v1/routers/emr.py`,
`src/athena/api/v1/dtos/emr.py`,
`src/athena/api/v1/services/emr_presentation_service.py`,
`src/athena/api/static/js/09b-emr-experimental.js`,
`src/athena/api/static/css/06b-emr-experimental.css`,
`tests/api/v1/test_emr_router.py`,
`docs/design/EM-6B-EXPERIMENTAL-RADAR-UI-CONTRACT.md`.

**Modified**: `src/athena/explosive_move/live/presentation.py` (one new
additive composition function + one new additive path helper — no
existing function changed), `src/athena/api/app.py` (`DASHBOARD_JS_PARTS`
+1 entry), `src/athena/api/dependencies.py` (+1 provider),
`src/athena/api/v1/router.py` (+1 router registration),
`src/athena/api/v1/dtos/__init__.py` (+1 re-export block),
`src/athena/api/static/dashboard.css` (+1 `@import`),
`src/athena/api/static/js/03-app-shell.js` (+1 guarded call in the
existing `market` tab dispatch), `src/athena/api/static/index.html` (new
`<details>` panel + version-string bump), plus two pre-existing tests
whose hardcoded dashboard version-string assertions needed updating to
match the bump (`test_dashboard_hosting.py`,
`test_decision_chart_release_gate.py`).

## 5. API endpoint

`GET /api/v1/emr/experimental/touch-10-radar?session_date=<optional>` —
authenticated (`Permission.READ`), read-only, no mutation endpoint of any
kind exists in this router.

## 6. API response contract

`AthenaResponse[EmrTouch10RadarDTO]` — `label`, `disclaimer`,
`scan` (nullable `EmrScanContextDTO`), `scan_age` (nullable
`EmrScanAgeDTO`), `touch_10` (tuple of `EmrCandidateDTO`), `coverage`
(nullable `EmrCoverageDTO`). Every field name is EM-5/EM-6A's own
research-contract vocabulary — nothing renamed into canonical ATHENA
terms.

## 7. Single-response/one-run coherence — implementation

New EM-6A-owned (not touching any existing function)
`build_touch_10_radar_snapshot()` in `presentation.py`: resolves exactly
**one** `EmrScanSnapshotInfo`, freezes its `run_id`, then derives both
`top_touch_10_candidates` and `coverage_summary` from that *same* frozen
`run_id` — never two independent latest-scan lookups for one response.
Mutation-verified: temporarily hardcoded the coverage lookup to a
different, stale `run_id` and confirmed the expected test failure
(`3 != 1` — the wrong run's candidate count leaking through), then
reverted.

## 8. Request-time clock semantics (corrected — EM-6B.1)

The **router** owns the single clock read for the whole request, via a
new injectable dependency, `get_emr_request_clock` (`app.state.emr_clock`
override for tests, real `datetime.now(tz=timezone.utc)` in production —
mirroring this repo's established injected-clock convention:
`OwnerValidationPipeline.persistence_clock`, `scanner.py`'s own `now`
parameter). Captured **exactly once** per request
(`request_as_of = clock()`), then passed explicitly into
`EmrPresentationService.get_touch_10_radar(request_as_of=...)` — which
uses it directly for `describe_scan_freshness()` rather than calling its
own constructor-injected `self._clock()` — and reused, unchanged, for
`ResponseMeta.as_of`. Applies identically in the populated-scan and
no-scan branches: the router's one clock read happens before the service
call either way. `EmrPresentationService.__init__`'s own `clock`
parameter remains only as a fallback for a caller that invokes the
service directly without supplying `request_as_of` — never exercised by
the real HTTP path.

**Pre-EM-6B.1 defect (now corrected):** the original implementation had
the service call its own injected clock internally while the router
separately called `datetime.now(tz=timezone.utc)` for `ResponseMeta.as_of`
— two independent clock reads for one response, violating this exact
invariant. See `IMPLEMENTATION_SUMMARY.md`'s EM-6B.1 entry for the full
root-cause/fix narrative.

## 9. No-scan semantics

`scan is None` → `EmrTouch10RadarDTO(scan=None, scan_age=None,
touch_10=(), coverage=None)`, HTTP 200, disclaimer text "No completed EMR
scan is available. The Experimental radar displays persisted scanner
output only." Never creates `db/emr.db`, never triggers the scanner,
never returns 500 for this legitimate state.

## 10. Zero-candidate semantics

Distinct from §9: a real `COMPLETE` scan exists (`scan` populated) but
`touch_10 == ()` — the UI renders "No ranked TOUCH-10 candidates in this
scan," never conflated with "no completed scan available."

## 11. Candidate semantics

Mechanically mapped from EM-6A's `EmrCandidateView` — `rank`,
`calibrated_probability`, `deterministic_score` all `None` (not `0`) when
genuinely absent; `probability_language`/`data_freshness`/`feasibility`/
`state`/`state_reason` passed through verbatim.

## 12. TOUCH-10 semantics

Exactly `family="TOUCH", threshold_percent=10` — reused unchanged from
EM-6A's own `top_touch_10_candidates()`. UI header reads "TOUCH 10%
Research Candidates," never "10% probability stocks" or "top 10 stocks."

## 13. Probability presentation

`74.0% (model probability)` for `probability_language ==
"calibrated_probability"`, `X% (raw estimate)` otherwise — never "72%
chance of profit" or any trading-success framing. `None` renders as `—`,
never `0%` (verified visually: NSE:TCS's `null` `calibrated_probability`
rendered as `—` in the live check, §38).

## 14. Deterministic-score presentation

Rendered under a column literally labelled "Evidence Score," 3-decimal
fixed display — never labelled confidence/rating/canonical score.

## 15. Coverage presentation

`Evaluated: N / Ranked: N / Not ranked: N` compact strip + a
`reason: count` line only when `unranked_reason_counts` is non-empty
(observed live: "Not-ranked reasons — STALE_DATA: 1").

## 16. Evidence-completeness presentation

Rendered as `known / total` in an "Evidence Coverage" column (e.g. `27 /
28`) — `None` renders `—`, never `0/0`.

## 17. Candidate data-freshness presentation

Rendered per-row in its own "Data Freshness" column (`FRESH`/`STALE`,
verbatim persisted value) — visually and semantically distinct from §20
below.

## 18. Scan-age presentation

Rendered in the scan-meta header strip as "Scan age: N min ago" (derived
from `describe_scan_freshness`'s `age_minutes`, no FRESH/STALE label
applied) — kept in a completely separate DOM region from per-candidate
`data_freshness`, satisfying the owner's explicit "do not merge both into
one freshness badge" instruction.

## 19. Checkpoint-price semantics

Rendered as "Checkpoint Price" (never "Entry Price"), with
`checkpoint_price_semantic` shown alongside in parentheses (observed
live: `₹1,512.35 (FIRST_OBSERVED_POST_CHECKPOINT_TRADE)`).

## 20. Model/calibration metadata presentation

Collapsed inside a secondary `<details>` ("Model & scan metadata") below
the candidate table — run ID, model version, eligible/ineligible counts —
never mixed into the primary candidate-name/rank hierarchy.

## 21. Experimental label/disclaimer

Rendered at the top of every populated and empty response: an amber
(never green/red) badge reading "Experimental" plus the disclaimer text.
Verified in the live browser check that the badge color token
(`--warning`) is deliberately neither the "success"/green nor
"danger"/red token used elsewhere in the dashboard for approved/rejected
states.

## 22-23. Dashboard placement / UI structure

Inside the existing Market Intelligence tab (`tab-market`), as a
collapsed-by-default `<details>` panel directly after "Trading Calendar &
Events" — no new top-level nav item, no redesign of any other Market
Intelligence section. Visual hierarchy: Experimental badge → disclaimer →
scan/session/checkpoint/age → TOUCH-10 table → coverage → metadata
(secondary/collapsed).

## 24. Loading state

`emr-loading-state` div shown immediately on tab activation and on every
manual refresh, replaced only once the fetch resolves (success or
error) — never a flash of "no candidates" before the first response
lands.

## 25. Empty states

Two distinct empty-state renderings (§9 vs. §10 above), each with its own
message — never a shared generic "no data" string.

## 26. Error state

`emr-error-state` (red/danger-colored) shown only on a genuine fetch
failure (non-2xx or thrown exception) — never used for the legitimate
no-scan empty state.

## 27. Provider/network impact

None. `test_router_and_service_source_have_no_provider_or_scanner_calls`
greps both new API-layer modules for provider/network terms and the
literal `run_scan_cycle(` call pattern — none found.

## 28. Scanner/scheduler impact

None. No "Run Radar"/"Refresh Scanner"/"Scan Now" control exists anywhere
in the new JS — the refresh button only re-issues the same read-only
`GET`. No cron/scheduler/background-task registration added anywhere.

## 29. FINAL_TEST impact

None. Neither the router, service, nor the one new `presentation.py`
composition function reference `partitions.py` or any research dataset
path.

## 30. Canonical ATHENA impact

None. Verified by AST import scan (§3) — zero references to
Scoring/Decision/Risk/TradePlan/EntryQualification/canonical
`SqliteRepository` anywhere in the three new API-layer files.

## 31. ID-track impact

None. Zero references to `entry_qualifications`, `SessionContext`,
`IntradaySignalSet`, or any ID-6E artifact.

## 32. DarvaX impact

None. Zero DarvaX import; no shared score/candidate list; DarvaX code
untouched.

## 33. Production DB impact

None. `db/emr.db` remains absent in production (unchanged from EM-6A);
`db/athena.db` untouched by this milestone's own actions (its checksum
legitimately changes over time from the live, already-running,
independent production server's own shadow accumulation — unrelated to
this milestone).

## 34. Real-data acceptance result

**Still `REAL_DATA_ACCEPTANCE_NOT_AVAILABLE`** — `db/emr.db` was
re-confirmed absent from the real repository both before and after this
milestone's work. Per explicit instruction, it was **not** created for
acceptance purposes. All populated-state verification instead used an
isolated scratch database (see §35-36) — never the production one.

## 35. API tests

15 new tests in `tests/api/v1/test_emr_router.py`, covering all 15
owner-required categories (auth required; missing db file; no-COMPLETE
scan; coherent scan with ranked candidates; zero-ranked-candidates within
a real scan; coverage with reasons; null probability preserved; timezone
preservation; no cross-scan mixing; read-only-never-mutates across 3
repeated requests; no provider/scanner call source-scan; no canonical/
DarvaX import via AST scan; no trade-authorizing terminology anywhere in
a populated response body; a corrupt (but existing) database file
surfacing as a real >=500 error, never silently "no candidates"; and
`session_date` query-param scoping). All against an isolated `tmp_path`
fixture database via `client.app.state.emr_db_path` — never
`db/emr.db`/`db/athena.db`.

## 36. UI tests/verification

No JS test/lint tooling exists in this repository (vanilla JS, no build
step, per ADR-004) — verified instead via direct browser rendering
against an **isolated scratch server**: a throwaway `uvicorn` instance on
port 8100 (never the live production instance on port 8000, which was
never touched — confirmed running, unchanged, throughout), pointed at a
scratch `ATHENA_CONFIG_DIR` and a scratch `ATHENA_EMR_DB_PATH` (a
locally-seeded fixture database, 3 candidates: 1 fully-ranked with a real
calibrated probability, 1 ranked with a `null` probability, 1 unranked
with `STALE_DATA`), using the established `ATHENA_SINGLE_USER=true` +
empty `ATHENA_OWNER_PASSWORD_HASH` local-verification bypass (the same
pattern already used for DarvaX UI verification in this repo). Verified
visually: Experimental badge (amber, distinct from success/danger
colors), disclaimer text, session/checkpoint/last-scan-time/scan-age all
rendered, TOUCH-10 table with correct columns, `null` probability
rendered as `—` (not `0%`), `STALE` data-freshness shown in muted color
distinct from the scan-age field, coverage strip with the `STALE_DATA`
reason breakdown, checkpoint price with its semantic annotation, and the
refresh button re-fetching (scan age advanced from "5 min ago" to "7 min
ago") without collapsing the panel. Scratch database confirmed unmutated
(1 scan run, 3 candidates, unchanged) after all interaction. Scratch
server stopped after verification; scratch files live only under the
session scratchpad, never in the repository.

## 37. Isolation tests

The pre-existing `tests/explosive_move/test_em5_isolation.py` (AST scan
over every file under `explosive_move/`) automatically covers the EM-6A
`presentation.py` additions unmodified. New, API-layer-specific AST-based
isolation tests were added in `test_emr_router.py` (§35) since the
existing EMR-side isolation test does not scan `src/athena/api/`.

## 38. EM-6A regression

`tests/explosive_move/test_em6a_presentation.py`: 26/26 passed (24
original + 2 new for the EM-6B composition addition — one coherence test,
one empty-state test — both added without modifying any pre-existing
test).

## 39. EM-5 regression

`tests/explosive_move/` (full directory, including EM-5 live/store/
isolation/no-model-learning suites): 423 passed, 0 failed, 1 pre-existing
skip.

## 40. Full-suite result

**3,231 passed, 0 failed, 1 pre-existing skip.**

## 41. JS lint/tests

Not applicable — no JS lint/test command exists in this repository.

## 42. Ruff

Clean across all 12 touched/created Python files.

## 43. `git diff --check`

Clean (exit 0).

## 44. Known limitations

Same as EM-6A: no production shadow evidence exists for this endpoint yet
(`db/emr.db` doesn't exist in production; no scheduler trigger exists or
was added). `logit_contributions_json` (per-term evidence explanation)
remains unexposed, unchanged from EM-6A's own deferral — the dashboard
currently shows "Evidence Score" (deterministic) and "Model Probability"
(calibrated) but not a per-feature contribution breakdown; addable later
without a schema change if the owner wants it. No cross-checkpoint
history/trend view was built (explicitly out of scope per instruction).

## 45. Recommendation

Bring this contract to the owner for review. EM-6 overall may be closed
once this review completes; EM-7 (isolated shadow validation) remains a
separate, not-yet-authorized milestone.
