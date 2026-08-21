# EM-1r2 Corporate-Action Coverage Contract

**Status:** Frozen and implemented; awaiting owner review on 2026-08-21
**Governing boundary:** ADR-012
**Contract version:** `emr-corporate-action-coverage-v1`

## Authority

Official NSE corporate-action filings and reports are the sole authority used
by EM-1r2. Kite prices may support market-data ingestion but are not evidence
that a corporate action occurred or did not occur.

An interval is covered only when its retrieval manifest identifies the
official NSE source, inclusive requested bounds, retrieval time, payload
checksum, source row count, accepted row count, and every exclusion. A complete
official response containing zero rows is action-free evidence for that exact
interval. An unavailable, truncated, ambiguous, or otherwise incomplete
response is `UNKNOWN`, not zero.

## Survivor Cohort

The initial population is
`ATHENA_CURRENT_CANONICAL_SURVIVOR_COHORT_V1`: a deterministic snapshot of the
currently available canonical `athena_core` universe and its source group
metadata. It is suitable only for survivor-cohort research.

It must never be described as point-in-time historical NSE membership. Current
membership is not projected backward. Every manifest, report, metric, and
survivorship-sensitive conclusion must carry this limitation. The cohort is an
identified input, so a future authoritative point-in-time membership source can
replace it without changing event or feature contracts.

## Resolution And Exclusion

- Rows carrying an official ISIN resolve by exact ISIN within the frozen cohort.
  If ATHENA's exact symbol-and-series match has no canonical ISIN, that match is
  permitted with the explicit resolution method
  `SYMBOL_SERIES_CANONICAL_ISIN_UNAVAILABLE`. This is evidence that canonical
  identity data is absent, not permission to ignore conflicting identity data.
- If ATHENA has a canonical ISIN that differs from the official NSE ISIN, the
  row is excluded as `INSTRUMENT_IDENTITY_CONFLICT`; no symbol fallback occurs.
  Rows without an official ISIN may resolve by an exact, unique symbol-series
  match.
- Ambiguous matches are excluded; no row-order or preferred-series heuristic may
  select one.
- Missing ex-dates, unclassifiable actions, malformed rows, and symbols outside
  the cohort are preserved as exclusions with stable reason codes.
- Known label-distorting actions identify raw event windows that later dataset
  admission must exclude unless a separately approved adjustment contract
  applies.
- Persisted action records retain the official subject and source identity.

## Replay And Immutability

Canonical rows, exclusions, cohort members, and retrieval-slice semantics are
sorted before hashing. Identical semantic inputs reproduce the same cohort and
replay IDs even if source row order changes. The `manifest_id` identifies the
exact provenance artifact, including retrieval timestamps. The `replay_id`
identifies equivalent semantic evidence independently of retrieval timestamps.
A manifest ID collision with different content fails loudly; manifests are
never overwritten.

## Intraday Repair Decision

EM-1r3 will prefer authoritative Kite re-ingestion. It may use only uniquely
deterministic normalization that invents no OHLCV information; interpolation
and synthetic candles are prohibited. EM-1r2 records this owner decision but
does not repair or rewrite intraday data.

## Claim Boundary

Passing this contract proves only the stated official NSE corporate-action
coverage for the frozen survivor cohort and interval. It does not prove
point-in-time universe membership, research readiness, or model validity.
Only an owner-approved EM-1r5 checkpoint set can unblock labels.

## Implementation Evidence

The measured EM-1r2 result is recorded in
`EM-1R2-CORPORATE-ACTION-COVERAGE-REPORT.md`. Its immutable evidence includes:

- manifest ID
  `8e1fd6c17365abe1a5ea3ac41fc00f83d36d8c972ef1ea7d725e51d28272a22c`;
- semantic replay ID
  `b88cc5338cc0f98614a58260c094597fea5ccb0e001a247e0579a45212180a52`;
- 37 of 37 complete monthly official NSE retrieval slices;
- 518 frozen survivor-cohort instruments, 2,009 accepted action records, and
  5,321 preserved exclusions.

All 2,009 accepted rows required the explicit
`SYMBOL_SERIES_CANONICAL_ISIN_UNAVAILABLE` fallback because the current
canonical instrument records do not contain ISINs. This is a visible identity
limitation, not silent evidence equivalence.
