"""Tests for production XBRL parser (SI-F2B).

Verifies:
1. Secure XML parsing against frozen F2A empirical fixtures.
2. Context classification (Duration vs Instant, dates, dimensions).
3. INFY Q3 vs 9M durations sharing period_end = 2024-12-31.
4. PAYTM signed Decimal preservation (negative PAT, negative EPS).
5. HDFCBANK banking taxonomy raw extraction.
6. Duplicate and nil fixture (ordinals, nil preservation, distinct occurrences).
7. Security: oversized documents (>20 MB), malformed XML, entity expansion rejection.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from athena.domain.enums import FinancialUnitClass, RawPeriodType
from athena.domain.fundamentals import MAX_RAW_DOCUMENT_SIZE_BYTES
from athena.fundamentals.xbrl_parser import parse_xbrl_document

FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "tools"
    / "research"
    / "si_fundamentals"
    / "fixtures"
)


def test_parser_infy_q3_and_9m_durations() -> None:
    """INFY Q3 and 9M facts must be extracted with authentic period coordinates."""
    xml_bytes = (FIXTURES_DIR / "infy_q3_fy25_sanitized.xml").read_bytes()
    facts = parse_xbrl_document(
        document_id="doc_infy_q3",
        filing_id="filing_infy_q3",
        raw_bytes=xml_bytes,
    )

    assert len(facts) == 14

    # Revenue facts by context
    q3_rev = next(f for f in facts if f.local_name == "RevenueFromOperations" and f.context_ref == "OneD")
    ytd_rev = next(f for f in facts if f.local_name == "RevenueFromOperations" and f.context_ref == "FourD")
    seg_ctx = "OneReportableSegmentRevenue01D"
    seg_rev = next(
        f for f in facts if f.local_name == "RevenueFromOperations" and f.context_ref == seg_ctx
    )

    # Verify duration coordinates
    assert q3_rev.period_type == RawPeriodType.DURATION
    assert str(q3_rev.period_start) == "2024-10-01"
    assert str(q3_rev.period_end) == "2024-12-31"
    assert q3_rev.duration_days == 92
    assert q3_rev.numeric_value == Decimal("417640000000.00")
    assert not q3_rev.is_dimensioned

    assert ytd_rev.period_type == RawPeriodType.DURATION
    assert str(ytd_rev.period_start) == "2024-04-01"
    assert str(ytd_rev.period_end) == "2024-12-31"
    assert ytd_rev.duration_days == 275
    assert ytd_rev.numeric_value == Decimal("1220640000000.00")
    assert not ytd_rev.is_dimensioned

    # Prove identical period_end but distinct period_start
    assert q3_rev.period_end == ytd_rev.period_end
    assert q3_rev.period_start != ytd_rev.period_start

    # Verify segment revenue is dimensioned
    assert seg_rev.is_dimensioned
    assert len(seg_rev.dimensions) == 1
    assert "FinancialServicesMember" in seg_rev.dimensions[0]["member"]


def test_parser_paytm_negative_pat_and_eps() -> None:
    """PAYTM negative PAT and EPS must be parsed as exact signed Decimals."""
    xml_bytes = (FIXTURES_DIR / "paytm_q3_fy25_loss_sanitized.xml").read_bytes()
    facts = parse_xbrl_document(
        document_id="doc_paytm",
        filing_id="filing_paytm",
        raw_bytes=xml_bytes,
    )

    pat_fact = next(f for f in facts if f.local_name == "ProfitLossForPeriod")
    assert pat_fact.numeric_value == Decimal("-2085000000.00")
    assert pat_fact.raw_value == "-2085000000.00"
    assert pat_fact.unit_class == FinancialUnitClass.CURRENCY

    eps_fact = next(
        f for f in facts
        if f.local_name == "DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
    )
    assert eps_fact.numeric_value == Decimal("-3.27")
    assert eps_fact.raw_value == "-3.27"
    assert eps_fact.unit_class == FinancialUnitClass.CURRENCY_PER_SHARE


def test_parser_hdfcbank_banking_taxonomy() -> None:
    """HDFCBANK banking taxonomy must parse raw facts losslessly."""
    xml_bytes = (FIXTURES_DIR / "hdfcbank_q3_fy25_banking_sanitized.xml").read_bytes()
    facts = parse_xbrl_document(
        document_id="doc_hdfc",
        filing_id="filing_hdfc",
        raw_bytes=xml_bytes,
    )

    assert len(facts) == 3
    interest_fact = next(f for f in facts if f.local_name == "InterestEarned")
    assert interest_fact.numeric_value == Decimal("850401700000.00")
    assert "in-bse-fin" in interest_fact.namespace_uri

    # RevenueFromOperations is absent in banking
    assert not any(f.local_name == "RevenueFromOperations" for f in facts)


def test_parser_duplicate_and_nil_fixture() -> None:
    """Duplicate facts must have distinct ordinals; nil facts must preserve is_nil=True."""
    xml_bytes = (FIXTURES_DIR / "duplicate_and_nil_cases_sanitized.xml").read_bytes()
    facts = parse_xbrl_document(
        document_id="doc_dup_nil",
        filing_id="filing_dup_nil",
        raw_bytes=xml_bytes,
    )

    # 1-based sequential ordinals
    ordinals = [f.source_occurrence_ordinal for f in facts]
    assert ordinals == list(range(1, len(facts) + 1))

    # Case 1: Exact duplicate
    rev_facts = [f for f in facts if f.local_name == "RevenueFromOperations"]
    assert len(rev_facts) == 2
    assert rev_facts[0].source_occurrence_ordinal != rev_facts[1].source_occurrence_ordinal
    assert rev_facts[0].numeric_value == rev_facts[1].numeric_value

    # Case 2: Compatible value duplicate
    pbt_facts = [f for f in facts if f.local_name == "ProfitLossBeforeTax"]
    assert len(pbt_facts) == 2
    assert pbt_facts[0].numeric_value == pbt_facts[1].numeric_value

    # Case 3: Conflicting duplicate (OtherIncome)
    other_inc = [f for f in facts if f.local_name == "OtherIncome"]
    assert len(other_inc) == 2
    assert other_inc[0].numeric_value != other_inc[1].numeric_value

    # Case 4: Nil fact (ExceptionalItems)
    nil_fact = next(f for f in facts if f.local_name == "ExceptionalItems")
    assert nil_fact.is_nil
    assert nil_fact.numeric_value is None
    assert nil_fact.raw_value == ""



def test_parser_oversized_document_rejected() -> None:
    """Documents exceeding MAX_RAW_DOCUMENT_SIZE_BYTES must be rejected."""
    oversized = b"<xbrl>" + b" " * (MAX_RAW_DOCUMENT_SIZE_BYTES + 10) + b"</xbrl>"
    with pytest.raises(ValueError, match="exceeds MAX_RAW_DOCUMENT_SIZE_BYTES"):
        parse_xbrl_document(
            document_id="doc_huge",
            filing_id="filing_huge",
            raw_bytes=oversized,
        )


def test_parser_malformed_xml_rejected() -> None:
    """Malformed XML must raise ValueError."""
    bad_xml = b"<xbrl><unclosed_tag>"
    with pytest.raises(ValueError, match="Secure XML parsing failed"):
        parse_xbrl_document(
            document_id="doc_bad",
            filing_id="filing_bad",
            raw_bytes=bad_xml,
        )


def test_parser_entity_expansion_dtd_safe() -> None:
    """XML entity expansion attacks (billion laughs) must be rejected safely by defusedxml."""
    billion_laughs = b"""<?xml version="1.0"?>
    <!DOCTYPE lolz [
     <!ENTITY lol "lol">
     <!ELEMENT lolz (#PCDATA)>
     <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
     <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
    ]>
    <lolz>&lol2;</lolz>
    """
    with pytest.raises(ValueError, match="Secure XML parsing failed"):
        parse_xbrl_document(
            document_id="doc_attack",
            filing_id="filing_attack",
            raw_bytes=billion_laughs,
        )


def test_parser_typed_dimensions_detected_and_persisted() -> None:
    """Context containing typedMember must be marked is_dimensioned=True and preserve typed payload."""
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
                xmlns:custom="http://example.com/custom"
                xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin">
        <xbrli:context id="TypedCtx">
            <xbrli:entity><xbrli:identifier scheme="http://bseindia.com">500112</xbrli:identifier></xbrli:entity>
            <xbrli:period>
                <xbrli:startDate>2024-10-01</xbrli:startDate>
                <xbrli:endDate>2024-12-31</xbrli:endDate>
            </xbrli:period>
            <xbrli:scenario>
                <xbrldi:typedMember dimension="custom:ContractAxis">
                    <custom:ContractId>CNT-999</custom:ContractId>
                </xbrldi:typedMember>
            </xbrli:scenario>
        </xbrli:context>
        <xbrli:unit id="INR">
            <xbrli:measure>iso4217:INR</xbrli:measure>
        </xbrli:unit>
        <in-bse-fin:RevenueFromOperations
            contextRef="TypedCtx" unitRef="INR" decimals="2">5000.00</in-bse-fin:RevenueFromOperations>
    </xbrli:xbrl>
    """
    facts = parse_xbrl_document(document_id="doc_typed", filing_id="fil_typed", raw_bytes=xml)
    assert len(facts) == 1
    f = facts[0]
    assert f.is_dimensioned
    assert len(f.dimensions) == 1
    d = f.dimensions[0]
    assert d["kind"] == "typed"
    assert d["dimension"] == "custom:ContractAxis"
    assert "CNT-999" in d["raw_content"]
    assert f.dimension_signature != ""


def test_parser_two_different_typed_values_produce_distinct_signatures() -> None:
    """Distinct typed member contents must generate different deterministic dimension signatures."""
    def make_xml(contract_id: str) -> bytes:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                    xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
                    xmlns:custom="http://example.com/custom"
                    xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin">
            <xbrli:context id="Ctx">
                <xbrli:entity><xbrli:identifier scheme="http://bseindia.com">500112</xbrli:identifier></xbrli:entity>
                <xbrli:period>
                    <xbrli:startDate>2024-10-01</xbrli:startDate>
                    <xbrli:endDate>2024-12-31</xbrli:endDate>
                </xbrli:period>
                <xbrli:scenario>
                    <xbrldi:typedMember dimension="custom:ContractAxis">
                        <custom:ContractId>{contract_id}</custom:ContractId>
                    </xbrldi:typedMember>
                </xbrli:scenario>
            </xbrli:context>
            <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
            <in-bse-fin:RevenueFromOperations
                contextRef="Ctx" unitRef="INR" decimals="2">5000.00</in-bse-fin:RevenueFromOperations>
        </xbrli:xbrl>
        """.encode()

    facts_a = parse_xbrl_document(document_id="doc_a", filing_id="fil_a", raw_bytes=make_xml("CNT-A"))
    facts_b = parse_xbrl_document(document_id="doc_b", filing_id="fil_b", raw_bytes=make_xml("CNT-B"))

    assert facts_a[0].dimension_signature != facts_b[0].dimension_signature

    # Repeated parsing produces identical signature
    facts_a_repeat = parse_xbrl_document(document_id="doc_a", filing_id="fil_a", raw_bytes=make_xml("CNT-A"))
    assert facts_a[0].dimension_signature == facts_a_repeat[0].dimension_signature


def test_parser_arbitrary_source_prefix_produces_clark_notation() -> None:
    """Arbitrary XML namespace prefix spelling does not alter Clark notation raw_qname or taxonomy identity."""
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                xmlns:arbitrary="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin">
        <xbrli:context id="Ctx">
            <xbrli:entity><xbrli:identifier scheme="http://bseindia.com">500112</xbrli:identifier></xbrli:entity>
            <xbrli:period>
                <xbrli:startDate>2024-10-01</xbrli:startDate>
                <xbrli:endDate>2024-12-31</xbrli:endDate>
            </xbrli:period>
        </xbrli:context>
        <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
        <arbitrary:RevenueFromOperations
            contextRef="Ctx" unitRef="INR" decimals="2">12345.00</arbitrary:RevenueFromOperations>
    </xbrli:xbrl>
    """
    facts = parse_xbrl_document(document_id="doc_pfx", filing_id="fil_pfx", raw_bytes=xml)
    assert len(facts) == 1
    f = facts[0]
    assert f.namespace_uri == "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"
    assert f.local_name == "RevenueFromOperations"
    assert f.raw_qname == "{http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin}RevenueFromOperations"
    assert f.numeric_value == Decimal("12345.00")


def test_parser_invalid_numeric_lexical_preserves_raw_value() -> None:
    """Unparseable or non-numeric lexical values are preserved in raw_value with numeric_value=None."""
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin">
        <xbrli:context id="Ctx">
            <xbrli:entity><xbrli:identifier scheme="http://bseindia.com">500112</xbrli:identifier></xbrli:entity>
            <xbrli:period>
                <xbrli:startDate>2024-10-01</xbrli:startDate>
                <xbrli:endDate>2024-12-31</xbrli:endDate>
            </xbrli:period>
        </xbrli:context>
        <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
        <in-bse-fin:RevenueFromOperations
            contextRef="Ctx" unitRef="INR" decimals="2">NOT_A_VALID_NUMBER</in-bse-fin:RevenueFromOperations>
    </xbrli:xbrl>
    """
    facts = parse_xbrl_document(document_id="doc_invalid", filing_id="fil_invalid", raw_bytes=xml)
    assert len(facts) == 1
    f = facts[0]
    assert f.raw_value == "NOT_A_VALID_NUMBER"
    assert f.numeric_value is None
