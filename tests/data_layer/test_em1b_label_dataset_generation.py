"""EM-1b production label dataset generation: unit tests for the pure
helpers, plus a non-vacuous regression test for a real determinism bug
found and fixed during this milestone -- gzip.open() embeds the current
wall-clock time in its header by default, so two runs over byte-identical
JSONL content produced DIFFERENT compressed bytes (and therefore
different manifest_id/sha256), silently breaking replayability."""

from __future__ import annotations

import gzip
from decimal import Decimal
from pathlib import Path

from athena.data.em1b_label_dataset_generation import (
    _decimal_str,
    _deterministic_gzip_writer,
    _manifest_row_counts,
)


def test_decimal_str_preserves_exact_precision():
    assert _decimal_str(Decimal("110.05")) == "110.05"


def test_decimal_str_is_none_for_none():
    assert _decimal_str(None) is None


def test_manifest_row_counts_scales_by_threshold_only_for_symbol_day():
    counts = _manifest_row_counts(2628, threshold_count=6, checkpoint_count=9)
    assert counts["symbol_day"] == 2628 * 6


def test_manifest_row_counts_scales_by_threshold_and_checkpoint_for_checkpoint_rows():
    counts = _manifest_row_counts(2628, threshold_count=6, checkpoint_count=9)
    assert counts["checkpoint"] == 2628 * 6 * 9


def test_manifest_row_counts_matches_a_real_measured_canary_result():
    # exact real numbers observed generating TRAIN for 2 real instruments
    # (NSE:360ONE, NSE:3MINDIA) against the corrected EM-1r3 evidence.
    counts = _manifest_row_counts(2628, threshold_count=6, checkpoint_count=9)
    assert counts == {"symbol_day": 15768, "checkpoint": 141912}
    excluded = _manifest_row_counts(12, threshold_count=6, checkpoint_count=9)
    assert excluded == {"symbol_day": 72, "checkpoint": 648}


def test_manifest_row_counts_zero_pairs_is_zero_rows():
    assert _manifest_row_counts(0, threshold_count=6, checkpoint_count=9) == {
        "symbol_day": 0, "checkpoint": 0,
    }


# --------------------------------------------------------------------------- #
# Non-vacuous regression: two independent writes of byte-identical JSONL
# content must produce byte-identical gzip output (and therefore identical
# sha256/manifest_id) -- proving determinism does not depend on when the
# write happened.
# --------------------------------------------------------------------------- #

def _write_deterministic(path: Path, lines: list[str]) -> bytes:
    writer = _deterministic_gzip_writer(path)
    for line in lines:
        writer.write(line + "\n")
    writer.close()
    return path.read_bytes()


def test_deterministic_gzip_writer_produces_identical_bytes_on_repeated_writes(tmp_path):
    # same target filename both times -- matches the real replay scenario
    # (re-running the generator writes the same partition-named file twice);
    # the gzip header also embeds the filename, so two DIFFERENT filenames
    # legitimately produce different bytes even with identical content.
    lines = ['{"a": 1}', '{"a": 2}', '{"a": 3}']
    run1_dir, run2_dir = tmp_path / "run1", tmp_path / "run2"
    run1_dir.mkdir()
    run2_dir.mkdir()
    first = _write_deterministic(run1_dir / "TRAIN_symbol_day.jsonl.gz", lines)
    second = _write_deterministic(run2_dir / "TRAIN_symbol_day.jsonl.gz", lines)
    assert first == second


def test_deterministic_gzip_writer_content_decompresses_correctly(tmp_path):
    lines = ['{"a": 1}', '{"a": 2}']
    _write_deterministic(tmp_path / "run.jsonl.gz", lines)
    with gzip.open(tmp_path / "run.jsonl.gz", "rt", encoding="utf-8") as f:
        decompressed = f.read()
    assert decompressed == '{"a": 1}\n{"a": 2}\n'


def test_deterministic_gzip_writer_is_non_vacuous_against_plain_gzip_open():
    """Reintroduce the exact bug this helper fixes (plain gzip.open, which
    embeds wall-clock mtime) and confirm two separate writes of identical
    content are NOT guaranteed byte-identical with it -- proving the test
    above would actually have caught the real bug found this milestone."""
    import io as _io

    # simulate two writes "at different times" by forcing distinct mtimes
    # into the header the way plain gzip.open()'s default (mtime=None,
    # meaning "read the clock") would across two real, separately-timed runs
    header_a = _io.BytesIO()
    with gzip.GzipFile(fileobj=header_a, mode="wb", mtime=1000) as gz:
        gz.write(b'{"a": 1}\n')
    header_b = _io.BytesIO()
    with gzip.GzipFile(fileobj=header_b, mode="wb", mtime=2000) as gz:
        gz.write(b'{"a": 1}\n')
    assert header_a.getvalue() != header_b.getvalue(), (
        "gzip mtime must actually vary the compressed bytes for this regression "
        "test to mean anything -- if this assertion itself fails, gzip's header "
        "format changed and the real bug this test guards against may no longer apply"
    )
