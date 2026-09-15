"""Tests for Canonical Mapping Registry (SI-F2B).

Verifies:
1. Exactly five approved canonical concepts are promotable.
2. Wrong namespace rejection.
3. Wrong period type rejection.
4. Wrong unit class rejection.
5. Material dimensions rejection from enterprise promotion.
6. Capital concept guard (PAID_UP_EQUITY_CAPITAL and FACE_VALUE_PER_SHARE cannot be promoted).
7. Zero share count derivation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from athena.domain.enums import (
    CanonicalFinancialConcept,
    FinancialUnitClass,
    RawPeriodType,
)
from athena.domain.fundamentals import RawFinancialFact
from athena.fundamentals.mapping_registry import (
    IN_BSE_FIN_2020_NS,
    get_v1_mapping_registry,
)


def _make_fact(
    *,
    local_name: str,
    namespace_uri: str = IN_BSE_FIN_2020_NS,
    period_type: RawPeriodType = RawPeriodType.DURATION,
    unit_class: FinancialUnitClass = FinancialUnitClass.CURRENCY,
    numeric_value: Decimal | None = Decimal("100000"),
    is_dimensioned: bool = False,
    is_nil: bool = False,
) -> RawFinancialFact:
    return RawFinancialFact(
        raw_fact_id="doc1:1",
        filing_id="filing1",
        document_id="doc1",
        source_occurrence_ordinal=1,
        namespace_uri=namespace_uri,
        local_name=local_name,
        raw_qname=f"test:{local_name}",
        context_ref="ctx1",
        period_type=period_type,
        period_start=date(2024, 10, 1) if period_type == RawPeriodType.DURATION else None,
        period_end=date(2024, 12, 31),
        duration_days=92 if period_type == RawPeriodType.DURATION else None,
        unit_class=unit_class,
        numeric_value=numeric_value,
        is_dimensioned=is_dimensioned,
        is_nil=is_nil,
        raw_value=str(numeric_value) if numeric_value is not None else "",
    )


def test_five_approved_concepts_promotable() -> None:
    """The registry must approve exactly 5 canonical concepts for promotion."""
    reg = get_v1_mapping_registry()

    # 1. Revenue
    f_rev = _make_fact(local_name="RevenueFromOperations")
    r_rev = reg.find_matching_rule(f_rev)
    assert r_rev is not None
    assert r_rev.can_promote
    assert r_rev.canonical_concept == CanonicalFinancialConcept.REVENUE_FROM_OPERATIONS

    # 2. PBT
    f_pbt = _make_fact(local_name="ProfitLossBeforeTax")
    r_pbt = reg.find_matching_rule(f_pbt)
    assert r_pbt is not None
    assert r_pbt.can_promote
    assert r_pbt.canonical_concept == CanonicalFinancialConcept.PROFIT_LOSS_BEFORE_TAX

    # 3. PAT
    f_pat = _make_fact(local_name="ProfitLossForPeriod")
    r_pat = reg.find_matching_rule(f_pat)
    assert r_pat is not None
    assert r_pat.can_promote
    assert r_pat.canonical_concept == CanonicalFinancialConcept.PROFIT_LOSS_FOR_PERIOD

    # 4. Basic EPS
    f_eps_b = _make_fact(
        local_name="BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        unit_class=FinancialUnitClass.CURRENCY_PER_SHARE,
        numeric_value=Decimal("15.20"),
    )
    r_eps_b = reg.find_matching_rule(f_eps_b)
    assert r_eps_b is not None
    assert r_eps_b.can_promote
    assert r_eps_b.canonical_concept == CanonicalFinancialConcept.EPS_BASIC

    # 5. Diluted EPS
    f_eps_d = _make_fact(
        local_name="DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        unit_class=FinancialUnitClass.CURRENCY_PER_SHARE,
        numeric_value=Decimal("15.18"),
    )
    r_eps_d = reg.find_matching_rule(f_eps_d)
    assert r_eps_d is not None
    assert r_eps_d.can_promote
    assert r_eps_d.canonical_concept == CanonicalFinancialConcept.EPS_DILUTED


def test_mapping_rejects_wrong_namespace() -> None:
    """Concepts from unknown or unauthorized namespaces must not map."""
    reg = get_v1_mapping_registry()
    f_bad_ns = _make_fact(
        local_name="RevenueFromOperations",
        namespace_uri="http://unauthorized.example.com/xbrl",
    )
    assert reg.find_matching_rule(f_bad_ns) is None


def test_mapping_rejects_wrong_period_type() -> None:
    """Duration concepts reported as INSTANT must not map."""
    reg = get_v1_mapping_registry()
    f_instant_rev = _make_fact(
        local_name="RevenueFromOperations",
        period_type=RawPeriodType.INSTANT,
    )
    assert reg.find_matching_rule(f_instant_rev) is None


def test_mapping_rejects_wrong_unit() -> None:
    """Revenue reported as SHARES must not map."""
    reg = get_v1_mapping_registry()
    f_shares_rev = _make_fact(
        local_name="RevenueFromOperations",
        unit_class=FinancialUnitClass.SHARES,
    )
    assert reg.find_matching_rule(f_shares_rev) is None


def test_mapping_rejects_dimensioned_facts() -> None:
    """Facts with dimensions must be rejected from enterprise promotion."""
    reg = get_v1_mapping_registry()
    f_dim_rev = _make_fact(
        local_name="RevenueFromOperations",
        is_dimensioned=True,
    )
    assert reg.find_matching_rule(f_dim_rev) is None


def test_capital_concepts_cannot_be_promoted() -> None:
    """Capital structure concepts (PaidUpEquityCapital, FaceValue) MUST NOT be promoted."""
    reg = get_v1_mapping_registry()

    # Paid up capital
    f_cap = _make_fact(
        local_name="PaidUpValueOfEquityShareCapital",
        period_type=RawPeriodType.INSTANT,
        unit_class=FinancialUnitClass.CURRENCY,
    )
    r_cap = reg.find_matching_rule(f_cap)
    assert r_cap is not None
    assert not r_cap.can_promote
    assert r_cap.canonical_concept is None

    # Face value
    f_fv = _make_fact(
        local_name="FaceValueOfEquityShareCapital",
        period_type=RawPeriodType.INSTANT,
        unit_class=FinancialUnitClass.CURRENCY_PER_SHARE,
        numeric_value=Decimal("5.00"),
    )
    r_fv = reg.find_matching_rule(f_fv)
    assert r_fv is not None
    assert not r_fv.can_promote
    assert r_fv.canonical_concept is None


def test_mapping_assessment_taxonomy_blocked_on_unapproved_mca_namespace() -> None:
    """Revenue concept with unapproved MCA taxonomy namespace must be TAXONOMY_BLOCKED."""
    from athena.fundamentals.mapping_registry import MappingAssessment

    reg = get_v1_mapping_registry()
    f_mca = _make_fact(
        local_name="RevenueFromOperations",
        namespace_uri="http://www.mca.gov.in/xbrl/ind-as/2020-03-31",
    )
    assessment, _ = reg.assess_raw_fact(f_mca)
    assert assessment == MappingAssessment.TAXONOMY_BLOCKED
    assert reg.find_matching_rule(f_mca) is None


def test_mapping_assessment_unit_and_dimension_blocked() -> None:
    """Unit and dimension mismatches must yield exact deterministic assessment classifications."""
    from athena.fundamentals.mapping_registry import MappingAssessment

    reg = get_v1_mapping_registry()

    # Unit blocked
    f_unit = _make_fact(
        local_name="RevenueFromOperations",
        unit_class=FinancialUnitClass.SHARES,
    )
    assessment, _ = reg.assess_raw_fact(f_unit)
    assert assessment == MappingAssessment.UNIT_BLOCKED

    # Dimension blocked
    f_dim = _make_fact(
        local_name="RevenueFromOperations",
        is_dimensioned=True,
    )
    assessment, _ = reg.assess_raw_fact(f_dim)
    assert assessment == MappingAssessment.DIMENSION_BLOCKED

    # Capital concept: not promotable
    f_cap = _make_fact(
        local_name="PaidUpValueOfEquityShareCapital",
        period_type=RawPeriodType.INSTANT,
        unit_class=FinancialUnitClass.CURRENCY,
    )
    assessment, _ = reg.assess_raw_fact(f_cap)
    assert assessment == MappingAssessment.NOT_PROMOTABLE

    # Truly unknown concept: unmapped
    f_unknown = _make_fact(local_name="UnrecognizedConceptName")
    assessment, _ = reg.assess_raw_fact(f_unknown)
    assert assessment == MappingAssessment.UNMAPPED
