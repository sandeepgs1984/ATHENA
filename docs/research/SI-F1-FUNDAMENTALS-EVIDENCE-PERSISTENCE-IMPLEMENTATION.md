# SI-F1 — Fundamentals Identity + Immutable Source-Evidence Persistence Foundation

**Status**: ✅ **COMPLETE AND FROZEN** (2026-09-15)
**Date**: 2026-09-15
**Author**: Antigravity (ATHENA Architecture Specialist)
**Milestone**: SI-F1 (Symbol Intelligence Fundamentals Track)
**Governing Standards**: ATHENA-000, ATHENA-001 (Accepted Amendments), ATHENA-002 §4, ADR-002, ADR-008, ADR-011, ADR-015, SI-F0 Frozen Architecture (`d41bcbc`), SI-F0.1 Feasibility Spike (`3912807`)
**Schema Version**: Upgraded to 21 (from Schema 20)

---

## 1. Executive Summary & Objective

Milestone **SI-F1** implements the production persistence and domain foundation for fundamental equity data in ATHENA.

Following the empirical findings of the **SI-F0.1 Feasibility Spike**, this milestone establishes the minimum trustworthy foundation required to store official fundamental source evidence without destroying:
- **Issuer identity**: The enduring legal corporate enterprise.
- **Time-versioned security identity**: ISIN and symbol changes over time across corporate action boundaries (such as splits, reclassifications, and renames).
- **Reporting-period identity**: Accounting period boundaries, financial years, quarterly/annual natures, and cumulative/discrete reporting.
- **Statement scope**: Strict isolation of Consolidated (`CONSOLIDATED`) vs Standalone (`STANDALONE`) reports.
- **Source-specific dissemination time**: Authentic legal disclosure timestamps (`source_published_at`) preserved with explicit precision (`PublicationPrecision`).
- **Publication precision**: Clear distinction between second-level timestamp disclosures (`EXACT_TIMESTAMP`), date-only filings (`DATE_ONLY`), and unknown precision (`UNKNOWN`), preventing temporal fabrication.
- **Raw filing identity**: Authentic source record identifiers (`source_record_id`) and multi-observation tracking.
- **Raw document reproducibility**: Original filing files (XBRL XML, PDF announcements) preserved in compressed format with cryptographic SHA-256 integrity digests computed on original uncompressed source bytes.
- **Ingestion provenance**: Systematic capture of ingestion timestamps and raw feed metadata payloads.
- **Multiple filing observations & supersession**: Append-only preservation of multiple disclosures for the same period with non-destructive, explicit revision lineage.

### Milestone Scope Boundary (Strictly Enforced)

| Included in SI-F1 | Strictly Excluded from SI-F1 (Deferred) |
| :--- | :--- |
| ✅ `IssuerRecord` domain model | ❌ Normalized financial facts / line-item extraction (SI-F2) |
| ✅ `SecurityIdentity` time-versioned domain model | ❌ XBRL taxonomy normalization / financial calculation (SI-F2) |
| ✅ `FundamentalFiling` immutable source observation | ❌ Derived metrics (PE, PB, ROCE, ROE, margins, debt ratios) |
| ✅ `FilingDocument` raw compressed document blob | ❌ Market capitalization / share count calculation (SI-F3) |
| ✅ Schema Version 21 DDL & migration | ❌ Production crawler / external network fetcher |
| ✅ PIT-safe query semantics (`list_filings_as_of`) | ❌ `DecisionEngine` or portfolio/conviction integration |
| ✅ Repository CRUD & invariant enforcement | ❌ DarvaX or technical analysis coupling |
| ✅ 15 unit, integration, and migration test suites | ❌ Symbol Intelligence UI or Web presentation |

---

## 2. Decoupling Corporate Issuer vs Security Identity

Empirical analysis of corporate actions (specifically Varun Beverages Limited `INE200M01013` to `INE200M01021` during its September 2024 stock split) revealed that exchange filing feeds often report legacy or inconsistent ISINs and symbols across split dates.

Directly keying fundamental filings to a mutable exchange instrument or a single ISIN causes severe data corruption:
1. Filings reported under a legacy ISIN become unfindable when querying a post-split instrument.
2. Corporate restructurings and symbol changes fragment fundamental financial history.
3. Market data instruments represent tradable quote feeds, whereas fundamental filings represent disclosures of an enduring legal enterprise.

### The Two-Tier Architecture

To solve this fundamentally:
- **`IssuerRecord`**: Models the enduring legal enterprise (e.g., Varun Beverages Limited or Infosys Limited). It persists across stock splits, ticker changes, series changes, and corporate reorganizations.
- **`SecurityIdentity`**: Models an exchange-tradable share class over a bounded temporal interval (`effective_from` to `effective_to`). It maps exchange symbols and ISINs to the parent `issuer_id`.

Per **Correction 1** of the Chief Architect review, `SecurityIdentity` does NOT store an independent mutable `is_active` boolean column. The active status on any date $t$ is strictly derived from the interval:
$$\text{is\_active}(t) \iff (\text{effective\_from} \le t \lor \text{effective\_from is NULL}) \land (t \le \text{effective\_to} \lor \text{effective\_to is NULL})$$

---

## 3. Domain Models Specification

Located in `src/athena/domain/fundamentals.py`.

### 3.1 `IssuerRecord`
- **Class Type**: Mutable dataclass (`slots=True`), permitting controlled administrative enrichment (e.g. updating CIN or legal name).
- **Attributes**:
  - `issuer_id: str`: Unique persistent canonical identifier.
  - `legal_name: str`: Formal corporate entity name.
  - `cin: str | None`: Corporate Identification Number (Ministry of Corporate Affairs).
  - `status: str`: Entity operational status (default `"ACTIVE"`).
  - `created_at: datetime`: Timezone-aware creation timestamp.
  - `updated_at: datetime`: Timezone-aware modification timestamp.

### 3.2 `SecurityIdentity`
- **Class Type**: Immutable frozen dataclass (`frozen=True, slots=True`).
- **Attributes**:
  - `security_id: str`: Unique security interval identifier.
  - `issuer_id: str`: Foreign key to `IssuerRecord.issuer_id`.
  - `exchange: str`: Exchange identifier (`"NSE"`, `"BSE"`).
  - `symbol: str`: Trading symbol during the interval.
  - `isin: str`: 12-character International Securities Identification Number.
  - `series: str`: Equity series (e.g. `"EQ"`).
  - `effective_from: date | None`: Beginning date of interval (inclusive), or None if unbounded past.
  - `effective_to: date | None`: Ending date of interval (inclusive), or None if currently open.
  - `source: str`: Provenance of this mapping (`"MANUAL"`, `"NSE"`, `"BSE"`).
  - `created_at: datetime`: Timezone-aware creation timestamp.
- **Derived Behavior**: `is_valid_on(as_of: date) -> bool`.

### 3.3 `FundamentalFiling`
- **Class Type**: Immutable frozen dataclass (`frozen=True, slots=True`).
- **Attributes**:
  - `filing_id: str`: Unique internal ATHENA filing identifier.
  - `issuer_id: str`: Foreign key to `IssuerRecord.issuer_id`.
  - `source: str`: Filing authority / provider (`"NSE"`, `"BSE"`).
  - `source_record_id: str`: Source-assigned sequence/broadcast ID (e.g. `"123456"`).
  - `source_reported_symbol: str`: Unmodified symbol as reported by the filing feed.
  - `source_reported_isin: str | None`: Unmodified ISIN as reported by the filing feed.
  - `source_reported_name: str | None`: Unmodified entity name as reported by the filing feed.
  - `period_start: date`: Financial accounting period start date.
  - `period_end: date`: Financial accounting period end date.
  - `financial_year: str`: Standardized fiscal year (e.g. `"FY2025"`).
  - `period_nature: PeriodNature`: `QUARTERLY`, `ANNUAL`, `HALF_YEARLY`, or `UNKNOWN`.
  - `cumulative_nature: CumulativeNature`: `NON_CUMULATIVE`, `CUMULATIVE`, or `UNKNOWN`.
  - `statement_scope: StatementScope`: `CONSOLIDATED`, `STANDALONE`, or `UNKNOWN`.
  - `audit_status: FilingAuditStatus`: `AUDITED`, `UNAUDITED`, `LIMITED_REVIEW`, or `UNKNOWN`.
  - `publication_precision: PublicationPrecision`: `EXACT_TIMESTAMP`, `DATE_ONLY`, or `UNKNOWN`.
  - `source_published_at: datetime | None`: Second-precision publication time (must be None if `DATE_ONLY`).
  - `source_published_date: date`: Calendar date of publication.
  - `market_available_at: datetime | None`: Earliest cross-market knowability timestamp (nullable, never fabricated).
  - `source_url: str | None`: Canonical download URL.
  - `revision_indicator: str | None`: Amendment indicator reported by source (e.g. `"N"`, `"A"`).
  - `supersedes_filing_id: str | None`: Internal ID of filing superseded by this disclosure.
  - `raw_metadata_json: str | None`: Raw unmodified source API JSON payload.
  - `ingested_at: datetime`: Timezone-aware ingestion timestamp.

### 3.4 `FilingDocument`
- **Class Type**: Immutable frozen dataclass (`frozen=True, slots=True`).
- **Attributes**:
  - `document_id: str`: Unique document identifier.
  - `filing_id: str`: Foreign key to `FundamentalFiling.filing_id`.
  - `document_type: str`: MIME / document type (`"XBRL_XML"`, `"PDF"`, `"EXCEL"`).
  - `source_url: str`: Download URL where this specific document was retrieved.
  - `file_name: str`: Original file name.
  - `source_sha256: str`: Cryptographic SHA-256 digest computed on the uncompressed raw bytes.
  - `raw_bytes_compressed: bytes`: Lossless zlib-compressed representation.
  - `decompressed_size_bytes: int`: Size of the original uncompressed document.
  - `created_at: datetime`: Timezone-aware storage timestamp.
- **Factory & Validation Methods**:
  - `FilingDocument.create(filing_id, document_type, source_url, file_name, raw_bytes, ...)`: Enforces uncompressed size cap $\le 20\text{ MB}$, computes SHA-256 on uncompressed bytes, applies zlib compression.
  - `decompress() -> bytes`: Decompresses raw bytes, strictly enforces 20 MB expansion cap, validates SHA-256 digest against `source_sha256`.

---

## 4. Schema Version 21 Specification

Located in `src/athena/data/store/schema.py`. `SCHEMA_VERSION` incremented from 20 to 21.

### 4.1 Tables
- `issuers`: Stores corporate enterprise records with unique `cin` and primary key `issuer_id`.
- `security_identities`: Stores share class mapping intervals with foreign key to `issuers`.
- `fundamental_filings`: Stores immutable filing disclosures with foreign key to `issuers`, self-referential foreign key for `supersedes_filing_id`, and composite unique constraint `(source, source_record_id, statement_scope)`.
- `filing_documents`: Stores compressed raw document blobs with foreign key to `fundamental_filings` and unique constraint `(filing_id, source_url)`.

---

## 5. Repository Implementation & Invariant Enforcement

Located in `src/athena/data/store/repository.py`.

### 5.1 Issuer Management & Conflict Detection
- **Idempotency**: Inserting an identical issuer record returns the existing record without error (`return False`).
- **Enrichment**: An existing issuer without a CIN can be enriched with an official CIN.
- **Conflict Rejection**: Attempting to upsert an issuer with a different CIN than already recorded raises `RepositoryError("CIN conflict for issuer ...")`.
- **Enrichment Contract**: Legal-name and operational status updates are ATHENA metadata enrichment, not mutations of historical source-reported names. Historical `filing.source_reported_name` remains strictly immutable.
- **Foreign Key Guard**: Attempting to delete an issuer that has linked `security_identities` or `fundamental_filings` fails loudly with `sqlite3.IntegrityError`.

### 5.2 Non-Overlapping Security Intervals
When inserting a `SecurityIdentity`, the repository validates all existing intervals for the same `(issuer_id, exchange, symbol, series)`. Overlapping intervals raise `RepositoryError`, while contiguous or disjoint intervals (e.g. pre-split vs post-split VBL) coexist cleanly.

### 5.3 Complete Filing Conflict & Idempotency Contract
Per Chief Architect closure review, `save_fundamental_filing()` enforces strict source-evidence immutability across all persisted fields:
- Retrying an identical filing observation returns `False` (safe idempotent no-op).
- If an existing filing exists for `(source, source_record_id, statement_scope)` or `filing_id`, every single source-evidence field is verified:
  - `source_reported_symbol`, `source_reported_isin`, `source_reported_name`
  - `period_start`, `period_end`, `financial_year`, `period_nature`, `cumulative_nature`
  - `statement_scope`, `audit_status`, `publication_precision`
  - `source_published_at`, `source_published_date`, `market_available_at`
  - `source_url`, `revision_indicator`, `supersedes_filing_id`, `raw_metadata`
- Any difference raises `RepositoryError` detailing the exact conflicting fields. No changed source evidence is silently overwritten or discarded.

### 5.4 Document Artifact Identity vs Storage Representation
A clear architectural separation is maintained for raw filing documents:
- **Source Artifact Identity**: Immutable source evidence consisting of `source_sha256`, `media_type`, and `raw_size_bytes` (uncompressed size). Duplicate retries matching this identity return `False` (idempotent no-op). Conflicting artifact identity raises `RepositoryError`.
- **ATHENA Storage Representation**: Storage-level attributes (`compression`, `stored_size_bytes`, `payload`) represent internal persistence encoding, permitting deterministic re-compression or engine optimizations without mutating the source artifact identity.

### 5.5 SHA-256 Digest, Bounded Decompression & Pre-Persistence Validation
- `source_sha256` is calculated strictly on original uncompressed source bytes and validated as a 64-character hexadecimal digest.
- Document size cap `MAX_RAW_DOCUMENT_SIZE_BYTES = 20 * 1024 * 1024` (20 MB) is enforced on creation, during decompression, and prior to storage.
- `save_filing_document()` executes `doc.get_raw_bytes()` before `INSERT`, verifying bounded extraction, raw size, and SHA-256 digest upfront. Tampered or corrupted documents are rejected with `RepositoryError` without persisting any database row.

### 5.6 Point-in-Time Safe Querying (`list_filings_as_of`)
- Requires a timezone-aware `as_of` datetime.
- Strictly filters `WHERE publication_precision = 'EXACT_TIMESTAMP' AND source_published_at <= :as_of`.
- Filings with `DATE_ONLY` or `UNKNOWN` publication precision are excluded from exact-timestamp PIT queries to prevent temporal lookahead bias.

---

## 6. Verification Suite Summary

Located in `tests/data_layer/test_fundamentals_repository.py`.

All 26 targeted unit, integration, and migration test suites pass deterministically:
1. `test_vbl_pre_and_post_split_isin_intervals_coexist`
2. `test_resolve_security_identity_as_of_split_boundary`
3. `test_infy_cross_exchange_filings_and_pit_safe_retrieval`
4. `test_schaeffler_revisions_coexist_without_automatic_supersession`
5. `test_filing_idempotent_retry_and_conflict_detection`
6. `test_filing_conflict_rejected_on_changed_source_reported_isin`
7. `test_filing_conflict_rejected_on_changed_audit_status_and_metadata`
8. `test_issuer_upsert_idempotency_enrichment_and_conflict`
9. `test_security_identity_interval_conflict_detection`
10. `test_document_round_trip_and_sha256_verification`
11. `test_tampered_document_payload_rejected`
12. `test_document_size_cap_enforced`
13. `test_document_stored_size_mismatch_rejected`
14. `test_document_uncompressed_raw_size_mismatch_rejected`
15. `test_document_invalid_hex_sha_rejected`
16. `test_document_decompression_raw_size_mismatch_rejected`
17. `test_document_truncated_zlib_stream_rejected`
18. `test_tampered_document_rejected_before_persistence`
19. `test_document_conflicting_media_type_or_raw_size_rejected`
20. `test_exact_timestamp_requires_timezone_aware_datetime`
21. `test_date_only_must_not_carry_fabricated_clock_time`
22. `test_pit_query_excludes_date_only_and_unknown_observations`
23. `test_unknown_precision_requires_both_date_and_time_to_be_none`
24. `test_domain_model_default_timestamps_are_timezone_aware`
25. `test_schema_20_database_migrates_cleanly_to_21`
26. `test_fresh_database_initializes_at_version_21`

### Regression & Full Suite
- `tests/data_layer/test_fundamentals_repository.py`: **26 passed**
- `tests/data_layer/test_repository.py`: **87 passed**
- `tests/data_layer/`: **648 passed, 0 failures**
- `tests/` (Full Repository Suite): **4,133 passed, 2 skipped, 0 failures**
- `rtk ruff check`: **PASS (0 violations)**
- `git diff --check`: **PASS**

---

## 7. Compliance with the 18 Owner Review Mandates & Closure Items

| # | Mandate / Closure Item | Implementation Compliance |
| :--- | :--- | :--- |
| 1 | Remove stored `is_active` | Derived dynamically via `is_valid_on(as_of)`. |
| 2 | Dataclass flexibility | `IssuerRecord` enrichable; `FundamentalFiling` and `FilingDocument` immutable value objects. |
| 3 | Issuer upsert & enrichment | Idempotent; permits None CIN enrichment; rejects conflicting CIN; documents metadata enrichment. |
| 4 | Security interval integrity | Enforces non-overlapping intervals for `(issuer_id, exchange, symbol, series)`. |
| 5 | Filing deduplication key | Composite unique key: `(source, source_record_id, statement_scope)`. |
| 6 | Multiple filing documents | Keyed by `document_id` with unique `(filing_id, source_url)`. |
| 7 | Source bytes hash | SHA-256 computed on original uncompressed source bytes; hex validity enforced. |
| 8 | Bounded document size | 20 MB cap enforced on creation, decompression, and retrieval. |
| 9 | `market_available_at` nullable | Nullable column, never defaulted to `source_published_at`. |
| 10 | Publication precision | `EXACT_TIMESTAMP`, `DATE_ONLY`, `UNKNOWN` with unambiguous rules prohibiting time/date fabrication. |
| 11 | Exact PIT query API | `list_filings_as_of` filters strictly on `EXACT_TIMESTAMP` and `source_published_at <= as_of`. |
| 12 | Supersession lineage | Preserved as supplied via `supersedes_filing_id`; never auto-derived. |
| 13 | Complete filing comparison | Full 20-field comparison in `save_fundamental_filing()`; rejects all conflicts with `RepositoryError`. |
| 14 | Pre-persistence doc check | `save_filing_document()` verifies bytes, raw size, and SHA-256 before `INSERT`. |
| 15 | Timezone-aware defaults | All domain model default factories use `datetime.now(timezone.utc)`. |
| 16 | Zero normalized facts | Zero XBRL fact normalization, zero financial line items extracted. |
| 17 | Zero derived metrics | Zero PE, PB, ROCE, margins, or market capitalization logic. |
| 18 | No auto-git commit | AI stops at `SI-F1 — IMPLEMENTED / REVIEW-READY`; provides consolidated commit message. |

---

## 8. Permanent Implementation Log & Repository Map Updates

- `docs/MILESTONES.md`: Updated with `SI-F1` status `🔄 IMPLEMENTED / REVIEW-READY`.
- `artifacts/SI-F1-source-review.zip`: Generated containing all modified and new source code, tests, and documentation.
- Ready for Principal Engineer / Owner Review.
