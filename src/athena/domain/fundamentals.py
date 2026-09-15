"""Fundamental equity domain models (ATHENA SI-F1).

Follows ATHENA architecture standards:
- Decouples enduring legal corporate enterprise (IssuerRecord) from
  time-versioned security/share-class identities (SecurityIdentity).
- Stores authentic official filing source observations (FundamentalFiling)
  preserving source-reported identity, exact publication precision, and
  authentic source dissemination timestamps.
- Preserves raw source documents (FilingDocument) with SHA-256 digests
  computed on original uncompressed bytes, lossless compression, and bounded
  resource protection.
- Separates immutable source evidence from enrichable ATHENA resolution metadata.
"""

from __future__ import annotations

import hashlib
import zlib
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from athena.domain.enums import (
    CanonicalFinancialConcept,
    CumulativeNature,
    DuplicateClassification,
    FilingAuditStatus,
    FinancialUnitClass,
    NormalizationEligibility,
    PeriodNature,
    PublicationPrecision,
    RawPeriodType,
    StatementScope,
)

#: Maximum allowed uncompressed raw document size (20 MB).
#: Empirically observed XBRL documents are 20-85 KB; PDF announcements 0.5-5 MB.
MAX_RAW_DOCUMENT_SIZE_BYTES: int = 20 * 1024 * 1024


@dataclass(slots=True)
class IssuerRecord:
    """Enduring legal corporate enterprise identity.

    An issuer represents the enduring corporate entity (e.g. Varun Beverages
    Limited or Infosys Limited), which persists across stock splits, ticker
    renames, ISIN changes, and corporate restructurings.
    """

    issuer_id: str
    legal_name: str
    cin: str | None = None
    status: str = "ACTIVE"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.issuer_id or not self.issuer_id.strip():
            raise ValueError("IssuerRecord.issuer_id must be non-empty")
        if not self.legal_name or not self.legal_name.strip():
            raise ValueError("IssuerRecord.legal_name must be non-empty")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("IssuerRecord timestamps must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SecurityIdentity:
    """Time-versioned mapping between an Issuer and a tradable security/ISIN.

    Temporal validity is derived strictly from the interval [effective_from, effective_to],
    never stored as duplicate mutable boolean state (Correction 1).
    Boundary convention: effective_from and effective_to are inclusive dates.
    effective_to = NULL indicates currently active/ongoing identity.
    """

    security_id: str
    issuer_id: str
    exchange: str
    symbol: str
    isin: str
    series: str = "EQ"
    effective_from: date | None = None
    effective_to: date | None = None
    source: str = "OFFICIAL_EXCHANGE"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.security_id or not self.security_id.strip():
            raise ValueError("SecurityIdentity.security_id must be non-empty")
        if not self.issuer_id or not self.issuer_id.strip():
            raise ValueError("SecurityIdentity.issuer_id must be non-empty")
        if not self.symbol or not self.symbol.strip():
            raise ValueError("SecurityIdentity.symbol must be non-empty")
        if not self.isin or not self.isin.strip():
            raise ValueError("SecurityIdentity.isin must be non-empty")
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValueError(
                f"SecurityIdentity effective_from ({self.effective_from}) cannot be after "
                f"effective_to ({self.effective_to})"
            )
        if self.created_at.tzinfo is None:
            raise ValueError("SecurityIdentity.created_at must be timezone-aware")

    def is_valid_on(self, as_of: date) -> bool:
        """Evaluate whether this security identity interval is valid on a specific date."""
        return (
            (self.effective_from is None or as_of >= self.effective_from)
            and (self.effective_to is None or as_of <= self.effective_to)
        )


@dataclass(frozen=True, slots=True)
class FundamentalFiling:
    """Immutable source observation of an official exchange financial filing.

    Preserves source-reported identity exactly as reported by the filing feed,
    distinct from ATHENA-resolved issuer identity.
    Preserves exact dissemination precision without fabricating clock times (Correction 10).
    """

    filing_id: str
    issuer_id: str | None
    source: str
    source_record_id: str
    source_reported_symbol: str | None
    source_reported_isin: str | None
    source_reported_name: str | None
    period_start: date | None
    period_end: date
    financial_year: str | None
    period_nature: PeriodNature
    cumulative_nature: CumulativeNature
    statement_scope: StatementScope
    audit_status: FilingAuditStatus
    publication_precision: PublicationPrecision
    source_published_at: datetime | None
    source_published_date: date | None
    market_available_at: datetime | None = None
    source_url: str | None = None
    revision_indicator: str | None = None
    supersedes_filing_id: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.filing_id or not self.filing_id.strip():
            raise ValueError("FundamentalFiling.filing_id must be non-empty")
        if not self.source or not self.source.strip():
            raise ValueError("FundamentalFiling.source must be non-empty")
        if not self.source_record_id or not self.source_record_id.strip():
            raise ValueError("FundamentalFiling.source_record_id must be non-empty")
        if self.ingested_at.tzinfo is None:
            raise ValueError("FundamentalFiling.ingested_at must be timezone-aware")

        # Temporal precision validation (Correction 10 & Review Item 3)
        if self.publication_precision == PublicationPrecision.EXACT_TIMESTAMP:
            if self.source_published_at is None:
                raise ValueError("EXACT_TIMESTAMP requires non-null source_published_at")
            if self.source_published_at.tzinfo is None:
                raise ValueError("EXACT_TIMESTAMP source_published_at must be timezone-aware")
            if self.source_published_date is None:
                object.__setattr__(self, "source_published_date", self.source_published_at.date())
            elif self.source_published_date != self.source_published_at.date():
                raise ValueError(
                    f"source_published_date ({self.source_published_date}) does not match "
                    f"source_published_at date ({self.source_published_at.date()})"
                )
        elif self.publication_precision == PublicationPrecision.DATE_ONLY:
            if self.source_published_date is None:
                raise ValueError("DATE_ONLY requires non-null source_published_date")
            if self.source_published_at is not None:
                raise ValueError(
                    "DATE_ONLY must NOT carry source_published_at (must not fabricate clock time)"
                )
        elif self.publication_precision == PublicationPrecision.UNKNOWN:
            if self.source_published_at is not None:
                raise ValueError("UNKNOWN precision must NOT carry source_published_at")
            if self.source_published_date is not None:
                raise ValueError("UNKNOWN precision must NOT carry source_published_date")

        if self.market_available_at is not None and self.market_available_at.tzinfo is None:
            raise ValueError("FundamentalFiling.market_available_at must be timezone-aware if set")


@dataclass(frozen=True, slots=True)
class FilingDocument:
    """Raw source document artifact attached to a filing observation.

    Supports 1:N relationship (one filing -> multiple document artifacts) (Correction 6).
    source_sha256 is ALWAYS computed on original uncompressed source bytes (Correction 7).
    Decompression and round-trip extraction are bounded by MAX_RAW_DOCUMENT_SIZE_BYTES (Correction 8).
    """

    document_id: str
    filing_id: str
    source_url: str
    media_type: str
    compression: str
    payload: bytes
    source_sha256: str
    raw_size_bytes: int
    stored_size_bytes: int
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.document_id or not self.document_id.strip():
            raise ValueError("FilingDocument.document_id must be non-empty")
        if not self.filing_id or not self.filing_id.strip():
            raise ValueError("FilingDocument.filing_id must be non-empty")
        if not self.source_url or not self.source_url.strip():
            raise ValueError("FilingDocument.source_url must be non-empty")
        if not self.source_sha256 or len(self.source_sha256) != 64:
            raise ValueError("FilingDocument.source_sha256 must be a 64-char hex digest")
        try:
            int(self.source_sha256, 16)
        except ValueError as exc:
            raise ValueError(
                f"FilingDocument.source_sha256 contains non-hex characters: {self.source_sha256!r}"
            ) from exc

        if self.raw_size_bytes < 0 or self.stored_size_bytes < 0:
            raise ValueError("FilingDocument sizes must be non-negative")
        if self.raw_size_bytes > MAX_RAW_DOCUMENT_SIZE_BYTES:
            raise ValueError(
                f"raw_size_bytes ({self.raw_size_bytes}) exceeds maximum allowed limit "
                f"({MAX_RAW_DOCUMENT_SIZE_BYTES} bytes)"
            )
        if self.stored_size_bytes != len(self.payload):
            raise ValueError(
                f"stored_size_bytes ({self.stored_size_bytes}) does not match payload length ({len(self.payload)})"
            )
        if self.compression == "none" and self.raw_size_bytes != len(self.payload):
            raise ValueError(
                f"For compression='none', raw_size_bytes ({self.raw_size_bytes}) "
                f"must match payload length ({len(self.payload)})"
            )
        if self.retrieved_at.tzinfo is None:
            raise ValueError("FilingDocument.retrieved_at must be timezone-aware")

    def get_raw_bytes(self) -> bytes:
        """Decompress (if needed), verify hash against source_sha256, and return original source bytes."""
        if self.compression == "zlib":
            try:
                # Bounded decompression against zip bombs
                decompressor = zlib.decompressobj()
                raw = decompressor.decompress(self.payload, MAX_RAW_DOCUMENT_SIZE_BYTES + 1)
                if len(raw) > MAX_RAW_DOCUMENT_SIZE_BYTES or decompressor.unconsumed_tail:
                    raise ValueError("Decompressed payload exceeds MAX_RAW_DOCUMENT_SIZE_BYTES")
                if not decompressor.eof:
                    raise ValueError("Incomplete or truncated compressed payload: zlib stream did not reach EOF")
            except Exception as exc:
                raise ValueError(f"Decompression failed: {exc}") from exc
        elif self.compression == "none":
            raw = self.payload
        else:
            raise ValueError(f"Unsupported compression format: {self.compression!r}")

        if len(raw) != self.raw_size_bytes:
            raise ValueError(
                f"Decompressed raw size mismatch: expected {self.raw_size_bytes} bytes, got {len(raw)} bytes"
            )

        actual_sha = hashlib.sha256(raw).hexdigest().lower()
        if actual_sha != self.source_sha256.lower():
            raise ValueError(
                f"Document hash integrity check failed: expected {self.source_sha256}, got {actual_sha}"
            )
        return raw

    @classmethod
    def create(
        cls,
        *,
        document_id: str,
        filing_id: str,
        source_url: str,
        raw_bytes: bytes,
        media_type: str = "application/xml",
        retrieved_at: datetime | None = None,
        compress: bool = True,
    ) -> FilingDocument:
        """Factory creating a FilingDocument from exact raw downloaded bytes."""
        raw_len = len(raw_bytes)
        if raw_len > MAX_RAW_DOCUMENT_SIZE_BYTES:
            raise ValueError(
                f"Source payload size ({raw_len} bytes) exceeds maximum limit "
                f"({MAX_RAW_DOCUMENT_SIZE_BYTES} bytes)"
            )
        digest = hashlib.sha256(raw_bytes).hexdigest().lower()

        if compress:
            stored_payload = zlib.compress(raw_bytes, level=6)
            compression_type = "zlib"
        else:
            stored_payload = raw_bytes
            compression_type = "none"

        retrieval_time = retrieved_at or datetime.now(timezone.utc)
        return cls(
            document_id=document_id,
            filing_id=filing_id,
            source_url=source_url,
            media_type=media_type,
            compression=compression_type,
            payload=stored_payload,
            source_sha256=digest,
            raw_size_bytes=raw_len,
            stored_size_bytes=len(stored_payload),
            retrieved_at=retrieval_time,
        )


@dataclass(frozen=True, slots=True)
class RawFinancialFact:
    """Layer 1: Lossless observation of a single raw XBRL fact occurrence.

    Preserves exact taxonomy qualification, document-level sequential ordinal,
    opaque context coordinates, units, raw lexical values, dimensions, and signed Decimal
    without synthetic alteration.
    """

    raw_fact_id: str
    filing_id: str
    document_id: str
    source_occurrence_ordinal: int
    namespace_uri: str
    local_name: str
    raw_qname: str
    context_ref: str
    period_type: RawPeriodType
    period_end: date
    period_start: date | None = None
    duration_days: int | None = None
    unit_ref: str | None = None
    raw_unit_identity: str | None = None
    unit_class: FinancialUnitClass = FinancialUnitClass.UNKNOWN
    decimals: str | None = None
    precision: str | None = None
    is_nil: bool = False
    raw_value: str = ""
    numeric_value: Decimal | None = None
    is_dimensioned: bool = False
    dimension_signature: str = ""
    dimensions: tuple[dict[str, str], ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.raw_fact_id or not self.raw_fact_id.strip():
            raise ValueError("RawFinancialFact.raw_fact_id must be non-empty")
        if not self.filing_id or not self.filing_id.strip():
            raise ValueError("RawFinancialFact.filing_id must be non-empty")
        if not self.document_id or not self.document_id.strip():
            raise ValueError("RawFinancialFact.document_id must be non-empty")
        if self.source_occurrence_ordinal < 1:
            raise ValueError(
                f"RawFinancialFact.source_occurrence_ordinal ({self.source_occurrence_ordinal}) must be >= 1"
            )
        if not self.local_name or not self.local_name.strip():
            raise ValueError("RawFinancialFact.local_name must be non-empty")
        if not self.context_ref or not self.context_ref.strip():
            raise ValueError("RawFinancialFact.context_ref must be non-empty")
        if self.is_nil and self.numeric_value is not None:
            raise ValueError("RawFinancialFact cannot carry numeric_value when is_nil is True")
        if self.period_type == RawPeriodType.DURATION:
            if self.period_start is None:
                raise ValueError("RawFinancialFact DURATION facts require period_start")
            if self.period_start > self.period_end:
                raise ValueError(
                    f"period_start ({self.period_start}) cannot be after period_end ({self.period_end})"
                )
        elif self.period_type == RawPeriodType.INSTANT:
            if self.period_start is not None:
                raise ValueError("RawFinancialFact INSTANT facts must have period_start=None")
        if self.created_at.tzinfo is None:
            raise ValueError("RawFinancialFact.created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CanonicalFinancialFact:
    """Layer 2: Standardized canonical financial fact observation.

    Represents a mapped economic fact adhering to ATHENA canonical concepts,
    explicit period coordinates, verified units, and mapping provenance.
    """

    canonical_fact_id: str
    filing_id: str
    document_id: str
    canonical_concept: CanonicalFinancialConcept
    statement_scope: StatementScope
    period_type: RawPeriodType
    period_end: date
    canonical_unit: str
    numeric_value: Decimal
    mapping_version: str
    mapping_rule_id: str
    primary_raw_fact_id: str
    period_start: date | None = None
    duplicate_classification: DuplicateClassification = DuplicateClassification.UNIQUE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.canonical_fact_id or not self.canonical_fact_id.strip():
            raise ValueError("CanonicalFinancialFact.canonical_fact_id must be non-empty")
        if not self.filing_id or not self.filing_id.strip():
            raise ValueError("CanonicalFinancialFact.filing_id must be non-empty")
        if not self.document_id or not self.document_id.strip():
            raise ValueError("CanonicalFinancialFact.document_id must be non-empty")
        if not self.primary_raw_fact_id or not self.primary_raw_fact_id.strip():
            raise ValueError("CanonicalFinancialFact.primary_raw_fact_id must be non-empty")
        if not self.mapping_version or not self.mapping_version.strip():
            raise ValueError("CanonicalFinancialFact.mapping_version must be non-empty")
        if not self.mapping_rule_id or not self.mapping_rule_id.strip():
            raise ValueError("CanonicalFinancialFact.mapping_rule_id must be non-empty")
        if self.period_type == RawPeriodType.DURATION:
            if self.period_start is None:
                raise ValueError("CanonicalFinancialFact DURATION facts require period_start")
            if self.period_start > self.period_end:
                raise ValueError(
                    f"period_start ({self.period_start}) cannot be after period_end ({self.period_end})"
                )
        elif self.period_type == RawPeriodType.INSTANT:
            if self.period_start is not None:
                raise ValueError("CanonicalFinancialFact INSTANT facts must have period_start=None")
        if self.created_at.tzinfo is None:
            raise ValueError("CanonicalFinancialFact.created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Deterministic result summary of a filing document normalization run."""

    document_id: str
    filing_id: str
    raw_occurrences_seen: int
    raw_occurrences_persisted: int
    canonical_promoted: int
    unmapped_count: int
    dimension_blocked_count: int
    unit_blocked_count: int
    taxonomy_blocked_count: int
    duplicate_count: int
    conflict_count: int
    eligibility: NormalizationEligibility
    error_message: str | None = None

