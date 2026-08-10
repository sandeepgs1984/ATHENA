"""SqlitePipelineRunProvider.get_runs() correctness (owner-reported,
2026-08-10): filtering/sorting/pagination were restructured to run on the
cheap RunRecord fields before fetching/parsing each run's (potentially
multi-MB) detail_json, instead of after building every result — this proves
that restructuring didn't change the actual output, only when detail_json
gets touched."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from athena.api.v1.dtos import PaginationParams, PipelineRunFilterParams, QuerySpecification, SortParams
from athena.api.v1.providers.sqlite_providers import SqlitePipelineRunProvider
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import RunStatus, RunTrigger
from athena.domain.run import RunRecord

BASE = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)


def _run(run_id: str, *, minutes: int, status: RunStatus) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        cycle_id=f"cycle-{run_id}",
        trigger=RunTrigger.REFRESH,
        started_ts=BASE + timedelta(minutes=minutes),
        status=status,
        software_version="1.0.0",
        blueprint_version="1.0.0",
        strategy_profile="default",
        strategy_profile_version="1",
        indicator_versions={},
        config_snapshot_id="cfg-test",
    )


def _spec(
    *, overall_status: str | None = None, page: int = 1, page_size: int = 100,
    sort_dir: str = "desc",
) -> QuerySpecification[PipelineRunFilterParams]:
    return QuerySpecification(
        filters=PipelineRunFilterParams(overall_status=overall_status),
        sort=SortParams(sort_by="as_of", sort_dir=sort_dir),
        pagination=PaginationParams(page=page, page_size=page_size),
    )


def test_get_runs_sorts_newest_first_by_default(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "a.db")
    repo.initialize()
    for i, run_id in enumerate(["run-a", "run-b", "run-c"]):
        repo.save_run(_run(run_id, minutes=i, status=RunStatus.COMPLETED))

    provider = SqlitePipelineRunProvider(repo)
    result = provider.get_runs(_spec())

    assert [r.run_id for r in result.items] == ["run-c", "run-b", "run-a"]
    assert result.total_count == 3
    repo.close()


def test_get_runs_filters_by_overall_status(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "b.db")
    repo.initialize()
    repo.save_run(_run("run-ok", minutes=0, status=RunStatus.COMPLETED))
    repo.save_run(_run("run-bad", minutes=1, status=RunStatus.FAILED))

    provider = SqlitePipelineRunProvider(repo)
    ok_only = provider.get_runs(_spec(overall_status="SUCCESS"))
    bad_only = provider.get_runs(_spec(overall_status="FAILED"))

    assert [r.run_id for r in ok_only.items] == ["run-ok"]
    assert ok_only.total_count == 1
    assert [r.run_id for r in bad_only.items] == ["run-bad"]
    assert bad_only.total_count == 1
    repo.close()


def test_get_runs_paginates_correctly(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "c.db")
    repo.initialize()
    for i in range(5):
        repo.save_run(_run(f"run-{i}", minutes=i, status=RunStatus.COMPLETED))

    provider = SqlitePipelineRunProvider(repo)
    page1 = provider.get_runs(_spec(page=1, page_size=2))
    page2 = provider.get_runs(_spec(page=2, page_size=2))
    page3 = provider.get_runs(_spec(page=3, page_size=2))

    assert [r.run_id for r in page1.items] == ["run-4", "run-3"]
    assert [r.run_id for r in page2.items] == ["run-2", "run-1"]
    assert [r.run_id for r in page3.items] == ["run-0"]
    assert page1.total_count == page2.total_count == page3.total_count == 5
    repo.close()


def test_get_runs_detail_still_populated_on_returned_items(tmp_path: Path):
    """The performance fix must not have silently dropped detail data for
    the rows that DO make it onto the page."""
    repo = SqliteRepository(tmp_path / "d.db")
    repo.initialize()
    repo.save_run(
        _run("run-with-detail", minutes=0, status=RunStatus.COMPLETED),
        detail={"phase": "closing_summary"},
    )

    provider = SqlitePipelineRunProvider(repo)
    result = provider.get_runs(_spec())

    assert len(result.items) == 1
    stage = result.items[0].pipeline_runs[0].stages[0]
    assert stage.message == "closing_summary"
    repo.close()
