"""EM-1r2 authoritative corporate-action and survivor-cohort contracts."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from athena.data.providers.nse_corporate_actions_provider import parse_official_nse_payload
from athena.domain.market import Instrument
from athena.explosive_move.corporate_action_coverage import (
    OFFICIAL_NSE_SOURCE,
    SURVIVOR_COHORT_LIMITATION,
    CorporateActionCoverageManifest,
    CorporateActionExclusionReason,
    OfficialCorporateActionRow,
    RetrievalSlice,
    build_survivor_cohort,
    normalize_official_actions,
    write_immutable_manifest,
)

SOURCE_URL = "https://www.nseindia.com/api/corporates-corporateActions"
PAYLOAD_HASH = "a" * 64


def _instrument(
    instrument_id: str,
    symbol: str,
    series: str = "EQ",
    isin: str | None = None,
) -> Instrument:
    return Instrument(
        instrument_id=instrument_id,
        symbol=symbol,
        exchange="NSE",
        series=series,
        isin=isin,
    )


def _cohort(*instrument_ids: str):
    return build_survivor_cohort(
        universe_name="athena_core",
        resolution_date=date(2026, 8, 21),
        instrument_ids=tuple(reversed(instrument_ids)),
        group_effective_dates=(("athena_core", date(2026, 8, 21)),),
    )


def _row(
    record_id: str,
    symbol: str,
    subject: str,
    *,
    isin: str | None = None,
) -> OfficialCorporateActionRow:
    return OfficialCorporateActionRow(
        source_record_id=record_id,
        symbol=symbol,
        series="EQ",
        ex_date=date(2024, 6, 3),
        subject=subject,
        source_url=SOURCE_URL,
        payload_sha256=PAYLOAD_HASH,
        isin=isin,
    )


def _slice(*, complete: bool = True) -> RetrievalSlice:
    return RetrievalSlice(
        requested_start=date(2024, 1, 1),
        requested_end=date(2024, 12, 31),
        retrieved_at=datetime(2026, 8, 21, 6, tzinfo=UTC),
        source_url=SOURCE_URL,
        payload_sha256=PAYLOAD_HASH,
        raw_artifact=f"raw/{PAYLOAD_HASH}.json",
        record_count=2,
        complete=complete,
        completeness_basis="official inclusive date-window response" if complete else "",
    )


def test_survivor_cohort_is_sorted_deterministic_and_visibly_limited() -> None:
    first = _cohort("nse:BBB", "nse:AAA")
    second = _cohort("nse:AAA", "nse:BBB")

    assert first.instrument_ids == ("nse:AAA", "nse:BBB")
    assert first.cohort_id == second.cohort_id
    assert first.limitation == SURVIVOR_COHORT_LIMITATION
    assert "not point-in-time" in first.limitation


def test_official_row_rejects_kite_as_corporate_action_authority() -> None:
    with pytest.raises(ValueError, match="official NSE"):
        OfficialCorporateActionRow(
            source_record_id="1",
            symbol="AAA",
            series="EQ",
            ex_date=date(2024, 1, 1),
            subject="Bonus 1:1",
            source_url="https://kite.trade/instruments",
            payload_sha256=PAYLOAD_HASH,
        )


def test_parser_preserves_payload_identity_and_excludes_malformed_rows() -> None:
    payload = json.dumps(
        {
            "data": [
                {
                    "id": "nse-1",
                    "symbol": "aaa",
                    "series": "eq",
                    "exDate": "03-Jun-2024",
                    "subject": "Bonus 1:1",
                    "isin": "INE000A01001",
                },
                {
                    "id": "nse-2",
                    "symbol": "BBB",
                    "series": "EQ",
                    "exDate": "not-a-date",
                    "subject": "Split 10 to 2",
                },
            ]
        }
    ).encode()

    parsed = parse_official_nse_payload(
        payload,
        source_url=SOURCE_URL,
        content_type="application/json",
    )

    assert len(parsed.rows) == 1
    assert parsed.rows[0].symbol == "AAA"
    assert parsed.rows[0].payload_sha256 == parsed.payload_sha256
    assert parsed.rows[0].isin == "INE000A01001"
    assert [item.reason for item in parsed.exclusions] == [
        CorporateActionExclusionReason.MALFORMED_SOURCE_ROW
    ]


def test_normalization_resolves_supported_actions_and_fails_closed() -> None:
    cohort = _cohort("nse:AAA", "nse:DUP-1", "nse:DUP-2")
    instruments = (
        _instrument("nse:AAA", "AAA"),
        _instrument("nse:DUP-1", "DUP"),
        _instrument("nse:DUP-2", "DUP"),
        _instrument("nse:OUT", "OUT"),
    )
    rows = (
        _row("1", "AAA", "Sub-division from Rs 10 to Rs 2"),
        _row("2", "AAA", "Scheme of amalgamation"),
        _row("3", "OUT", "Bonus 1:1"),
        _row("4", "DUP", "Bonus 1:1"),
        _row("5", "AAA", "Board meeting update"),
    )

    actions, exclusions = normalize_official_actions(
        rows,
        instruments=instruments,
        cohort=cohort,
    )

    assert [(item.action_type, item.instrument_id) for item in actions] == [
        ("SPLIT", "nse:AAA"),
        ("MERGER", "nse:AAA"),
    ]
    assert actions[0].details["from_shares"] == 1
    assert actions[0].details["to_shares"] == 5
    assert actions[0].details["population_basis"] == "SURVIVOR_COHORT"
    assert {item.reason for item in exclusions} == {
        CorporateActionExclusionReason.SYMBOL_OUTSIDE_COHORT,
        CorporateActionExclusionReason.INSTRUMENT_RESOLUTION_AMBIGUOUS,
        CorporateActionExclusionReason.ACTION_CLASSIFICATION_AMBIGUOUS,
    }


def test_incomplete_coverage_is_persisted_but_never_authoritative(tmp_path: Path) -> None:
    manifest = CorporateActionCoverageManifest(
        study_start=date(2024, 1, 1),
        study_end=date(2024, 12, 31),
        cohort=_cohort("nse:AAA"),
        retrieval_slices=(_slice(complete=False),),
        actions=(),
        exclusions=(),
    )

    first = write_immutable_manifest(tmp_path, manifest)
    second = write_immutable_manifest(tmp_path, manifest)

    assert manifest.authority == OFFICIAL_NSE_SOURCE
    assert manifest.coverage_complete is False
    assert manifest.authoritative_for_research is False
    assert first == second
    assert first.name == f"{manifest.manifest_id}.json"


def test_gap_free_complete_coverage_is_authoritative_and_replay_stable() -> None:
    manifest = CorporateActionCoverageManifest(
        study_start=date(2024, 1, 1),
        study_end=date(2024, 12, 31),
        cohort=_cohort("nse:AAA"),
        retrieval_slices=(_slice(),),
        actions=(),
        exclusions=(),
    )

    replay = CorporateActionCoverageManifest(**{
        "study_start": manifest.study_start,
        "study_end": manifest.study_end,
        "cohort": manifest.cohort,
        "retrieval_slices": manifest.retrieval_slices,
        "actions": manifest.actions,
        "exclusions": manifest.exclusions,
    })

    assert manifest.coverage_complete is True
    assert manifest.authoritative_for_research is True
    assert replay.manifest_id == manifest.manifest_id
    assert replay.replay_id == manifest.replay_id


def test_normalization_prefers_official_isin_over_changed_symbol() -> None:
    cohort = _cohort("nse:AAA")
    instruments = (_instrument("nse:AAA", "NEWNAME", isin="INE000A01001"),)

    actions, exclusions = normalize_official_actions(
        (_row("1", "OLDNAME", "Bonus 1:1", isin="INE000A01001"),),
        instruments=instruments,
        cohort=cohort,
    )

    assert exclusions == ()
    assert actions[0].instrument_id == "nse:AAA"
    assert actions[0].details["resolution_method"] == "ISIN"


def test_unmatched_official_isin_never_falls_back_to_symbol() -> None:
    cohort = _cohort("nse:AAA")
    instruments = (_instrument("nse:AAA", "AAA", isin="INE000A01001"),)

    actions, exclusions = normalize_official_actions(
        (_row("1", "AAA", "Bonus 1:1", isin="INE999A01001"),),
        instruments=instruments,
        cohort=cohort,
    )

    assert actions == ()
    assert exclusions[0].reason is CorporateActionExclusionReason.INSTRUMENT_IDENTITY_CONFLICT


def test_official_isin_uses_symbol_series_only_when_canonical_isin_is_absent() -> None:
    cohort = _cohort("nse:AAA")
    instruments = (_instrument("nse:AAA", "AAA", isin=None),)

    actions, exclusions = normalize_official_actions(
        (_row("1", "AAA", "Bonus 1:1", isin="INE000A01001"),),
        instruments=instruments,
        cohort=cohort,
    )

    assert exclusions == ()
    assert actions[0].instrument_id == "nse:AAA"
    assert (
        actions[0].details["resolution_method"]
        == "SYMBOL_SERIES_CANONICAL_ISIN_UNAVAILABLE"
    )


def test_official_isin_does_not_resolve_an_ambiguous_isin_absent_symbol() -> None:
    cohort = _cohort("nse:AAA-1", "nse:AAA-2")
    instruments = (
        _instrument("nse:AAA-1", "AAA", isin=None),
        _instrument("nse:AAA-2", "AAA", isin=None),
    )

    actions, exclusions = normalize_official_actions(
        (_row("1", "AAA", "Bonus 1:1", isin="INE000A01001"),),
        instruments=instruments,
        cohort=cohort,
    )

    assert actions == ()
    assert exclusions[0].reason is CorporateActionExclusionReason.INSTRUMENT_RESOLUTION_AMBIGUOUS
