# SI-F2A — Financial Fact Normalization Methodology & XBRL Mapping Discovery

**Status**: SI-F2A — COMPLETE AND FROZEN
**Date**: 2026-09-15
**Approval**: Owner / Chief Architect approved D1-D12 on 2026-09-15
**Author**: Antigravity (ATHENA Architecture Specialist)
**Milestone**: SI-F2A (Symbol Intelligence Fundamentals Track)
**Governing Standards**: ATHENA-000 (Constitution), ATHENA-001 (Accepted Amendments), ATHENA-002, ADR-002, ADR-008, ADR-011, ADR-015, SI-F0 (`d41bcbc`), SI-F0.1 (`3912807`), SI-F1 (`256ee4b`)
**Active Production Schema**: `SCHEMA_VERSION = 21` (Frozen, Unchanged)
**Production Code Impact**: `git diff -- src/athena` = **ZERO** (Strictly untouched)

---

## 1. Executive Summary

Milestone **SI-F2A** investigates and establishes the empirical foundation for transforming official, immutable corporate financial filing evidence into normalized, Point-in-Time (PIT) safe financial facts.

### Primary Discovery Findings
Given an official exchange XBRL/XML document containing facts, contexts, units, dimensions, and filing metadata:
1. **Context IDs are Opaque Tokens**: Identifiers such as `OneD`, `FourD`, and `OneI` are arbitrary generator tokens. ATHENA must classify contexts semantically using explicit duration coordinates (`startDate`, `endDate`), instant dates (`instant`), and dimensional members.
2. **Quarterly vs Cumulative Separation**: Exchange filings report both quarter-specific values (e.g., INFY Q3 Revenue: ₹41,764 Cr) and cumulative/YTD values (e.g., INFY 9M Revenue: ₹122,064 Cr) within the same filing document. Normalization must match duration coordinates strictly against filing period bounds (`fromDate`, `toDate`). **No synthetic quarter values may be derived by subtraction** (e.g., $Q2 = H1 - Q1$) during fact normalization.
3. **Two-Layer Persistence Architecture**: Normalization must preserve a **Raw Fact Observation Layer** (capturing verbatim XML QNames, context coordinates, units, raw lexical strings, occurrence ordinals, and decimals) separate from a **Canonical Fact Mapping Layer** (evaluating mapped canonical concepts, rules, and confidence). Raw facts remain queryable and auditable even if unmapped.
4. **Distinct Raw Occurrence vs Canonical Economic Identities**:
   - *Raw Source Occurrence Identity*: `(document_id, source_occurrence_ordinal)` where `source_occurrence_ordinal` is a 1-based sequential integer in XML document order. Separates physical source location from fact payload.
   - *Canonical Economic Identity*: Combines concept, statement scope, period type, `period_start`, and `period_end` so that quarter and YTD facts (which share identical `period_end`) never collide.
5. **Strict Scope Isolation**: Consolidated and Standalone statements are disseminated as separate filings with distinct sequence numbers, timestamps, and XBRL documents. They must never be merged or mixed.
6. **Decimal Precision & Decimals Semantics**: Numeric facts are stored as Python `Decimal` / SQLite `TEXT`. The XBRL `decimals` attribute specifies reporting accuracy/rounding precision ($10^{\text{decimals}}$), **not** a unit conversion multiplier. The raw lexical value in the XML element is already in base units. Negative numbers (PAT losses, negative EPS) are first-class signed Decimals.
7. **Conservative Duplicate Policy (Raw Preservation)**: Physically distinct XML occurrences are never erased from the raw layer. Exact duplicates are deduplicated at canonical promotion; compatible duplicates preserve source evidence without picking an arbitrary "highest precision" winner; conflicting values trigger `CONFLICT_UNRESOLVED` (fail loudly).
8. **Financial-Sector Boundary & Eligibility**: Banking filings use an entirely distinct taxonomy (`BANKING_` namespace, `InterestEarned` vs `RevenueFromOperations`), confirming banking exclusion from non-financial normalization. NBFCs and insurance issuers are conservatively excluded as `NOT YET EMPIRICALLY VALIDATED`. If the repository lacks an authoritative sector classification, unknown issuer classification must default to `NOT ELIGIBLE FOR CANONICAL NORMALIZATION`.
9. **Bounded Initial Canonical Promotion**: Bounded to 5 pure income concepts (`REVENUE_FROM_OPERATIONS`, `PROFIT_LOSS_BEFORE_TAX`, `PROFIT_LOSS_FOR_PERIOD`, `EPS_BASIC`, `EPS_DILUTED`). Capital structure concepts (`PAID_UP_EQUITY_CAPITAL`, `FACE_VALUE_PER_SHARE`) have proven raw mappings but require explicitly approved context rules before canonical promotion.

---

## 2. Scope / Non-Goals

### In Scope (SI-F2A Discovery)
- Empirical inspection and deterministic parsing of sanitized official NSE/BSE IndAS XBRL fixtures and constructed methodology fixtures.
- Context classification rules (duration vs instant, period dates, dimensions).
- Period semantics (quarter vs cumulative/YTD) without synthetic subtraction.
- Statement scope isolation (Consolidated vs Standalone).
- Canonical concept candidate mapping and confidence classification.
- Duplicate fact resolution semantics (Exact, Compatible, Conflicting) with raw occurrence preservation.
- Raw Fact vs Canonical Fact two-layer architecture design.
- Machine-readable evidence artifact (`tools/research/si_fundamentals/f2a_normalization_evidence.json`).

### Explicit Non-Goals (Hard Boundary)
- **NO schema modifications**: `SCHEMA_VERSION` remains strictly **21**.
- **NO production tables, repositories, or parsers**: Implementation is deferred to SI-F2B.
- **NO network crawler or ingestion**: Ingestion remains research-only.
- **NO derived metrics or ratios**: Zero PE, PB, ROCE, ROE, margins, or debt ratios.
- **NO market cap or dilution calculations**: Deferred to SI-F3.
- **NO share-count derivation**: Deriving share count from paid-up capital / face value is strictly prohibited in F2B.
- **NO architectural coupling**: `DecisionEngine`, `Portfolio`, `DarvaX`, scoring, and UI remain 100% untouched.
- **NO financial-sector inclusion**: Financial sector remains an excluded negative control.

---

## 3. Frozen Inputs from F0 / F0.1 / F1

SI-F2A strictly inherits and preserves all frozen decisions:
- **ATHENA-000 / ATHENA-001**: Factual evidence only; zero automated trading; zero order placement.
- **SI-F0**: Four-dimensional temporal model; non-financial mainboard scope; no timestamp fabrication.
- **SI-F0.1**: Canonical provenance grounded in official exchange feeds; source publication time separated from earliest market availability (`market_available_at`).
- **SI-F1**: Frozen persistence foundation on Schema v21:
  - `issuers` (enduring enterprise entity);
  - `security_identities` (time-versioned share class / ISIN);
  - `fundamental_filings` (immutable filing observation);
  - `filing_documents` (bounded raw compressed artifact with SHA-256 integrity).

---

## 4. Research Method & Reproducible Fixture Provenance

Discovery combines:
1. **Source-Derived Sanitized Fixtures** (`SOURCE_DERIVED_SANITIZED_FIXTURE`):
   - `infy_q3_fy25_sanitized.xml`:
     - *Issuer*: Infosys Limited (`INE009A01021`, NSE: `INFY`)
     - *Filing*: Q3 FY25 Consolidated (2024-10-01 to 2024-12-31)
     - *Source Record*: NSE sequence number `1189811`, disseminated `2025-01-16 19:40:31 IST`
     - *Source Artifact*: `https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117292_1348213_16012025074012.xml`
     - *Sanitization Statement*: Sanitized XML containing core income/capital facts, quarter (`OneD`) vs 9M YTD (`FourD`) durations, instant context (`OneI`), and segment dimension (`OneReportableSegmentRevenue01D`).
   - `paytm_q3_fy25_loss_sanitized.xml`:
     - *Issuer*: One 97 Communications Limited (`INE982J01020`, NSE: `PAYTM`)
     - *Filing*: Q3 FY25 Consolidated (2024-10-01 to 2024-12-31)
     - *Source Record*: NSE sequence number `1190043`, disseminated `2025-01-20 18:37:43 IST`
     - *Source Artifact*: `https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117412_1353590_20012025063743.xml`
     - *Sanitization Statement*: Sanitized XML demonstrating negative PAT (-₹208.5 Cr) and negative diluted EPS (-₹3.27).
   - `hdfcbank_q3_fy25_banking_sanitized.xml`:
     - *Issuer*: HDFC Bank Limited (`INE040A01034`, NSE: `HDFCBANK`)
     - *Filing*: Q3 FY25 Consolidated (2024-10-01 to 2024-12-31)
     - *Source Record*: NSE sequence number `1190261`, disseminated `2025-01-23 12:27:21 IST`
     - *Source Artifact*: `https://nsearchives.nseindia.com/corporate/xbrl/BANKING_117525_1359016_23012025122721.xml`
     - *Sanitization Statement*: Sanitized XML demonstrating presence of `InterestEarned` / `InterestExpended` and total absence of `RevenueFromOperations`.
2. **Constructed Methodology Fixture** (`CONSTRUCTED_METHODOLOGY_FIXTURE`):
   - `duplicate_and_nil_cases_sanitized.xml`:
     - *Classification*: `METHODOLOGY / PARSER BEHAVIOR VALIDATED`
     - *Sanitization Statement*: Purpose-built synthetic XML fixture constructed to validate parser and methodological behavior on exact duplicates, compatible duplicates, conflicting duplicates, and reported nil (`xsi:nil="true"`). Does not represent a single official filing.
3. **Documented External Metadata** (`DOCUMENTED_EXTERNAL_METADATA`):
   - Recorded from live exchange feed queries in SI-F0.1 (INFY Consolidated seq 1189811 vs Standalone seq 1189815, TCS side-by-side filings, SCHAEFFLER revision sequence numbers 1197098 vs 1197319, exchange dissemination timestamps).
4. **Planning Estimates** (`INFERRED_PLANNING_ESTIMATE`):
   - Estimates for facts per filing, payload sizes, and 5-year SQLite capacity.

---

## 5. Empirical Filing Matrix

| Case ID | Symbol | ISIN | Filing Scope | Period Analyzed | Sequence / Filing ID | Key Focus & Findings |
|---|---|---|---|---|---|---|
| **A** | `INFY` | `INE009A01021` | Consolidated | Q3 FY25 (2024-10-01 to 2024-12-31) | NSE: `1189811` | Clean mainboard issuer; quarter vs YTD facts in same XML; exact dissemination time (`19:40:31 IST`). |
| **B** | `INFY` | `INE009A01021` | Standalone | Q3 FY25 (2024-10-01 to 2024-12-31) | NSE: `1189815` | Disseminated 2m13s after Consolidated; distinct `seqNumber` and XBRL URL; different top-line numbers. |
| **C** | `TCS` | `INE467B01029` | Consolidated & Standalone | Q3 FY25 (2024-10-01 to 2024-12-31) | NSE: `1189599` / `1189595` | Proved side-by-side filing pattern on `2025-01-09` with distinct URLs and sequence IDs. |
| **D** | `PAYTM` | `INE982J01020` | Consolidated | Q3 FY25 (2024-10-01 to 2024-12-31) | NSE: `1190043` | Loss-making issuer; proved negative PAT (-₹208.5 Cr) and negative EPS (-₹3.27) represented as valid signed Decimals. |
| **E** | `IDEA` | `INE669E01016` | Consolidated | Q3 FY25 (2024-10-01 to 2024-12-31) | NSE: `1194584` | Heavy-loss issuer; multi-thousand crore negative net profit; complex capital structure. |
| **F** | `VBL` | `INE200M01013` / `INE200M01021` | Consolidated | Q4 FY24 (2024-10-01 to 2024-12-31) | NSE: `1193953` | Corporate action (1:2.5 stock split); decoupled issuer identity from feed ISIN. |
| **G** | `SCHAEFFLER` | `INE513A01022` | Consolidated | FY24 (ended 2024-12-31) | NSE: `1197098` / `1197319` | Revision case: initial filing on 27-Feb-2025 (`reInd=N`), revised filing 26 days later (`reInd=R`). Both persist immutably. |
| **H (Neg Control)** | `HDFCBANK` | `INE040A01034` | Consolidated | Q3 FY25 (2024-10-01 to 2024-12-31) | NSE: `1190261` | Banking negative control; `BANKING_` taxonomy; `InterestEarned` tags; lacks `RevenueFromOperations`. |

---

## 6. XBRL Document Anatomy

Official Indian corporate results filings share a standardized XBRL 2.1 XML structure:
- **Root Element**: `<xbrli:xbrl>` declaring namespaces.
- **Taxonomy Namespace Observed**: `xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"` (prefix `in-bse-fin`).
- **Context Declarations**: `<xbrli:context id="...">` defining entity, temporal boundaries (`<period>`), and dimensional breakdowns (`<scenario>`, `<segment>`).
- **Unit Declarations**: `<xbrli:unit id="...">` defining currency measures (`<measure>iso4217:INR</measure>`), share counts (`<measure>xbrli:shares</measure>`), or per-share ratios (`<divide>`).
- **Fact Elements**: XML child elements bearing the concept QName (e.g. `<in-bse-fin:RevenueFromOperations>`), referencing a context (`contextRef="OneD"`), unit (`unitRef="INR"`), precision (`decimals="-7"`), and raw lexical value (`"417640000000.00"`).

---

## 7. Context Semantics

### The Context-ID Fallacy `[EMPIRICALLY PROVEN]`
Context IDs such as `OneD`, `FourD`, `OneI`, `OneOperatingExpenses01D` are **arbitrary string tokens** generated by filing software.
**Rule**: ATHENA must NEVER assign semantic meaning to context ID string names.

### Authoritative Semantic Context Classification Pipeline
A context is uniquely and deterministically classified by its underlying XML children:
```
Context XML Element
  ├── <entity>: CIK / ScripCode identifier
  ├── <period>:
  │     ├── <instant>: Point-in-Time date (YYYY-MM-DD) -> INSTANT
  │     └── <startDate> + <endDate>: Temporal Interval -> DURATION
  └── <scenario> / <segment>:
        └── <explicitMember>: Dimensional breakdown -> DIMENSIONED
```

1. **Duration vs Instant**:
   - If `<instant>` is present: classify as `INSTANT` (`period_start = None`, `period_end = instant_date`).
   - If `<startDate>` and `<endDate>` are present: classify as `DURATION` (`start_date`, `end_date`, `duration_days = (end - start).days + 1`).
2. **Dimension Filtering**:
   - If `<segment>` or `<scenario>` contains child dimension members: classify as `DIMENSIONED` (segment/geography/category slice).
   - If NO dimensions exist: classify as `PRIMARY_ENTITY_AGGREGATE`.

---

## 8. Period Classification: Structural Period vs Reporting Semantics

To avoid brittle assumptions regarding quarter day counts, ATHENA separates **Structural Period Shape** from **Reporting Period Semantics**:

### Layer A: Structural Period `[EMPIRICALLY PROVEN]`
- `INSTANT`: `<instant>` date present (`duration_days = 0`).
- `DURATION`: `<startDate>` and `<endDate>` present (`duration_days = (end - start).days + 1`).

### Layer B: Reporting Period Semantics `[INFERRED / RECOMMENDED]`
Reporting semantics reconcile the structural interval against official filing metadata (`fromDate`, `toDate`, `period`, `cumulative`):

| Reporting Semantics | Reconciliation Rule |
|---|---|
| **`QUARTER`** | `context.startDate == filing.fromDate` AND `context.endDate == filing.toDate` AND `85 <= duration_days <= 95` |
| **`HALF_YEAR`** | `context.startDate == filing.fromDate` AND `context.endDate == filing.toDate` AND `175 <= duration_days <= 190` |
| **`NINE_MONTH`** | `context.startDate == fiscal_year_start` AND `context.endDate == filing.toDate` AND `265 <= duration_days <= 280` |
| **`FULL_YEAR`** | `context.startDate == fiscal_year_start` AND `context.endDate == fiscal_year_end` AND `355 <= duration_days <= 375` |
| **`AMBIGUOUS_PERIOD`** | Context coordinates contradict filing metadata or fall outside standard tolerances (fail loudly). |
| **`OTHER_DURATION`** | Documented stub or transition period. |

---

## 9. Quarterly vs Cumulative / YTD — No Synthetic Subtraction

### Empirical Demonstration (INFY Q3 FY25) `[EMPIRICALLY PROVEN]`
In the parsed INFY fixture (`infy_q3_fy25_sanitized.xml`), the company reported:
- Under Quarterly Duration (`2024-10-01` to `2024-12-31`, 92 days):
  - Revenue from Operations = **₹41,764.00 Cr** (`417640000000.00`)
  - Net Profit for Period = **₹6,822.00 Cr** (`68220000000.00`)
- Under 9-Month YTD Duration (`2024-04-01` to `2024-12-31`, 275 days):
  - Revenue from Operations = **₹122,064.00 Cr** (`1220640000000.00`)
  - Net Profit for Period = **₹19,712.00 Cr** (`197120000000.00`)

### The Synthetic Subtraction Prohibition `[GOVERNING PRINCIPLE]`
- In Indian Q2 (H1) and Q3 (9M) filings, companies legally report single-quarter numbers and cumulative YTD numbers side-by-side.
- **Rule**: ATHENA must preserve reported facts exactly as disclosed.
- **Prohibition**: ATHENA must **NEVER derive quarterly values by synthetic subtraction** (e.g., $Q2 = H1 - Q1$ or $Q3 = 9M - H1$) during fact normalization.
- **Rationale**: Subtraction assumes restatement-free consistency across prior filings, introduces hidden accounting assumptions, and fabricates numbers that were not directly attested by management or auditors in that filing.

---

## 10. Statement Scope

### Consolidated vs Standalone Isolation `[DOCUMENTED]`
Empirical evidence proves that Indian issuers routinely file both Consolidated and Standalone results on the same day:
- **INFY Q3 FY25**: Consolidated (`seqNumber = 1189811`) vs Standalone (`seqNumber = 1189815`).
- **TCS Q3 FY25**: Consolidated (`seqNumber = 1189599`) vs Standalone (`seqNumber = 1189595`).

### Resolution Rules
1. Filing-level metadata (`consolidated="Consolidated"` vs `"Non-Consolidated"`) establishes statement scope.
2. Consolidated facts and Standalone facts are stored as strictly separate factual streams tied to their distinct `filing_id`.
3. Presentation policy (frozen in SI-F0): **Consolidated preferred, Standalone fallback**. The persistence layer never blends them.

---

## 11. Instant vs Duration Facts

- **Duration Facts**: Flow concepts representing economic activity over time (Revenue, Expenses, PBT, PAT). Must have `period_type = DURATION` with non-null `period_start` and `period_end`.
- **Instant Facts**: Stock concepts representing economic status at a specific date (Total Assets, Equity Capital, Borrowings). Must have `period_type = INSTANT` with `period_start = NULL` and `period_end = as_of_date`.
- **Capital Structure Invariant**: `PaidUpValueOfEquityShareCapital` and `FaceValueOfEquityShareCapital` are reported in XBRL results under both duration and instant contexts. ATHENA normalizes them preserving explicit context coordinates to prevent key collision.

---

## 12. Concept Identity & Taxonomy Qualification

### Taxonomy QName Preservation
A concept in XBRL cannot be identified by local name alone.
- **Authoritative Raw Concept Identity**: `(namespace_uri, local_name)` or XML Qualified Name (`in-bse-fin:RevenueFromOperations`).
- **Observed Standard Namespace**: `http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin`.
- **Scope Limitation `[DOCUMENTED]`**: The 2020-03-31 namespace is proven for sampled 2024–2025 filings. Historical filings (2015–2019) may declare earlier taxonomy versions; F2B mappings must be strictly taxonomy-qualified and version-aware.

---

## 13. Canonical Concept Scope: High Confidence vs Rule Required

SI-F2A bounds initial canonical promotion into two distinct confidence tiers:

### Tier 1: High-Confidence Canonical Promotion (5 Pure Income Concepts)
Directly reported on the face of IndAS corporate results; unambiguous context semantics:
1. `REVENUE_FROM_OPERATIONS` (`DURATION`, `CURRENCY_INR`)
2. `PROFIT_LOSS_BEFORE_TAX` (`DURATION`, `CURRENCY_INR`)
3. `PROFIT_LOSS_FOR_PERIOD` (`DURATION`, `CURRENCY_INR`)
4. `EPS_BASIC` (`DURATION`, `INR_PER_SHARE`)
5. `EPS_DILUTED` (`DURATION`, `INR_PER_SHARE`)

### Tier 2: Raw Mapping Proven but Canonical Context Rule Required (2 Capital Concepts)
Raw QName mapping is proven, but tags appear in both instant (`OneI`) and duration (`OneD`) contexts:
1. `PAID_UP_EQUITY_CAPITAL` (`INSTANT_OR_DURATION`, `CURRENCY_INR`)
2. `FACE_VALUE_PER_SHARE` (`INSTANT_OR_DURATION`, `INR_PER_SHARE`)

*Policy*: In F2B, Tier 2 concepts are preserved in the raw layer. Canonical promotion requires an explicitly approved context rule (e.g. prefer instant over duration). **Deriving share count from paid-up capital / face value is strictly prohibited in F2B.**

*(Deferred Concepts: `OPERATING_CASH_FLOW` is `PROVISIONAL` due to absence in Q1/Q3; `TOTAL_BORROWINGS` is `AMBIGUOUS` due to line-item fragmentation; `EBITDA` is `UNMAPPED` as non-GAAP).*

---

## 14. Mapping Evidence Matrix

| Canonical Concept | Raw Taxonomy QName | Empirical Issuer Evidence | Promotion Status | Mapping Rationale |
|---|---|---|---|---|
| `REVENUE_FROM_OPERATIONS` | `in-bse-fin:RevenueFromOperations` | INFY, TCS, PAYTM, IDEA, VBL | **HIGH_CONFIDENCE** | Core operational top-line under IndAS across all non-financial corporate filings. |
| `PROFIT_LOSS_FOR_PERIOD` | `in-bse-fin:ProfitLossForPeriod` | INFY, TCS, PAYTM, IDEA, VBL | **HIGH_CONFIDENCE** | Authoritative net profit/loss after tax. Handles negative losses seamlessly. |
| `PROFIT_LOSS_BEFORE_TAX` | `in-bse-fin:ProfitLossBeforeTax` | INFY, TCS, PAYTM, IDEA | **HIGH_CONFIDENCE** | Standard pre-tax earnings before exceptional items and tax expense. |
| `EPS_BASIC` | `in-bse-fin:BasicEarningsLossPerShare...` | INFY (16.41), PAYTM (-3.27) | **HIGH_CONFIDENCE** | Legally reported basic EPS on face of financial results. |
| `EPS_DILUTED` | `in-bse-fin:DilutedEarningsLossPerShare...` | INFY (16.39), PAYTM (-3.27) | **HIGH_CONFIDENCE** | Legally reported diluted EPS on face of financial results. |
| `PAID_UP_EQUITY_CAPITAL` | `in-bse-fin:PaidUpValueOfEquityShareCapital` | INFY, TCS, PAYTM, IDEA, VBL | **RULE_REQUIRED** | Raw mapping proven; context promotion rule required before canonical promotion. |
| `FACE_VALUE_PER_SHARE` | `in-bse-fin:FaceValueOfEquityShareCapital` | INFY (5.0), TCS (1.0), PAYTM (1.0) | **RULE_REQUIRED** | Raw mapping proven; context promotion rule required before canonical promotion. |

---

## 15. Units and Scale: Correcting Decimals Semantics

### The Decimals Semantics Rule `[EMPIRICALLY PROVEN]`
- The XBRL `decimals` attribute expresses **reporting accuracy / rounding precision** ($10^{\text{decimals}}$), **NOT a unit conversion scale multiplier**.
  - Example: `<RevenueFromOperations decimals="-7">417640000000.00</RevenueFromOperations>` denotes accuracy to the nearest $10^7$ (1 Crore).
  - The raw lexical string `"417640000000.00"` is ALREADY the reported value in base currency (`INR`).
  - **Correction**: Normalization converts `Decimal("417640000000.00")`. It does NOT multiply by $10^{-7}$.
- ATHENA stores raw values in base units (`INR`, `INRPerShare`). Conversion to "₹ in Crores" is strictly presentation-layer formatting.

---

## 16. Decimal / Numeric Representation

- **Decimal Mandate**: All financial facts must be parsed and stored using Python `Decimal` / SQLite `TEXT`. **Binary floating-point (`REAL` / `float`) is strictly prohibited.**
- **Signed Representation**: Negative numbers (losses) carry standard leading minus signs (e.g. `-2085000000.00` in PAYTM). They convert directly to `Decimal("-2085000000.00")`.
- **Dual Persistence**: To guarantee zero loss of provenance, persistence must store:
  - `raw_value`: Exact verbatim string from XML (e.g. `"-2085000000.00"`).
  - `numeric_value`: Exact parsed `Decimal`.

---

## 17. Dimensions: Enterprise Eligibility Policy

### Total vs Segment Rule `[EMPIRICALLY PROVEN]`
In the INFY fixture, context `OneReportableSegmentRevenue01D` carries:
```xml
<xbrli:scenario>
  <xbrldi:explicitMember dimension="in-bse-fin:ReportableSegmentsAxis">
    in-bse-fin:FinancialServicesMember
  </xbrldi:explicitMember>
</xbrli:scenario>
```
Segment revenue is reported as ₹11,842 Cr, while enterprise total revenue is ₹41,764 Cr.

### Dimension Policy for Initial F2B
- We do NOT claim that all non-dimensioned contexts are universally equivalent to enterprise aggregate across all taxonomies.
- **Conservative Rule**: For the initial 5 high-confidence canonical mappings, canonical enterprise promotion requires a context with **NO unsupported material dimensions**.
- Dimensioned raw facts are preserved in Layer 1, but excluded from Layer 2 canonical enterprise promotion.

---

## 18. Duplicate Facts: Raw Occurrence Preservation Policy

ATHENA establishes four deterministic categories for duplicate handling:

1. **`RAW_OCCURRENCE_PRESERVATION`**: Physically distinct XML occurrences in the source document are **never deleted or silently dropped**. Every occurrence is recorded in the raw observation layer with its sequential `source_occurrence_ordinal`.
2. **`EXACT_DUPLICATE`**: Same economic coordinates, same concept, and identical raw value.
   $\implies$ Preserved in raw layer; deduplicated during canonical promotion to avoid duplicate canonical rows.
3. **`DISTINCT_CONTEXT`**: Different context identity, dimensions, or period coordinates.
   $\implies$ Distinct factual observations.
4. **`COMPATIBLE_VALUE_DUPLICATE`**: Economically equivalent coordinates and numerically compatible values, but differing decimals/precision.
   $\implies$ Preserve source observations; **DO NOT automatically select "highest precision" as canonical truth**.
5. **`CONFLICTING_DUPLICATE`**: Same economic coordinates, but contradictory numeric values.
   $\implies$ Preserve all observations and mark `CONFLICT_UNRESOLVED` (fail loudly).

*Zero averaging. Zero silent first-value selection. Zero arbitrary precision winners.*

---

## 19. Nil / Missing / Zero Semantics

Explicit semantic boundaries:
- `0.00 != MISSING`: Zero is an explicit reported number.
- `negative != MISSING`: Negative loss is a valid reported number.
- `xsi:nil="true" != 0`: Explicitly declared nil represents "Not Applicable / Nil", distinct from numeric zero. Verified in fixture `duplicate_and_nil_cases_sanitized.xml` for `ExceptionalItems`. Documented as XBRL 2.1 standard requirement.
- `absent element != reported nil`: Missing from XML means unreported.
- `unmapped concept != missing concept`: An unmapped concept exists in the source filing but lacks an approved canonical mapping.

---

## 20. Revision / Restatement Behavior

### Empirical Proof from SCHAEFFLER Case `[DOCUMENTED]`
- **Observation 1**: `seqNumber = 1197098`, filed `2025-02-27 17:26:38 IST` (`reInd=N`).
- **Observation 2**: `seqNumber = 1197319`, filed `2025-03-25 12:29:20 IST` (`reInd=R`).
- **Persistence Invariant**: Both filings and their associated normalized facts persist as independent, immutable rows bound to their `filing_id`.
- **Point-in-Time (PIT) Replay**:
  - As-of `2025-03-01`: Replay returns Observation 1.
  - As-of `2025-04-01`: Replay returns both observations.
  - Historical facts are never overwritten in place.

---

## 21. Cross-Exchange Observations `[DOCUMENTED / CLAIM DISCIPLINE]`

In dual-listed companies (INFY):
- Publication timing differences are proven (BSE PDF disclosure earlier, NSE XBRL later).
- **Cross-exchange machine-readable fact equality is NOT YET EMPIRICALLY PROVEN** across automated feeds.
- **Policy**: NSE and BSE observations remain independent source observations. Cross-exchange economic reconciliation is deferred beyond F2B.

---

## 22. Raw Fact vs Canonical Fact Architecture

SI-F2A establishes a **Two-Layer Architecture**:

```
Official Filing Document (XML Artifact)
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ LAYER 1: RAW SOURCE FACT OBSERVATION                   │
│ • Raw Source Occurrence Identity:                      │
│   (document_id, source_occurrence_ordinal)             │
│ • Raw QName (namespace + local_name)                  │
│ • Context reference & structural period coordinates    │
│ • Unit reference & decimals metadata                   │
│ • Verbatim raw lexical string value                    │
│ • Parsed base Decimal value                            │
│ • 100% of reported facts preserved even if unmapped    │
└────────────────────────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ LAYER 2: CANONICAL FACT MAPPINGS                       │
│ • Canonical Economic Identity:                         │
│   (filing_id, canonical_concept, period_type,          │
│    period_start, period_end, statement_scope)          │
│ • Canonical unit & value in base units                 │
│ • Mapping Rule ID & Mapping Version                    │
│ • Confidence status (PROVEN_CANONICAL)                 │
│ • Promotes only approved non-dimensioned enterprise    │
│   aggregates                                           │
└────────────────────────────────────────────────────────┘
```

---

## 23. Fact Identity Proposals: Source Occurrence vs Economic Identity

### Raw Source Occurrence Identity `[INFERRED / RECOMMENDED]`
Separates physical source location from fact payload:
```
Primary Locator: (document_id, source_occurrence_ordinal)
```
Where `source_occurrence_ordinal` is a 1-based sequential integer assigned in document order across all fact elements in the XML.

*Payload Attributes*: `raw_qname, context_ref, unit_ref, decimals, raw_value, numeric_value, is_nil, is_dimensioned, dimension_signature`.

### Canonical Economic Identity `[INFERRED / RECOMMENDED]`
Must include `period_start` and `period_end` so that quarterly and YTD facts never collide:
```
Canonical Key: (filing_id, canonical_concept, period_type, period_start, period_end, statement_scope)
```

---

## 24. PIT Semantics

- Every normalized fact inherits `filing_id` joined to `fundamental_filings.source_published_at`.
- PIT filtering: `WHERE filing.source_published_at <= :as_of_timestamp`.
- Exact timestamp requirement: `DATE_ONLY` and `UNKNOWN` precision filings remain excluded from exact-timestamp PIT replay queries.

---

## 25. Parser Security: Technical Recommendation

- **Hardened Parser**: Recommend `defusedxml.ElementTree` for production parsing in SI-F2B.
- **Dependency Finding**: `defusedxml` is **NOT currently present** in `pyproject.toml` or `uv.lock`. Adding it will require explicit Owner dependency approval in SI-F2B.
- **Application Bounds**:
  - Raw document size bound: `MAX_RAW_DOCUMENT_SIZE_BYTES = 50 MB` (inherited from SI-F1).
  - Decompressed byte bound: 50 MB.
  - XML entity expansion / DTD processing: Prohibited.

---

## 26. Performance / Scale Estimate `[INFERRED / PLANNING ESTIMATE]`

Planning estimates based on sampled filings (not a measured census):
- ~150–500 facts per filing, ~30–250 KB XML.
- 500 issuers over 5 years (20 quarters, Consol + Standalone) $\approx 20,000$ filings, $\approx 6 \text{M}$ raw facts.
- SQLite storage footprint $\approx 800\text{ MB} - 1.5\text{ GB}$ with standard indexes, fitting comfortably on local storage.

---

## 27. Financial-Sector Negative Control

### Empirical Evidence from HDFCBANK `[EMPIRICALLY PROVEN]`
- In parsed fixture `hdfcbank_q3_fy25_banking_sanitized.xml`:
  - `InterestEarned` = ₹85,040.17 Cr.
  - `InterestExpended` = ₹46,914.28 Cr.
  - `RevenueFromOperations`: **ABSENT**.
- **Conclusion**: Banking taxonomy differs fundamentally from corporate IndAS.
- **Claim Scope**: Banking entities (`bank == 'B'`) are proven outside corporate normalization. NBFCs and insurance companies are classified as **`NOT YET EMPIRICALLY VALIDATED / EXCLUDED CONSERVATIVELY`** for initial F2B.

---

## 28. Initial Eligibility Contract: Non-Financial Boundary

A filing is eligible for SI-F2B canonical normalization iff:
1. `series == "EQ"` (Mainboard equity);
2. Authoritative non-financial corporate issuer classification (NOT banking, NOT NBFC, NOT insurance);
3. Supported taxonomy (`in-bse-fin` 2020-03-31);
4. Supported statement scope (`Consolidated` or `Non-Consolidated`);
5. XML payload passes security validation and parses without error.

**Critical Eligibility Rule**:
`bank == "N"` in exchange feeds does **not** prove an issuer is non-financial (it does not differentiate NBFCs or insurance companies).
If ATHENA does not currently possess an authoritative sector classification field, this is an **unresolved eligibility input**.
**Safe Default**: `UNKNOWN ISSUER CLASSIFICATION => NOT ELIGIBLE FOR CANONICAL NORMALIZATION`.

---

## 29. Proposed SI-F2B Domain Model (Design Only)

*Zero production code added in SI-F2A.*

```python
@dataclass(frozen=True, slots=True)
class RawFinancialFact:
    """Verbatim fact observation extracted from official XBRL filing."""
    raw_fact_id: str             # UUID
    filing_id: str               # FK to fundamental_filings
    document_id: str             # FK to filing_documents
    source_occurrence_ordinal: int # Sequential 1..N in document order
    raw_qname: str               # e.g. "in-bse-fin:RevenueFromOperations"
    context_ref: str             # e.g. "OneD"
    unit_ref: str                # e.g. "INR"
    period_type: str             # DURATION, INSTANT
    period_start: date | None
    period_end: date
    duration_days: int
    is_dimensioned: bool
    dimension_signature: str
    decimals: str | None
    raw_value: str               # Verbatim XML text
    numeric_value: Decimal | None
    is_nil: bool

@dataclass(frozen=True, slots=True)
class CanonicalFinancialFact:
    """Normalized economic fact promoted through approved canonical mapping."""
    fact_id: str                 # UUID
    raw_fact_id: str             # FK to RawFinancialFact
    filing_id: str               # FK to fundamental_filings
    canonical_concept: str       # e.g. "REVENUE_FROM_OPERATIONS"
    statement_scope: Scope       # CONSOLIDATED, STANDALONE
    period_type: PeriodType      # QUARTER, HALF_YEAR, NINE_MONTH, FULL_YEAR, INSTANT
    period_start: date | None
    period_end: date
    canonical_unit: str          # "CURRENCY_INR", "INR_PER_SHARE"
    value: Decimal               # Normalized value in base unit
    mapping_version: str         # e.g. "2026-09-v1"
    confidence: MappingConfidence# PROVEN_CANONICAL
```

---

## 30. Proposed SI-F2B Persistence Model (Design Only)

*Schema version remains 21.*

Proposed Schema v22 Additions:
1. `raw_financial_facts`:
   - Primary Key: `raw_fact_id`
   - Unique: `(document_id, source_occurrence_ordinal)`
   - Indexes: `(filing_id)`, `(raw_qname, period_end)`, `(filing_id, is_dimensioned)`
2. `canonical_financial_facts`:
   - Primary Key: `fact_id`
   - Indexes: `(filing_id, canonical_concept)`, `(canonical_concept, period_end, statement_scope)`
   - Unique Constraint: `(filing_id, canonical_concept, period_type, period_start, period_end, statement_scope)`

---

## 31. Explicitly Unresolved Questions

1. **Authoritative Sector Classification**: Does ATHENA's existing instrument master or external feed provide an authoritative flag distinguishing non-financial corporates from NBFCs and insurance companies?
2. **Standalone Cash Flows in Q1/Q3**: Indian companies legally publish cash flow statements at H1 and FY only. Expose cash flows only for H1/FY, or permit derived quarters in later phases? *(Recommendation: Expose only reported H1 and FY cash flows; no synthetic subtraction).*
3. **Segment Revenue Normalization**: Should segment dimensions be normalized in F2B or deferred? *(Recommendation: Exclude dimensional breakdowns from initial canonical facts; preserve in raw facts).*

---

## 32. Risks

1. **Taxonomy Evolution Risk**: Historical filings (pre-2020) may use legacy namespaces. *Mitigation*: F2B mappings must be namespace-qualified and version-aware.
2. **Vendor Software Idiosyncrasies**: Different filing tools format whitespace or context names differently. *Mitigation*: Semantic context classification parses underlying ISO date tags directly.

---

## 33. Empirically Proven Findings

1. Context IDs (`OneD`, `FourD`) are arbitrary vendor tokens and must not be used as semantic rules.
2. Official filings report both single-quarter and cumulative YTD facts in the same document with identical concept QNames, distinguishable strictly by context duration dates.
3. INFY Q3 Revenue (₹41,764 Cr) and 9M Revenue (₹122,064 Cr) share `period_end = 2024-12-31`, proving `period_start` is mandatory in canonical identity.
4. Negative numbers (PAT losses, negative EPS) are reported as native signed strings and convert losslessly to Python `Decimal`.
5. Official banking filings use an incompatible `BANKING_` taxonomy lacking standard corporate revenue concepts.
6. Contexts with explicit dimensions represent segment slices and must not be promoted as enterprise totals.

---

## 34. Documented but Not Empirically Proven Findings

1. Whether 100% of NSE-listed non-financial companies adopt identical IndAS taxonomy namespaces over a 10-year historical span.
2. Machine-readable fact equality between NSE XBRL and BSE disclosures.

---

## 35. Unknowns

1. Authoritative issuer-sector classification availability in current ATHENA databases.
2. Exact edge-case handling for companies transitioning fiscal year-ends (e.g. 15-month stub financial years).
3. Behavior of SME platform XBRL filings.

---

## 36. Recommendations

1. **Adopt Two-Layer Fact Architecture**: Persist `raw_financial_facts` and `canonical_financial_facts` separately.
2. **Enforce Semantic Context Resolution**: Classify contexts strictly by `<period>` dates and dimension presence.
3. **Prohibit Synthetic Subtraction**: Never compute derived quarterly numbers during fact normalization.
4. **Scope Initial Canonical Vocabulary**: Bound initial canonical promotion to the 5 high-confidence income concepts.
5. **Exclude Financial Sector**: Reject `bank == 'B'` filings; treat NBFCs/insurance as conservatively excluded pending authoritative sector classification.

---

## 37. Final 12 Owner Decisions Ready for Freeze

- **D1. APPROVE two-layer architecture**: Raw Source Fact Observation + Canonical Mapping.
- **D2. APPROVE source occurrence identity**: `(document_id, source_occurrence_ordinal)` separate from canonical economic identity and fact payload.
- **D3. APPROVE reported-facts-only normalization**: No synthetic quarter subtraction ($Q2 = H1 - Q1$).
- **D4. APPROVE period-safe canonical duration identity**: `period_start` + `period_end` required for duration identity.
- **D5. APPROVE raw dimensioned fact preservation**: Unsupported material dimensions excluded from initial enterprise promotion.
- **D6. APPROVE duplicate policy**: Preserve raw source occurrences; no highest-precision winner; canonical duplicates classified deterministically; conflicting duplicates unresolved.
- **D7. APPROVE cross-exchange independence in F2B**: Source observations remain independent; reconciliation deferred.
- **D8. APPROVE versioned canonical mappings**: Local reprocessing from immutable source documents/raw observations.
- **D9. APPROVE exact PIT inheritance from SI-F1**: `DATE_ONLY`/`UNKNOWN` remain excluded from exact timestamp replay.
- **D10. APPROVE initial non-financial-only boundary**: Banks excluded empirically; NBFC/insurance conservatively excluded pending evidence; unknown issuer classification $\implies$ not canonically normalized.
- **D11. APPROVE secure XML parser requirement**: Exact dependency added only during reviewed F2B implementation.
- **D12. APPROVE initial concept scope split**:
  - *High-Confidence Canonical Promotion*: `REVENUE_FROM_OPERATIONS`, `PROFIT_LOSS_BEFORE_TAX`, `PROFIT_LOSS_FOR_PERIOD`, `EPS_BASIC`, `EPS_DILUTED`.
  - *Raw Mapping Proven but Canonical Context Rule Required*: `PAID_UP_EQUITY_CAPITAL`, `FACE_VALUE_PER_SHARE`.

---

## 38. GO / NO-GO for SI-F2B

### **STATUS: SI-F2A COMPLETE AND FROZEN**

Owner / Chief Architect approved decisions D1 through D12 on 2026-09-15 and authorized milestone freeze. SI-F2B is cleared for future execution once formally scheduled; SI-F2B implementation is NOT started in this milestone.

---

## 39. Files Created / Changed

- `docs/research/SI-F2A-FINANCIAL-FACT-NORMALIZATION-DISCOVERY.md` *(Updated Discovery Document)*
- `tools/research/si_fundamentals/f2a_normalization_discovery.py` *(Updated Fixture-Parsing Evidence Builder)*
- `tools/research/si_fundamentals/f2a_normalization_evidence.json` *(Updated Deterministic Machine-Readable Evidence Artifact)*
- `tools/research/si_fundamentals/fixtures/infy_q3_fy25_sanitized.xml` *(Sanitized Source-Derived XML Fixture)*
- `tools/research/si_fundamentals/fixtures/paytm_q3_fy25_loss_sanitized.xml` *(Sanitized Source-Derived XML Fixture)*
- `tools/research/si_fundamentals/fixtures/hdfcbank_q3_fy25_banking_sanitized.xml` *(Sanitized Source-Derived XML Fixture)*
- `tools/research/si_fundamentals/fixtures/duplicate_and_nil_cases_sanitized.xml` *(Constructed Methodology XML Fixture)*

*Zero production code modified. `SCHEMA_VERSION` remains 21.*
