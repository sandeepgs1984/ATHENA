"""Canonical financial fact mapping registry (SI-F2B).

Follows ATHENA frozen decisions:
- D8: Versioned deterministic mapping registry (MAPPING_VERSION_V1 = 'SI_FUNDAMENTALS_MAPPING_V1').
- D10: Non-financial mainboard corporate boundary.
- D12: Exactly five approved canonical concepts promoted:
       1. REVENUE_FROM_OPERATIONS
       2. PROFIT_LOSS_BEFORE_TAX
       3. PROFIT_LOSS_FOR_PERIOD
       4. EPS_BASIC
       5. EPS_DILUTED
- D12: Capital concepts (PAID_UP_EQUITY_CAPITAL, FACE_VALUE_PER_SHARE) are raw-mapped only,
       CANNOT be promoted canonically.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from typing import Final

from athena.domain.enums import (
    CanonicalFinancialConcept,
    FinancialUnitClass,
    RawPeriodType,
)
from athena.domain.fundamentals import RawFinancialFact

MAPPING_VERSION_V1: Final[str] = "SI_FUNDAMENTALS_MAPPING_V1"

# Known approved taxonomy namespaces for Indian corporate reporting
# Only the BSE/NSE financial results 2020 namespace was empirically validated by SI-F2A.
# MCA namespace is unproven for these 5 rules and is deliberately excluded.
IN_BSE_FIN_2020_NS: Final[str] = "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"

APPROVED_NAMESPACES: Final[frozenset[str]] = frozenset({
    IN_BSE_FIN_2020_NS,
})


@unique
class MappingAssessment(str, Enum):
    """Detailed deterministic outcome of evaluating a raw fact against the mapping registry."""

    MATCH = "MATCH"
    TAXONOMY_BLOCKED = "TAXONOMY_BLOCKED"
    PERIOD_BLOCKED = "PERIOD_BLOCKED"
    UNIT_BLOCKED = "UNIT_BLOCKED"
    DIMENSION_BLOCKED = "DIMENSION_BLOCKED"
    NOT_PROMOTABLE = "NOT_PROMOTABLE"
    UNMAPPED = "UNMAPPED"


@dataclass(frozen=True, slots=True)
class MappingRule:
    """Deterministic rule matching a raw XBRL fact occurrence to a canonical concept."""

    rule_id: str
    canonical_concept: CanonicalFinancialConcept | None
    allowed_namespaces: frozenset[str]
    local_name: str
    expected_period_type: RawPeriodType
    expected_unit_class: FinancialUnitClass
    canonical_unit: str
    allow_dimensions: bool = False
    can_promote: bool = True

    def matches(self, fact: RawFinancialFact) -> bool:
        """Evaluate whether a raw fact matches this rule's taxonomy and structural criteria."""
        if fact.namespace_uri not in self.allowed_namespaces:
            return False
        if fact.local_name != self.local_name:
            return False
        if fact.period_type != self.expected_period_type:
            return False
        if fact.unit_class != self.expected_unit_class:
            return False
        if not self.allow_dimensions and fact.is_dimensioned:
            return False
        return not (fact.is_nil or fact.numeric_value is None)


class MappingRegistry:
    """Registry of versioned canonical financial fact mapping rules."""

    def __init__(self, mapping_version: str = MAPPING_VERSION_V1) -> None:
        self.mapping_version = mapping_version
        self._rules: list[MappingRule] = []

    def register(self, rule: MappingRule) -> None:
        self._rules.append(rule)

    def assess_raw_fact(self, fact: RawFinancialFact) -> tuple[MappingAssessment, MappingRule | None]:
        """Assess a raw fact and return the deterministic classification and matching rule."""
        rules_for_local_name = [r for r in self._rules if r.local_name == fact.local_name]
        if not rules_for_local_name:
            return MappingAssessment.UNMAPPED, None

        for rule in rules_for_local_name:
            if fact.namespace_uri not in rule.allowed_namespaces:
                return MappingAssessment.TAXONOMY_BLOCKED, rule
            if fact.period_type != rule.expected_period_type:
                return MappingAssessment.PERIOD_BLOCKED, rule
            if fact.unit_class != rule.expected_unit_class:
                return MappingAssessment.UNIT_BLOCKED, rule
            if not rule.allow_dimensions and fact.is_dimensioned:
                return MappingAssessment.DIMENSION_BLOCKED, rule
            if fact.is_nil or fact.numeric_value is None:
                return MappingAssessment.UNMAPPED, rule
            if not rule.can_promote:
                return MappingAssessment.NOT_PROMOTABLE, rule
            return MappingAssessment.MATCH, rule

        return MappingAssessment.UNMAPPED, None

    def find_matching_rule(self, fact: RawFinancialFact) -> MappingRule | None:
        """Find the unique matching rule for a raw fact. Returns None if unmapped."""
        for rule in self._rules:
            if rule.matches(fact):
                return rule
        return None


def get_v1_mapping_registry() -> MappingRegistry:
    """Build the frozen SI_FUNDAMENTALS_MAPPING_V1 registry.

    Encodes exactly 5 approved canonical concepts for promotion:
    1. REVENUE_FROM_OPERATIONS
    2. PROFIT_LOSS_BEFORE_TAX
    3. PROFIT_LOSS_FOR_PERIOD
    4. EPS_BASIC
    5. EPS_DILUTED

    Also registers capital concepts with can_promote=False (raw mapped only).
    """
    reg = MappingRegistry(MAPPING_VERSION_V1)

    # 1. REVENUE_FROM_OPERATIONS
    reg.register(
        MappingRule(
            rule_id="MAP-V1-REV-OP",
            canonical_concept=CanonicalFinancialConcept.REVENUE_FROM_OPERATIONS,
            allowed_namespaces=APPROVED_NAMESPACES,
            local_name="RevenueFromOperations",
            expected_period_type=RawPeriodType.DURATION,
            expected_unit_class=FinancialUnitClass.CURRENCY,
            canonical_unit="INR",
            allow_dimensions=False,
            can_promote=True,
        )
    )

    # 2. PROFIT_LOSS_BEFORE_TAX
    reg.register(
        MappingRule(
            rule_id="MAP-V1-PBT",
            canonical_concept=CanonicalFinancialConcept.PROFIT_LOSS_BEFORE_TAX,
            allowed_namespaces=APPROVED_NAMESPACES,
            local_name="ProfitLossBeforeTax",
            expected_period_type=RawPeriodType.DURATION,
            expected_unit_class=FinancialUnitClass.CURRENCY,
            canonical_unit="INR",
            allow_dimensions=False,
            can_promote=True,
        )
    )

    # 3. PROFIT_LOSS_FOR_PERIOD
    reg.register(
        MappingRule(
            rule_id="MAP-V1-PAT",
            canonical_concept=CanonicalFinancialConcept.PROFIT_LOSS_FOR_PERIOD,
            allowed_namespaces=APPROVED_NAMESPACES,
            local_name="ProfitLossForPeriod",
            expected_period_type=RawPeriodType.DURATION,
            expected_unit_class=FinancialUnitClass.CURRENCY,
            canonical_unit="INR",
            allow_dimensions=False,
            can_promote=True,
        )
    )

    # 4. EPS_BASIC
    reg.register(
        MappingRule(
            rule_id="MAP-V1-EPS-BASIC",
            canonical_concept=CanonicalFinancialConcept.EPS_BASIC,
            allowed_namespaces=APPROVED_NAMESPACES,
            local_name="BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
            expected_period_type=RawPeriodType.DURATION,
            expected_unit_class=FinancialUnitClass.CURRENCY_PER_SHARE,
            canonical_unit="INR_PER_SHARE",
            allow_dimensions=False,
            can_promote=True,
        )
    )
    reg.register(
        MappingRule(
            rule_id="MAP-V1-EPS-BASIC-SHORT",
            canonical_concept=CanonicalFinancialConcept.EPS_BASIC,
            allowed_namespaces=APPROVED_NAMESPACES,
            local_name="BasicEarningsLossPerShare",
            expected_period_type=RawPeriodType.DURATION,
            expected_unit_class=FinancialUnitClass.CURRENCY_PER_SHARE,
            canonical_unit="INR_PER_SHARE",
            allow_dimensions=False,
            can_promote=True,
        )
    )

    # 5. EPS_DILUTED
    reg.register(
        MappingRule(
            rule_id="MAP-V1-EPS-DILUTED",
            canonical_concept=CanonicalFinancialConcept.EPS_DILUTED,
            allowed_namespaces=APPROVED_NAMESPACES,
            local_name="DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
            expected_period_type=RawPeriodType.DURATION,
            expected_unit_class=FinancialUnitClass.CURRENCY_PER_SHARE,
            canonical_unit="INR_PER_SHARE",
            allow_dimensions=False,
            can_promote=True,
        )
    )
    reg.register(
        MappingRule(
            rule_id="MAP-V1-EPS-DILUTED-SHORT",
            canonical_concept=CanonicalFinancialConcept.EPS_DILUTED,
            allowed_namespaces=APPROVED_NAMESPACES,
            local_name="DilutedEarningsLossPerShare",
            expected_period_type=RawPeriodType.DURATION,
            expected_unit_class=FinancialUnitClass.CURRENCY_PER_SHARE,
            canonical_unit="INR_PER_SHARE",
            allow_dimensions=False,
            can_promote=True,
        )
    )

    # Capital Concepts: Registered but can_promote=False (Strict D12 Capital Guard)
    reg.register(
        MappingRule(
            rule_id="MAP-V1-PAID-UP-CAPITAL-GUARD",
            canonical_concept=None,
            allowed_namespaces=APPROVED_NAMESPACES,
            local_name="PaidUpValueOfEquityShareCapital",
            expected_period_type=RawPeriodType.INSTANT,
            expected_unit_class=FinancialUnitClass.CURRENCY,
            canonical_unit="INR",
            allow_dimensions=False,
            can_promote=False,
        )
    )
    reg.register(
        MappingRule(
            rule_id="MAP-V1-FACE-VALUE-GUARD",
            canonical_concept=None,
            allowed_namespaces=APPROVED_NAMESPACES,
            local_name="FaceValueOfEquityShareCapital",
            expected_period_type=RawPeriodType.INSTANT,
            expected_unit_class=FinancialUnitClass.CURRENCY_PER_SHARE,
            canonical_unit="INR_PER_SHARE",
            allow_dimensions=False,
            can_promote=False,
        )
    )

    return reg
