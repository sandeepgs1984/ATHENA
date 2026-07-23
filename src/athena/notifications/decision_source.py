"""SQLite-backed DecisionSummarySource for daily briefings (R2)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision, DecisionTrace


class SqliteDecisionSummarySource:
    """Load persisted decisions (+ traces) for ``as_of``'s local calendar day."""

    def __init__(
        self,
        repo: SqliteRepository,
        *,
        tzinfo: ZoneInfo,
        max_scanned: int = 500,
    ) -> None:
        self._repo = repo
        self._tzinfo = tzinfo
        self._max_scanned = max_scanned

    def list_for_day(
        self, as_of: datetime,
    ) -> list[tuple[Decision, DecisionTrace | None]]:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        day = as_of.astimezone(self._tzinfo).date()
        out: list[tuple[Decision, DecisionTrace | None]] = []
        for decision in self._repo.list_decisions(limit=self._max_scanned):
            if decision.ts.astimezone(self._tzinfo).date() != day:
                continue
            out.append((decision, self._repo.get_trace(decision.decision_id)))
        out.sort(key=lambda item: (item[0].ts, item[0].decision_id))
        return out
