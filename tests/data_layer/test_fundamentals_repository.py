"""Tests for SI-F1 Fundamentals Identity and Immutable Source-Evidence Persistence.

Covers all 7 mandatory areas:
A. VBL Identity Evolution (issuer decoupled from security ISIN intervals)
B. INFY Cross-Exchange (independent BSE vs NSE observations, PIT queries)
C. SCHAEFFLER Multiple Observations (distinct seqNumber observations retained)
D. Duplicate Retry & Idempotency (safe no-op vs conflict detection)
E. Hash Integrity & Bounded Compression (source_sha256, zlib round-trip, tamper rejection, size caps)
F. Publication Precision (EXACT_TIMESTAMP vs DATE_ONLY vs UNKNOWN, zero lookahead leakage)
G. Schema Migration (Schema 20 -> 21 upgrade, fresh DB, idempotency)
"""

from __future__ import annotations

import hashlib
import sqlite3
import zlib
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.store import SqliteRepository
from athena.data.store.schema import SCHEMA_VERSION
from athena.domain.enums import (
    CanonicalFinancialConcept,
    CumulativeNature,
    DuplicateClassification,
    FilingAuditStatus,
    FinancialUnitClass,
    PeriodNature,
    PublicationPrecision,
    RawPeriodType,
    StatementScope,
)
from athena.domain.fundamentals import (
    MAX_RAW_DOCUMENT_SIZE_BYTES,
    CanonicalFinancialFact,
    FilingDocument,
    FundamentalFiling,
    IssuerRecord,
    RawFinancialFact,
    SecurityIdentity,
)
from athena.errors import RepositoryError

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "athena_test.db")
    r.initialize()
    yield r
    r.close()


def _make_issuer(
    issuer_id: str = "ISS-TEST",
    legal_name: str = "Test Enterprise Limited",
    cin: str | None = "L12345MH2000PLC123456",
) -> IssuerRecord:
    now = datetime(2025, 1, 1, 10, 0, tzinfo=IST)
    return IssuerRecord(
        issuer_id=issuer_id,
        legal_name=legal_name,
        cin=cin,
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )


def _make_filing(
    filing_id: str = "FILING-NSE-117292",
    issuer_id: str | None = "ISS-TEST",
    source: str = "NSE",
    source_record_id: str = "117292",
    scope: StatementScope = StatementScope.CONSOLIDATED,
    precision: PublicationPrecision = PublicationPrecision.EXACT_TIMESTAMP,
    published_at: datetime | None = datetime(2025, 1, 16, 19, 40, 31, tzinfo=IST),
    published_date: date | None = None,
    period_end: date = date(2024, 12, 31),
    reported_isin: str | None = "INE009A01021",
) -> FundamentalFiling:
    now = datetime(2025, 1, 17, 10, 0, tzinfo=IST)
    p_date = published_date or (published_at.date() if published_at else None)
    return FundamentalFiling(
        filing_id=filing_id,
        issuer_id=issuer_id,
        source=source,
        source_record_id=source_record_id,
        source_reported_symbol="TEST",
        source_reported_isin=reported_isin,
        source_reported_name="Test Enterprise Limited",
        period_start=date(2024, 10, 1),
        period_end=period_end,
        financial_year="01-Apr-2024 To 31-Mar-2025",
        period_nature=PeriodNature.QUARTERLY,
        cumulative_nature=CumulativeNature.NON_CUMULATIVE,
        statement_scope=scope,
        audit_status=FilingAuditStatus.AUDITED,
        publication_precision=precision,
        source_published_at=published_at,
        source_published_date=p_date,
        market_available_at=None,
        source_url="https://example.com/filing.xml",
        revision_indicator="N",
        supersedes_filing_id=None,
        raw_metadata={"foo": "bar"},
        ingested_at=now,
    )


def _make_doc(
    document_id: str = "DOC-TEST",
    filing_id: str = "FILING-NSE-117292",
    raw_content: bytes = b"<xbrl>Test Payload</xbrl>",
    media_type: str = "application/xml",
    source_url: str = "https://example.com/test.xml",
) -> FilingDocument:
    return FilingDocument.create(
        document_id=document_id,
        filing_id=filing_id,
        media_type=media_type,
        source_url=source_url,
        raw_bytes=raw_content,
    )


# ==============================================================================
# A. VBL IDENTITY EVOLUTION
# ==============================================================================


class TestVblIdentityEvolution:
    def test_vbl_pre_and_post_split_intervals_coexist_under_same_issuer(self, repo: SqliteRepository):
        issuer = _make_issuer(
            issuer_id="VBL-CORP",
            legal_name="Varun Beverages Limited",
            cin="L74899DL1995PLC069838",
        )
        assert repo.upsert_issuer(issuer) is True

        # Pre-split security identity: Face Value Rs 5, ISIN INE200M01013
        pre_split = SecurityIdentity(
            security_id="SEC-VBL-NSE-EQ-PRE",
            issuer_id="VBL-CORP",
            exchange="NSE",
            symbol="VBL",
            isin="INE200M01013",
            series="EQ",
            effective_from=date(2016, 11, 8),
            effective_to=date(2024, 9, 11),  # Day before ex-date
            source="NSE_SECURITY_MASTER",
            created_at=datetime(2024, 1, 1, 10, 0, tzinfo=IST),
        )
        assert repo.add_security_identity(pre_split) is True

        # Post-split security identity: Face Value Rs 2, ISIN INE200M01021
        post_split = SecurityIdentity(
            security_id="SEC-VBL-NSE-EQ-POST",
            issuer_id="VBL-CORP",
            exchange="NSE",
            symbol="VBL",
            isin="INE200M01021",
            series="EQ",
            effective_from=date(2024, 9, 12),  # Ex-date
            effective_to=None,  # Ongoing active identity
            source="NSE_SECURITY_MASTER",
            created_at=datetime(2024, 9, 12, 9, 15, tzinfo=IST),
        )
        assert repo.add_security_identity(post_split) is True

        # Both intervals coexist under the same issuer
        identities = repo.list_security_identities_for_issuer("VBL-CORP")
        assert len(identities) == 2
        assert identities[0].isin == "INE200M01013"
        assert identities[1].isin == "INE200M01021"

        # Point-in-time security resolution
        # Before split: resolves to old ISIN
        resolved_pre = repo.resolve_security_identity(exchange="NSE", symbol="VBL", as_of=date(2024, 8, 15))
        assert resolved_pre is not None
        assert resolved_pre.isin == "INE200M01013"

        # After split: resolves to new ISIN
        resolved_post = repo.resolve_security_identity(exchange="NSE", symbol="VBL", as_of=date(2024, 10, 15))
        assert resolved_post is not None
        assert resolved_post.isin == "INE200M01021"

        # Current identity (as_of=None): resolves to post-split (effective_to is None)
        resolved_curr = repo.resolve_security_identity(exchange="NSE", symbol="VBL", as_of=None)
        assert resolved_curr is not None
        assert resolved_curr.isin == "INE200M01021"

    def test_vbl_filing_reports_legacy_isin_without_rewriting_source_evidence(self, repo: SqliteRepository):
        issuer = _make_issuer("VBL-CORP", "Varun Beverages Limited")
        repo.upsert_issuer(issuer)

        # In Q4 CY24 (filed on 2025-02-10), the exchange feed reported the legacy ISIN INE200M01013
        filing = _make_filing(
            filing_id="FILING-VBL-Q4-2024",
            issuer_id="VBL-CORP",
            source="NSE",
            source_record_id="1193953",
            reported_isin="INE200M01013",  # Source-reported legacy ISIN
            period_end=date(2024, 12, 31),
            published_at=datetime(2025, 2, 10, 17, 26, 40, tzinfo=IST),
        )
        assert repo.save_fundamental_filing(filing) is True

        retrieved = repo.get_fundamental_filing("FILING-VBL-Q4-2024")
        assert retrieved is not None
        assert retrieved.issuer_id == "VBL-CORP"
        # Source reported ISIN is strictly preserved and never mutated
        assert retrieved.source_reported_isin == "INE200M01013"


# ==============================================================================
# B. INFY CROSS-EXCHANGE OBSERVATIONS & PIT QUERIES
# ==============================================================================


class TestInfyCrossExchangeObservations:
    def test_infy_dual_exchange_observations_and_pit_queries(self, repo: SqliteRepository):
        issuer = _make_issuer("INFY-CORP", "Infosys Limited", "L85110KA1981PLC013115")
        repo.upsert_issuer(issuer)

        # Observation 1: BSE Corporate Announcement PDF at 15:56:58 IST
        bse_time = datetime(2025, 1, 16, 15, 56, 58, tzinfo=IST)
        filing_bse = _make_filing(
            filing_id="FILING-INFY-BSE-20250116",
            issuer_id="INFY-CORP",
            source="BSE",
            source_record_id="500209-ANN-20250116",
            scope=StatementScope.CONSOLIDATED,
            published_at=bse_time,
            period_end=date(2024, 12, 31),
        )
        assert repo.save_fundamental_filing(filing_bse) is True

        # Observation 2: NSE Machine-Readable XBRL XML at 19:40:31 IST
        nse_time = datetime(2025, 1, 16, 19, 40, 31, tzinfo=IST)
        filing_nse = _make_filing(
            filing_id="FILING-INFY-NSE-117292",
            issuer_id="INFY-CORP",
            source="NSE",
            source_record_id="117292",
            scope=StatementScope.CONSOLIDATED,
            published_at=nse_time,
            period_end=date(2024, 12, 31),
        )
        assert repo.save_fundamental_filing(filing_nse) is True

        # Both filings exist independently; market_available_at is unresolved (None)
        fb = repo.get_fundamental_filing("FILING-INFY-BSE-20250116")
        fn = repo.get_fundamental_filing("FILING-INFY-NSE-117292")
        assert fb is not None and fn is not None
        assert fb.market_available_at is None
        assert fn.market_available_at is None
        assert fb.source == "BSE" and fn.source == "NSE"

        # 1. PIT query at market close (15:30:00 IST) -> Neither observation is visible
        as_of_close = datetime(2025, 1, 16, 15, 30, 0, tzinfo=IST)
        res_close = repo.list_filings_as_of(as_of=as_of_close, issuer_id="INFY-CORP")
        assert len(res_close) == 0

        # 2. PIT query between BSE and NSE (17:00:00 IST) -> Only BSE observation is visible
        as_of_interim = datetime(2025, 1, 16, 17, 0, 0, tzinfo=IST)
        res_interim = repo.list_filings_as_of(as_of=as_of_interim, issuer_id="INFY-CORP")
        assert len(res_interim) == 1
        assert res_interim[0].filing_id == "FILING-INFY-BSE-20250116"

        # 3. PIT query after both (20:00:00 IST) -> Both observations are visible
        as_of_evening = datetime(2025, 1, 16, 20, 0, 0, tzinfo=IST)
        res_evening = repo.list_filings_as_of(as_of=as_of_evening, issuer_id="INFY-CORP")
        assert len(res_evening) == 2
        assert [f.filing_id for f in res_evening] == [
            "FILING-INFY-BSE-20250116",
            "FILING-INFY-NSE-117292",
        ]


# ==============================================================================
# C. SCHAEFFLER MULTIPLE OBSERVATIONS & REVISIONS
# ==============================================================================


class TestSchaefflerMultipleObservations:
    def test_schaeffler_revisions_coexist_without_automatic_supersession(self, repo: SqliteRepository):
        issuer = _make_issuer("SCHAEFFLER-CORP", "Schaeffler India Limited")
        repo.upsert_issuer(issuer)

        # Observation 1: Original filing on 2025-02-27
        t1 = datetime(2025, 2, 27, 17, 26, 38, tzinfo=IST)
        f1 = _make_filing(
            filing_id="FILING-SCH-1197098",
            issuer_id="SCHAEFFLER-CORP",
            source="NSE",
            source_record_id="1197098",
            published_at=t1,
            period_end=date(2024, 12, 31),
        )
        assert repo.save_fundamental_filing(f1) is True

        # Observation 2: Revised filing 26 days later on 2025-03-25
        t2 = datetime(2025, 3, 25, 12, 29, 20, tzinfo=IST)
        f2 = _make_filing(
            filing_id="FILING-SCH-1197319",
            issuer_id="SCHAEFFLER-CORP",
            source="NSE",
            source_record_id="1197319",
            published_at=t2,
            period_end=date(2024, 12, 31),
        )
        assert repo.save_fundamental_filing(f2) is True

        # Both observations coexist; earlier observation is NOT overwritten or deleted
        filings = repo.list_filings_for_issuer("SCHAEFFLER-CORP", period_end=date(2024, 12, 31))
        assert len(filings) == 2
        ids = {f.filing_id for f in filings}
        assert ids == {"FILING-SCH-1197098", "FILING-SCH-1197319"}

        # Supersession is not automatically inferred merely because F2 is later (Correction 12)
        f2_retrieved = repo.get_fundamental_filing("FILING-SCH-1197319")
        assert f2_retrieved is not None
        assert f2_retrieved.supersedes_filing_id is None

        # PIT queries observe chronology faithfully:
        # As of March 1: Only F1 is knowable
        march1 = repo.list_filings_as_of(as_of=datetime(2025, 3, 1, 0, 0, tzinfo=IST), issuer_id="SCHAEFFLER-CORP")
        assert len(march1) == 1
        assert march1[0].filing_id == "FILING-SCH-1197098"

        # As of April 1: Both F1 and F2 are knowable
        april1 = repo.list_filings_as_of(as_of=datetime(2025, 4, 1, 0, 0, tzinfo=IST), issuer_id="SCHAEFFLER-CORP")
        assert len(april1) == 2


# ==============================================================================
# D. DUPLICATE RETRY & IDEMPOTENCY
# ==============================================================================


class TestDuplicateRetryAndIdempotency:
    def test_filing_idempotent_retry_and_conflict_detection(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-1")
        repo.upsert_issuer(issuer)

        filing = _make_filing("FILING-1", "ISS-1", source="NSE", source_record_id="1001")
        assert repo.save_fundamental_filing(filing) is True
        # Identical retry returns False (no-op)
        assert repo.save_fundamental_filing(filing) is False

        # Conflicting filing with same (source, source_record_id, statement_scope) but different period_end
        conflicting = _make_filing(
            "FILING-1-CONFLICT",
            "ISS-1",
            source="NSE",
            source_record_id="1001",
            period_end=date(2025, 3, 31),
        )
        with pytest.raises(RepositoryError, match="Conflicting fundamental filing"):
            repo.save_fundamental_filing(conflicting)

    def test_filing_conflict_rejected_on_changed_source_reported_isin(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-CONF-1")
        repo.upsert_issuer(issuer)
        filing = _make_filing(
            "F-CONF-1", "ISS-CONF-1", source="NSE", source_record_id="REC-ISIN", reported_isin="INE111A01011"
        )
        assert repo.save_fundamental_filing(filing) is True

        # Retry with different source_reported_isin -> must raise RepositoryError, not silent False
        changed_isin = _make_filing(
            "F-CONF-1", "ISS-CONF-1", source="NSE", source_record_id="REC-ISIN", reported_isin="INE999Z01099"
        )
        with pytest.raises(RepositoryError, match=r"Conflicting fundamental filing.*source_reported_isin"):
            repo.save_fundamental_filing(changed_isin)

    def test_filing_conflict_rejected_on_changed_audit_status_and_metadata(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-CONF-2")
        repo.upsert_issuer(issuer)
        filing = _make_filing("F-CONF-2", "ISS-CONF-2", source="NSE", source_record_id="REC-AUD")
        assert repo.save_fundamental_filing(filing) is True

        # Changed audit status
        changed_audit = FundamentalFiling(
            filing_id="F-CONF-2",
            issuer_id=filing.issuer_id,
            source=filing.source,
            source_record_id=filing.source_record_id,
            source_reported_symbol=filing.source_reported_symbol,
            source_reported_isin=filing.source_reported_isin,
            source_reported_name=filing.source_reported_name,
            period_start=filing.period_start,
            period_end=filing.period_end,
            financial_year=filing.financial_year,
            period_nature=filing.period_nature,
            cumulative_nature=filing.cumulative_nature,
            statement_scope=filing.statement_scope,
            audit_status=FilingAuditStatus.UNAUDITED,
            publication_precision=filing.publication_precision,
            source_published_at=filing.source_published_at,
            source_published_date=filing.source_published_date,
            raw_metadata=filing.raw_metadata,
            ingested_at=filing.ingested_at,
        )
        with pytest.raises(RepositoryError, match=r"Conflicting fundamental filing.*audit_status"):
            repo.save_fundamental_filing(changed_audit)

        # Changed raw metadata
        changed_meta = FundamentalFiling(
            filing_id="F-CONF-2",
            issuer_id=filing.issuer_id,
            source=filing.source,
            source_record_id=filing.source_record_id,
            source_reported_symbol=filing.source_reported_symbol,
            source_reported_isin=filing.source_reported_isin,
            source_reported_name=filing.source_reported_name,
            period_start=filing.period_start,
            period_end=filing.period_end,
            financial_year=filing.financial_year,
            period_nature=filing.period_nature,
            cumulative_nature=filing.cumulative_nature,
            statement_scope=filing.statement_scope,
            audit_status=filing.audit_status,
            publication_precision=filing.publication_precision,
            source_published_at=filing.source_published_at,
            source_published_date=filing.source_published_date,
            raw_metadata={"different": "value"},
            ingested_at=filing.ingested_at,
        )
        with pytest.raises(RepositoryError, match=r"Conflicting fundamental filing.*raw_metadata"):
            repo.save_fundamental_filing(changed_meta)

        # Changed source_url
        changed_url = FundamentalFiling(
            filing_id="F-CONF-2",
            issuer_id=filing.issuer_id,
            source=filing.source,
            source_record_id=filing.source_record_id,
            source_reported_symbol=filing.source_reported_symbol,
            source_reported_isin=filing.source_reported_isin,
            source_reported_name=filing.source_reported_name,
            period_start=filing.period_start,
            period_end=filing.period_end,
            financial_year=filing.financial_year,
            period_nature=filing.period_nature,
            cumulative_nature=filing.cumulative_nature,
            statement_scope=filing.statement_scope,
            audit_status=filing.audit_status,
            publication_precision=filing.publication_precision,
            source_published_at=filing.source_published_at,
            source_published_date=filing.source_published_date,
            source_url="https://example.com/other.xml",
            raw_metadata=filing.raw_metadata,
            ingested_at=filing.ingested_at,
        )
        with pytest.raises(RepositoryError, match=r"Conflicting fundamental filing.*source_url"):
            repo.save_fundamental_filing(changed_url)

    def test_issuer_upsert_idempotency_enrichment_and_conflict(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-2", "Company Beta", cin=None)
        assert repo.upsert_issuer(issuer) is True
        # Identical retry -> no-op
        assert repo.upsert_issuer(issuer) is False

        # Controlled enrichment: adding CIN to existing issuer with cin=None
        enriched = _make_issuer("ISS-2", "Company Beta", cin="L99999MH2020PLC999999")
        assert repo.upsert_issuer(enriched) is True
        got = repo.get_issuer("ISS-2")
        assert got is not None and got.cin == "L99999MH2020PLC999999"

        # Conflicting CIN for the same issuer raises RepositoryError (Correction 3)
        conflicting_cin = _make_issuer("ISS-2", "Company Beta", cin="L88888MH2020PLC888888")
        with pytest.raises(RepositoryError, match="Conflicting CIN"):
            repo.upsert_issuer(conflicting_cin)

    def test_security_identity_interval_conflict_detection(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-3")
        repo.upsert_issuer(issuer)

        si1 = SecurityIdentity(
            security_id="SEC-1",
            issuer_id="ISS-3",
            exchange="NSE",
            symbol="SYM",
            isin="INE111A01011",
            series="EQ",
            effective_from=date(2020, 1, 1),
            effective_to=date(2022, 12, 31),
            source="NSE",
            created_at=datetime(2020, 1, 1, tzinfo=IST),
        )
        assert repo.add_security_identity(si1) is True
        # Identical retry -> False
        assert repo.add_security_identity(si1) is False

        # Overlapping interval for the same (issuer_id, exchange, symbol, series) raises RepositoryError
        overlapping = SecurityIdentity(
            security_id="SEC-2",
            issuer_id="ISS-3",
            exchange="NSE",
            symbol="SYM",
            isin="INE111A01022",
            series="EQ",
            effective_from=date(2022, 6, 1),  # Overlaps with 2020-01-01 to 2022-12-31
            effective_to=date(2024, 12, 31),
            source="NSE",
            created_at=datetime(2022, 6, 1, tzinfo=IST),
        )
        with pytest.raises(RepositoryError, match="Contradictory overlapping interval"):
            repo.add_security_identity(overlapping)


# ==============================================================================
# E. HASH INTEGRITY & BOUNDED RAW COMPRESSION
# ==============================================================================


class TestHashIntegrityAndBoundedCompression:
    def test_document_round_trip_and_sha256_verification(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-DOC")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-DOC-1", "ISS-DOC")
        repo.save_fundamental_filing(filing)

        raw_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance">
  <RevenueFromOperations>417640000000.00</RevenueFromOperations>
</xbrl>"""

        expected_digest = hashlib.sha256(raw_xml).hexdigest()
        doc = FilingDocument.create(
            document_id="DOC-1",
            filing_id="FILING-DOC-1",
            source_url="https://nsearchives.nseindia.com/corporate/xbrl/sample.xml",
            raw_bytes=raw_xml,
            media_type="application/xml",
            retrieved_at=datetime(2025, 1, 17, 10, 0, tzinfo=IST),
            compress=True,
        )

        assert doc.source_sha256 == expected_digest
        assert doc.compression == "zlib"
        assert doc.raw_size_bytes == len(raw_xml)
        assert repo.save_filing_document(doc) is True

        # Idempotent re-save
        assert repo.save_filing_document(doc) is False

        # Retrieve bytes and verify faithful round-trip
        retrieved_bytes = repo.get_filing_document_bytes("DOC-1")
        assert retrieved_bytes == raw_xml
        assert hashlib.sha256(retrieved_bytes).hexdigest() == expected_digest

    def test_tampered_document_payload_rejected(self, repo: SqliteRepository):
        raw_xml = b"<root>Original</root>"
        doc = FilingDocument.create(
            document_id="DOC-TAMPER",
            filing_id="FILING-1",
            source_url="https://example.com/doc.xml",
            raw_bytes=raw_xml,
            retrieved_at=datetime(2025, 1, 1, tzinfo=IST),
        )

        # Forge corrupted payload with identical length so raw size matches but SHA fails
        corrupted_payload = zlib.compress(b"<root>Forged!!</root>")
        corrupted_doc = FilingDocument(
            document_id=doc.document_id,
            filing_id=doc.filing_id,
            source_url=doc.source_url,
            media_type=doc.media_type,
            compression="zlib",
            payload=corrupted_payload,
            source_sha256=doc.source_sha256,  # Original hash
            raw_size_bytes=len(raw_xml),
            stored_size_bytes=len(corrupted_payload),
            retrieved_at=doc.retrieved_at,
        )

        with pytest.raises(ValueError, match="Document hash integrity check failed"):
            corrupted_doc.get_raw_bytes()

    def test_document_size_cap_enforced(self):
        # Oversized payload rejected by constant cap (Correction 8)
        oversized = b"A" * (MAX_RAW_DOCUMENT_SIZE_BYTES + 10)
        with pytest.raises(ValueError, match="exceeds maximum limit"):
            FilingDocument.create(
                document_id="DOC-OVERSIZED",
                filing_id="FILING-1",
                source_url="https://example.com/large.xml",
                raw_bytes=oversized,
                retrieved_at=datetime(2025, 1, 1, tzinfo=IST),
            )

    def test_document_stored_size_mismatch_rejected(self):
        raw = b"<root>Hello</root>"
        with pytest.raises(ValueError, match=r"stored_size_bytes .* does not match payload length"):
            FilingDocument(
                document_id="DOC-SZ1",
                filing_id="FIL-1",
                source_url="https://example.com/1",
                media_type="application/xml",
                compression="none",
                payload=raw,
                source_sha256=hashlib.sha256(raw).hexdigest(),
                raw_size_bytes=len(raw),
                stored_size_bytes=len(raw) + 5,
                retrieved_at=datetime(2025, 1, 1, tzinfo=IST),
            )

    def test_document_uncompressed_raw_size_mismatch_rejected(self):
        raw = b"<root>Hello</root>"
        with pytest.raises(ValueError, match=r"raw_size_bytes .* must match payload length"):
            FilingDocument(
                document_id="DOC-SZ2",
                filing_id="FIL-1",
                source_url="https://example.com/2",
                media_type="application/xml",
                compression="none",
                payload=raw,
                source_sha256=hashlib.sha256(raw).hexdigest(),
                raw_size_bytes=len(raw) + 10,
                stored_size_bytes=len(raw),
                retrieved_at=datetime(2025, 1, 1, tzinfo=IST),
            )

    def test_document_invalid_hex_sha_rejected(self):
        raw = b"<root>Hello</root>"
        with pytest.raises(ValueError, match="contains non-hex characters"):
            FilingDocument(
                document_id="DOC-HEX",
                filing_id="FIL-1",
                source_url="https://example.com/3",
                media_type="application/xml",
                compression="none",
                payload=raw,
                source_sha256="g" * 64,
                raw_size_bytes=len(raw),
                stored_size_bytes=len(raw),
                retrieved_at=datetime(2025, 1, 1, tzinfo=IST),
            )

    def test_document_decompression_raw_size_mismatch_rejected(self):
        raw = b"<root>Hello World</root>"
        compressed = zlib.compress(raw)
        # Set raw_size_bytes to wrong value
        doc = FilingDocument(
            document_id="DOC-DECOMP-SZ",
            filing_id="FIL-1",
            source_url="https://example.com/4",
            media_type="application/xml",
            compression="zlib",
            payload=compressed,
            source_sha256=hashlib.sha256(raw).hexdigest(),
            raw_size_bytes=len(raw) + 10,  # Wrong declared raw size!
            stored_size_bytes=len(compressed),
            retrieved_at=datetime(2025, 1, 1, tzinfo=IST),
        )
        with pytest.raises(ValueError, match="Decompressed raw size mismatch"):
            doc.get_raw_bytes()

    def test_document_truncated_zlib_stream_rejected(self):
        raw = b"<root>Valid data that has reasonable length for compression</root>"
        compressed = zlib.compress(raw)
        truncated_payload = compressed[:-4]  # Cut off trailing zlib bytes
        doc = FilingDocument(
            document_id="DOC-TRUNC",
            filing_id="FIL-1",
            source_url="https://example.com/trunc",
            media_type="application/xml",
            compression="zlib",
            payload=truncated_payload,
            source_sha256=hashlib.sha256(raw).hexdigest(),
            raw_size_bytes=len(raw),
            stored_size_bytes=len(truncated_payload),
            retrieved_at=datetime(2025, 1, 1, tzinfo=IST),
        )
        with pytest.raises(ValueError, match=r"Decompression failed.*(stream did not reach EOF|Error -5)"):
            doc.get_raw_bytes()

    def test_tampered_document_rejected_before_persistence(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-TAMPER")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FIL-TAMPER", "ISS-TAMPER")
        repo.save_fundamental_filing(filing)

        # Create tampered doc where payload does not match SHA-256
        raw = b"<root>Valid</root>"
        forged = zlib.compress(b"<root>Forged</root>")
        tampered_doc = FilingDocument(
            document_id="DOC-FORGED",
            filing_id="FIL-TAMPER",
            source_url="https://example.com/forged.xml",
            media_type="application/xml",
            compression="zlib",
            payload=forged,
            source_sha256=hashlib.sha256(raw).hexdigest(),
            raw_size_bytes=len(forged),
            stored_size_bytes=len(forged),
            retrieved_at=datetime(2025, 1, 1, tzinfo=IST),
        )

        with pytest.raises(RepositoryError, match="Cannot persist structurally invalid or corrupted"):
            repo.save_filing_document(tampered_doc)

        # Verify no row was persisted
        assert repo.get_filing_document("DOC-FORGED") is None

    def test_document_conflicting_media_type_or_raw_size_rejected(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-DOC-CONF")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FIL-DOC-CONF", "ISS-DOC-CONF")
        repo.save_fundamental_filing(filing)

        raw = b"<root>DocContent</root>"
        doc1 = FilingDocument.create(
            document_id="DOC-C1",
            filing_id="FIL-DOC-CONF",
            source_url="https://example.com/doc.xml",
            raw_bytes=raw,
            media_type="application/xml",
        )
        assert repo.save_filing_document(doc1) is True

        # Same URL and filing, but different media_type -> RepositoryError
        doc2 = FilingDocument(
            document_id="DOC-C2",
            filing_id="FIL-DOC-CONF",
            source_url="https://example.com/doc.xml",
            media_type="application/pdf",
            compression=doc1.compression,
            payload=doc1.payload,
            source_sha256=doc1.source_sha256,
            raw_size_bytes=doc1.raw_size_bytes,
            stored_size_bytes=doc1.stored_size_bytes,
            retrieved_at=doc1.retrieved_at,
        )
        with pytest.raises(RepositoryError, match=r"Conflicting document artifact identity.*media_type"):
            repo.save_filing_document(doc2)


# ==============================================================================
# F. PUBLICATION PRECISION INVARIANTS & TEMPORAL SAFETY
# ==============================================================================


class TestPublicationPrecisionInvariants:
    def test_exact_timestamp_requires_timezone_aware_datetime(self):
        with pytest.raises(ValueError, match="EXACT_TIMESTAMP requires non-null source_published_at"):
            FundamentalFiling(
                filing_id="F-INV-1",
                issuer_id=None,
                source="NSE",
                source_record_id="1",
                source_reported_symbol="X",
                source_reported_isin="INE1",
                source_reported_name="X Ltd",
                period_start=None,
                period_end=date(2024, 12, 31),
                financial_year=None,
                period_nature=PeriodNature.QUARTERLY,
                cumulative_nature=CumulativeNature.NON_CUMULATIVE,
                statement_scope=StatementScope.CONSOLIDATED,
                audit_status=FilingAuditStatus.AUDITED,
                publication_precision=PublicationPrecision.EXACT_TIMESTAMP,
                source_published_at=None,
                source_published_date=None,
                ingested_at=datetime.now(tz=IST),
            )

    def test_date_only_must_not_carry_fabricated_clock_time(self):
        with pytest.raises(ValueError, match="DATE_ONLY must NOT carry source_published_at"):
            FundamentalFiling(
                filing_id="F-INV-2",
                issuer_id=None,
                source="NSE",
                source_record_id="2",
                source_reported_symbol="X",
                source_reported_isin="INE1",
                source_reported_name="X Ltd",
                period_start=None,
                period_end=date(2024, 12, 31),
                financial_year=None,
                period_nature=PeriodNature.QUARTERLY,
                cumulative_nature=CumulativeNature.NON_CUMULATIVE,
                statement_scope=StatementScope.CONSOLIDATED,
                audit_status=FilingAuditStatus.AUDITED,
                publication_precision=PublicationPrecision.DATE_ONLY,
                source_published_at=datetime(2025, 1, 16, 0, 0, tzinfo=IST),  # Fabricated midnight!
                source_published_date=date(2025, 1, 16),
                ingested_at=datetime.now(tz=IST),
            )

    def test_pit_query_excludes_date_only_and_unknown_observations(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-PREC")
        repo.upsert_issuer(issuer)

        # 1. Exact timestamp observation
        t_exact = datetime(2025, 1, 16, 19, 40, tzinfo=IST)
        f_exact = _make_filing(
            filing_id="F-EXACT",
            issuer_id="ISS-PREC",
            source="NSE",
            source_record_id="REC-1",
            precision=PublicationPrecision.EXACT_TIMESTAMP,
            published_at=t_exact,
        )
        repo.save_fundamental_filing(f_exact)

        # 2. Date only observation
        f_date = _make_filing(
            filing_id="F-DATE",
            issuer_id="ISS-PREC",
            source="NSE",
            source_record_id="REC-2",
            precision=PublicationPrecision.DATE_ONLY,
            published_at=None,
            published_date=date(2025, 1, 16),
        )
        repo.save_fundamental_filing(f_date)

        # 3. Unknown precision observation
        f_unk = _make_filing(
            filing_id="F-UNK",
            issuer_id="ISS-PREC",
            source="NSE",
            source_record_id="REC-3",
            precision=PublicationPrecision.UNKNOWN,
            published_at=None,
            published_date=None,
        )
        repo.save_fundamental_filing(f_unk)

        # Query as of 2025-01-17: Only F-EXACT should be returned by exact-timestamp PIT query (Correction 11)
        results = repo.list_filings_as_of(as_of=datetime(2025, 1, 17, 0, 0, tzinfo=IST), issuer_id="ISS-PREC")
        assert len(results) == 1
        assert results[0].filing_id == "F-EXACT"

    def test_unknown_precision_requires_both_date_and_time_to_be_none(self):
        # UNKNOWN with published_at -> Error
        with pytest.raises(ValueError, match="UNKNOWN precision must NOT carry source_published_at"):
            FundamentalFiling(
                filing_id="F-UNK-INV1",
                issuer_id=None,
                source="NSE",
                source_record_id="UNK1",
                source_reported_symbol=None,
                source_reported_isin=None,
                source_reported_name=None,
                period_start=None,
                period_end=date(2024, 12, 31),
                financial_year=None,
                period_nature=PeriodNature.QUARTERLY,
                cumulative_nature=CumulativeNature.NON_CUMULATIVE,
                statement_scope=StatementScope.CONSOLIDATED,
                audit_status=FilingAuditStatus.AUDITED,
                publication_precision=PublicationPrecision.UNKNOWN,
                source_published_at=datetime(2025, 1, 16, 10, 0, tzinfo=IST),
                source_published_date=None,
            )

        # UNKNOWN with published_date -> Error
        with pytest.raises(ValueError, match="UNKNOWN precision must NOT carry source_published_date"):
            FundamentalFiling(
                filing_id="F-UNK-INV2",
                issuer_id=None,
                source="NSE",
                source_record_id="UNK2",
                source_reported_symbol=None,
                source_reported_isin=None,
                source_reported_name=None,
                period_start=None,
                period_end=date(2024, 12, 31),
                financial_year=None,
                period_nature=PeriodNature.QUARTERLY,
                cumulative_nature=CumulativeNature.NON_CUMULATIVE,
                statement_scope=StatementScope.CONSOLIDATED,
                audit_status=FilingAuditStatus.AUDITED,
                publication_precision=PublicationPrecision.UNKNOWN,
                source_published_at=None,
                source_published_date=date(2025, 1, 16),
            )

        # UNKNOWN with both None -> Valid!
        f_valid_unk = FundamentalFiling(
            filing_id="F-UNK-OK",
            issuer_id=None,
            source="NSE",
            source_record_id="UNK3",
            source_reported_symbol=None,
            source_reported_isin=None,
            source_reported_name=None,
            period_start=None,
            period_end=date(2024, 12, 31),
            financial_year=None,
            period_nature=PeriodNature.QUARTERLY,
            cumulative_nature=CumulativeNature.NON_CUMULATIVE,
            statement_scope=StatementScope.CONSOLIDATED,
            audit_status=FilingAuditStatus.AUDITED,
            publication_precision=PublicationPrecision.UNKNOWN,
            source_published_at=None,
            source_published_date=None,
        )
        assert f_valid_unk.publication_precision == PublicationPrecision.UNKNOWN
        assert f_valid_unk.source_published_at is None
        assert f_valid_unk.source_published_date is None

    def test_domain_model_default_timestamps_are_timezone_aware(self):
        # IssuerRecord defaults
        issuer = IssuerRecord(issuer_id="ISS-DEF", legal_name="Default Corp")
        assert issuer.created_at.tzinfo is not None
        assert issuer.updated_at.tzinfo is not None

        # SecurityIdentity defaults
        sec = SecurityIdentity(
            security_id="SEC-DEF",
            issuer_id="ISS-DEF",
            exchange="NSE",
            symbol="DEF",
            isin="INE000000000",
        )
        assert sec.created_at.tzinfo is not None

        # FundamentalFiling defaults
        filing = FundamentalFiling(
            filing_id="FIL-DEF",
            issuer_id="ISS-DEF",
            source="NSE",
            source_record_id="DEF-1",
            source_reported_symbol="DEF",
            source_reported_isin="INE000000000",
            source_reported_name="Default Corp",
            period_start=None,
            period_end=date(2024, 12, 31),
            financial_year=None,
            period_nature=PeriodNature.QUARTERLY,
            cumulative_nature=CumulativeNature.NON_CUMULATIVE,
            statement_scope=StatementScope.CONSOLIDATED,
            audit_status=FilingAuditStatus.AUDITED,
            publication_precision=PublicationPrecision.UNKNOWN,
            source_published_at=None,
            source_published_date=None,
        )
        assert filing.ingested_at.tzinfo is not None

        # FilingDocument.create defaults
        doc = FilingDocument.create(
            document_id="DOC-DEF",
            filing_id="FIL-DEF",
            source_url="https://example.com/doc",
            raw_bytes=b"<data/>",
        )
        assert doc.retrieved_at.tzinfo is not None


# ==============================================================================
# G. SCHEMA 20 -> 21 MIGRATION
# ==============================================================================


class TestSchema20To21Migration:
    def test_schema_20_database_migrates_cleanly_to_21(self, tmp_path: Path):
        db_path = tmp_path / "legacy_v20.db"
        conn = sqlite3.connect(db_path)

        # Create schema 20 tables manually (simulating pre-existing v20 database)
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version(version) VALUES (20)")
        conn.execute("""
            CREATE TABLE instruments (
                instrument_id TEXT PRIMARY KEY,
                isin TEXT,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                series TEXT NOT NULL,
                name TEXT,
                sector TEXT,
                lot_size INTEGER NOT NULL,
                tick_size TEXT NOT NULL,
                status TEXT NOT NULL,
                listed_date TEXT,
                delisted_date TEXT
            )
        """)
        # Insert pre-existing instrument
        conn.execute(
            "INSERT INTO instruments(instrument_id, symbol, exchange, series, lot_size, tick_size, status) "
            "VALUES ('NSE:INFY', 'INFY', 'NSE', 'EQ', 1, '0.05', 'ACTIVE')"
        )
        conn.commit()
        conn.close()

        # Open with new SqliteRepository and initialize
        repo = SqliteRepository(db_path)
        repo.initialize()

        # 1. Verify schema_version upgraded to 22
        ver = repo._conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert ver == 22
        assert repo.verify_integrity().schema_version_ok

        # 2. Verify pre-existing data preserved
        inst = repo.get_instrument("NSE:INFY")
        assert inst is not None and inst.symbol == "INFY"

        # 3. Verify all 7 fundamentals tables exist
        table_names = {
            r[0] for r in repo._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "issuers" in table_names
        assert "security_identities" in table_names
        assert "fundamental_filings" in table_names
        assert "filing_documents" in table_names
        assert "raw_financial_facts" in table_names
        assert "canonical_financial_facts" in table_names
        assert "canonical_fact_raw_sources" in table_names

        # 4. Verify functionality on upgraded DB
        issuer = _make_issuer("ISS-MIGRATE", "Migrated Company Ltd")
        assert repo.upsert_issuer(issuer) is True
        assert repo.get_issuer("ISS-MIGRATE") is not None

        # 5. Idempotent re-initialization
        repo.initialize()
        ver_again = repo._conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert ver_again == 22
        repo.close()

    def test_migration_from_schema_21_to_22(self, tmp_path: Path):
        """Simulate an existing Schema 21 database upgrading to Schema 22."""
        db_path = tmp_path / "schema21.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version(version) VALUES (21)")
        conn.execute("""
            CREATE TABLE issuers (
                issuer_id TEXT PRIMARY KEY,
                legal_name TEXT NOT NULL,
                cin TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO issuers(issuer_id, legal_name, status, created_at, updated_at) "
            "VALUES ('ISS-21', 'Pre-existing 21 Ltd', 'ACTIVE', "
            "'2026-09-15T00:00:00+00:00', '2026-09-15T00:00:00+00:00')"
        )
        conn.commit()
        conn.close()

        repo = SqliteRepository(db_path)
        repo.initialize()

        ver = repo._conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert ver == 22
        assert repo.get_issuer("ISS-21") is not None

        table_names = {
            r[0] for r in repo._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "raw_financial_facts" in table_names
        assert "canonical_financial_facts" in table_names
        assert "canonical_fact_raw_sources" in table_names
        repo.close()

    def test_fresh_database_initializes_at_version_22(self, tmp_path: Path):
        db_path = tmp_path / "fresh.db"
        repo = SqliteRepository(db_path)
        repo.initialize()

        ver = repo._conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert ver == 22
        assert SCHEMA_VERSION == 22
        assert repo.verify_integrity().schema_version_ok
        repo.close()


class TestRawAndCanonicalFactsPersistence:
    """SI-F2B: Production raw and canonical fact repository persistence tests."""

    def test_save_and_get_raw_financial_facts_atomic_and_idempotent(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-F2B", "F2B Test Ltd")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-F2B", issuer_id="ISS-F2B", source_record_id="REC-F2B")
        repo.save_fundamental_filing(filing)
        doc = _make_doc("DOC-F2B", filing_id="FILING-F2B")
        repo.save_filing_document(doc)

        f1 = RawFinancialFact(
            raw_fact_id="DOC-F2B:1",
            filing_id="FILING-F2B",
            document_id="DOC-F2B",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="in-bse-fin:RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            unit_class=FinancialUnitClass.CURRENCY,
            raw_value="100000000.00",
            numeric_value=Decimal("100000000.00"),
        )
        f2 = RawFinancialFact(
            raw_fact_id="DOC-F2B:2",
            filing_id="FILING-F2B",
            document_id="DOC-F2B",
            source_occurrence_ordinal=2,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="ProfitLossForPeriod",
            raw_qname="in-bse-fin:ProfitLossForPeriod",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            unit_class=FinancialUnitClass.CURRENCY,
            raw_value="20000000.00",
            numeric_value=Decimal("20000000.00"),
        )

        assert repo.save_raw_financial_facts([f1, f2]) == 2
        # Idempotent re-run
        assert repo.save_raw_financial_facts([f1, f2]) == 0

        stored = repo.get_raw_financial_facts("DOC-F2B")
        assert len(stored) == 2
        assert stored[0].raw_fact_id == "DOC-F2B:1"
        assert stored[0].numeric_value == Decimal("100000000.00")
        assert stored[1].raw_fact_id == "DOC-F2B:2"
        assert stored[1].numeric_value == Decimal("20000000.00")

    def test_save_raw_facts_rejects_conflicting_ordinal(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-F2B-CONF", "F2B Conflict Ltd")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-CONF", issuer_id="ISS-F2B-CONF", source_record_id="REC-CONF")
        repo.save_fundamental_filing(filing)
        doc = _make_doc("DOC-CONF", filing_id="FILING-CONF")
        repo.save_filing_document(doc)

        f1 = RawFinancialFact(
            raw_fact_id="DOC-CONF:1",
            filing_id="FILING-CONF",
            document_id="DOC-CONF",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="in-bse-fin:RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="100.00",
            numeric_value=Decimal("100.00"),
        )
        repo.save_raw_financial_facts([f1])

        # Attempt to insert different fact for same document and ordinal
        f_conflict = RawFinancialFact(
            raw_fact_id="DOC-CONF:1",
            filing_id="FILING-CONF",
            document_id="DOC-CONF",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="in-bse-fin:RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="200.00",  # Changed value!
            numeric_value=Decimal("200.00"),
        )
        with pytest.raises(RepositoryError, match="Conflicting raw fact"):
            repo.save_raw_financial_facts([f_conflict])

    def test_save_raw_facts_rejects_conflicting_namespace_uri(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-F2B-NS", "F2B NS Ltd")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-NS", issuer_id="ISS-F2B-NS", source_record_id="REC-NS")
        repo.save_fundamental_filing(filing)
        doc = _make_doc("DOC-NS", filing_id="FILING-NS")
        repo.save_filing_document(doc)

        f1 = RawFinancialFact(
            raw_fact_id="DOC-NS:1",
            filing_id="FILING-NS",
            document_id="DOC-NS",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="{http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin}RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="100.00",
            numeric_value=Decimal("100.00"),
        )
        assert repo.save_raw_financial_facts([f1]) == 1

        f_conf = replace(f1, namespace_uri="http://www.mca.gov.in/xbrl/ind-as/2017-03-31/ind-as-in-fin")
        with pytest.raises(RepositoryError, match="Conflicting raw fact payload"):
            repo.save_raw_financial_facts([f_conf])

    def test_save_raw_facts_rejects_conflicting_precision(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-F2B-PREC", "F2B Prec Ltd")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-PREC", issuer_id="ISS-F2B-PREC", source_record_id="REC-PREC")
        repo.save_fundamental_filing(filing)
        doc = _make_doc("DOC-PREC", filing_id="FILING-PREC")
        repo.save_filing_document(doc)

        f1 = RawFinancialFact(
            raw_fact_id="DOC-PREC:1",
            filing_id="FILING-PREC",
            document_id="DOC-PREC",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="{http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin}RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="100.00",
            numeric_value=Decimal("100.00"),
            precision="2",
        )
        assert repo.save_raw_financial_facts([f1]) == 1

        f_conf = replace(f1, precision="4")
        with pytest.raises(RepositoryError, match="Conflicting raw fact payload"):
            repo.save_raw_financial_facts([f_conf])

    def test_save_raw_facts_rejects_conflicting_is_nil(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-F2B-NIL", "F2B Nil Ltd")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-NIL", issuer_id="ISS-F2B-NIL", source_record_id="REC-NIL")
        repo.save_fundamental_filing(filing)
        doc = _make_doc("DOC-NIL", filing_id="FILING-NIL")
        repo.save_filing_document(doc)

        f1 = RawFinancialFact(
            raw_fact_id="DOC-NIL:1",
            filing_id="FILING-NIL",
            document_id="DOC-NIL",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="{http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin}RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="100.00",
            numeric_value=Decimal("100.00"),
            is_nil=False,
        )
        assert repo.save_raw_financial_facts([f1]) == 1

        f_conf = replace(f1, is_nil=True, numeric_value=None, raw_value="")
        with pytest.raises(RepositoryError, match="Conflicting raw fact payload"):
            repo.save_raw_financial_facts([f_conf])

    def test_save_raw_facts_rejects_conflicting_raw_unit_identity(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-F2B-UID", "F2B UnitId Ltd")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-UID", issuer_id="ISS-F2B-UID", source_record_id="REC-UID")
        repo.save_fundamental_filing(filing)
        doc = _make_doc("DOC-UID", filing_id="FILING-UID")
        repo.save_filing_document(doc)

        f1 = RawFinancialFact(
            raw_fact_id="DOC-UID:1",
            filing_id="FILING-UID",
            document_id="DOC-UID",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="{http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin}RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="100.00",
            numeric_value=Decimal("100.00"),
            raw_unit_identity="iso4217:INR",
        )
        assert repo.save_raw_financial_facts([f1]) == 1

        f_conf = replace(f1, raw_unit_identity="iso4217:USD")
        with pytest.raises(RepositoryError, match="Conflicting raw fact payload"):
            repo.save_raw_financial_facts([f_conf])

    def test_save_raw_facts_rejects_conflicting_dimensions_payload(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-F2B-DIM", "F2B Dim Ltd")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-DIM", issuer_id="ISS-F2B-DIM", source_record_id="REC-DIM")
        repo.save_fundamental_filing(filing)
        doc = _make_doc("DOC-DIM", filing_id="FILING-DIM")
        repo.save_filing_document(doc)

        f1 = RawFinancialFact(
            raw_fact_id="DOC-DIM:1",
            filing_id="FILING-DIM",
            document_id="DOC-DIM",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="{http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin}RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="100.00",
            numeric_value=Decimal("100.00"),
            is_dimensioned=False,
            dimensions=(),
            dimension_signature="",
        )
        assert repo.save_raw_financial_facts([f1]) == 1

        new_dims = ({"dimension": "custom:Axis", "kind": "explicit", "member": "custom:Mem"},)
        f_conf = replace(
            f1,
            is_dimensioned=True,
            dimensions=new_dims,
            dimension_signature='[{"dimension": "custom:Axis", "kind": "explicit", "member": "custom:Mem"}]',
        )
        with pytest.raises(RepositoryError, match="Conflicting raw fact payload"):
            repo.save_raw_financial_facts([f_conf])

    def test_save_canonical_source_links_rejects_conflicting_is_primary(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-LINK-CONF", "Link Conflict Ltd")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-LINK-CONF", issuer_id="ISS-LINK-CONF", source_record_id="REC-LINK-CONF")
        repo.save_fundamental_filing(filing)
        doc = _make_doc("DOC-LINK-CONF", filing_id="FILING-LINK-CONF")
        repo.save_filing_document(doc)

        f_raw = RawFinancialFact(
            raw_fact_id="DOC-LINK-CONF:1",
            filing_id="FILING-LINK-CONF",
            document_id="DOC-LINK-CONF",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="{http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin}RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="50000.00",
            numeric_value=Decimal("50000.00"),
        )
        repo.save_raw_financial_facts([f_raw])

        can_fact = CanonicalFinancialFact(
            canonical_fact_id="CAN-LINK-1",
            filing_id="FILING-LINK-CONF",
            document_id="DOC-LINK-CONF",
            canonical_concept=CanonicalFinancialConcept.REVENUE_FROM_OPERATIONS,
            statement_scope=StatementScope.CONSOLIDATED,
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            canonical_unit="INR",
            numeric_value=Decimal("50000.00"),
            mapping_version="SI_FUNDAMENTALS_MAPPING_V1",
            mapping_rule_id="MAP-V1-REV-OP",
            duplicate_classification=DuplicateClassification.UNIQUE,
            primary_raw_fact_id="DOC-LINK-CONF:1",
        )
        assert repo.save_canonical_financial_facts([can_fact], [("CAN-LINK-1", "DOC-LINK-CONF:1", True)]) == 1

        # Re-saving identical link is idempotent no-op
        assert repo.save_canonical_financial_facts([can_fact], [("CAN-LINK-1", "DOC-LINK-CONF:1", True)]) == 0

        # Attempt to save contradictory is_primary meaning for same link
        with pytest.raises(RepositoryError, match="Conflicting canonical source link"):
            repo.save_canonical_financial_facts([can_fact], [("CAN-LINK-1", "DOC-LINK-CONF:1", False)])

    def test_save_and_get_canonical_financial_facts_and_links(self, repo: SqliteRepository):
        issuer = _make_issuer("ISS-CAN", "Canonical Ltd")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-CAN", issuer_id="ISS-CAN", source_record_id="REC-CAN")
        repo.save_fundamental_filing(filing)
        doc = _make_doc("DOC-CAN", filing_id="FILING-CAN")
        repo.save_filing_document(doc)

        f_raw = RawFinancialFact(
            raw_fact_id="DOC-CAN:1",
            filing_id="FILING-CAN",
            document_id="DOC-CAN",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="in-bse-fin:RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="50000.00",
            numeric_value=Decimal("50000.00"),
        )
        repo.save_raw_financial_facts([f_raw])

        can_fact = CanonicalFinancialFact(
            canonical_fact_id="CAN-1",
            filing_id="FILING-CAN",
            document_id="DOC-CAN",
            canonical_concept=CanonicalFinancialConcept.REVENUE_FROM_OPERATIONS,
            statement_scope=StatementScope.CONSOLIDATED,
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            canonical_unit="INR",
            numeric_value=Decimal("50000.00"),
            mapping_version="SI_FUNDAMENTALS_MAPPING_V1",
            mapping_rule_id="MAP-V1-REV-OP",
            duplicate_classification=DuplicateClassification.UNIQUE,
            primary_raw_fact_id="DOC-CAN:1",
        )
        links = [("CAN-1", "DOC-CAN:1", True)]

        assert repo.save_canonical_financial_facts([can_fact], links) == 1
        # Idempotent re-run
        assert repo.save_canonical_financial_facts([can_fact], links) == 0

        retrieved = repo.get_canonical_financial_facts("FILING-CAN")
        assert len(retrieved) == 1
        assert retrieved[0].canonical_concept == CanonicalFinancialConcept.REVENUE_FROM_OPERATIONS
        assert retrieved[0].numeric_value == Decimal("50000.00")

        raw_ids = repo.get_raw_source_ids_for_canonical_fact("CAN-1")
        assert raw_ids == ["DOC-CAN:1"]

    def test_multi_document_per_filing_raw_and_canonical_isolation(self, repo: SqliteRepository):
        """Two documents under the same filing can each have ordinal=1 without raw or canonical collision."""
        issuer = _make_issuer("ISS-MULTI", "Multi Doc Ltd")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-MULTI", issuer_id="ISS-MULTI", source_record_id="REC-MULTI")
        repo.save_fundamental_filing(filing)

        doc_a = _make_doc("DOC-MULTI-A", filing_id="FILING-MULTI", source_url="https://example.com/test_a.xml")
        doc_b = _make_doc(
            "DOC-MULTI-B",
            filing_id="FILING-MULTI",
            source_url="https://example.com/test_b.xml",
            raw_content=b"<xbrl>Test Payload B</xbrl>",
        )
        repo.save_filing_document(doc_a)
        repo.save_filing_document(doc_b)

        # Both documents have source_occurrence_ordinal = 1
        raw_a = RawFinancialFact(
            raw_fact_id="DOC-MULTI-A:1",
            filing_id="FILING-MULTI",
            document_id="DOC-MULTI-A",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="in-bse-fin:RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="1000.00",
            numeric_value=Decimal("1000.00"),
        )
        raw_b = RawFinancialFact(
            raw_fact_id="DOC-MULTI-B:1",
            filing_id="FILING-MULTI",
            document_id="DOC-MULTI-B",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="in-bse-fin:RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="2000.00",
            numeric_value=Decimal("2000.00"),
        )

        assert repo.save_raw_financial_facts([raw_a]) == 1
        assert repo.save_raw_financial_facts([raw_b]) == 1

        # Both documents have canonical facts for the same economic coordinates
        can_a = CanonicalFinancialFact(
            canonical_fact_id="CAN-MULTI-A",
            filing_id="FILING-MULTI",
            document_id="DOC-MULTI-A",
            canonical_concept=CanonicalFinancialConcept.REVENUE_FROM_OPERATIONS,
            statement_scope=StatementScope.CONSOLIDATED,
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            canonical_unit="INR",
            numeric_value=Decimal("1000.00"),
            mapping_version="SI_FUNDAMENTALS_MAPPING_V1",
            mapping_rule_id="MAP-V1-REV-OP",
            duplicate_classification=DuplicateClassification.UNIQUE,
            primary_raw_fact_id="DOC-MULTI-A:1",
        )
        can_b = CanonicalFinancialFact(
            canonical_fact_id="CAN-MULTI-B",
            filing_id="FILING-MULTI",
            document_id="DOC-MULTI-B",
            canonical_concept=CanonicalFinancialConcept.REVENUE_FROM_OPERATIONS,
            statement_scope=StatementScope.CONSOLIDATED,
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            canonical_unit="INR",
            numeric_value=Decimal("2000.00"),
            mapping_version="SI_FUNDAMENTALS_MAPPING_V1",
            mapping_rule_id="MAP-V1-REV-OP",
            duplicate_classification=DuplicateClassification.UNIQUE,
            primary_raw_fact_id="DOC-MULTI-B:1",
        )

        assert repo.save_canonical_financial_facts([can_a], [("CAN-MULTI-A", "DOC-MULTI-A:1", True)]) == 1
        assert repo.save_canonical_financial_facts([can_b], [("CAN-MULTI-B", "DOC-MULTI-B:1", True)]) == 1

        filing_facts = repo.get_canonical_financial_facts("FILING-MULTI")
        assert len(filing_facts) == 2

    def test_canonical_fact_idempotency_conflict_detection(self, repo: SqliteRepository):
        """Re-saving canonical fact with changed numeric value or unit must raise RepositoryError."""
        issuer = _make_issuer("ISS-CAN-CONF", "Canonical Conflict Ltd")
        repo.upsert_issuer(issuer)
        filing = _make_filing("FILING-CAN-CONF", issuer_id="ISS-CAN-CONF", source_record_id="REC-CAN-CONF")
        repo.save_fundamental_filing(filing)
        doc = _make_doc("DOC-CAN-CONF", filing_id="FILING-CAN-CONF")
        repo.save_filing_document(doc)

        f_raw = RawFinancialFact(
            raw_fact_id="DOC-CAN-CONF:1",
            filing_id="FILING-CAN-CONF",
            document_id="DOC-CAN-CONF",
            source_occurrence_ordinal=1,
            namespace_uri="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
            local_name="RevenueFromOperations",
            raw_qname="in-bse-fin:RevenueFromOperations",
            context_ref="OneD",
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            duration_days=92,
            raw_value="50000.00",
            numeric_value=Decimal("50000.00"),
        )
        repo.save_raw_financial_facts([f_raw])

        can_fact = CanonicalFinancialFact(
            canonical_fact_id="CAN-CONF-1",
            filing_id="FILING-CAN-CONF",
            document_id="DOC-CAN-CONF",
            canonical_concept=CanonicalFinancialConcept.REVENUE_FROM_OPERATIONS,
            statement_scope=StatementScope.CONSOLIDATED,
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            canonical_unit="INR",
            numeric_value=Decimal("50000.00"),
            mapping_version="SI_FUNDAMENTALS_MAPPING_V1",
            mapping_rule_id="MAP-V1-REV-OP",
            duplicate_classification=DuplicateClassification.UNIQUE,
            primary_raw_fact_id="DOC-CAN-CONF:1",
        )
        assert repo.save_canonical_financial_facts([can_fact], [("CAN-CONF-1", "DOC-CAN-CONF:1", True)]) == 1

        # Attempt to re-save same identity with changed numeric value
        can_conflicting = CanonicalFinancialFact(
            canonical_fact_id="CAN-CONF-1",
            filing_id="FILING-CAN-CONF",
            document_id="DOC-CAN-CONF",
            canonical_concept=CanonicalFinancialConcept.REVENUE_FROM_OPERATIONS,
            statement_scope=StatementScope.CONSOLIDATED,
            period_type=RawPeriodType.DURATION,
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            canonical_unit="INR",
            numeric_value=Decimal("99999.00"),  # Changed!
            mapping_version="SI_FUNDAMENTALS_MAPPING_V1",
            mapping_rule_id="MAP-V1-REV-OP",
            duplicate_classification=DuplicateClassification.UNIQUE,
            primary_raw_fact_id="DOC-CAN-CONF:1",
        )
        with pytest.raises(RepositoryError, match="Conflicting canonical fact payload"):
            repo.save_canonical_financial_facts([can_conflicting], [])

    def test_record_counts_includes_fundamentals_tables(self, repo: SqliteRepository):
        counts = repo.record_counts()
        assert "raw_financial_facts" in counts
        assert "canonical_financial_facts" in counts
        assert "canonical_fact_raw_sources" in counts
        assert "issuers" in counts
        assert "fundamental_filings" in counts
