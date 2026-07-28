"""Institutional flow ingest — fetch via Protocol, append-only persist (MH-1)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from athena.data.store.repository import SqliteRepository
from athena.domain.interfaces import InstitutionalFlowProvider
from athena.domain.market import InstitutionalFlowSession
from athena.errors import ProviderError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InstitutionalIngestResult:
    """Outcome of one institutional-flow ingest attempt."""

    attempted: bool
    written: bool
    skipped_duplicate: bool
    error: str | None = None
    session_date: str | None = None


class InstitutionalFlowIngestor:
    """Pull latest FII/DII session and append when new (never cycle-aborting)."""

    def __init__(
        self,
        repo: SqliteRepository,
        provider: InstitutionalFlowProvider,
    ) -> None:
        self._repo = repo
        self._provider = provider

    def run(self, *, as_of: datetime, run_id: str = "") -> InstitutionalIngestResult:
        if as_of.tzinfo is None:
            raise ValueError("InstitutionalFlowIngestor.run as_of must be timezone-aware")
        try:
            session = self._provider.latest_session()
        except ProviderError as exc:
            logger.warning("institutional flow fetch failed (continuing): %s", exc)
            return InstitutionalIngestResult(
                attempted=True, written=False, skipped_duplicate=False, error=str(exc)
            )
        stamped = InstitutionalFlowSession(
            session_date=session.session_date,
            fii_buy=session.fii_buy,
            fii_sell=session.fii_sell,
            fii_net=session.fii_net,
            dii_buy=session.dii_buy,
            dii_sell=session.dii_sell,
            dii_net=session.dii_net,
            provisional=session.provisional,
            source_id=session.source_id,
            fetched_at=as_of if session.fetched_at is None else session.fetched_at,
            run_id=run_id or session.run_id,
        )
        latest = self._repo.get_latest_institutional_flow(prefer_final=False)
        if (
            latest is not None
            and latest.session_date == stamped.session_date
            and latest.fii_net == stamped.fii_net
            and latest.dii_net == stamped.dii_net
            and latest.provisional == stamped.provisional
            and latest.source_id == stamped.source_id
        ):
            return InstitutionalIngestResult(
                attempted=True,
                written=False,
                skipped_duplicate=True,
                session_date=stamped.session_date.isoformat(),
            )
        self._repo.add_institutional_flow(stamped)
        return InstitutionalIngestResult(
            attempted=True,
            written=True,
            skipped_duplicate=False,
            session_date=stamped.session_date.isoformat(),
        )
