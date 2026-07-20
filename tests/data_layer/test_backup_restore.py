"""Backup & Restore tests (M1.6): backup, restore, recovery validation,
schema compatibility, and failure modes. Isolated temp repositories throughout."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.store import SqliteRepository, create_backup, restore_backup
from athena.data.store.backup import _META_SUFFIX
from athena.data.validation.quarantine import QuarantineRecord
from athena.data.validation.reports import (
    Severity,
    ValidationReport,
    ValidationResult,
    ValidationType,
)
from athena.domain.enums import Timeframe
from athena.domain.market import (
    Candle,
    CorporateAction,
    Instrument,
    MarketSnapshot,
    Quote,
)
from athena.errors import RepositoryError

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 1, 18, 0, tzinfo=IST)
INST = "INE-BR-0001"


def _populate(repo: SqliteRepository) -> None:
    repo.upsert_instrument(Instrument(instrument_id=INST, symbol="AAA", exchange="NSE",
                                      series="EQ", isin="INE000A01AAA", lot_size=1,
                                      tick_size=Decimal("0.05"), status="ACTIVE",
                                      listed_date=date(2020, 1, 1)))
    repo.add_candles([
        Candle(instrument_id=INST, timeframe=Timeframe.D1,
               ts_open=datetime(2026, 2, d, 9, 15, tzinfo=IST),
               open=Decimal("100"), high=Decimal("101"), low=Decimal("99"),
               close=Decimal("100.5"), volume=1000, source="test")
        for d in (2, 3, 4)
    ])
    repo.add_quotes([Quote(instrument_id=INST, ts=datetime(2026, 2, 4, 15, 30, tzinfo=IST),
                           last_price=Decimal("100.5"), volume=5000, source="test")])
    repo.add_snapshot(MarketSnapshot(ts=datetime(2026, 2, 4, 15, 30, tzinfo=IST),
                                     indices={"NIFTY50": Decimal("25000")}))
    repo.add_corporate_action(CorporateAction(action_id="s1", instrument_id=INST,
                                              action_type="SPLIT", ex_date=date(2026, 2, 4),
                                              details={"from_shares": "1", "to_shares": "5"}))
    report = ValidationReport(validation_type=ValidationType.OHLC, result=ValidationResult.FAILED,
                             severity=Severity.CRITICAL, explanation="bad", ts=AS_OF)
    repo.save_quarantine(QuarantineRecord(dataset_id="Q1", reason="OHLC: bad",
                                          failed_reports=(report,), quarantined_ts=AS_OF))


@pytest.fixture()
def source_repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "source.db")
    r.initialize()
    _populate(r)
    yield r
    r.close()


class TestBackup:
    def test_successful_backup_writes_file_and_metadata(self, source_repo, tmp_path):
        dest = tmp_path / "backup" / "athena.bak"
        result = create_backup(source_repo, dest, as_of=AS_OF)
        assert dest.exists()
        assert dest.with_name(dest.name + _META_SUFFIX).exists()
        assert result.integrity_ok
        assert result.record_counts["candles"] == 3

    def test_backup_refuses_overwrite_by_default(self, source_repo, tmp_path):
        dest = tmp_path / "athena.bak"
        create_backup(source_repo, dest, as_of=AS_OF)
        with pytest.raises(RepositoryError, match=r"already exists"):
            create_backup(source_repo, dest, as_of=AS_OF)

    def test_backup_overwrite_when_explicit(self, source_repo, tmp_path):
        dest = tmp_path / "athena.bak"
        create_backup(source_repo, dest, as_of=AS_OF)
        result = create_backup(source_repo, dest, as_of=AS_OF, overwrite=True)
        assert result.integrity_ok

    def test_backup_to_readonly_destination_fails(self, source_repo, tmp_path):
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        try:
            with pytest.raises(RepositoryError):
                create_backup(source_repo, ro / "athena.bak", as_of=AS_OF)
        finally:
            ro.chmod(0o700)


class TestRestore:
    def test_restore_recovers_all_entities(self, source_repo, tmp_path):
        dest = tmp_path / "athena.bak"
        create_backup(source_repo, dest, as_of=AS_OF)

        target = tmp_path / "restored.db"
        result = restore_backup(dest, target, as_of=AS_OF)
        assert result.ok
        assert result.integrity_ok and result.foreign_keys_ok
        assert result.schema_version_ok and result.counts_match

        restored = SqliteRepository(target)
        try:
            assert restored.get_instrument(INST) is not None
            assert len(restored.get_candles(INST, Timeframe.D1,
                                            datetime(2026, 2, 1, tzinfo=IST),
                                            datetime(2026, 2, 28, tzinfo=IST))) == 3
            assert len(restored.get_quotes(INST)) == 1
            assert restored.get_latest_snapshot() is not None
            assert len(restored.get_corporate_actions(INST)) == 1
            assert restored.get_quarantine("Q1") is not None
        finally:
            restored.close()

    def test_restored_repo_identical_to_original(self, source_repo, tmp_path):
        dest = tmp_path / "athena.bak"
        create_backup(source_repo, dest, as_of=AS_OF)
        target = tmp_path / "restored.db"
        restore_backup(dest, target, as_of=AS_OF)

        restored = SqliteRepository(target)
        try:
            assert restored.record_counts() == source_repo.record_counts()
            assert restored.get_instrument(INST) == source_repo.get_instrument(INST)
        finally:
            restored.close()

    def test_deterministic_backup_restore_cycles(self, source_repo, tmp_path):
        counts = []
        for i in range(2):
            dest = tmp_path / f"b{i}.bak"
            create_backup(source_repo, dest, as_of=AS_OF)
            target = tmp_path / f"r{i}.db"
            counts.append(restore_backup(dest, target, as_of=AS_OF).record_counts)
        assert counts[0] == counts[1]


class TestFailureModes:
    def test_missing_backup(self, tmp_path):
        with pytest.raises(RepositoryError, match=r"backup not found"):
            restore_backup(tmp_path / "nope.bak", tmp_path / "t.db", as_of=AS_OF)

    def test_corrupted_backup_detected_and_target_untouched(self, source_repo, tmp_path):
        good_target = tmp_path / "live.db"
        create_backup(source_repo, tmp_path / "good.bak", as_of=AS_OF)
        restore_backup(tmp_path / "good.bak", good_target, as_of=AS_OF)

        corrupt = tmp_path / "corrupt.bak"
        corrupt.write_bytes(b"not a database" * 20)
        with pytest.raises(RepositoryError, match=r"corrupt"):
            restore_backup(corrupt, good_target, as_of=AS_OF)
        # target remains a valid repository
        r = SqliteRepository(good_target)
        try:
            assert r.verify_integrity().ok
        finally:
            r.close()

    def test_incompatible_schema_version_refused(self, source_repo, tmp_path):
        dest = tmp_path / "athena.bak"
        create_backup(source_repo, dest, as_of=AS_OF)
        # Tamper the backup's schema version.
        bad = SqliteRepository(dest)
        try:
            with bad.transaction() as cur:
                cur.execute("UPDATE schema_version SET version = 999")
        finally:
            bad.close()

        target = tmp_path / "t.db"
        with pytest.raises(RepositoryError, match=r"incompatible schema version"):
            restore_backup(dest, target, as_of=AS_OF)
        assert not target.exists()  # target never created on refusal

    def test_backup_of_unhealthy_repo_refused(self, tmp_path):
        corrupt = tmp_path / "corrupt.db"
        corrupt.write_bytes(b"garbage" * 50)
        with pytest.raises(RepositoryError):
            repo = SqliteRepository(corrupt)
            create_backup(repo, tmp_path / "out.bak", as_of=AS_OF)
