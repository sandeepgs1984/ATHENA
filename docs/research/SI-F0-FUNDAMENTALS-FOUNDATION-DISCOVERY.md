# SI-F0 — ATHENA Fundamentals Foundation Discovery & Architecture

Status: COMPLETE AND FROZEN (Owner / Chief Architect Approved 2026-09-15)
Date: 2026-09-15
Author: Antigravity (ATHENA Architecture Specialist)
Milestone: SI-F0 (Symbol Intelligence Fundamentals Track)
Governing Standards: ATHENA-000, ATHENA-001 (Accepted Amendments), ATHENA-002, ADR-002, ADR-008, ADR-011, ADR-015

---

## 1. Executive Summary

ATHENA is an advisory-only decision-intelligence platform for Indian equities (NSE/BSE). Up through milestone `SI-P2E`, Symbol Intelligence (SI) has successfully composed technical price structure, trend, multi-timeframe price action, DarvaX screening, and portfolio context for any exchange-listed equity. However, across all existing surfaces, fundamental and earnings intelligence is represented by an explicit placeholder:

```json
"fundamentals": {
  "status": "NOT_INGESTED",
  "reason": "ATHENA has no point-in-time-safe fundamental/earnings source in SI-P1. Ingesting unversioned snapshots would corrupt replay determinism."
}
```

The objective of milestone **SI-F0** is to establish the authoritative discovery and architectural framework required to introduce fundamentals into ATHENA. This foundation must eventually answer factual investor questions (business identity, market capitalization, revenue and profit trajectories, margins, balance sheet leverage, cash flow generation, quarterly earnings results, and ownership/shareholding structure) without ever guessing, fabricating missing timestamps, scraping fragile HTML pages, or inventing synthetic ratings.

### Key Discovery Findings & Post-Review Corrections

1. **Zero Fundamental State in Existing Database (Repository Fact)**: ATHENA currently stores **zero** financial statement line items (no revenue, PAT, EBITDA, debt, or cash flow) and **zero** market capitalization or shares outstanding metrics. The only fundamental metadata stored is a seed-backfilled `sector` / `industry` string on `instruments` (derived from NSE constituent CSVs via `ops/constituents.py`) and official corporate actions (splits, bonuses, dividends) in `corporate_actions`.
2. **Kite API is Purely Market Data (Repository Fact)**: Zerodha Kite Connect provides quotes, LTP, daily/intraday candles, and an instrument CSV dump. It provides **no** balance sheets, P&L statements, cash flows, or shareholding patterns. It cannot serve as a fundamentals source.
3. **Official Exchange Filings are the Strongest Candidate Canonical Provenance Source**: Both NSE and BSE mandate structured financial reporting under SEBI (Listing Obligations and Disclosure Requirements) Regulations, 2015 (LODR Reg 33). Official exchange filings preserve the original legal disclosure and dissemination context (`published_at`). Commercial aggregators are reclassified as **Candidate Normalization / Secondary Providers** whose claims of coverage, depth, and PIT preservation must be empirically proven in a dedicated feasibility spike (`SI-F0.1`) before any architectural commitment.
4. **Point-In-Time (PIT) & Bitemporal Lineage are Hard Requirements**: In backtesting, historical replay, and retrospective trade review (ID-7B1), ATHENA must answer: *"What was actually knowable at market close on date X?"* Financial numbers published for the quarter ending June 30 must never be visible on June 30; they only become knowable when the board meeting outcome is disseminated by the exchange (typically 30 to 45 days later). Restatements, clerical corrections, and revised filings must be tracked bitemporally and versioned immutably without ever overwriting historical truth.
5. **No Timestamp Fabrication**: ATHENA must **never** fabricate publication timestamps (e.g. defaulting missing timestamps to `23:59:59 IST` is strictly rejected). Publication precision must be explicitly represented (`EXACT_TIMESTAMP`, `DATE_ONLY`, `UNKNOWN`), and date-only eligibility policies must remain conservative and transparent.
6. **Strict Evidence-to-Decision Boundary**: Fundamentals must enter ATHENA as immutable, factual evidence. They must **not** be blended into `DecisionEngine`, used to modify trade plan conviction, or transformed into synthetic "Quality Grades" or "Valuation Scores".
7. **Phased Implementation Order**: Implementation cannot proceed directly to schema/persistence without empirical source validation. A dedicated **SI-F0.1 Source Feasibility Spike** must validate real-world filing artifacts across a representative matrix of Indian issuers before `SI-F1` persistence is designed.

### Final Verdict: COMPLETE AND FROZEN 2026-09-15 — PROCEED TO SI-F0.1 SOURCE FEASIBILITY SPIKE

---

## 2. Repository Findings (Established Facts)

A comprehensive audit of the ATHENA repository was conducted across source modules, schema definitions, provider implementations, and CLI tools.

### 2.1 Symbols & Identity (`src/athena/symbols/`, `src/athena/domain/market.py`)
- `Instrument` (`athena.domain.market`): Carries `instrument_id` (`EXCHANGE:SYMBOL`), `symbol`, `exchange`, `series`, `isin` (optional), `name`, `sector`, `lot_size`, `tick_size`, `status`, `listed_date`, and `delisted_date`.
- `SymbolRecord` (`athena.symbols.models`): Implements ADR-011. Distinguishes what *exists* on an exchange from what has been *ingested*. Tracks `series_source` (`NSE_OFFICIAL`, `INFERRED_SUFFIX`, `BROKER`) and `board` (`MAINBOARD`, `SME`, `UNKNOWN`).
- **Repository Fact**: Neither `Instrument` nor `SymbolRecord` tracks `cin` (Corporate Identity Number), `bse_code` (6-digit scrip code), `shares_outstanding`, or corporate cross-listings across dual exchanges.

### 2.2 Data Store & Schema (`src/athena/data/store/schema.py`, `repository.py`)
- The active SQLite database operates at `SCHEMA_VERSION = 20`.
- Tables present: `instruments`, `candles`, `quotes`, `market_snapshots`, `institutional_flows`, `corporate_actions`, `quarantine_records`, `runs`, `decisions`, `decision_traces`, `decision_journal`, `trade_outcomes`, `owner_positions`, `portfolio_*` (holdings, sync, analysis), `owner_candidates`, `saved_symbols`, `entry_qualifications`, `entry_actionabilities`.
- **Repository Fact**: There is **no table for financial statements, earnings, balance sheets, cash flows, shares outstanding, or shareholding patterns**.
- `corporate_actions` stores `action_id`, `instrument_id`, `action_type`, `ex_date`, and `details_json`. It records discrete corporate events (dividends, splits, bonuses) but not company financial statements or historical share-count trajectories.

### 2.3 Sector & Industry Metadata (`src/athena/ops/constituents.py`, `sector_health/`)
- `ops/constituents.py` downloads official NSE index constituent CSVs (`ind_nifty500list.csv`, etc.).
- `parse_nifty_constituent_rows()` extracts `symbol` and `industry`, then backfills `instruments.sector` in SQLite.
- **Repository Fact**: The official NSE CSV contains `Company Name,Industry,Symbol,Series,ISIN Code`. Currently, `constituents.py` extracts only `symbol` and `industry`, dropping `Company Name` and `ISIN Code`. Backfilling overwrites the `sector` column unversioned.

### 2.4 Market Cap & Size Findings (`src/athena/darvax/screening/liquidity.py`)
- DarvaX explicit design note in `liquidity.py`:
  > *"Why liquidity and not capitalisation: ATHENA holds no market-cap data: there is no `market_cap` or `shares_outstanding` column anywhere, and the broker dump reports `last_price = 0` for every row, so it cannot even be derived. A real size filter needs a new versioned data source."*
- **Repository Fact**: All current size filtering in ATHENA is based on median daily traded rupee turnover, not market capitalization.

### 2.5 Provider Infrastructure (`src/athena/data/providers/`)
- `kite_provider.py`: Reads OHLCV candles, quotes, and LTP via GET-only endpoints. No fundamentals.
- `nse_corporate_actions_provider.py`: Implements direct HTTP retrieval from official NSE endpoints (`https://www.nseindia.com/api/corporates-corporateActions`) using cookie jar session maintenance. Demonstrates an established pattern for official exchange data retrieval.
- `nse_institutional_provider.py`: Fetches daily FII/DII flow totals from official NSE JSON.

### 2.6 Symbol Intelligence (`src/athena/symbol_intelligence/composer.py`, `dtos/symbol_intelligence.py`)
- In `composer.py`, `fundamentals` and `news` are hardcoded as `SiNotIngestedDTO(reason=SI_FUNDAMENTALS_REASON)`.
- The system is architected to receive typed evidence DTOs once a backend provider is connected.

---

## 3. Existing-Capability Reuse Matrix

| Capability | Current Owner | Source | Persisted? | PIT-Safe? | Provenance? | Universal NSE/BSE? | Reusable for SI-F? | Gap / Action Required |
|---|---|---|---|---|---|---|---|---|
| **Security Identity** | `symbols.models` | Kite / Symbol Master | Yes (`symbol_master`) | Yes | Yes (`source`) | Partial (NSE-skewed) | **YES (Baseline)** | Lacks BSE 6-digit codes and CIN. |
| **ISIN Code** | `domain.market` / `ops` | NSE Index CSV / File Provider | Partial (`instruments.isin`) | Yes | Weak | Partial | **YES** | Need to persist ISIN universally for all catalog symbols. |
| **Industry / Sector** | `ops.constituents` | NSE Indices CSV | Yes (`instruments.sector`) | No (Unversioned overwrite) | Partial | No (Nifty 500 only) | **PARTIAL** | Unversioned overwrite; only covers ~500 NSE index scrips. |
| **Listing Board** | `symbols.classify` | Symbol Master | Yes (`symbol_master.board`) | Yes | Yes | Yes (NSE Mainboard / SME) | **YES** | Ready for board discrimination. |
| **Market Capitalization** | *None* | *None* | **NO** | N/A | N/A | N/A | **NO** | Unresolved: need PIT share count chronology or verified source. |
| **D1 Price / OHLCV** | `data.store` | Kite / Provider | Yes (`candles`) | Yes (`ts_open`) | Yes (`source`) | Yes (for ingested scrips) | **YES** | Can provide the price input for valuation multiples. |
| **Corporate Actions** | `data.providers.nse_ca` | Official NSE API | Yes (`corporate_actions`) | Yes (`ex_date`) | Yes | NSE only | **YES (Events)** | Captures dividend events, splits, and bonus history. |
| **Institutional Flows** | `data.providers.nse_inst` | Official NSE API | Yes (`institutional_flows`) | Yes (`session_date`) | Yes | Market-level | **NO (Macro only)** | FII/DII is aggregate market-wide, not per-symbol shareholding. |
| **Financial Statements** | *None* | *None* | **NO** | N/A | N/A | N/A | **NO** | Complete greenfield required for statements & results. |
| **Shareholding Patterns** | *None* | *None* | **NO** | N/A | N/A | N/A | **NO** | Greenfield required for promoter/FII/DII holding percentages. |
| **Earnings Dates** | *None* | *None* | **NO** | N/A | N/A | N/A | **NO** | Greenfield required for board meeting / results filing dates. |

---

## 4. Fundamental Evidence Taxonomy & Conceptual Fact Identity

### 4.1 The Conceptual Normalized Fact Identity
The preliminary discovery tuple `(period_end, published_at, ingested_at, source, value)` was an availability/provenance record, not an adequate entity identity. It fails to distinguish between quarterly vs YTD numbers, consolidated vs standalone filings, or original vs revised submissions.

To prevent semantic collisions, every normalized fundamental fact in ATHENA must conform conceptually to the following multi-attribute identity:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ATHENA NORMALIZED FACT IDENTITY MODEL                    │
├──────────────────────────┬──────────────────────────────────────────────────┤
│ ENTITY & MAPPING         │ • issuer_id (CIN or canonical entity key)        │
│                          │ • instrument_mapping (EXCHANGE:SYMBOL, ISIN)     │
│                          │ • metric_key (canonical taxonomy identifier)     │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ REPORTING PERIOD         │ • period_start (nullable for snapshot BS items)  │
│ (ECONOMIC TIME)          │ • period_end (calendar boundary date)            │
│                          │ • period_type (QUARTER / YTD / HALF_YEAR / FY)   │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ DISCLOSURE CONTEXT       │ • statement_scope (CONSOLIDATED / STANDALONE)    │
│                          │ • audit_status (AUDITED / UNAUDITED_LIMITED_REV) │
│                          │ • filing_id (source filing document identifier)  │
│                          │ • filing_version / revision_relationship         │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ AVAILABILITY & LINEAGE   │ • published_at (exchange broadcast timestamp)    │
│ (MARKET-KNOWLEDGE TIME)  │ • publication_precision (EXACT / DATE / UNKNOWN) │
│ (ATHENA SYSTEM TIME)     │ • ingested_at (ATHENA storage timestamp)         │
│                          │ • source (e.g. NSE_XBRL, BSE_XBRL, PROVIDER_X)   │
│                          │ • source_record_id                               │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ MEASUREMENT              │ • value (Decimal)                                │
│                          │ • unit (e.g. INR_CRORES, NUMBER, RATIO)          │
│                          │ • currency (INR)                                 │
└──────────────────────────┴──────────────────────────────────────────────────┘
```

#### Collision Preventions Guaranteed by this Identity
- **Quarterly vs YTD Collision**: Prevents treating Q3 YTD (9-month cumulative PAT) as Q3 Standalone (3-month quarterly PAT).
- **Scope Collision**: Prevents mixing Tata Motors Consolidated (including JLR) with Standalone (domestic India operations only).
- **Revision Collision**: Prevents a clerical correction filed on Day 2 from overwriting or colliding with the original Day 1 filing.
- **Horizon Collision**: Prevents conflating full-year FY EPS with 3-month quarterly EPS.

*(Note: Exact SQL DDL columns and indices are deliberately NOT frozen in SI-F0; they will be formalized in SI-F1 after source feasibility is established).*

### 4.2 Candidate Evidence Classes (Non-Financial Corporates)

#### A. Identity Evidence
- `company_name`: Official legal entity name.
- `symbol`: Trading ticker on exchange.
- `exchange`: `NSE` or `BSE`.
- `isin`: Universal 12-character ISIN code.
- `cin`: 21-character Corporate Identity Number registered with MCA.
- `bse_code`: 6-digit BSE scrip code where applicable.
- `sector` & `industry`: Official classification.
- `board`: `MAINBOARD` or `SME`.

#### B. Income Statement Line Items (Quarterly & Annual)
- `revenue_from_operations`: Net top-line sales turnover.
- `other_income`: Treasury, non-operating income.
- `total_income`: Sum of operational revenue and other income.
- `operating_expenses`: Sum of raw materials, staff costs, and other operational expenses.
- `operating_profit` / `ebitda`: Factual statement line items as filed under IndAS.
- `depreciation_and_amortization`: Non-cash write-downs.
- `finance_costs`: Interest expenses.
- `exceptional_items`: Disclosed one-off adjustments.
- `pbt`: Profit Before Tax.
- `tax_expense`: Current and deferred tax.
- `pat` / `net_income`: Profit After Tax attributable to owners.
- `diluted_eps`: Diluted earnings per share.

#### C. Balance Sheet Line Items (Half-Yearly & Annual)
- `share_capital`: Issued and paid-up equity capital.
- `reserves_and_surplus`: Retained earnings and reserves.
- `net_worth` / `total_equity`: Share capital + reserves.
- `total_debt`: Non-current borrowings + current borrowings.
- `cash_and_equivalents`: Cash, bank balances, liquid investments.
- `total_assets`: Total assets reported under IndAS Schedule III.
- `current_assets` & `current_liabilities`.

#### D. Cash Flow Line Items (Half-Yearly & Annual)
- `cash_from_operating_activities` (CFO).
- `cash_from_investing_activities` (CFI).
- `cash_from_financing_activities` (CFF).
- `capex`: Additions to PP&E / capital work-in-progress as disclosed in CFI or schedules.

#### E. Shareholding Line Items (Quarterly under SEBI Reg 31)
- `promoter_holding_pct`: Total promoter group equity percentage.
- `promoter_pledged_pct`: Pledged shares as % of promoter holding.
- `promoter_pledged_of_total_pct`: Pledged shares as % of total equity.
- `fii_holding_pct`: Foreign Institutional Investor percentage.
- `dii_holding_pct`: Domestic Institutional Investor percentage (Mutual Funds, Insurance).
- `public_holding_pct`: Retail and non-institutional public.
- `total_equity_shares`: Total number of issued equity shares.

---

## 5. Source Strategy: Canonical Provenance vs Candidate Normalization

In response to Chief Architect review, the source strategy is formally clarified:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PROPOSED SOURCE ARCHITECTURE                          │
├──────────────────────────────────────┬──────────────────────────────────────┤
│ PRIMARY CANONICAL PROVENANCE         │ CANDIDATE NORMALIZATION / SECONDARY  │
│ • Official NSE / BSE XBRL Filings    │ • Commercial Indian APIs (Screener,  │
│ • Mandated by SEBI LODR Reg 33       │   Trendlyne, Accord Fintech)         │
│ • Preserves true legal dissemination │ • Must undergo empirical validation  │
│   timestamp (`published_at`)         │   in SI-F0.1 spike before adoption   │
│ • Authoritative audit trail          │ • Evaluated for coverage & fidelity  │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

### 5.1 Official Exchange Disclosures (Strongest Canonical Candidate)
- **Role**: Primary candidate for authoritative provenance and legal verification.
- **Strengths**: Legal compliance record under SEBI LODR; includes original board meeting dissemination timestamps; full access to notes and auditor qualifications; free of commercial vendor licensing encumbrances.
- **Challenges**: In-house parsing of complex XBRL taxonomy namespaces across IndAS divisions and revisions; exchange portal bot-protection (Cloudflare/Akamai).

### 5.2 Commercial Aggregators (Candidate Normalization / Secondary)
- **Role**: Reclassified as **Candidate Normalization / Secondary Providers** pending an empirical feasibility spike.
- **Unverified Properties**: The preliminary discovery made unsupported assertions regarding coverage and PIT suitability. ATHENA does not currently possess empirical evidence that commercial providers:
  - preserve original exchange dissemination timestamps (many store only dates or ingestion times);
  - retain complete historical revisions without overwriting;
  - distinguish quarterly vs cumulative YTD reporting without silent heuristics;
  - maintain immutable historical values across ticker changes and restatements;
  - permit local, automated single-user caching under their terms of service.
- **Requirement**: No commercial aggregator will be adopted into production without passing the **SI-F0.1 Source Feasibility Spike**.

### 5.3 Global Financial APIs (Yahoo Finance, AlphaVantage, FMP)
- **Status**: **REJECTED** for core Indian equity fundamentals.
- **Rationale**: Proven track record of corrupting Indian April–March fiscal cycles, missing IndAS-specific exceptional items, omitting SEBI shareholding patterns, and overwriting historical quarters without versioning.

---

## 6. Point-In-Time (PIT), Bitemporal Lineage & Precision Model

To guarantee 100% determinism in historical backtesting and retrospective trade analysis (ID-7B1), ATHENA explicitly separates three temporal dimensions and one lineage dimension:

```
                             FOUR-DIMENSIONAL TEMPORAL MODEL
┌─────────────────────────┬──────────────────────────────────────────────────┐
│ 1. ECONOMIC TIME        │ • period_start (e.g. 2026-04-01)                 │
│ (The reporting period)  │ • period_end (e.g. 2026-06-30)                   │
├─────────────────────────┼──────────────────────────────────────────────────┤
│ 2. MARKET-KNOWLEDGE TIME│ • published_at (e.g. 2026-08-11 14:15:22 IST)    │
│ (When the public knew)  │ • publication_precision (EXACT, DATE_ONLY, UNKN) │
├─────────────────────────┼──────────────────────────────────────────────────┤
│ 3. ATHENA SYSTEM TIME   │ • ingested_at (e.g. 2026-08-11 14:17:05 UTC)     │
│ (When ATHENA stored it) │ • audit run_id and payload SHA256                │
├─────────────────────────┼──────────────────────────────────────────────────┤
│ 4. VERSION LINEAGE      │ • filing_version (ORIGINAL, REVISED, RESTATED)   │
│ (Immutable history)     │ • supersedes_filing_id                           │
└─────────────────────────┴──────────────────────────────────────────────────┘
```

### 6.1 Answering: "What Was Knowable at Date $X$?"
For any historical query evaluated at as-of timestamp $T$:
$$\text{Eligible Evidence}(T) = \{ f \in \text{Ledger} \mid f.\text{market\_available\_at} \le T \}$$
Where multiple versions of a filing exist for the same `(issuer_id, period_end, metric_key)`, ATHENA selects the latest version whose `market_available_at <= T`. Previous versions are **never overwritten**, preserving the exact market reality that existed at earlier historical moments.

### 6.2 Zero Timestamp Fabrication Policy
The preliminary discovery proposal to fabricate missing publication times by defaulting to `23:59:59 IST` is **formally revoked**. ATHENA must never invent artificial provenance data.

Instead, the system models publication precision explicitly:
- **`EXACT_TIMESTAMP`**: Dissemination timestamp is known down to the second (e.g. from exchange broadcast feeds: `2026-08-11 14:15:22 IST`). Available immediately at that timestamp.
- **`DATE_ONLY`**: The source records only a calendar date of publication (e.g. `2026-08-11`). The exact intraday release time is unknown.
- **`UNKNOWN`**: Publication date is missing or unverified.

#### Candidate Date-Only Replay Policies (Unresolved Methodology Choice)
When evaluating daily-close replay against evidence with `DATE_ONLY` precision:
- *Conservative Option (Recommended)*: Consider the fact knowable only on the **next valid trading session** after the publication date ($T+1$). This guarantees zero lookahead leakage into the publication day's close.
- *Permissive Option*: Consider the fact knowable at market close on the publication date ($T+0$), assuming results were filed during market hours or prior to close. (Carries risk of leaking after-market announcements into the same day's close).
- *Methodology Status*: Left unresolved for Owner decision prior to historical backtesting integration. The original uncertainty (`publication_precision = DATE_ONLY`) remains permanently observable in the ledger.

---

## 7. Raw vs Normalized vs Derived Evidence Architecture

Data flows through four strictly isolated stages. Derived metrics must never masquerade as source-provided facts.

```
┌────────────────────────┐
│  1. RAW FILING         │  Verbatim payload (XBRL/JSON) stored with document hash.
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│  2. NORMALIZED FACT    │  Canonical metric keys mapped from source taxonomy.
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│  3. DERIVED METRIC     │  Pure deterministic mathematical functions.
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│  4. PRESENTATION DTO   │  Formatted display values, currency units (₹ Cr), audit badges.
└────────────────────────┘
```

### 7.1 Candidate Derived Metrics — Formula/Taxonomy Validation Required
In accordance with Chief Architect instructions, the following derived formulas are **not frozen** in SI-F0. They are classified as **Candidate Derived Metrics** pending taxonomy validation in SI-F0.1/SI-F3:

1. **TTM (Trailing Twelve Months)**:
   - *Proposed Formula*: $\sum_{i=0}^{3} \text{Quarterly Metric}_{Q-i}$.
   - *Constraint*: Requires exactly 4 consecutive quarters under identical `statement_scope`. If any quarter is missing, TTM = `NULL`.
2. **Free Cash Flow (FCF)**:
   - *Status*: Unfrozen. Requires validation of whether `capex` can be reliably and consistently extracted from IndAS Cash Flow schedules across issuers before freezing `CFO - capex`.
3. **EBITDA Normalization**:
   - *Status*: Unfrozen. Indian companies vary in treating "Other Income" inside vs outside Operating Profit. Normalization rules must be validated against actual filing practices.
4. **Valuation Multiples (P/E, P/B, EV/EBITDA)**:
   - *Status*: Unfrozen. Exact numerator and denominator chronology, negative EPS treatment, and net debt definitions require empirical validation.
5. **ROCE / ROE**:
   - *Status*: Unfrozen. Capital employed definitions (average vs ending net worth, lease liabilities under IndAS 116) require methodology freeze.

---

## 8. Market Capitalization & Share Count Chronology (Unresolved)

The preliminary recommendation to calculate market cap as `SEBI Reg 31 Shares Outstanding × D1 Close` is **withdrawn from approval**. It is preserved as one of two candidate paths pending investigation.

### 8.1 The Share Count Chronology Problem
Shares outstanding is not a static quarterly number. Between quarterly shareholding filings (SEBI Reg 31), significant corporate events alter the share count:
- Bonus issues and stock splits (changes share count without altering market cap);
- New share issuance (QIP, preferential allotments, rights issues);
- Employee stock option (ESOP) allotments (frequent small additions);
- Share buybacks and capital reductions;
- Conversion of warrants or convertible debentures.

Furthermore, there is a divergence between the **effective/allotment date** and the **exchange listing/filing date**. Multiplying a stale quarterly share count by a split-adjusted or post-dilution D1 price produces an erroneous market capitalization.

### 8.2 Two Candidate Paths for Market Capitalization
- **Candidate Path A (Chronology-Adjusted Shares × D1 Close)**:
  - Track an event-driven shares-outstanding ledger adjusted by corporate action corporate filings (splits, bonuses, allotments) multiplied by the coherent completed-D1 close.
- **Candidate Path B (Source-Provided PIT-Safe Market Capitalization)**:
  - Ingest an authoritative, exchange-calculated market capitalization snapshot provided directly by the exchange or verified provider with explicit as-of timestamps.
- **Decision Status**: **DELIBERATELY UNRESOLVED**. The choice between Path A and Path B will be determined based on empirical evidence gathered in `SI-F0.1`.

---

## 9. Sector-Specific Semantics — Owner Approved Decision

### 9.1 Approved Scope: Non-Financial Mainboard Equities First
The Owner / Chief Architect has approved:
**Initial fundamentals implementation will focus strictly on Non-Financial Mainboard Equities.**

### 9.2 Rationale & Guardrails
- Commercial Banks, NBFCs, Insurance companies, and REITs/InvITs operate under fundamentally different financial accounting standards:
  - **Banks & NBFCs**: Do not report EBITDA or Gross Margin. Operating profit is driven by Net Interest Income (NII), Net Interest Margin (NIM), and credit loss provisions.
  - **Insurance**: Driven by Net Premium Income, Solvency Ratios, and Combined Ratios.
  - **REITs/InvITs**: Driven by Net Operating Income (NOI) and Distributions per Unit (DPU).
- **Rule**: Forcing financial institutions through a non-financial corporate template produces financial nonsense. In the initial release, financial institutions will be identified and flagged:
  `FINANCIAL_INSTITUTION_SPECIALIZED_TEMPLATE_PENDING`
  rather than displaying corrupted corporate metrics. The architecture will accommodate sector-specific normalizer adapters in later milestones.

---

## 10. Financial Statement Scope — Owner Approved Decision & Integrity Rule

### 10.1 Approved Policy
- **Consolidated Preferred**: Consolidated financial statements are preferred for investor presentation in Symbol Intelligence when available.
- **Standalone Fallback**: Standalone statements serve as an automatic fallback when consolidated statements are not filed (e.g. single-entity operating companies).

### 10.2 Mandatory Integrity Rule: Scope Isolation
- **Independent Persistence**: Consolidated facts and Standalone facts must **always remain independently persisted records**. They must never be merged or blended into a single row.
- **No Silent Scope Switching**: A multi-quarter financial trajectory must **never silently switch scope between periods** (e.g. Q1 Consolidated $\to$ Q2 Standalone $\to$ Q3 Consolidated). If a continuous time series cannot maintain coherent scope, the comparison must **fail closed** or prominently disclose the scope transition in the UI.

---

## 11. SME Board Coverage — Owner Approved Deferral

### 11.1 Approved Policy
- **Defer Initial Ingestion**: Fundamentals for SME scrips (NSE Emerge / BSE SME) are deferred from initial `SI-F1`–`SI-F3` implementation.
- **Regulatory Grounding**: Under Chapter IX of SEBI (Issue of Capital and Disclosure Requirements) Regulations, SME listed companies are legally required to file financial statements **half-yearly**, not quarterly.
- **Representation**: SME scrips will not be treated as broken or permanently unsupported; they will display an explicit phased-coverage badge:
  `SME_HALF_YEARLY_REPORTING_MODEL_DEFERRED`
  until dedicated half-yearly statement adapters are built.

---

## 12. Regulatory Freshness Model (SEBI LODR Reg 33)

Fundamentals freshness is governed by regulatory filing cycles, not daily market session clocks.

```
SEBI LODR Filing Windows:
┌─────────────────────────┬─────────────────────────┬─────────────────────────┐
│ Reporting Quarter       │ Quarter End Date        │ Mandatory Filing Cutoff │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ Q1 (April - June)       │ June 30                 │ August 14 (45 days)     │
│ Q2 (July - September)   │ September 30            │ November 14 (45 days)   │
│ Q3 (October - December) │ December 31             │ February 14 (45 days)   │
│ Q4 / Annual (Jan - Mar) │ March 31                │ May 30 (60 days)        │
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

### 12.1 Deterministic Freshness Statuses
1. **`CURRENT`**: Latest reported quarter is within the active reporting cycle (i.e. prior quarter reported, current deadline not yet passed).
2. **`AGING`**: Calendar date has passed the quarter-end date, but is within the statutory 45/60-day filing window. Stock 360 displays: `RESULTS AWAITED (DUE BY [DATE])`.
3. **`OVERDUE_STALE`**: The statutory filing deadline has passed with no filing disseminated. Indicates regulatory delay or non-compliance.
4. **`UNAVAILABLE`**: No fundamental filing exists on record for the instrument.

### 12.2 Bitemporal Valuation Freshness
Valuation multiples display both timestamps explicitly:
`P/E: 24.2 (Price as of: 2026-09-15 | Earnings as of: Q1 FY27, ended 2026-06-30)`

---

## 13. Proposed Fundamentals UX Architecture (Stock 360)

The Fundamentals surface within Stock 360 presents dense, factual evidence with full audit lineage.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STOCK 360 ──► [OVERVIEW]  [TECHNICAL D1]  [FUNDAMENTALS]  [PORTFOLIO]       │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. SUMMARY KPI STRIP                                                        │
│ MCap: ₹4,85,200 Cr | P/E: 24.2 | P/B: 6.8 | TTM Rev: ₹1,52,000 Cr (+14% YoY)│
│ TTM PAT: ₹26,400 Cr (+18% YoY) | D/E: 0.12 | Scope: CONSOLIDATED            │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. TRAILING QUARTERLY PERFORMANCE (LAST 8 QUARTERS)                         │
│ [Bar Chart: Revenue & PAT Trajectory with Scope Indicator]                  │
│ Quarter   Rev (₹ Cr)  YoY %   PAT (₹ Cr)  YoY %   Op Margin %  Filing Date  │
│ Q1 FY27     38,500    +14.2%    6,800     +18.4%    21.2%      2026-08-11   │
│ Q4 FY26     37,200    +12.1%    6,450     +15.0%    20.8%      2026-05-18   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. CAPITAL STRUCTURE & BALANCE SHEET (LAST 4 REPORTED PERIODS)              │
│ Metric (₹ Cr)           FY26 (A)      H1 FY26 (A)    FY25 (A)     FY24 (A)  │
│ Net Worth               92,400          86,100        78,200       69,500   │
│ Total Debt              11,200          11,500        12,000       14,100   │
│ Cash & Equivalents      18,500          14,200        12,800        9,400   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. OWNERSHIP & SHAREHOLDING STRUCTURE (SEBI REG 31)                         │
│ Category          Current %     Prev Qtr %     QoQ Shift      Pledged %     │
│ Promoter           50.85%         50.85%          0.00%         0.00%       │
│ FII / FPI          22.40%         21.60%         +0.80%          N/A        │
│ DII (MF/Ins)       15.25%         15.50%         -0.25%          N/A        │
│ Public / Other     11.50%         12.05%         -0.55%          N/A        │
├─────────────────────────────────────────────────────────────────────────────┤
│ 5. AUDIT TRAIL & PROVENANCE                                                 │
│ Source: Official NSE XBRL Disclosure | Scope: CONSOLIDATED | Auditor: Clean │
│ Exchange Dissemination: 2026-08-11 14:15:22 IST (EXACT) | Hash: 8f2c...4a1 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Prohibited UX Elements (Owner Approved)
The following synthetic labels are **strictly forbidden** across all ATHENA surfaces:
- ❌ "Strong Fundamentals" / "Weak Fundamentals"
- ❌ "Undervalued" / "Overvalued" / "Cheap" / "Expensive"
- ❌ "Quality Score" / "Fundamental Score" / "Valuation Score"
- ❌ "Buy" / "Sell" / "Accumulate" recommendations
- ❌ Automated conviction adjustments in trade plans

---

## 14. Boundaries with Existing ATHENA Engines (Owner Approved)

```
                        ┌──────────────────────────────┐
                        │      ATHENA CORE ENGINE      │
                        │  (Regime, Indicators, Setup) │
                        └──────────────┬───────────────┘
                                       │
                  ┌────────────────────┴────────────────────┐
                  ▼                                         ▼
       ┌─────────────────────┐                   ┌─────────────────────┐
       │   DECISION ENGINE   │                   │ SYMBOL INTELLIGENCE │
       │  • Technical Gating │                   │  • Composition Only │
       │  • Risk & Execution │                   │  • Stock 360        │
       │  • Trade Plans      │                   │  • Reads Core + SI-F│
       └─────────────────────┘                   └──────────┬──────────┘
                  │                                         │
                  │ (FROZEN BOUNDARY)                       ▼
                  │ NO DIRECT LINKAGE            ┌─────────────────────┐
                  └─────────── X ───────────────►│    SI-F (NEW)       │
                                                 │  • Pure Factual Ev. │
                                                 │  • Statements/Ratios│
                                                 └─────────────────────┘
```

1. **DecisionEngine Boundary**: Fundamentals remain **pure factual evidence**. Fundamentals will not be fed into `DecisionEngine` gates or scoring algorithms. Any future use by DecisionEngine requires an independent, Owner-approved methodology milestone supported by historical replay validation.
2. **Portfolio & DarvaX**: No side effects on existing portfolio holdings, reconciliation, or DarvaX box scans.
3. **Symbol Intelligence Composer**: The composer will transition `fundamentals` from `SiNotIngestedDTO` to typed factual DTOs once implementation milestones are completed.

---

## 15. Security, Licensing & Operational Concerns

1. **Exchange Access Discipline**: Direct access to official exchange disclosures must respect exchange rate limits and maintain proper session handling (`CookieJar`), avoiding aggressive scraping that triggers Cloudflare IP blocks.
2. **Commercial Vendor Licensing**: If a commercial aggregator is validated in `SI-F0.1`, usage must strictly adhere to single-user local decision-support licensing terms.
3. **Storage Efficiency**: An append-only facts table for 2,000 equities across 8 quarters will occupy ~50–80 MB in SQLite, maintaining rapid query performance under proper compound indexing.

---

## 16. Testing Strategy

1. **Deterministic Bitemporal Query Tests**: Ingest simulated filings with distinct `period_end` and `published_at` dates. Prove that historical queries at $T$ never leak results published at $T + \Delta$.
2. **Revision Priority Tests**: Verify that revised filings append cleanly and take precedence for as-of queries evaluated after the revision, while preserving original values for earlier queries.
3. **Scope Integrity Tests**: Assert that a time series query fails or explicitly flags when consecutive quarters have mismatched scopes (Consolidated vs Standalone).
4. **Precision Handling Tests**: Verify that `DATE_ONLY` publication precision is handled according to policy without timestamp fabrication.

---

## 17. Revised Phased Implementation Roadmap

In accordance with Chief Architect instructions, implementation sequence is refined to require a **Source Feasibility Spike (`SI-F0.1`)** before schema and parser commitments:

```
SI-F0 (Current)  ──► Architecture & Discovery Blueprint (Frozen)
       │
       ▼
SI-F0.1          ──► SOURCE FEASIBILITY SPIKE (Bounded Real-Company Matrix)
       │
       ▼ (Owner Source Approval Gate)
SI-F1            ──► Issuer Identity + Bitemporal/Versioned Persistence Foundation
       │
       ▼
SI-F2            ──► Approved Statement Ingestion + Normalized Factual Evidence
       │
       ▼
SI-F3            ──► Deterministic Derived Metrics (after formula validation)
       │
       ▼
SI-F4            ──► Shareholding Evidence & Ownership Dynamics
       │
       ▼
SI-F5            ──► Fundamentals UX / Stock 360 Integration
```

### Milestone Definitions
- **SI-F0**: Architecture & Discovery Blueprint (THIS MILESTONE — Review Complete).
- **SI-F0.1**: **Source Feasibility Spike**. Inspect and test real filing payloads across a bounded matrix of Indian issuers (normal non-financial, consolidated parent, loss-making, revised filing, dual-listed, share-count change). Prove timestamp availability, scope consistency, and normalization feasibility. No production ingestion.
- **SI-F1**: Issuer Identity + Bitemporal / Versioned Persistence Foundation (`SCHEMA_VERSION = 21`).
- **SI-F2**: Approved Statement Ingestion + Normalized Evidence Engine.
- **SI-F3**: Deterministic Derived Metrics (TTM, Margins, Ratios) after formula freeze.
- **SI-F4**: Shareholding Evidence Pipeline (Promoter, FII, DII, Public, Pledges).
- **SI-F5**: Stock 360 Fundamentals UX Delivery.

---

## 18. Risks & Open Questions

1. **Real-World Timestamp Availability**: Does the primary candidate source provide true dissemination timestamps or only dates? (To be answered by SI-F0.1).
2. **XBRL Taxonomy Inconsistencies**: Variation in IndAS Schedule III tagging across diverse accounting software used by Indian listed firms.
3. **Share Count Chronology**: Resolving dilution events between quarterly shareholding filings to ensure accurate market cap calculation.

---

## 19. Explicit Non-Goals

- ❌ **NO Order Placement or Execution**: Strict constitutional rule.
- ❌ **NO Synthetic Scoring or Quality Badges**: No Piotroski, Altman Z, or invented Athena scores.
- ❌ **NO Valuation Forecasting**: No DCF projections, target prices, or fair value guesses.
- ❌ **NO Automated DecisionEngine Filtering**: Fundamentals will not gate or alter DecisionEngine trades.
- ❌ **NO Intraday Fundamental Streaming**: Financial statements change quarterly; live tick re-evaluation is out of scope.
- ❌ **NO SI-N0 (News & Catalysts)**: News remains a completely separate future track.

---

## 20. Final GO / NO-GO Recommendation

### Recommendation: **GO FOR SI-F0.1 SOURCE FEASIBILITY SPIKE**

**Rationale**:
The architectural principles of PIT correctness, multi-attribute fact identity, bitemporal versioning, non-fabrication of timestamps, and strict boundary separation from DecisionEngine are now fully aligned with ATHENA standards. Conducting a bounded, zero-risk feasibility spike (`SI-F0.1`) on a real-company matrix is the exact engineering discipline required before writing schema or ingestion code.

---

# SECTION 21: GOVERNANCE & DECISION AUDIT

### Category A: Facts Established by Repository Evidence
1. `candles` and `quotes` in `db/athena.db` (`SCHEMA_VERSION = 20`) hold market pricing only. There is no financial statement or market cap data stored in the database.
2. `Instrument.sector` exists in SQLite, but is an unversioned string backfilled from NSE constituent CSVs (`ops/constituents.py`). It covers only ~500 index scrips.
3. Zerodha Kite Connect provides no fundamental data, balance sheets, or shareholding patterns.
4. `composer.py` currently emits an explicit `NOT_INGESTED` placeholder for `fundamentals` in `SymbolIntelligenceBundleDTO`.
5. Official NSE corporate actions provider (`nse_corporate_actions_provider.py`) proves ATHENA can reliably interface with official exchange web endpoints.

### Category B: Final Architectural Principles (Post-Review)
1. **Multi-Attribute Fact Identity**: Every fact is uniquely identified by entity, security mapping, metric key, period start/end/type, statement scope, audit status, filing ID/version, and publication precision.
2. **Four-Dimensional Temporal Model**: Strict separation of Economic Time, Market-Knowledge Time, ATHENA System Time, and Version Lineage.
3. **Zero Timestamp Fabrication**: Precision is explicitly recorded (`EXACT_TIMESTAMP`, `DATE_ONLY`, `UNKNOWN`). No artificial timestamps (`23:59:59`) are ever injected.
4. **Strict Scope Isolation**: Consolidated and Standalone statements are independently persisted; time series must never silently mix scopes.
5. **No Synthetic Ratings**: Fundamentals enter as immutable, factual evidence. No scores, no buy/sell labels, and no coupling to DecisionEngine.

### Category C: Approved Owner Decisions
1. **Initial Issuer Scope**: `NON-FINANCIAL MAINBOARD EQUITIES FIRST`. Specialized financial templates deferred.
2. **Statement Scope Precedence**: `CONSOLIDATED PREFERRED` for presentation, with `STANDALONE` fallback, subject to mandatory scope isolation.
3. **SME Coverage**: `DEFERRED` from initial F1–F3 implementation due to half-yearly reporting cycle.
4. **DecisionEngine Boundary**: `ZERO COUPLING`. Fundamentals are advisory factual evidence only.
5. **Implementation Phasing**: Execute `SI-F0.1 SOURCE FEASIBILITY SPIKE` before committing to persistence schema or parser code.

### Category D: Decisions Deliberately Left Unresolved
1. **Primary Data Source Selection**: Whether to use official exchange XBRL feeds, a commercial normalized API, or a hybrid will be decided after empirical evaluation in `SI-F0.1`.
2. **Market Capitalization Methodology**: Whether to use a chronology-adjusted share count or source-provided PIT market cap will be decided after `SI-F0.1`.
3. **Date-Only Replay Eligibility Policy**: Conservative ($T+1$) vs Permissive ($T+0$) eligibility for `DATE_ONLY` evidence will be evaluated prior to historical backtesting integration.
4. **Derived Metric Formulas**: Specific operational formulas for FCF, ROCE, and EBITDA normalization remain candidate proposals pending taxonomy validation in `SI-F0.1` and `SI-F3`.

---

## 22. Verification & Safety Checks

Because this milestone is **DISCOVERY ONLY**:
- ❌ No production code was modified.
- ❌ No database tables were created or migrated (`SCHEMA_VERSION` remains 20).
- ❌ No external packages or API clients were installed.
- ❌ No UI files or CSS were altered.
- ❌ `SI-F0.1` and `SI-F1` were NOT started.
- ❌ `SI-N0` (News) was NOT started.
- ❌ No git actions (`git commit`, `git push`, etc.) were executed.
