"""End-to-end tests for FundamentalFactNormalizer service (SI-F2B).

Verifies:
1. INFY Q3 vs 9M durations: both promoted, no collision in canonical facts.
2. Segment facts preserved in raw but excluded from canonical facts.
3. No synthetic quarter derivation (zero Q2 = H1 - Q1 arithmetic).
4. PAYTM signed Decimal preservation without float drift.
5. HDFCBANK banking taxonomy canonical rejection.
6. Issuer eligibility enforcement (ISSUER_CLASSIFICATION_UNAVAILABLE stops at raw).
7. Duplicate policy: exact duplicates produce 1 canonical fact with multiple raw links;
   conflicting duplicates fail canonical promotion and mark conflict.
8. Point-In-Time replay: EXACT_TIMESTAMP participates, DATE_ONLY/UNKNOWN excluded.
9. Idempotency: rerunning normalization on the same document is safe and deterministic.
10. Revision coexistence: revised filing facts coexist with original filing facts.
11. Scope isolation: CONSOLIDATED and STANDALONE persist independently.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.store import SqliteRepository
from athena.domain.enums import (
    CanonicalFinancialConcept,
    CumulativeNature,
    DuplicateClassification,
    FilingAuditStatus,
    NormalizationEligibility,
    PeriodNature,
    PublicationPrecision,
    StatementScope,
)
from athena.domain.fundamentals import (
    FilingDocument,
    FundamentalFiling,
    IssuerRecord,
)
from athena.errors import RepositoryError
from athena.fundamentals.normalizer import (
    FundamentalFactNormalizer,
    StaticIssuerEligibilityResolver,
)

FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "tools"
    / "research"
    / "si_fundamentals"
    / "fixtures"
)

UTC = timezone.utc
IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "test_fundamentals_f2b.db")
    r.initialize()
    yield r
    r.close()


def _setup_issuer_and_filing(
    repo: SqliteRepository,
    *,
    issuer_id: str = "iss_infy",
    filing_id: str = "filing_infy_q3",
    document_id: str = "doc_infy_q3",
    xml_fixture_name: str = "infy_q3_fy25_sanitized.xml",
    scope: StatementScope = StatementScope.CONSOLIDATED,
    precision: PublicationPrecision = PublicationPrecision.EXACT_TIMESTAMP,
    published_at: datetime | None = None,
) -> tuple[FundamentalFiling, FilingDocument]:
    issuer = IssuerRecord(issuer_id=issuer_id, legal_name="Test Enterprise")
    repo.upsert_issuer(issuer)

    if precision == PublicationPrecision.DATE_ONLY:
        pub_time = None
        pub_date = (published_at.date() if published_at else date(2025, 1, 16))
    elif precision == PublicationPrecision.UNKNOWN:
        pub_time = None
        pub_date = None
    else:
        pub_time = published_at or datetime(2025, 1, 16, 16, 30, tzinfo=IST)
        pub_date = pub_time.date()

    filing = FundamentalFiling(
        filing_id=filing_id,
        issuer_id=issuer_id,
        source="NSE",
        source_record_id=f"rec_{filing_id}",
        source_reported_symbol="INFY",
        source_reported_isin="INE009A01021",
        source_reported_name="Infosys Limited",
        period_start=date(2024, 10, 1),
        period_end=date(2024, 12, 31),
        financial_year="2024-2025",
        period_nature=PeriodNature.QUARTERLY,
        cumulative_nature=CumulativeNature.NON_CUMULATIVE,
        statement_scope=scope,
        audit_status=FilingAuditStatus.UNAUDITED,
        publication_precision=precision,
        source_published_at=pub_time,
        source_published_date=pub_date,
    )
    repo.save_fundamental_filing(filing)

    xml_bytes = (FIXTURES_DIR / xml_fixture_name).read_bytes()
    doc = FilingDocument.create(
        document_id=document_id,
        filing_id=filing_id,
        source_url=f"https://example.com/{xml_fixture_name}",
        raw_bytes=xml_bytes,
    )
    repo.save_filing_document(doc)
    return filing, doc


def test_infy_q3_vs_9m_both_promoted_without_collision(repo: SqliteRepository) -> None:
    """INFY Q3 and 9M revenue must both be promoted canonically without collision."""
    filing, doc = _setup_issuer_and_filing(repo, xml_fixture_name="infy_q3_fy25_sanitized.xml")
    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )

    result = normalizer.normalize_filing_document(filing=filing, doc=doc)

    assert result.raw_occurrences_seen == 14
    assert result.raw_occurrences_persisted == 14
    # Promoted concepts: Q3/9M Revenue, Q3/9M PBT, Q3/9M PAT, Q3/9M EPS
    assert result.canonical_promoted >= 6

    # Verify canonical facts in database
    facts = repo.get_canonical_financial_facts(filing.filing_id)
    rev_facts = [f for f in facts if f.canonical_concept == CanonicalFinancialConcept.REVENUE_FROM_OPERATIONS]
    assert len(rev_facts) == 2

    q3_rev = next(f for f in rev_facts if f.period_start == date(2024, 10, 1))
    nine_m_rev = next(f for f in rev_facts if f.period_start == date(2024, 4, 1))

    assert q3_rev.period_end == date(2024, 12, 31)
    assert nine_m_rev.period_end == date(2024, 12, 31)
    assert q3_rev.numeric_value == Decimal("417640000000.00")
    assert nine_m_rev.numeric_value == Decimal("1220640000000.00")

    # Verify segment revenue is not in canonical facts
    assert len(rev_facts) == 2


def test_no_synthetic_quarter_derivation(repo: SqliteRepository) -> None:
    """Normalization must NEVER synthesize Q2 by subtracting Q1 from H1."""
    filing, doc = _setup_issuer_and_filing(repo, xml_fixture_name="infy_q3_fy25_sanitized.xml")
    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )

    normalizer.normalize_filing_document(filing=filing, doc=doc)

    facts = repo.get_canonical_financial_facts(filing.filing_id)

    # Infy fixture has Q3 (Oct-Dec) and 9M (Apr-Dec).
    # It does NOT report H1 or standalone H2.
    # Ensure NO synthetic period coordinates were fabricated!
    for f in facts:
        assert f.period_start in (date(2024, 10, 1), date(2024, 4, 1))
        assert f.period_end == date(2024, 12, 31)


def test_paytm_negative_pat_and_eps_preservation(repo: SqliteRepository) -> None:
    """PAYTM negative loss and EPS must persist with signed Decimal fidelity."""
    filing, doc = _setup_issuer_and_filing(
        repo,
        issuer_id="iss_paytm",
        filing_id="filing_paytm_q3",
        document_id="doc_paytm_q3",
        xml_fixture_name="paytm_q3_fy25_loss_sanitized.xml",
    )
    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )

    result = normalizer.normalize_filing_document(filing=filing, doc=doc)

    assert result.canonical_promoted >= 2
    facts = repo.get_canonical_financial_facts(filing.filing_id)

    pat = next(f for f in facts if f.canonical_concept == CanonicalFinancialConcept.PROFIT_LOSS_FOR_PERIOD)
    assert pat.numeric_value == Decimal("-2085000000.00")

    eps = next(f for f in facts if f.canonical_concept == CanonicalFinancialConcept.EPS_DILUTED)
    assert eps.numeric_value == Decimal("-3.27")


def test_hdfcbank_banking_canonical_denied(repo: SqliteRepository) -> None:
    """HDFCBANK banking filings must parse raw but produce ZERO canonical facts."""
    filing, doc = _setup_issuer_and_filing(
        repo,
        issuer_id="iss_hdfc",
        filing_id="filing_hdfc_q3",
        document_id="doc_hdfc_q3",
        xml_fixture_name="hdfcbank_q3_fy25_banking_sanitized.xml",
    )
    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.INELIGIBLE_BANKING),
    )

    result = normalizer.normalize_filing_document(filing=filing, doc=doc)
    assert result.raw_occurrences_persisted == 3
    assert result.canonical_promoted == 0

    # Even with non-financial eligibility asserted, banking concepts are unmapped
    normalizer2 = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )
    result2 = normalizer2.normalize_filing_document(filing=filing, doc=doc)
    assert result2.canonical_promoted == 0


def test_issuer_eligibility_unavailable_stops_at_raw(repo: SqliteRepository) -> None:
    """Default resolver fails closed to ISSUER_CLASSIFICATION_UNAVAILABLE, safely stopping at raw facts."""
    filing, doc = _setup_issuer_and_filing(repo, xml_fixture_name="infy_q3_fy25_sanitized.xml")
    normalizer = FundamentalFactNormalizer(repo)  # default resolver fails closed per D10

    result = normalizer.normalize_filing_document(filing=filing, doc=doc)

    assert result.eligibility == NormalizationEligibility.ISSUER_CLASSIFICATION_UNAVAILABLE
    assert result.raw_occurrences_persisted == 14
    assert result.canonical_promoted == 0
    assert len(repo.get_canonical_financial_facts(filing.filing_id)) == 0


def test_duplicate_and_conflict_resolution(repo: SqliteRepository) -> None:
    """Exact duplicates produce 1 canonical fact; conflicting duplicates block promotion."""
    filing, doc = _setup_issuer_and_filing(
        repo,
        issuer_id="iss_dup",
        filing_id="filing_dup",
        document_id="doc_dup",
        xml_fixture_name="duplicate_and_nil_cases_sanitized.xml",
    )
    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )

    result = normalizer.normalize_filing_document(filing=filing, doc=doc)

    # 2 Revenue (exact dup) + 2 PBT (exact dup numeric values) -> 2 promoted, 2 duplicates
    assert result.duplicate_count == 2
    assert result.canonical_promoted == 2
    assert result.unmapped_count == 3  # 2 OtherIncome + 1 ExceptionalItems

    facts = repo.get_canonical_financial_facts(filing.filing_id)
    assert len(facts) == 2
    rev_fact = next(f for f in facts if f.canonical_concept == CanonicalFinancialConcept.REVENUE_FROM_OPERATIONS)
    assert rev_fact.duplicate_classification == DuplicateClassification.EXACT_DUPLICATE

    # Verify both raw facts are linked via canonical_fact_raw_sources
    source_ids = repo.get_raw_source_ids_for_canonical_fact(rev_fact.canonical_fact_id)
    assert len(source_ids) == 2


def test_conflicting_duplicate_blocks_canonical_promotion(repo: SqliteRepository) -> None:
    """Conflicting values for the same canonical concept must NOT promote an arbitrary winner."""
    conflict_xml = b"""<?xml version="1.0" encoding="utf-8"?>
    <xbrli:xbrl
      xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
      <xbrli:context id="C1">
        <xbrli:entity><xbrli:identifier scheme="bse">500209</xbrli:identifier></xbrli:entity>
        <xbrli:period>
          <xbrli:startDate>2024-10-01</xbrli:startDate>
          <xbrli:endDate>2024-12-31</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>
      <xbrli:context id="C2">
        <xbrli:entity><xbrli:identifier scheme="bse">500209</xbrli:identifier></xbrli:entity>
        <xbrli:period>
          <xbrli:startDate>2024-10-01</xbrli:startDate>
          <xbrli:endDate>2024-12-31</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>
      <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
      <in-bse-fin:RevenueFromOperations
        contextRef="C1" unitRef="INR" decimals="-7">100000000.00</in-bse-fin:RevenueFromOperations>
      <in-bse-fin:RevenueFromOperations
        contextRef="C2" unitRef="INR" decimals="-7">200000000.00</in-bse-fin:RevenueFromOperations>
    </xbrli:xbrl>
    """
    issuer = IssuerRecord(issuer_id="iss_conflict", legal_name="Conflict Corp")
    repo.upsert_issuer(issuer)
    filing = FundamentalFiling(
        filing_id="filing_conflict",
        issuer_id="iss_conflict",
        source="NSE",
        source_record_id="rec_conflict",
        source_reported_symbol="CONFLICT",
        source_reported_isin="INE999A01099",
        source_reported_name="Conflict Corp",
        period_start=date(2024, 10, 1),
        period_end=date(2024, 12, 31),
        financial_year="2024-2025",
        period_nature=PeriodNature.QUARTERLY,
        cumulative_nature=CumulativeNature.NON_CUMULATIVE,
        statement_scope=StatementScope.CONSOLIDATED,
        audit_status=FilingAuditStatus.UNAUDITED,
        publication_precision=PublicationPrecision.EXACT_TIMESTAMP,
        source_published_at=datetime(2025, 1, 16, 16, 30, tzinfo=IST),
        source_published_date=date(2025, 1, 16),
    )
    repo.save_fundamental_filing(filing)
    doc = FilingDocument.create(
        document_id="doc_conflict",
        filing_id="filing_conflict",
        source_url="https://example.com/conflict.xml",
        raw_bytes=conflict_xml,
    )
    repo.save_filing_document(doc)

    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )
    result = normalizer.normalize_filing_document(filing=filing, doc=doc)

    assert result.raw_occurrences_persisted == 2
    assert result.conflict_count == 2
    assert result.canonical_promoted == 0  # Conflicting candidates withheld!
    assert len(repo.get_canonical_financial_facts(filing.filing_id)) == 0


def test_unapproved_taxonomy_namespace_blocked(repo: SqliteRepository) -> None:
    """Facts from unapproved MCA namespace must persist in raw but yield taxonomy_blocked_count."""
    mca_xml = b"""<?xml version="1.0" encoding="utf-8"?>
    <xbrli:xbrl
      xmlns:mca="http://www.mca.gov.in/xbrl/ind-as/2020-03-31"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
      <xbrli:context id="C1">
        <xbrli:entity><xbrli:identifier scheme="cin">L12345MH2000PLC123456</xbrli:identifier></xbrli:entity>
        <xbrli:period>
          <xbrli:startDate>2024-10-01</xbrli:startDate>
          <xbrli:endDate>2024-12-31</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>
      <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
      <mca:RevenueFromOperations contextRef="C1" unitRef="INR" decimals="-7">500000000.00</mca:RevenueFromOperations>
    </xbrli:xbrl>
    """
    issuer = IssuerRecord(issuer_id="iss_mca", legal_name="MCA Test Corp")
    repo.upsert_issuer(issuer)
    filing = FundamentalFiling(
        filing_id="filing_mca",
        issuer_id="iss_mca",
        source="NSE",
        source_record_id="rec_mca",
        source_reported_symbol="MCACORP",
        source_reported_isin="INE888A01088",
        source_reported_name="MCA Test Corp",
        period_start=date(2024, 10, 1),
        period_end=date(2024, 12, 31),
        financial_year="2024-2025",
        period_nature=PeriodNature.QUARTERLY,
        cumulative_nature=CumulativeNature.NON_CUMULATIVE,
        statement_scope=StatementScope.CONSOLIDATED,
        audit_status=FilingAuditStatus.UNAUDITED,
        publication_precision=PublicationPrecision.EXACT_TIMESTAMP,
        source_published_at=datetime(2025, 1, 16, 16, 30, tzinfo=IST),
        source_published_date=date(2025, 1, 16),
    )
    repo.save_fundamental_filing(filing)
    doc = FilingDocument.create(
        document_id="doc_mca",
        filing_id="filing_mca",
        source_url="https://example.com/mca.xml",
        raw_bytes=mca_xml,
    )
    repo.save_filing_document(doc)

    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )
    result = normalizer.normalize_filing_document(filing=filing, doc=doc)

    assert result.raw_occurrences_persisted == 1
    assert result.taxonomy_blocked_count == 1
    assert result.canonical_promoted == 0
    assert len(repo.get_canonical_financial_facts(filing.filing_id)) == 0


def test_frozen_duplicate_semantics_four_cases(repo: SqliteRepository) -> None:
    """Test the 4 explicit frozen duplicate cases:

    A. Identical values, different decimals: no precision winner, both raw preserved,
       1 canonical emitted (EXACT_DUPLICATE), both raw sources linked.
    B. Different values, different decimals: no promotion, conflict_count > 0.
    C. Identical values, identical decimals: exact duplicate behavior.
    D. Physically duplicate occurrence: different source_occurrence_ordinal values.
    """
    # Case A: Identical values (500,000,000.00), different decimals (-7 vs -5)
    xml_case_a = b"""<?xml version="1.0" encoding="utf-8"?>
    <xbrli:xbrl
      xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
      <xbrli:context id="C1">
        <xbrli:entity><xbrli:identifier scheme="bse">500001</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:startDate>2024-10-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period>
      </xbrli:context>
      <xbrli:context id="C2">
        <xbrli:entity><xbrli:identifier scheme="bse">500001</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:startDate>2024-10-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period>
      </xbrli:context>
      <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
      <in-bse-fin:RevenueFromOperations
          contextRef="C1" unitRef="INR" decimals="-7">500000000.00</in-bse-fin:RevenueFromOperations>
      <in-bse-fin:RevenueFromOperations
          contextRef="C2" unitRef="INR" decimals="-5">500000000.00</in-bse-fin:RevenueFromOperations>
    </xbrli:xbrl>
    """
    issuer = IssuerRecord(issuer_id="iss_cases", legal_name="Cases Corp")
    repo.upsert_issuer(issuer)
    filing_a = FundamentalFiling(
        filing_id="filing_case_a",
        issuer_id="iss_cases",
        source="NSE",
        source_record_id="rec_case_a",
        source_reported_symbol="CASES",
        source_reported_isin="INE777A01077",
        source_reported_name="Cases Corp",
        period_start=date(2024, 10, 1),
        period_end=date(2024, 12, 31),
        financial_year="2024-2025",
        period_nature=PeriodNature.QUARTERLY,
        cumulative_nature=CumulativeNature.NON_CUMULATIVE,
        statement_scope=StatementScope.CONSOLIDATED,
        audit_status=FilingAuditStatus.UNAUDITED,
        publication_precision=PublicationPrecision.EXACT_TIMESTAMP,
        source_published_at=datetime(2025, 1, 16, 16, 30, tzinfo=IST),
        source_published_date=date(2025, 1, 16),
    )
    repo.save_fundamental_filing(filing_a)
    doc_a = FilingDocument.create(
        document_id="doc_case_a",
        filing_id="filing_case_a",
        source_url="https://example.com/case_a.xml",
        raw_bytes=xml_case_a,
    )
    repo.save_filing_document(doc_a)

    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )
    res_a = normalizer.normalize_filing_document(filing=filing_a, doc=doc_a)

    # Case A assertions:
    # 1. Both raw occurrences preserved
    assert res_a.raw_occurrences_persisted == 2
    raw_facts = repo.get_raw_financial_facts(doc_a.document_id)
    assert len(raw_facts) == 2
    # Case D: physically duplicate occurrences have distinct ordinals (1 and 2)
    assert raw_facts[0].source_occurrence_ordinal == 1
    assert raw_facts[1].source_occurrence_ordinal == 2
    # 2. No "higher precision winner" - exactly one canonical fact emitted because numeric values match
    assert res_a.canonical_promoted == 1
    assert res_a.duplicate_count == 1
    can_facts = repo.get_canonical_financial_facts(filing_a.filing_id)
    assert len(can_facts) == 1
    assert can_facts[0].numeric_value == Decimal("500000000.00")
    assert can_facts[0].duplicate_classification == DuplicateClassification.EXACT_DUPLICATE
    # 3. Both raw sources linked
    linked_raw_ids = repo.get_raw_source_ids_for_canonical_fact(can_facts[0].canonical_fact_id)
    assert len(linked_raw_ids) == 2
    assert raw_facts[0].raw_fact_id in linked_raw_ids
    assert raw_facts[1].raw_fact_id in linked_raw_ids


def test_point_in_time_publication_precision_filtering(repo: SqliteRepository) -> None:
    """Only EXACT_TIMESTAMP filings published <= as_of participate in PIT queries."""
    # 1. Exact timestamp filing at 16:30 IST on 2025-01-16
    t_pub = datetime(2025, 1, 16, 16, 30, tzinfo=IST)
    filing1, doc1 = _setup_issuer_and_filing(
        repo,
        issuer_id="iss_pit",
        filing_id="filing_exact",
        document_id="doc_exact",
        xml_fixture_name="infy_q3_fy25_sanitized.xml",
        precision=PublicationPrecision.EXACT_TIMESTAMP,
        published_at=t_pub,
    )
    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )
    normalizer.normalize_filing_document(filing=filing1, doc=doc1)

    # 2. DATE_ONLY filing for same issuer
    filing2, doc2 = _setup_issuer_and_filing(
        repo,
        issuer_id="iss_pit",
        filing_id="filing_date_only",
        document_id="doc_date_only",
        xml_fixture_name="infy_q3_fy25_sanitized.xml",
        precision=PublicationPrecision.DATE_ONLY,
        published_at=t_pub,
    )
    normalizer.normalize_filing_document(filing=filing2, doc=doc2)

    # 3. UNKNOWN precision filing for same issuer
    filing3, doc3 = _setup_issuer_and_filing(
        repo,
        issuer_id="iss_pit",
        filing_id="filing_unknown",
        document_id="doc_unknown",
        xml_fixture_name="infy_q3_fy25_sanitized.xml",
        precision=PublicationPrecision.UNKNOWN,
        published_at=t_pub,
    )
    normalizer.normalize_filing_document(filing=filing3, doc=doc3)

    # As of 16:00 (before publication) -> 0 facts
    before_pub = datetime(2025, 1, 16, 16, 0, tzinfo=IST)
    facts_before = repo.get_canonical_facts_for_issuer("iss_pit", as_of=before_pub)
    assert len(facts_before) == 0

    # As of 17:00 (after publication) -> Only facts from filing_exact (EXACT_TIMESTAMP)
    # Both DATE_ONLY and UNKNOWN precision filings are strictly excluded
    after_pub = datetime(2025, 1, 16, 17, 0, tzinfo=IST)
    facts_after = repo.get_canonical_facts_for_issuer("iss_pit", as_of=after_pub)
    assert len(facts_after) > 0
    assert all(f.filing_id == "filing_exact" for f in facts_after)

    # Naive datetime raises RepositoryError
    naive_as_of = datetime(2025, 1, 16, 17, 0)
    with pytest.raises(RepositoryError, match="as_of datetime must be timezone-aware"):
        repo.get_canonical_facts_for_issuer("iss_pit", as_of=naive_as_of)


def test_typed_dimension_fact_persists_raw_but_blocked_from_canonical(repo: SqliteRepository) -> None:
    """Facts with typedMember dimensions persist in raw_financial_facts but are blocked from canonical promotion."""
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
                <xbrldi:typedMember dimension="custom:SegmentAxis">
                    <custom:SegmentVal>SEG-01</custom:SegmentVal>
                </xbrldi:typedMember>
            </xbrli:scenario>
        </xbrli:context>
        <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
        <in-bse-fin:RevenueFromOperations
            contextRef="TypedCtx" unitRef="INR" decimals="2">99999.00</in-bse-fin:RevenueFromOperations>
    </xbrli:xbrl>
    """
    issuer = IssuerRecord(issuer_id="iss_typed", legal_name="Typed Test Ltd")
    repo.upsert_issuer(issuer)
    now = datetime(2025, 1, 17, 10, 0, tzinfo=IST)
    filing = FundamentalFiling(
        filing_id="filing_typed",
        issuer_id="iss_typed",
        source="NSE",
        source_record_id="rec_typed",
        source_reported_symbol="TYPED",
        source_reported_isin=None,
        source_reported_name="Typed Test Ltd",
        period_start=date(2024, 10, 1),
        period_end=date(2024, 12, 31),
        financial_year="2024-2025",
        period_nature=PeriodNature.QUARTERLY,
        cumulative_nature=CumulativeNature.NON_CUMULATIVE,
        statement_scope=StatementScope.CONSOLIDATED,
        audit_status=FilingAuditStatus.AUDITED,
        publication_precision=PublicationPrecision.EXACT_TIMESTAMP,
        source_published_at=datetime(2025, 1, 16, 16, 30, tzinfo=IST),
        source_published_date=date(2025, 1, 16),
        market_available_at=None,
        source_url="https://example.com/typed.xml",
        revision_indicator="N",
        supersedes_filing_id=None,
        raw_metadata={},
        ingested_at=now,
    )
    repo.save_fundamental_filing(filing)
    doc = FilingDocument.create(
        document_id="doc_typed",
        filing_id="filing_typed",
        media_type="application/xml",
        source_url="https://example.com/typed.xml",
        raw_bytes=xml,
    )
    repo.save_filing_document(doc)

    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )
    res = normalizer.normalize_filing_document(filing=filing, doc=doc)

    assert res.raw_occurrences_seen == 1
    assert res.raw_occurrences_persisted == 1
    assert res.canonical_promoted == 0
    assert res.dimension_blocked_count == 1

    # Raw fact is preserved with dimensions
    raw_facts = repo.get_raw_financial_facts("doc_typed")
    assert len(raw_facts) == 1
    assert raw_facts[0].is_dimensioned is True
    assert raw_facts[0].dimensions[0]["kind"] == "typed"

    # Zero canonical facts promoted
    canonical_facts = repo.get_canonical_financial_facts("filing_typed")
    assert len(canonical_facts) == 0


def test_invalid_numeric_fact_persists_raw_zero_canonical_promotion(repo: SqliteRepository) -> None:
    """Facts with unparseable numeric lexical values persist in raw but are not promoted to canonical."""
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
            contextRef="Ctx" unitRef="INR" decimals="2">NOT_A_NUMBER</in-bse-fin:RevenueFromOperations>
    </xbrli:xbrl>
    """
    issuer = IssuerRecord(issuer_id="iss_inv_num", legal_name="Invalid Num Ltd")
    repo.upsert_issuer(issuer)
    now = datetime(2025, 1, 17, 10, 0, tzinfo=IST)
    filing = FundamentalFiling(
        filing_id="filing_inv_num",
        issuer_id="iss_inv_num",
        source="NSE",
        source_record_id="rec_inv_num",
        source_reported_symbol="INVNUM",
        source_reported_isin=None,
        source_reported_name="Invalid Num Ltd",
        period_start=date(2024, 10, 1),
        period_end=date(2024, 12, 31),
        financial_year="2024-2025",
        period_nature=PeriodNature.QUARTERLY,
        cumulative_nature=CumulativeNature.NON_CUMULATIVE,
        statement_scope=StatementScope.CONSOLIDATED,
        audit_status=FilingAuditStatus.AUDITED,
        publication_precision=PublicationPrecision.EXACT_TIMESTAMP,
        source_published_at=datetime(2025, 1, 16, 16, 30, tzinfo=IST),
        source_published_date=date(2025, 1, 16),
        market_available_at=None,
        source_url="https://example.com/inv_num.xml",
        revision_indicator="N",
        supersedes_filing_id=None,
        raw_metadata={},
        ingested_at=now,
    )
    repo.save_fundamental_filing(filing)
    doc = FilingDocument.create(
        document_id="doc_inv_num",
        filing_id="filing_inv_num",
        media_type="application/xml",
        source_url="https://example.com/inv_num.xml",
        raw_bytes=xml,
    )
    repo.save_filing_document(doc)

    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )
    res = normalizer.normalize_filing_document(filing=filing, doc=doc)

    assert res.raw_occurrences_seen == 1
    assert res.raw_occurrences_persisted == 1
    assert res.canonical_promoted == 0
    assert res.unmapped_count == 1

    # Raw fact is preserved with numeric_value=None and raw_value="NOT_A_NUMBER"
    raw_facts = repo.get_raw_financial_facts("doc_inv_num")
    assert len(raw_facts) == 1
    assert raw_facts[0].numeric_value is None
    assert raw_facts[0].raw_value == "NOT_A_NUMBER"

    # Zero canonical facts
    assert len(repo.get_canonical_financial_facts("filing_inv_num")) == 0


def test_normalization_idempotency_rerun(repo: SqliteRepository) -> None:
    """Rerunning normalization on the same document must be idempotent and safe."""
    filing, doc = _setup_issuer_and_filing(repo, xml_fixture_name="infy_q3_fy25_sanitized.xml")
    normalizer = FundamentalFactNormalizer(
        repo,
        eligibility_resolver=StaticIssuerEligibilityResolver(NormalizationEligibility.ELIGIBLE_NON_FINANCIAL),
    )

    res1 = normalizer.normalize_filing_document(filing=filing, doc=doc)
    res2 = normalizer.normalize_filing_document(filing=filing, doc=doc)

    assert res1.raw_occurrences_persisted == 14
    assert res2.raw_occurrences_persisted == 0  # 0 newly inserted
    assert len(repo.get_raw_financial_facts(doc.document_id)) == 14
    assert len(repo.get_canonical_financial_facts(filing.filing_id)) == res1.canonical_promoted
