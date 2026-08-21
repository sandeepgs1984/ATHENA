# EM-1 Research Data Remediation Plan

**Milestone:** EM-1r2
**Status:** Implemented and self-validated 2026-08-21; awaiting owner review
**Governing boundary:** ADR-012
**Input audit:** `docs/research/EM-1A-DATA-COVERAGE-AUDIT.md`

## 1. Decision

EM-1a is owner-approved as an honest, fail-closed audit. It authorizes no
historical labels because the ledger currently admits zero research-safe
checkpoints. EM-1b remains blocked.

The remediation is split into small approval-gated milestones. No milestone
may create labels, features, models, rankings, scanner output, or UI until
EM-1r5 approves a non-empty checkpoint set.

## 2. Architecture boundary

The existing ADR-012 boundary is sufficient for this remediation provided the
following ownership rules remain true:

| Concern | Owner | Rule |
|---|---|---|
| Source acquisition | Infrastructure adapters | Network and provider calls stay outside EMR business logic. |
| Canonical market records | Existing ATHENA persistence layer | EMR never mutates canonical data; ingestion uses existing repository boundaries. |
| Coverage and provenance manifests | EMR research storage | Immutable manifests record source, bounds, counts, exclusions, and content identity. |
| Research reads | Explicit read-only ports | EMR receives frozen inputs and cannot import concrete providers. |
| Labels and partitions | EMR research storage | Still prohibited until EM-1r5 is approved. |

No canonical schema or `MarketDataProvider` contract change is approved by
EM-1r1. If a later remediation milestone cannot fit these boundaries, stop and
write an ADR proposal before implementation.

## 3. Remediation milestones

### EM-1r1 - Architecture and acceptance plan

Freeze ownership, ordering, evidence standards, and stop conditions. This is a
documentation-only milestone and creates no ingestion or research data.

**Exit:** approved 2026-08-21. The three source/scope choices are frozen in
Section 7.

### EM-1r2 - Authoritative corporate-action coverage

Acquire corporate actions through an approved infrastructure adapter, persist
canonical action records through existing repositories, and write an immutable
EMR coverage manifest with provider identity, retrieval time, inclusive date
bounds, instrument resolution results, row counts, checksum, and exclusions.

**Acceptance:**

- coverage bounds are explicit per source and instrument/cohort;
- zero rows means authoritative action-free coverage only when the manifest
  proves the source covered the complete interval;
- unresolved instruments and ambiguous actions fail closed;
- raw windows containing a known action remain excluded;
- rerunning identical inputs reproduces counts and manifest identity;
- no provider call exists in EMR domain or research loops.

### EM-1r3 - Canonical intraday session reconstruction

Re-ingest or deterministically normalize 5-minute data into exchange-calendar
slots. Preserve source rows for audit, quarantine ambiguity, and admit only
duplicate-free complete sessions.

**Acceptance:**

- each admitted regular session contains exactly the exchange-calendar slots;
- every admitted instrument/session/slot has one record;
- timestamp drift is mapped only by a frozen, tested rule;
- conflicting overlaps are quarantined, never selected heuristically;
- OHLCV invariants, timezone, session bounds, and replay identity pass;
- completeness and exclusion counts are persisted in a manifest.

**Implementation status (2026-08-21):** Implemented and self-validated;
awaiting owner review. The provider-owned capture service persists immutable,
content-addressed source rows before the provider-free reconstruction contract
admits only complete exact-slot regular sessions. Identical duplicates may be
collapsed by the frozen normalization rule; conflicting duplicates,
off-grid/out-of-session rows, retrieval failures, and missing slots fail
closed with manifest-recorded reasons. No OHLCV interpolation or synthesis is
permitted.

The deterministic fixture cohort measured three symbol-sessions: one admitted
and two excluded. Four captured rows produced two admitted authoritative rows,
one identical-duplicate collapse, one unrepaired missing slot, one retrieval
failure, and zero invented rows. Provider-free replay reproduced the manifest
identity, and tampered source evidence was rejected. These are contract-test
measurements, not a claim of production historical coverage.

### EM-1r4 - Cohort admission and quote hygiene

Apply the survivor-cohort contract frozen by EM-1r2 to research admission and
exclude epoch-default quotes from all research reads. Acquiring authoritative
point-in-time historical membership remains a separate future option and is
not part of the current remediation scope.

**Acceptance:**

- every admitted symbol-day has dated eligibility evidence;
- current membership is never projected backward;
- listing/delisting ambiguity is excluded;
- the cohort name and limitation appear in every manifest and report;
- timestamps at the Unix epoch or outside study/session bounds are rejected;
- sector history remains `UNKNOWN` where it is not point-in-time authoritative.

### EM-1r5 - Coverage re-audit and checkpoint admission

Rerun the EM-1a measurements against immutable remediation manifests. Freeze
the usable study interval, cohort, references, and non-empty checkpoint set.

**Acceptance:**

- every claimed source and bound is reproducible from persisted provenance;
- corporate-action, membership/cohort, quote, and candle gates all pass;
- admitted checkpoints have duplicate-free complete-session evidence;
- exclusions are counted by stable reason code;
- the owner approves a non-empty checkpoint set.

Only an approved EM-1r5 unblocks EM-1b.

## 4. Fail-closed rules

- Missing authority is `UNKNOWN`, not evidence that an event did not occur.
- No current universe, listing state, or sector is backfilled into history.
- No duplicate candle is chosen by newest timestamp, largest volume, or row
  order unless a separately reviewed source-authority contract proves why.
- No raw corporate-action window is adjusted by an inferred ratio.
- No epoch-default quote can enter a feature, reference, checkpoint, or label.
- Partial remediation cannot be presented as research readiness.

## 5. Required provenance

Every remediation artifact must include an immutable ID, contract version,
source/provider identity, retrieval timestamp, effective bounds, requested and
resolved instruments, source and accepted row counts, exclusions by reason,
input checksums, output checksum, calendar version, code/config versions, and
the parent artifact IDs needed for replay.

Credentials and provider payloads containing secrets are never persisted in a
manifest.

## 6. Verification strategy

Each implementation milestone must include focused contract tests, repository
tests, deterministic replay tests, malformed/missing-data tests, architecture
tests proving provider and canonical-decision isolation, and the full ATHENA
suite. Large-data acceptance evidence records runtime and database query
volume, but performance cannot weaken correctness gates.

## 7. Approved owner decisions for EM-1r2

The owner approved these decisions together on 2026-08-21.

1. **Corporate actions:** official NSE corporate-action filings and reports are
   authoritative for splits, bonuses, mergers, and other label-distorting
   actions. Kite is not a corporate-action authority. A research interval is
   covered only when retrieval manifests prove the required official NSE
   interval is complete enough for the stated analysis. Incomplete, ambiguous,
   or unresolved records fail closed with a provenance reason; ATHENA never
   guesses or silently adjusts them.
2. **Historical population:** initial EMR work uses the formally named
   `ATHENA_CURRENT_CANONICAL_SURVIVOR_COHORT_V1`, frozen from the currently
   available canonical `athena_core` universe. It is survivor-cohort research,
   never point-in-time historical NSE-universe evidence. Every artifact and
   survivorship-sensitive conclusion must display this limitation. Cohort
   metadata is replaceable without changing event or feature contracts. Current
   membership must never be projected backward.
3. **Intraday repair:** authoritative Kite re-ingestion is the preferred repair
   path. Deterministic normalization is allowed only when a malformed or missing
   slot is uniquely attributable and no market information is invented. OHLCV
   interpolation or synthesis is prohibited. Unrepairable candles remain
   missing/`UNKNOWN` and are admitted or excluded by the dataset contract.

Decision 3 governs EM-1r3 and is recorded now for continuity; EM-1r2 performs
no intraday repair.

## 8. Explicit non-goals

EM-1r2 does not acquire point-in-time membership, integrate external
corporate-action vendors, build generalized data-cleaning infrastructure,
repair candles, generate labels, compute base rates, train a model, rank
symbols, mount a scanner, or affect canonical ATHENA decisions.

## 9. EM-1r2 measured outcome

The implementation and measured evidence are recorded in
`docs/research/EM-1R2-CORPORATE-ACTION-COVERAGE-REPORT.md`.

- The official NSE interval from 2023-08-11 through 2026-08-21 is represented
  by 37 of 37 complete monthly retrieval slices and 7,330 source records.
- The frozen survivor cohort contains 518 current canonical instruments. The
  result is explicitly not point-in-time historical NSE-universe evidence.
- Materialization accepted 2,009 actions and preserved 5,321 exclusions.
- Identical replay reproduced the same manifest and replay IDs and inserted
  zero duplicate rows.
- EM-1r2 performed zero intraday repairs. EM-1r3 remains the owner of that work.

EM-1r2 stops at owner review. EM-1r3 must not start automatically.
