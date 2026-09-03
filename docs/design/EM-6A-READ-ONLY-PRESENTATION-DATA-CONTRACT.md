# EM-6A — Read-Only EMR Presentation Data Contract

**Status:** Implementation complete. Ready for owner review.
**Depends on:** EM-5 (`OWNER APPROVED / CLOSED`, 2026-09-01); EM-6 discovery
(`docs/research/EM-6-DISCOVERY-AND-MODELING-CONTRACT.md`, owner-ratified
2026-09-03).
**Does not:** run the scanner, fit/refit any model, read FINAL_TEST, call
any provider, write to `db/emr.db` or `db/athena.db`, add an HTTP route,
touch any dashboard file, or touch canonical ATHENA/DarvaX code.

## 1. Consumer

The future, not-yet-authorized EM-6B dashboard (a permanently
"Experimental" Market Intelligence tab). No consumer exists yet — this
contract is built and tested in isolation, callable as a plain Python
function.

## 2. Source

`db/emr.db` only — `emr_scan_runs` and `emr_candidates`
(`EMR_SCHEMA_VERSION = 1`, `src/athena/explosive_move/store/schema.py`,
frozen, unmodified). Never `db/athena.db`, never TRAIN/VALIDATION/
CALIBRATION/FINAL_TEST research datasets, never live provider calls.

## 3. Existing EM-5 seam audit — critical finding

`docs/design/EM-5-LIVE-SCANNER-CONTRACT.md` §8/§17 **describe**
`top_candidates(session_date, checkpoint, family, threshold, n)` and
`top_touch_10_candidates(session_date, checkpoint, n)` as functions EM-5
built for EM-6 to call. **A repo-wide search found neither function
implemented anywhere** — they exist only as design-doc prose. This is not
a wrapper milestone; EM-6A is the first actual implementation of that
described seam, built directly against the real, frozen
`EmrRepository`/schema (composition, not duplication — see §4).

## 4. UI-requirement / source matrix

| # | UI requirement | Existing source | Already available? | New query needed? |
|---|---|---|---|---|
| 1 | Latest available scan | `emr_scan_runs` (no "latest" query existed) | Partially (schema yes, query no) | **Yes** — `latest_scan_snapshot()` |
| 2 | When evaluated | `emr_scan_runs.started_ts`/`finished_ts` | Yes | No |
| 3 | Which checkpoint | `emr_scan_runs.checkpoint` | Yes | No |
| 4 | Freshness/staleness | timestamps present, no derivation existed | Partially | **Yes** — `describe_scan_freshness()` (pure, `as_of`-explicit) |
| 5 | Highest-ranked candidates | `emr_candidates.rank` (existing `list_candidates()` returns all, unfiltered/unlimited) | Partially | **Yes** — `top_candidates()` |
| 6 | TOUCH-10 candidates | Same table, no dedicated query | Partially | **Yes** — `top_touch_10_candidates()` |
| 7 | Calibrated probability/evidence per candidate | `calibrated_probability`, `probability_language`, `logit_contributions_json` | Yes | No |
| 8 | Model family/threshold/version context | `family`, `threshold_percent`, `em4b_model_version`, `em4d_calibration_version` | Yes | No |
| 9 | Evidence completeness | `evidence_completeness_known`/`_total` | Yes | No |
| 10 | Why something is unavailable | `feasibility_reason`, `state_reason` per row; no aggregation existed | Partially | **Yes** — `coverage_summary()` |
| 11 | No scan/candidate evidence | No explicit "no data" contract existed | No | **Yes** — empty-state return values (`None`/`()`), not a new query |
| 12 | Staleness relative to session/market | Raw timestamps only | Partially | **Yes** — `describe_scan_freshness()` |

Only 5 genuinely new functions were needed; everything else reuses
already-persisted columns directly, exposed through typed views.

## 5. Gaps actually implemented

`src/athena/explosive_move/live/presentation.py` (new file, 279 lines):
`latest_scan_snapshot()`, `top_candidates()`, `top_touch_10_candidates()`,
`coverage_summary()`, `describe_scan_freshness()`,
`build_experimental_snapshot()`. No other file modified.

**Read-only connection design decision:** rather than route through
`EmrRepository` (a read-*write* connection, since it also owns
`save_scan_run`/`save_candidates`/`initialize`), this module opens its
own SQLite connection with `mode=ro`+`PRAGMA query_only=ON` — the same
pattern the ID-track's own `id6e_replay_shadow_validation.run_shadow_audit`
established. This gives a **structural**, SQLite-level read-only
guarantee (a write attempt raises `sqlite3.OperationalError`, proven in
`test_presentation_connection_is_sqlite_read_only_mode`), not merely a
convention of "only calling the read methods."

## 6. Presentation model/structure

Five frozen dataclasses (`@dataclass(frozen=True, slots=True)`):
`EmrScanSnapshotInfo`, `EmrCandidateView`, `EmrCoverageView`,
`EmrScanFreshness`, `EmrExperimentalSnapshot`. No generic dict blob —
typed, explicit-optionality fields throughout, matching this repo's
established domain-object convention.

## 7. Latest-scan semantics

"Latest scan" = the `emr_scan_runs` row with `status='COMPLETE'` (never
`RUNNING`/`SKIPPED_SESSION_TYPE`/any other status) with the greatest
`started_ts`, optionally scoped to one `session_date`. `run_id` is
deterministically derived by the scanner itself
(`em5-scan-<sha256(session_date, checkpoint, universe, model_version)>`)
— re-running the identical checkpoint upserts the same row rather than
creating ambiguity.

## 8. Scan/checkpoint coherence

Every candidate this module returns is scoped to one explicit `run_id`,
always sourced from this module's own `latest_scan_snapshot()` (or a
caller-supplied `run_id`) — never from an independent `MAX(created_ts)`
over `emr_candidates`. Mixing candidates from two different scans into
one apparent snapshot is structurally unreachable, proven by
`test_candidates_from_a_different_run_never_leak_into_top_candidates` and
`test_build_experimental_snapshot_only_ever_uses_its_own_latest_run_id`.

## 9. Candidate query semantics

`top_candidates(db_path, run_id, family, threshold_percent, limit)` —
`rank IS NOT NULL` only, ordered `rank ASC`, `LIMIT` applied at the SQL
layer. No probability/score threshold anywhere; `limit` is the only
caller-supplied cutoff.

## 10. TOUCH-10 semantics

`top_touch_10_candidates()` is exactly `family="TOUCH",
threshold_percent=10` — one of the 18 frozen (family, threshold)
combinations, per `docs/design/EM-5-LIVE-SCANNER-CONTRACT.md` §8. Not
"10% probability," not "top 10 stocks," not a 10-minute target — proven
by `test_touch_10_is_exactly_touch_family_ten_percent_threshold` (which
seeds `TOUCH`@10%, `TOUCH`@20%, and `CLOSE`@10% candidates and confirms
only the first is returned).

## 11. Ranking/tie-break semantics

Reused verbatim — no re-ranking. `rank` is read directly from the
already-persisted column (assigned once, at scan time, by EM-5's own
frozen `rank_candidates()`/EM-4C tie-break convention). This module never
recomputes or re-sorts by score.

## 12. Calibration context

Exposed as persisted: `calibrated_probability`, `deterministic_score`,
`probability_language` (`"calibrated_probability"` vs. `"raw_estimate"`,
already correctly set by the scanner per contract §7),
`em4b_model_version`, `em4d_calibration_version`. No calibration fitting,
no CALIBRATION/FINAL_TEST dataset access anywhere in this module.

## 13. Evidence context

`evidence_completeness_known`/`evidence_completeness_total` and the
persisted `checkpoint_price`/`checkpoint_price_semantic` are exposed as-is.
`logit_contributions_json` (per-term evidence explanation) exists in the
schema but was **not** added to `EmrCandidateView` in this slice — no UI
requirement in §3 of the owner's authorization named it explicitly, and
adding it wasn't required to satisfy the 12 presentation questions; it
remains available in the raw column for a future extension if EM-6B needs
it, without any schema change.

## 14. Missing-coverage semantics

`coverage_summary(db_path, run_id, family, threshold_percent)` returns
`evaluated_count`/`ranked_count`/`unranked_count` plus
`unranked_reason_counts` (a reason → count tuple, built from
`feasibility_reason` falling back to `state_reason`, falling back to the
literal string `"UNKNOWN"` only when *neither* persisted reason exists —
never converting a genuine `UNKNOWN` into `0`). Proven by
`test_coverage_summary_separates_ranked_from_unranked_with_reasons`.

## 15. Freshness representation

`describe_scan_freshness(scan, *, as_of)` is a **pure function** — no
`datetime.now()` anywhere in this module (grep-confirmed and
test-enforced). It returns `age_seconds`/`age_minutes` as facts and
applies **no** FRESH/STALE label — no owner-approved staleness threshold
exists anywhere in the frozen EMR contracts, so none was invented. A
future EM-6B may choose to render "last scan: 12 minutes ago, checkpoint
12:00" without this module ever claiming that is "stale."

## 16. Empty/no-scan semantics

Three empty states, all well-defined, none an exception: (a) `db/emr.db`
does not exist yet → `latest_scan_snapshot()` returns `None` immediately,
no file is created; (b) the schema is initialized but has zero
`COMPLETE` runs → `None`; (c) a run exists but has zero ranked
candidates for the requested (family, threshold) → `top_candidates()`
returns `()`. `build_experimental_snapshot()` composes these into
`EmrExperimentalSnapshot(scan=None, touch_10=())` as the single
top-level empty state a future UI would check.

## 17. Read-only architecture

`_connect_read_only()` returns `None` (not an exception) when the file
doesn't exist; otherwise opens `sqlite3.connect(f"file:{path}?mode=ro",
uri=True)` + `PRAGMA query_only=ON`. No `INSERT`/`UPDATE`/`DELETE`
anywhere in the module (grep-confirmed: zero occurrences). No call to
`EmrRepository.initialize()`, `save_scan_run()`, `save_candidates()`, or
`run_scan_cycle()` anywhere (grep-confirmed, and
`test_presentation_module_source_has_no_provider_or_network_calls`
explicitly checks for `"run_scan_cycle("` as a call pattern).

## 18. Persistence mutation proof

`test_presentation_queries_never_mutate_the_database` records file mtime
and size before running every public function in this module against a
seeded fixture DB, then asserts both are byte-identical after. A second
test, `test_presentation_connection_is_sqlite_read_only_mode`, proves the
connection itself refuses a `DELETE` at the SQLite layer
(`sqlite3.OperationalError`), not merely by convention.

## 19. Provider/network isolation proof

`test_presentation_module_source_has_no_provider_or_network_calls` greps
the module source for `kite`/`requests.`/`httpx.`/`urllib.request` and
for the literal call pattern `run_scan_cycle(`. All absent.

## 20. Canonical ATHENA isolation proof

`test_presentation_module_imports_nothing_canonical_or_darvax` greps for
`athena.scoring`/`athena.decision`/`athena.risk`/`athena.trade_plan`/
`athena.darvax`/`athena.data.store.repository`/`SqliteRepository`/
`athena.intraday`/`entry_qualification` — none present. Additionally, the
**pre-existing** `tests/explosive_move/test_em5_isolation.py` architecture
test (a repo-wide AST scan over every file under `explosive_move/`,
including this new one) already covers the same boundary and passed
unmodified.

## 21. DarvaX isolation proof

Same grep above covers `athena.darvax`. No DarvaX table, module, or
scoring concept referenced anywhere in this slice.

## 22. FINAL_TEST isolation proof

`presentation.py` never imports `partitions.py`, never opens a research
dataset path, and only reads `emr_scan_runs`/`emr_candidates` — tables
that exist independently of, and were never populated from,
TRAIN/VALIDATION/CALIBRATION/FINAL_TEST. No reference to FINAL_TEST
anywhere in the module.

## 23. Production scanner impact

None. `run_scan_cycle` (`scanner.py`) was not touched, not called, not
imported by this module (only referenced in its own docstring/tests, as
a call-pattern grep target, to document that it must never be called
here).

## 24. Scheduler/cron impact

None. Per the owner's explicit instruction (§7 of the authorization), no
production trigger for `run_scan_cycle` was added. `db/emr.db` remains
un-created in production (§31 below) — this is expected, not a defect.

## 25. API/HTTP impact

None. No FastAPI route, mount file, or OpenAPI schema touched.

## 26. Dashboard/UI impact

None. No `index.html`, JS, CSS, or `DASHBOARD_JS_PARTS` file touched.

## 27. ID-track impact

None. No `entry_qualifications`, ID-6E report, `SessionContext`, or
`IntradaySignalSet` reference anywhere in this module.

## 28. Real-data acceptance result

**`REAL_DATA_ACCEPTANCE_NOT_AVAILABLE`.** Confirmed: `db/emr.db` does not
exist in the real repository (`ls db/emr.db` → no such file) — the live
scanner has never been run against production, consistent with the EM-6
discovery's own finding that `run_scan_cycle` currently has no
scheduler/cron trigger. `build_experimental_snapshot('db/emr.db')` was
called once, read-only, confirmed to return the well-defined empty state
(`scan=None, touch_10=()`), and confirmed **not** to create the file. No
scan was triggered. `db/athena.db` reconfirmed unaffected
(`schema_version=17`, `integrity_check=ok`) after this check.

## 29. UI contract preview (informational — no mock UI built)

A future EM-6B dashboard tab would receive, per rendered snapshot:

```
label: "Experimental research signal -- not a trade recommendation"
scan:
  run_id, session_date, checkpoint, frozen_model_version
  started_ts, finished_ts, eligible_count, ineligible_count
  (or: no scan available)
touch_10: [
  { instrument_id, rank, calibrated_probability, probability_language,
    em4b_model_version, em4d_calibration_version,
    evidence_completeness_known/total, data_freshness,
    feasibility, feasibility_reason, state, state_reason,
    checkpoint_price, checkpoint_price_semantic }
  ...
]
```

Plus, on request: `top_candidates()` for any of the other 17 (family,
threshold) combinations, `coverage_summary()` for missing-coverage
context, and `describe_scan_freshness(scan, as_of=<viewer's own now>)`
for an age fact the UI itself decides how to phrase. This is exactly what
the future EM-6B needs and nothing about research internals (no raw
EM-2/EM-3 feature values, no FINAL_TEST, no model coefficients) beyond
what the scanner itself already chose to persist for explainability.

## 30. Known limitations

- `db/emr.db` does not exist in production yet — no shadow evidence for
  this contract exists beyond the fixture-based tests. This mirrors
  ID-6E.2's own early finding for the ID-track and is expected, not a
  defect: the scanner has no production trigger, per explicit owner
  instruction not to add one in this slice.
- `logit_contributions_json` (per-term evidence explanation) is not yet
  exposed in `EmrCandidateView` — deferred, not required by the 12 named
  presentation questions, addable without a schema change if EM-6B needs
  it.
- No cross-checkpoint/cross-run history view was built (e.g., "this
  candidate's rank over the last 3 checkpoints") — not named in the 12
  presentation questions; `EmrRepository.list_candidates_for_symbol`
  already exists for this if a future slice needs it.

## 31. Recommendation

Bring this contract to the owner for review. If approved, EM-6B (API
mount + dashboard) may be authorized as a separate, explicit next step —
this document deliberately does not request that authorization.
