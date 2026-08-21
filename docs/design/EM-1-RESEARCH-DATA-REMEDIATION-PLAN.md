# EM-1 Research Data Remediation Plan

**Milestone:** EM-1r1  
**Status:** Implemented 2026-08-21; awaiting owner review  
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

**Exit:** owner approves this plan and resolves the source/scope choices listed
in Section 7.

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

### EM-1r4 - Point-in-time cohort and quote hygiene

Implement one approved historical-population contract: authoritative dated
membership/listing lifecycle, or an explicitly named survivor cohort with a
narrow claim. Exclude epoch-default quotes from all research reads.

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

## 7. Owner decisions required before EM-1r2

1. Approve an authoritative corporate-action source and permitted study bounds.
2. Choose authoritative historical membership/listing evidence or approve a
   formally named survivor-cohort research claim.
3. Approve re-ingestion as the preferred intraday repair source; deterministic
   normalization is a fallback only for slots with unambiguous provenance.

These are data-authority decisions, not UI or modelling choices. EM-1r2 must
not start until they are recorded in its milestone design.

## 8. Explicit non-goals

EM-1r1 does not acquire data, alter schemas, change provider protocols, repair
candles, create a survivor cohort, generate labels, compute base rates, train a
model, rank symbols, mount a scanner, or affect canonical ATHENA decisions.
