"""DecisionMetadataDTO.instrument_name (owner reference-mock screenshot,
2026-07-27): a real company name from the instruments table, looked up via
an optional repo passed to DecisionsService — mirrors the same optional-
repo-alongside-primary-abstraction precedent already used by
MarketHistoryService. Tested against an isolated tmp_path SqliteRepository,
never the real production db (see test_market_history.py for why: the
`client` fixture wires the real db/athena.db, which makes value-level
assertions non-deterministic)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from athena.api.dependencies import get_decision_provider
from athena.api.v1.services.decisions_service import DecisionsService
from athena.data.store import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction
from athena.domain.market import Instrument


def _service(tmp_path: Path, repo: SqliteRepository | None) -> DecisionsService:
    return DecisionsService(
        get_decision_provider(),
        config_dir=Path("config"),
        db_path=tmp_path / "unused.db",
        backup_dir=tmp_path / "backups",
        repo=repo,
    )


def test_instrument_name_populated_from_real_repo_record(tmp_path):
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    repo.upsert_instrument(
        Instrument(
            instrument_id="NSE:DIXON", symbol="DIXON", exchange="NSE", series="EQ",
            name="Dixon Technologies (India) Ltd",
        )
    )
    dec_p = get_decision_provider()
    decision_id = "dec-instrument-name-known"
    dec_p.decisions.append(  # type: ignore[attr-defined]
        Decision(
            decision_id=decision_id, ts=datetime.now(tz=timezone.utc), run_id="run-name-1",
            cycle_id="cycle-name", instrument_id="NSE:DIXON", direction=Direction.LONG,
            decision_type=DecisionType.WATCH, explanation="name lookup test",
        )
    )

    dto = _service(tmp_path, repo).get_decision(decision_id)

    assert dto.metadata.instrument_name == "Dixon Technologies (India) Ltd"
    repo.close()


def test_instrument_name_none_when_instrument_not_in_repo(tmp_path):
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    dec_p = get_decision_provider()
    decision_id = "dec-instrument-name-unknown"
    dec_p.decisions.append(  # type: ignore[attr-defined]
        Decision(
            decision_id=decision_id, ts=datetime.now(tz=timezone.utc), run_id="run-name-2",
            cycle_id="cycle-name", instrument_id="NSE:NOSUCHSYMBOL", direction=Direction.LONG,
            decision_type=DecisionType.WATCH, explanation="unknown instrument test",
        )
    )

    dto = _service(tmp_path, repo).get_decision(decision_id)

    assert dto.metadata.instrument_name is None
    repo.close()


def test_instrument_name_none_when_no_repo_wired():
    """No repo means no lookup at all — never a fabricated fallback name."""
    dec_p = get_decision_provider()
    decision_id = "dec-instrument-name-no-repo"
    dec_p.decisions.append(  # type: ignore[attr-defined]
        Decision(
            decision_id=decision_id, ts=datetime.now(tz=timezone.utc), run_id="run-name-3",
            cycle_id="cycle-name", instrument_id="NSE:DIXON", direction=Direction.LONG,
            decision_type=DecisionType.WATCH, explanation="no repo wired test",
        )
    )

    dto = DecisionsService(get_decision_provider(), repo=None).get_decision(decision_id)

    assert dto.metadata.instrument_name is None
