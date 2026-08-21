# EM-1r2 Corporate-Action Coverage Report

**Status:** Implemented and self-validated 2026-08-21; awaiting owner review  
**Contract:** `EM-1R2-CORPORATE-ACTION-COVERAGE-CONTRACT.md`  
**Governing boundary:** ADR-012  
**Coverage contract:** `EM-1R2_CA_COVERAGE_V1`  
**Normalization contract:** `EM-1R2_CA_NORMALIZATION_V2`

## Scope And Claim Boundary

EM-1r2 acquires official NSE corporate-action records, resolves them against a
frozen survivor cohort, persists accepted actions and explicit exclusions, and
writes immutable replayable provenance. It does not create event labels,
features, base rates, models, rankings, scanner output, or UI.

This is survivor-cohort research. It must not be presented as point-in-time
historical NSE-universe evidence. Passing this milestone proves only bounded
official NSE corporate-action coverage for the named cohort and interval. It
does not make EMR research-ready; EM-1b remains blocked until EM-1r5.

## Approved Owner Decisions

- Official NSE corporate-action filings/reports are authoritative. Kite is not
  a corporate-action authority.
- The initial population is a named current canonical survivor cohort. Current
  membership is never projected backward.
- Kite re-ingestion and deterministic non-inventive normalization govern the
  later EM-1r3 intraday repair milestone. EM-1r2 performs no candle repair.

## Measured Corporate-Action Coverage

| Measure | Result |
|---|---:|
| Inclusive study interval | 2023-08-11 through 2026-08-21 |
| Monthly retrieval slices | 37 requested / 37 complete |
| Official NSE source records | 7,330 |
| Malformed official rows | 0 |
| Authoritative for this bounded retrieval claim | Yes |
| Accepted canonical actions | 2,009 |
| Accepted symbols | 440 |
| Preserved exclusions | 5,321 |
| Excluded source symbols | 1,790 |

`authoritative_for_research=true` means that every requested monthly slice was
retrieved and parsed. It does not mean every official source row belongs to or
can be classified for the survivor cohort; those rows remain explicit
exclusions below.

## Survivor Cohort

The cohort is `ATHENA_CURRENT_CANONICAL_SURVIVOR_COHORT_V1`, frozen from the
currently available canonical `athena_core` universe at materialization time.
It contains 518 instruments. The manifest persists the cohort name, source
group metadata, members, and content identity so a future authoritative
point-in-time membership source can replace it without changing event or
feature contracts.

The cohort has survivorship bias by construction. Any conclusion sensitive to
historical listings, delistings, constituent turnover, or failed companies must
display this limitation. No historical membership is inferred from today's
cohort.

## Accepted Actions And Identity Resolution

| Action type | Accepted rows |
|---|---:|
| Bonus | 48 |
| Demerger | 6 |
| Dividend | 1,911 |
| Rights | 9 |
| Split | 35 |
| **Total** | **2,009** |

No merger or rename row was accepted in this bounded cohort and interval.

All 2,009 accepted rows resolved through the explicit
`SYMBOL_SERIES_CANONICAL_ISIN_UNAVAILABLE` method. The canonical database has
blank ISINs for all 2,204 NSE instruments, so exact official ISIN resolution
could not be exercised. The fallback requires one exact symbol-and-series
match and is permitted only when the canonical ISIN is absent. A populated but
conflicting canonical ISIN would fail closed.

This canonical identity gap is the principal EM-1r2 limitation. It does not
invalidate the bounded materialization, but it weakens cross-source identity
assurance and must remain visible in downstream reports.

## Exclusions Introduced By Data-Quality Rules

| Stable reason | Count |
|---|---:|
| `ACTION_CLASSIFICATION_AMBIGUOUS` | 175 |
| `SYMBOL_OUTSIDE_COHORT` | 5,146 |
| **Total** | **5,321** |

There were no malformed-source exclusions or canonical identity conflicts in
this capture. Ambiguous actions were not guessed, and out-of-cohort actions
were not silently discarded; both remain persisted with provenance.

## Intraday Repair And Missing Data

EM-1r2 performed no intraday repair:

| Repair type | Count |
|---|---:|
| Authoritative Kite re-ingestion | 0 |
| Deterministic normalization | 0 |
| Synthetic/interpolated OHLCV | 0 |

The unrepaired EM-1a baseline therefore remains: 844,914 stored 5-minute rows,
671,851 canonical logical slots, 173,063 surplus rows across 150,740 duplicate
slots, and up to four rows in one logical slot. The 15-minute store contains
124,085 rows across 533 instruments with 16 duplicate rows and generally only
10 to 23 of 25 expected regular-session intervals. All nine checkpoint
candidates remain unaccepted. EM-1r3 owns repair and exclusion decisions.

## Deterministic Replay And Provenance

- Manifest ID:
  `8e1fd6c17365abe1a5ea3ac41fc00f83d36d8c972ef1ea7d725e51d28272a22c`
- Semantic replay ID:
  `b88cc5338cc0f98614a58260c094597fea5ccb0e001a247e0579a45212180a52`
- Original retrieval manifest:
  `af1d2dc9860f9eda82dddddb1a69807c9866db1025be89a75f5caba07466c99a`
- Materialized manifest:
  `artifacts/research/em1r2/corporate-actions/manifests/8e1fd6c17365abe1a5ea3ac41fc00f83d36d8c972ef1ea7d725e51d28272a22c.json`

Replaying the same immutable source artifacts reproduced both IDs, all counts,
and all exclusions. The second persistence pass inserted zero action rows and
zero exclusion rows, demonstrating deterministic and idempotent materialization.
Replay also verifies each raw artifact remains under the declared root and
matches its recorded SHA-256 digest.

## Verification

- Focused provider, ingestion, repository, contract, malformed-data, and replay
  suite: 22 passed.
- Architecture boundary: provider/network code remains under infrastructure;
  EMR receives immutable materialized evidence and imports no concrete provider.
- Canonical ATHENA scoring, confidence, risk, Decision, TradePlan, DarvaX, and
  order behavior are unchanged.
- Full-suite and repository static-check outcomes are recorded in the EM-1r2
  milestone review and `IMPLEMENTATION_SUMMARY.md`.

## Known Limitations

- The cohort is survivor-biased and not point-in-time historical membership.
- Canonical NSE instruments currently lack ISINs, so accepted rows use the
  strict symbol-series fallback instead of exact cross-source ISIN resolution.
- Ambiguous action descriptions remain excluded rather than normalized by an
  inferred ratio or unsupported classifier.
- Corporate-action coverage does not repair intraday duplicates, missing slots,
  timestamp hygiene, sector history, price bands, halts, or catalysts.
- No checkpoint is accepted and no event label is authorized.

## Recommendation

Approve EM-1r2 only if the bounded survivor-cohort claim and the canonical ISIN
limitation are acceptable. After approval, design and implement EM-1r3 as a
separate milestone using the already approved repair rules. Do not start
EM-1r3 automatically.
