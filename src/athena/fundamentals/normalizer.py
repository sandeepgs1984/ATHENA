"""Production fundamental fact normalization service (SI-F2B).

Coordinates the end-to-end normalization pipeline:
1. Re-validates SI-F1 source document integrity (hash, size, decompression).
2. Parses raw XBRL facts via secure xbrl_parser (Layer 1).
3. Atomically persists raw fact observations to repository.
4. Enforces issuer eligibility (D10: non-financial corporates only).
5. Applies versioned canonical mapping rules (D12: exactly 5 approved concepts).
6. Deterministically resolves duplicate vs conflicting candidates (D6).
7. Atomically persists canonical facts and traceability links (Layer 2).
8. Returns deterministic NormalizationResult.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Protocol

from athena.data.store import SqliteRepository
from athena.domain.enums import (
    CanonicalFinancialConcept,
    DuplicateClassification,
    NormalizationEligibility,
    RawPeriodType,
)
from athena.domain.fundamentals import (
    CanonicalFinancialFact,
    FilingDocument,
    FundamentalFiling,
    NormalizationResult,
    RawFinancialFact,
)
from athena.fundamentals.mapping_registry import (
    MappingAssessment,
    MappingRegistry,
    MappingRule,
    get_v1_mapping_registry,
)
from athena.fundamentals.xbrl_parser import parse_xbrl_document


class IssuerEligibilityResolver(Protocol):
    """Protocol for resolving an issuer's normalization eligibility from authoritative evidence."""

    def resolve_eligibility(
        self,
        issuer_id: str | None,
        filing: FundamentalFiling,
    ) -> NormalizationEligibility:
        """Determine whether the filing's issuer is an eligible non-financial corporate."""
        ...


class DefaultIssuerEligibilityResolver:
    """Default production eligibility resolver for SI-F2B.

    In SI-F2B, authoritative corporate sector classifications (Non-Financial vs Banking vs
    NBFC vs Insurance) are NOT yet persisted in the database (Schema 22 does not invent or
    derive sector classifications without verified source evidence).

    Per frozen decision D10:
    Unknown issuer classification => NOT ELIGIBLE FOR CANONICAL NORMALIZATION.
    Fails closed to ISSUER_CLASSIFICATION_UNAVAILABLE.
    Authoritative issuer classification will be wired in SI-F2C prior to fleet-wide normalization.
    """

    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo

    def resolve_eligibility(
        self,
        issuer_id: str | None,
        filing: FundamentalFiling,
    ) -> NormalizationEligibility:
        if issuer_id is None:
            return NormalizationEligibility.ISSUER_CLASSIFICATION_UNAVAILABLE

        issuer = self._repo.get_issuer(issuer_id)
        if issuer is None:
            return NormalizationEligibility.ISSUER_CLASSIFICATION_UNAVAILABLE

        # In Schema 22 / SI-F2B, IssuerRecord lacks verified sector classification.
        # Fails closed per D10. F2C will wire authoritative classification.
        return NormalizationEligibility.ISSUER_CLASSIFICATION_UNAVAILABLE


class StaticIssuerEligibilityResolver:
    """Deterministic eligibility resolver for test harnesses and verified injected evidence."""

    def __init__(
        self,
        default_eligibility: NormalizationEligibility = NormalizationEligibility.ELIGIBLE_NON_FINANCIAL,
        overrides: dict[str, NormalizationEligibility] | None = None,
    ) -> None:
        self._default = default_eligibility
        self._overrides = overrides or {}

    def resolve_eligibility(
        self,
        issuer_id: str | None,
        filing: FundamentalFiling,
    ) -> NormalizationEligibility:
        if issuer_id is None:
            return NormalizationEligibility.ISSUER_CLASSIFICATION_UNAVAILABLE
        return self._overrides.get(issuer_id, self._default)


class FundamentalFactNormalizer:
    """Production service for normalizing financial filings into raw and canonical facts."""

    def __init__(
        self,
        repo: SqliteRepository,
        mapping_registry: MappingRegistry | None = None,
        eligibility_resolver: IssuerEligibilityResolver | None = None,
    ) -> None:
        self._repo = repo
        self._registry = mapping_registry or get_v1_mapping_registry()
        self._resolver = eligibility_resolver or DefaultIssuerEligibilityResolver(repo)

    def normalize_filing_document(
        self,
        *,
        filing: FundamentalFiling,
        doc: FilingDocument,
    ) -> NormalizationResult:
        """Execute full normalization pipeline on an already-persisted SI-F1 filing document."""
        if doc.filing_id != filing.filing_id:
            raise ValueError(
                f"Document filing_id ({doc.filing_id!r}) does not match filing ({filing.filing_id!r})"
            )

        # 1. Recover uncompressed bytes with SI-F1 verified hash and bounded size integrity
        raw_bytes = doc.get_raw_bytes()

        # 2. Layer 1: Secure XBRL parsing into raw fact occurrences
        raw_facts = parse_xbrl_document(
            document_id=doc.document_id,
            filing_id=filing.filing_id,
            raw_bytes=raw_bytes,
        )

        # 3. Layer 1 Persistence: Atomically and idempotently persist raw facts
        raw_persisted = self._repo.save_raw_financial_facts(raw_facts)

        raw_seen = len(raw_facts)
        unmapped_count = 0
        dimension_blocked_count = 0
        unit_blocked_count = 0
        taxonomy_blocked_count = 0
        duplicate_count = 0
        conflict_count = 0

        # 4. Check Issuer Eligibility via authoritative resolver (D10)
        eligibility = self._resolver.resolve_eligibility(filing.issuer_id, filing)
        if eligibility != NormalizationEligibility.ELIGIBLE_NON_FINANCIAL:
            return NormalizationResult(
                document_id=doc.document_id,
                filing_id=filing.filing_id,
                raw_occurrences_seen=raw_seen,
                raw_occurrences_persisted=raw_persisted,
                canonical_promoted=0,
                unmapped_count=0,
                dimension_blocked_count=0,
                unit_blocked_count=0,
                taxonomy_blocked_count=0,
                duplicate_count=0,
                conflict_count=0,
                eligibility=eligibility,
            )

        # 5. Layer 2: Evaluate canonical mapping rules
        # Group candidate observations by economic coordinates:
        # (concept, scope, period_type, period_start, period_end)
        CandidateKey = tuple[CanonicalFinancialConcept, str, RawPeriodType, Any, Any]
        candidates_by_econ_key: dict[CandidateKey, list[tuple[RawFinancialFact, MappingRule]]] = defaultdict(list)

        for f in raw_facts:
            assessment, rule = self._registry.assess_raw_fact(f)
            if assessment == MappingAssessment.MATCH:
                assert rule is not None
                assert rule.canonical_concept is not None
                econ_key: CandidateKey = (
                    rule.canonical_concept,
                    filing.statement_scope.value,
                    f.period_type,
                    f.period_start,
                    f.period_end,
                )
                candidates_by_econ_key[econ_key].append((f, rule))
            elif assessment == MappingAssessment.TAXONOMY_BLOCKED:
                taxonomy_blocked_count += 1
            elif assessment == MappingAssessment.UNIT_BLOCKED:
                unit_blocked_count += 1
            elif assessment == MappingAssessment.DIMENSION_BLOCKED:
                dimension_blocked_count += 1
            elif assessment in (
                MappingAssessment.PERIOD_BLOCKED,
                MappingAssessment.NOT_PROMOTABLE,
                MappingAssessment.UNMAPPED,
            ):
                unmapped_count += 1

        # 6. Deduplicate and resolve candidates deterministically
        canonical_facts_to_save: list[CanonicalFinancialFact] = []
        links_to_save: list[tuple[str, str, bool]] = []

        for econ_key, candidate_group in candidates_by_econ_key.items():
            concept, _scope_str, p_type, p_start, p_end = econ_key

            if len(candidate_group) == 1:
                fact, rule = candidate_group[0]
                can_id = f"cf_{doc.document_id}_{fact.source_occurrence_ordinal}"
                can_fact = CanonicalFinancialFact(
                    canonical_fact_id=can_id,
                    filing_id=filing.filing_id,
                    document_id=doc.document_id,
                    canonical_concept=concept,
                    statement_scope=filing.statement_scope,
                    period_type=p_type,
                    period_start=p_start,
                    period_end=p_end,
                    canonical_unit=rule.canonical_unit,
                    numeric_value=fact.numeric_value,  # type: ignore[arg-type]
                    mapping_version=self._registry.mapping_version,
                    mapping_rule_id=rule.rule_id,
                    duplicate_classification=DuplicateClassification.UNIQUE,
                    primary_raw_fact_id=fact.raw_fact_id,
                )
                canonical_facts_to_save.append(can_fact)
                links_to_save.append((can_id, fact.raw_fact_id, True))

            else:
                # Multiple candidates for the same economic coordinates
                distinct_values = {cand[0].numeric_value for cand in candidate_group}
                if len(distinct_values) == 1:
                    # EXACT_DUPLICATE: Identical values reported multiple times
                    duplicate_count += len(candidate_group) - 1
                    primary_fact, primary_rule = candidate_group[0]
                    can_id = f"cf_{doc.document_id}_{primary_fact.source_occurrence_ordinal}"
                    can_fact = CanonicalFinancialFact(
                        canonical_fact_id=can_id,
                        filing_id=filing.filing_id,
                        document_id=doc.document_id,
                        canonical_concept=concept,
                        statement_scope=filing.statement_scope,
                        period_type=p_type,
                        period_start=p_start,
                        period_end=p_end,
                        canonical_unit=primary_rule.canonical_unit,
                        numeric_value=primary_fact.numeric_value,  # type: ignore[arg-type]
                        mapping_version=self._registry.mapping_version,
                        mapping_rule_id=primary_rule.rule_id,
                        duplicate_classification=DuplicateClassification.EXACT_DUPLICATE,
                        primary_raw_fact_id=primary_fact.raw_fact_id,
                    )
                    canonical_facts_to_save.append(can_fact)
                    links_to_save.append((can_id, primary_fact.raw_fact_id, True))
                    for other_fact, _ in candidate_group[1:]:
                        links_to_save.append((can_id, other_fact.raw_fact_id, False))
                else:
                    # CONFLICTING_DUPLICATE: Different numeric values for same coordinates
                    # Omit canonical promotion for this economic concept; mark CONFLICT_UNRESOLVED
                    conflict_count += len(candidate_group)

        # 7. Layer 2 Persistence: Atomically persist canonical facts and traceability links
        canonical_promoted = self._repo.save_canonical_financial_facts(
            canonical_facts_to_save, links_to_save
        )

        return NormalizationResult(
            document_id=doc.document_id,
            filing_id=filing.filing_id,
            raw_occurrences_seen=raw_seen,
            raw_occurrences_persisted=raw_persisted,
            canonical_promoted=canonical_promoted,
            unmapped_count=unmapped_count,
            dimension_blocked_count=dimension_blocked_count,
            unit_blocked_count=unit_blocked_count,
            taxonomy_blocked_count=taxonomy_blocked_count,
            duplicate_count=duplicate_count,
            conflict_count=conflict_count,
            eligibility=eligibility,
        )
