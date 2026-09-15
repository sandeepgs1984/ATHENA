"""SI-F2A Empirical Normalization Evidence Builder & Verifier.

Parses sanitized XBRL/XML fixtures directly to empirically extract and verify:
1. Context classification (Duration vs Instant, Dates, Dimensions);
2. Quarter vs Cumulative/YTD period discrimination;
3. Negative values and signed Decimal preservation;
4. Banking negative control taxonomy differences;
5. Duplicate fact handling (Exact, Compatible, Conflicting);
6. Nil / Missing distinctions (xsi:nil vs 0 vs absent);
7. Canonical concept mapping candidate evaluation (5 High Confidence + 2 Rule Required).

Distinguishes:
A. Source-Derived Sanitized Fixtures (with full filing provenance)
B. Constructed Methodology Fixtures (purpose-built edge case verification)
C. Documented External Metadata (from official exchange feeds)
D. Inferred / Architectural Recommendations (for future F2B planning)

Enforces internal self-validation assertions and deterministic JSON output.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = BASE_DIR / "fixtures"
OUTPUT_FILE = BASE_DIR / "f2a_normalization_evidence.json"
SPIKE_FILE = BASE_DIR / "spike_evidence.json"

XBRL_INSTANCE_NS = "http://www.xbrl.org/2003/instance"
XBRL_DIM_NS = "http://xbrl.org/2006/xbrldi"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def parse_xbrl_fixture(xml_path: Path) -> dict[str, Any]:
    """Parse an XBRL XML fixture into structured contexts, units, and raw facts."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    contexts: dict[str, dict[str, Any]] = {}
    units: dict[str, dict[str, Any]] = {}
    raw_facts: list[dict[str, Any]] = []

    # 1. Parse Contexts
    for elem in root.findall(f"{{{XBRL_INSTANCE_NS}}}context"):
        cid = elem.attrib.get("id", "")
        period_elem = elem.find(f"{{{XBRL_INSTANCE_NS}}}period")
        cdata: dict[str, Any] = {"context_id": cid, "period_type": "UNKNOWN"}

        if period_elem is not None:
            instant = period_elem.find(f"{{{XBRL_INSTANCE_NS}}}instant")
            if instant is not None and instant.text:
                cdata["period_type"] = "INSTANT"
                cdata["period_start"] = None
                cdata["period_end"] = instant.text.strip()
                cdata["duration_days"] = 0
            else:
                start = period_elem.find(f"{{{XBRL_INSTANCE_NS}}}startDate")
                end = period_elem.find(f"{{{XBRL_INSTANCE_NS}}}endDate")
                if start is not None and end is not None and start.text and end.text:
                    cdata["period_type"] = "DURATION"
                    cdata["period_start"] = start.text.strip()
                    cdata["period_end"] = end.text.strip()
                    s_parts = [int(p) for p in cdata["period_start"].split("-")]
                    e_parts = [int(p) for p in cdata["period_end"].split("-")]
                    d_len = (date(*e_parts) - date(*s_parts)).days + 1
                    cdata["duration_days"] = d_len

        # Check dimensions in scenario or segment
        dimensions: list[dict[str, str]] = []
        for container_name in ("scenario", "segment"):
            container = elem.find(f"{{{XBRL_INSTANCE_NS}}}{container_name}")
            if container is not None:
                for member in container.findall(f"{{{XBRL_DIM_NS}}}explicitMember"):
                    dim = member.attrib.get("dimension", "")
                    val = (member.text or "").strip()
                    dimensions.append({"dimension": dim, "member": val})

        cdata["is_dimensioned"] = len(dimensions) > 0
        cdata["dimensions"] = sorted(dimensions, key=lambda d: d["dimension"])
        contexts[cid] = cdata

    # 2. Parse Units
    for elem in root.findall(f"{{{XBRL_INSTANCE_NS}}}unit"):
        uid = elem.attrib.get("id", "")
        measure = elem.find(f"{{{XBRL_INSTANCE_NS}}}measure")
        divide = elem.find(f"{{{XBRL_INSTANCE_NS}}}divide")
        if measure is not None and measure.text:
            units[uid] = {"unit_id": uid, "type": "MEASURE", "measure": measure.text.strip()}
        elif divide is not None:
            num = divide.find(f"{{{XBRL_INSTANCE_NS}}}unitNumerator/{{{XBRL_INSTANCE_NS}}}measure")
            den = divide.find(f"{{{XBRL_INSTANCE_NS}}}unitDenominator/{{{XBRL_INSTANCE_NS}}}measure")
            units[uid] = {
                "unit_id": uid,
                "type": "DIVIDE",
                "numerator": num.text.strip() if num is not None and num.text else "",
                "denominator": den.text.strip() if den is not None and den.text else "",
            }

    # 3. Parse Fact Elements with Document-Level and Group-Level Ordinals
    doc_occurrence_counter = 0
    dup_group_counter: dict[tuple[str, str], int] = {}
    for elem in root:
        tag = elem.tag
        if tag.startswith(f"{{{XBRL_INSTANCE_NS}}}"):
            continue  # skip context, unit, schemaRef

        doc_occurrence_counter += 1

        if tag.startswith("{"):
            ns_uri, local_name = tag[1:].split("}", 1)
        else:
            ns_uri, local_name = "", tag

        cref = elem.attrib.get("contextRef", "")
        uref = elem.attrib.get("unitRef", "")
        dec = elem.attrib.get("decimals")
        is_nil = elem.attrib.get(f"{{{XSI_NS}}}nil") == "true"
        raw_val = (elem.text or "").strip()

        group_key = (tag, cref)
        dup_group_counter[group_key] = dup_group_counter.get(group_key, 0) + 1
        dup_ordinal = dup_group_counter[group_key]

        parsed_dec = None
        if not is_nil and raw_val:
            try:
                parsed_dec = str(Decimal(raw_val))
            except Exception:
                parsed_dec = None

        c_info = contexts.get(cref, {})
        fact: dict[str, Any] = {
            "source_occurrence_ordinal": doc_occurrence_counter,
            "duplicate_group_ordinal": dup_ordinal,
            "raw_qname": f"in-bse-fin:{local_name}" if "bseindia" in ns_uri else local_name,
            "namespace_uri": ns_uri,
            "local_name": local_name,
            "context_ref": cref,
            "unit_ref": uref,
            "decimals": dec,
            "is_nil": is_nil,
            "raw_value": raw_val,
            "numeric_value": parsed_dec,
            "period_type": c_info.get("period_type"),
            "period_start": c_info.get("period_start"),
            "period_end": c_info.get("period_end"),
            "duration_days": c_info.get("duration_days"),
            "is_dimensioned": c_info.get("is_dimensioned", False),
            "dimensions": c_info.get("dimensions", []),
        }
        raw_facts.append(fact)

    return {
        "file": xml_path.name,
        "contexts_count": len(contexts),
        "units_count": len(units),
        "facts_count": len(raw_facts),
        "contexts": contexts,
        "units": units,
        "facts": raw_facts,
    }


def build_evidence() -> dict[str, Any]:
    # 1. Parse all fixtures
    infy_parsed = parse_xbrl_fixture(FIXTURES_DIR / "infy_q3_fy25_sanitized.xml")
    paytm_parsed = parse_xbrl_fixture(FIXTURES_DIR / "paytm_q3_fy25_loss_sanitized.xml")
    hdfc_parsed = parse_xbrl_fixture(FIXTURES_DIR / "hdfcbank_q3_fy25_banking_sanitized.xml")
    dups_parsed = parse_xbrl_fixture(FIXTURES_DIR / "duplicate_and_nil_cases_sanitized.xml")

    # Load F0.1 spike observations for filing-level metadata
    spike_matrix: dict[str, Any] = {}
    if SPIKE_FILE.exists():
        with open(SPIKE_FILE, encoding="utf-8") as f:
            spike_data = json.load(f)
            spike_matrix = spike_data.get("matrix_tests", {})

    # 2. Extract Quarter vs YTD facts from INFY fixture
    infy_facts_by_concept_context: dict[tuple[str, str], dict[str, Any]] = {
        (f["local_name"], f["context_ref"]): f for f in infy_parsed["facts"]
    }

    q3_rev = infy_facts_by_concept_context.get(("RevenueFromOperations", "OneD"), {})
    ytd_rev = infy_facts_by_concept_context.get(("RevenueFromOperations", "FourD"), {})
    seg_rev = infy_facts_by_concept_context.get(("RevenueFromOperations", "OneReportableSegmentRevenue01D"), {})
    q3_pat = infy_facts_by_concept_context.get(("ProfitLossForPeriod", "OneD"), {})
    ytd_pat = infy_facts_by_concept_context.get(("ProfitLossForPeriod", "FourD"), {})

    # Extract PAYTM loss facts
    paytm_facts = {f["local_name"]: f for f in paytm_parsed["facts"] if f["context_ref"] == "OneD"}
    paytm_pat = paytm_facts.get("ProfitLossForPeriod", {})
    paytm_eps = paytm_facts.get(
        "DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations", {}
    )

    # Extract Banking concepts
    hdfc_concepts = {f["local_name"] for f in hdfc_parsed["facts"]}

    # Extract Duplicate and Nil cases
    dup_facts = dups_parsed["facts"]
    exact_dups = [f for f in dup_facts if f["local_name"] == "RevenueFromOperations"]
    compat_dups = [f for f in dup_facts if f["local_name"] == "ProfitLossBeforeTax"]
    conflict_dups = [f for f in dup_facts if f["local_name"] == "OtherIncome"]
    nil_facts = [f for f in dup_facts if f["local_name"] == "ExceptionalItems"]

    # 3. SELF-VALIDATION ASSERTIONS (Deterministic Proof)
    # A. Quarter vs YTD share period_end but have different period_start
    assert q3_rev["period_end"] == ytd_rev["period_end"] == "2024-12-31", "Period end must match"
    assert q3_rev["period_start"] == "2024-10-01", "Q3 start date must be 2024-10-01"
    assert ytd_rev["period_start"] == "2024-04-01", "YTD start date must be 2024-04-01"
    assert q3_rev["duration_days"] == 92, "Q3 duration must be 92 days"
    assert ytd_rev["duration_days"] == 275, "9M duration must be 275 days"
    assert Decimal(q3_rev["numeric_value"]) == Decimal("417640000000.00")
    assert Decimal(ytd_rev["numeric_value"]) == Decimal("1220640000000.00")

    # B. Document occurrence ordinals are strictly monotonic (1..N)
    for p_doc in (infy_parsed, paytm_parsed, hdfc_parsed, dups_parsed):
        ordinals = [f["source_occurrence_ordinal"] for f in p_doc["facts"]]
        assert ordinals == list(range(1, len(p_doc["facts"]) + 1)), "Ordinals must be sequential 1..N"

    # C. Dimensioned segment context separated from primary enterprise
    assert seg_rev["is_dimensioned"] is True, "Segment fact must be marked dimensioned"
    assert q3_rev["is_dimensioned"] is False, "Enterprise total must be non-dimensioned"

    # D. Loss facts preserved as signed Decimals
    assert Decimal(paytm_pat["numeric_value"]) < 0, "PAYTM PAT must be negative"
    assert Decimal(paytm_eps["numeric_value"]) < 0, "PAYTM EPS must be negative"
    assert paytm_pat["numeric_value"] == "-2085000000.00"

    # E. Banking negative control lacks RevenueFromOperations
    assert "RevenueFromOperations" not in hdfc_concepts, "Banking must lack RevenueFromOperations"
    assert "InterestEarned" in hdfc_concepts, "Banking must have InterestEarned"

    # F. Duplicate classifications verified
    assert len(exact_dups) == 2 and exact_dups[0]["raw_value"] == exact_dups[1]["raw_value"]
    assert len(compat_dups) == 2 and compat_dups[0]["numeric_value"] == compat_dups[1]["numeric_value"]
    assert len(conflict_dups) == 2 and conflict_dups[0]["numeric_value"] != conflict_dups[1]["numeric_value"]
    assert len(nil_facts) == 1 and nil_facts[0]["is_nil"] is True

    # 4. Formulate Canonical Concepts Matrix
    # High-Confidence Canonical Promotion (5 Pure Income Concepts)
    high_confidence_concepts = [
        {
            "canonical_concept": "REVENUE_FROM_OPERATIONS",
            "category": "INCOME_STATEMENT",
            "raw_namespace": "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            "raw_local_name": "RevenueFromOperations",
            "period_type": "DURATION",
            "canonical_unit": "CURRENCY_INR",
            "canonical_promotion_status": "HIGH_CONFIDENCE_CANONICAL_PROMOTION",
            "rationale": "Directly reported line item representing core operational revenue.",
        },
        {
            "canonical_concept": "PROFIT_LOSS_BEFORE_TAX",
            "category": "INCOME_STATEMENT",
            "raw_namespace": "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            "raw_local_name": "ProfitLossBeforeTax",
            "period_type": "DURATION",
            "canonical_unit": "CURRENCY_INR",
            "canonical_promotion_status": "HIGH_CONFIDENCE_CANONICAL_PROMOTION",
            "rationale": "Standard pre-tax earnings before exceptional items/taxation.",
        },
        {
            "canonical_concept": "PROFIT_LOSS_FOR_PERIOD",
            "category": "INCOME_STATEMENT",
            "raw_namespace": "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            "raw_local_name": "ProfitLossForPeriod",
            "period_type": "DURATION",
            "canonical_unit": "CURRENCY_INR",
            "canonical_promotion_status": "HIGH_CONFIDENCE_CANONICAL_PROMOTION",
            "rationale": "Authoritative net profit/loss after tax. Handles negative losses.",
        },
        {
            "canonical_concept": "EPS_BASIC",
            "category": "INCOME_STATEMENT",
            "raw_namespace": "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            "raw_local_name": "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
            "period_type": "DURATION",
            "canonical_unit": "INR_PER_SHARE",
            "canonical_promotion_status": "HIGH_CONFIDENCE_CANONICAL_PROMOTION",
            "rationale": "Basic EPS as legally reported on the face of the financial results.",
        },
        {
            "canonical_concept": "EPS_DILUTED",
            "category": "INCOME_STATEMENT",
            "raw_namespace": "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            "raw_local_name": "DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
            "period_type": "DURATION",
            "canonical_unit": "INR_PER_SHARE",
            "canonical_promotion_status": "HIGH_CONFIDENCE_CANONICAL_PROMOTION",
            "rationale": "Diluted EPS as legally reported on the face of the financial results.",
        },
    ]

    # Raw Mapping Proven but Canonical Context Rule Required (2 Capital Concepts)
    capital_rule_required_concepts = [
        {
            "canonical_concept": "PAID_UP_EQUITY_CAPITAL",
            "category": "CAPITAL_STRUCTURE",
            "raw_namespace": "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            "raw_local_name": "PaidUpValueOfEquityShareCapital",
            "period_type": "INSTANT_OR_DURATION",
            "canonical_unit": "CURRENCY_INR",
            "canonical_promotion_status": "RAW_MAPPING_PROVEN_CANONICAL_RULE_REQUIRED",
            "rationale": (
                "Raw QName mapping is proven, but tag appears under both instant and duration "
                "contexts. Canonical promotion requires an explicitly approved context rule."
            ),
        },
        {
            "canonical_concept": "FACE_VALUE_PER_SHARE",
            "category": "CAPITAL_STRUCTURE",
            "raw_namespace": "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            "raw_local_name": "FaceValueOfEquityShareCapital",
            "period_type": "INSTANT_OR_DURATION",
            "canonical_unit": "INR_PER_SHARE",
            "canonical_promotion_status": "RAW_MAPPING_PROVEN_CANONICAL_RULE_REQUIRED",
            "rationale": (
                "Raw QName mapping is proven, but tag appears under both instant and duration "
                "contexts. Canonical promotion requires an explicitly approved context rule."
            ),
        },
    ]

    # Fixture Provenance Catalog
    fixture_provenance = {
        "infy_q3_fy25_sanitized.xml": {
            "fixture_type": "SOURCE_DERIVED_SANITIZED_FIXTURE",
            "issuer": "Infosys Limited",
            "symbol": "INFY",
            "isin": "INE009A01021",
            "exchange": "NSE",
            "filing_period": "Q3 FY25 (2024-10-01 to 2024-12-31)",
            "source_seq_number": "1189811",
            "dissemination_time": "2025-01-16 19:40:31 IST",
            "source_url": (
                "https://nsearchives.nseindia.com/corporate/xbrl/"
                "INDAS_117292_1348213_16012025074012.xml"
            ),
            "sanitization_statement": (
                "Sanitized subset of actual official XBRL containing core income line items, "
                "equity capital, quarter (OneD) vs 9M YTD (FourD) duration contexts, and "
                "segment dimension (OneReportableSegmentRevenue01D)."
            ),
        },
        "paytm_q3_fy25_loss_sanitized.xml": {
            "fixture_type": "SOURCE_DERIVED_SANITIZED_FIXTURE",
            "issuer": "One 97 Communications Limited",
            "symbol": "PAYTM",
            "isin": "INE982J01020",
            "exchange": "NSE",
            "filing_period": "Q3 FY25 (2024-10-01 to 2024-12-31)",
            "source_seq_number": "1190043",
            "dissemination_time": "2025-01-20 18:37:43 IST",
            "source_url": (
                "https://nsearchives.nseindia.com/corporate/xbrl/"
                "INDAS_117412_1353590_20012025063743.xml"
            ),
            "sanitization_statement": (
                "Sanitized subset of actual official XBRL demonstrating negative PAT (-₹208.5 Cr) "
                "and negative diluted EPS (-₹3.27)."
            ),
        },
        "hdfcbank_q3_fy25_banking_sanitized.xml": {
            "fixture_type": "SOURCE_DERIVED_SANITIZED_FIXTURE",
            "issuer": "HDFC Bank Limited",
            "symbol": "HDFCBANK",
            "isin": "INE040A01034",
            "exchange": "NSE",
            "filing_period": "Q3 FY25 (2024-10-01 to 2024-12-31)",
            "source_seq_number": "1190261",
            "dissemination_time": "2025-01-23 12:27:21 IST",
            "source_url": (
                "https://nsearchives.nseindia.com/corporate/xbrl/"
                "BANKING_117525_1359016_23012025122721.xml"
            ),
            "sanitization_statement": (
                "Sanitized subset of actual official banking XBRL demonstrating presence of "
                "InterestEarned / InterestExpended and total absence of RevenueFromOperations."
            ),
        },
        "duplicate_and_nil_cases_sanitized.xml": {
            "fixture_type": "CONSTRUCTED_METHODOLOGY_FIXTURE",
            "purpose": (
                "Purpose-built synthetic XML fixture constructed to validate parser and "
                "methodological behavior on exact duplicates, compatible duplicates, "
                "conflicting duplicates, and reported nil (xsi:nil=true)."
            ),
            "evidence_classification": "METHODOLOGY_PARSER_BEHAVIOR_VALIDATED",
            "sanitization_statement": (
                "Constructed fixture. Does NOT claim these specific numbers occurred in a single "
                "official filing; validates parser handling rules."
            ),
        },
    }

    # Final 12 Owner Decisions Ready for Freeze
    owner_decisions = {
        "D1": "APPROVE two-layer architecture: Raw Source Fact Observation + Canonical Mapping.",
        "D2": "APPROVE source occurrence identity as separate from canonical economic identity and payload.",
        "D3": "APPROVE reported-facts-only normalization. No synthetic quarter subtraction.",
        "D4": "APPROVE period-safe canonical duration identity: period_start + period_end required.",
        "D5": (
            "APPROVE raw dimensioned fact preservation; unsupported material dimensions "
            "excluded from initial enterprise promotion."
        ),
        "D6": (
            "APPROVE duplicate policy: preserve raw occurrences; no highest-precision winner; "
            "conflicting duplicates unresolved."
        ),
        "D7": "APPROVE cross-exchange source observations remain independent in F2B; reconciliation deferred.",
        "D8": (
            "APPROVE versioned canonical mappings and local reprocessing from immutable "
            "source documents/raw observations."
        ),
        "D9": (
            "APPROVE exact PIT inheritance from SI-F1; DATE_ONLY/UNKNOWN remain excluded from "
            "exact timestamp replay."
        ),
        "D10": (
            "APPROVE initial non-financial-only boundary: banks excluded empirically; NBFC/insurance conservatively "
            "excluded pending evidence; unknown issuer classification => not canonically normalized."
        ),
        "D11": (
            "APPROVE secure XML parser requirement (exact dependency added only during "
            "reviewed F2B implementation)."
        ),
        "D12": (
            "APPROVE initial concept scope: 5 High-Confidence Canonical Promotion concepts + "
            "2 Raw Mapping Proven but Canonical Context Rule Required concepts."
        ),
    }

    # Build Structured Evidence Package
    evidence = {
        "schema_version": "21",
        "milestone": "SI-F2A",
        "title": "Empirical Fact Normalization Methodology & XBRL Mapping Evidence",
        "date": "2026-09-15",
        "evidence_classification_definitions": {
            "SOURCE_DERIVED_SANITIZED_FIXTURE": (
                "Derived from captured official exchange filings with documented provenance."
            ),
            "CONSTRUCTED_METHODOLOGY_FIXTURE": (
                "Purpose-built synthetic fixture to validate methodology/parser edge cases."
            ),
            "DOCUMENTED_EXTERNAL_METADATA": "Recorded from live exchange feed queries in SI-F0.1.",
            "INFERRED_PLANNING_ESTIMATE": (
                "Planning estimates for storage and capacity; not claimed as broad empirical truths."
            ),
            "ARCHITECTURAL_RECOMMENDATION": "Proposed design recommendations for future F2B planning.",
            "UNKNOWN": "Explicitly unresolved questions requiring further empirical research.",
        },
        "fixture_provenance_catalog": fixture_provenance,
        "reproducible_findings": {
            "INFY_QUARTER_VS_YTD": {
                "evidence_status": "SOURCE_DERIVED_SANITIZED_FIXTURE",
                "quarter_context": infy_parsed["contexts"]["OneD"],
                "ytd_context": infy_parsed["contexts"]["FourD"],
                "quarter_revenue": q3_rev,
                "ytd_revenue": ytd_rev,
                "quarter_pat": q3_pat,
                "ytd_pat": ytd_pat,
                "segment_revenue": seg_rev,
                "conclusion": (
                    "Quarterly and cumulative YTD facts share concept QName and period_end, "
                    "but are strictly distinguished by context period_start and duration_days. "
                    "Contexts with explicitMember dimensions represent segment breakdowns."
                ),
            },
            "PAYTM_LOSS_FACTS": {
                "evidence_status": "SOURCE_DERIVED_SANITIZED_FIXTURE",
                "profit_loss_fact": paytm_pat,
                "diluted_eps_fact": paytm_eps,
                "conclusion": (
                    "Negative PAT and EPS are reported with leading minus signs and "
                    "parsed into signed Decimals."
                ),
            },
            "HDFCBANK_BANKING_NEGATIVE_CONTROL": {
                "evidence_status": "SOURCE_DERIVED_SANITIZED_FIXTURE",
                "observed_concepts": sorted(list(hdfc_concepts)),
                "has_RevenueFromOperations": False,
                "has_InterestEarned": True,
                "conclusion": (
                    "Banking taxonomy lacks standard corporate revenue line items. "
                    "Confirms banking exclusion from non-financial normalization."
                ),
            },
            "DUPLICATE_AND_NIL_CLASSIFICATION": {
                "evidence_status": "CONSTRUCTED_METHODOLOGY_FIXTURE",
                "exact_duplicates_count": len(exact_dups),
                "compatible_duplicates_count": len(compat_dups),
                "conflicting_duplicates_count": len(conflict_dups),
                "reported_nil_count": len(nil_facts),
                "duplicate_policy_rules": {
                    "RAW_OCCURRENCE_PRESERVATION": (
                        "Physically distinct XML occurrences in the source document are preserved "
                        "at the raw layer (document_id, source_occurrence_ordinal); never erased."
                    ),
                    "EXACT_DUPLICATE": "Identical economic coordinates and value; deduplicated at canonical promotion.",
                    "COMPATIBLE_VALUE_DUPLICATE": (
                        "Same economic coordinates, compatible values; preserve observations "
                        "without picking highest precision as canonical truth."
                    ),
                    "CONFLICTING_DUPLICATE": (
                        "Same economic coordinates, incompatible values; preserve all, "
                        "mark CONFLICT_UNRESOLVED."
                    ),
                    "REPORTED_NIL": "xsi:nil='true' preserved as is_nil=True, distinct from numeric 0.00.",
                },
            },
        },
        "observed_filing_metadata": {
            "evidence_status": "DOCUMENTED_EXTERNAL_METADATA",
            "source": "NSE Corporate Financial Results API Feed (SI-F0.1)",
            "symbols_sampled": list(spike_matrix.keys()),
            "statement_scope_findings": {
                "INFY_scope_separation": (
                    "Consolidated seq 1189811 vs Standalone seq 1189815 with distinct URLs and timestamps."
                ),
                "TCS_scope_separation": "Consolidated seq 1189599 vs Standalone seq 1189595 on 2025-01-09.",
            },
            "revision_metadata_findings": {
                "SCHAEFFLER_revision": "Seq 1197098 (reInd=N) on 2025-02-27 vs Seq 1197319 (reInd=R) on 2025-03-25.",
            },
        },
        "canonical_concept_vocabulary": {
            "high_confidence_canonical_promotion": high_confidence_concepts,
            "raw_mapping_proven_canonical_rule_required": capital_rule_required_concepts,
        },
        "identity_proposals": {
            "evidence_status": "ARCHITECTURAL_RECOMMENDATION",
            "raw_source_occurrence_identity": "(document_id, source_occurrence_ordinal)",
            "raw_fact_payload_attributes": (
                "raw_qname, context_ref, unit_ref, decimals, raw_value, numeric_value, "
                "is_nil, is_dimensioned, dimension_signature"
            ),
            "canonical_economic_identity": (
                "filing_id, canonical_concept, period_type, period_start, period_end, statement_scope"
            ),
        },
        "performance_and_storage_estimates": {
            "evidence_status": "INFERRED_PLANNING_ESTIMATE",
            "facts_per_filing_range": "150-500 facts per quarterly XML",
            "xml_payload_size_range": "30-250 KB uncompressed",
            "five_year_projection_500_issuers": "~20,000 filings, ~6M raw facts, ~800 MB-1.5 GB SQLite",
            "note": "Capacity planning estimate only; not claimed as measured census.",
        },
        "proposed_owner_decisions_d1_to_d12": owner_decisions,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(evidence, indent=2)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write(serialized)

    file_sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    print(f"Generated {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size} bytes, SHA-256: {file_sha256})")
    return evidence


if __name__ == "__main__":
    build_evidence()
