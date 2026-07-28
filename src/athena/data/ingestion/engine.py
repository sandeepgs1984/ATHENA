"""LiveIngestionEngine — poll → validate → persist (M10.1).

Composable over ``MarketDataProvider`` + ``DatasetValidator`` + ``SqliteRepository``.
No broker binding (DD-1 open). No scheduler (M10.2). No order methods.
Time is always injected as ``as_of`` for determinism and replay.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from athena.config.models import GapConfig, IngestionConfig, ValidationConfig
from athena.data.ingestion.institutional_flow import InstitutionalFlowIngestor
from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.data.validation.dataset_validator import DatasetValidator
from athena.data.validation.quarantine import QuarantineRegistry
from athena.data.validation.reports import ValidationSummary, ValidationType
from athena.data.validation.validators import validate_quotes
from athena.domain.enums import Timeframe
from athena.domain.interfaces import InstitutionalFlowProvider, MarketDataProvider
from athena.domain.market import Candle, Quote
from athena.errors import DataStaleError, DataValidationError


def _validation_for_ingest(base: ValidationConfig, config: IngestionConfig) -> ValidationConfig:
    if config.validate_gaps:
        return base
    return ValidationConfig(
        freshness=base.freshness,
        gaps=GapConfig(daily_enabled=False, intraday_enabled=False),
    )


def _raise_for_summary(summary: ValidationSummary) -> None:
    failures = summary.failures
    detail = "; ".join(f"{r.validation_type.value}: {r.explanation}" for r in failures)
    message = f"ingest rejected dataset '{summary.dataset_id}': {detail}"
    if any(r.validation_type is ValidationType.FRESHNESS for r in failures):
        raise DataStaleError(message)
    raise DataValidationError(message)


class LiveIngestionEngine:
    """One callable ingest cycle over a read-only market-data provider."""

    def __init__(
        self,
        provider: MarketDataProvider,
        repo: SqliteRepository,
        validator: DatasetValidator,
        quarantine: QuarantineRegistry,
        config: IngestionConfig,
        validation_config: ValidationConfig,
        *,
        tzinfo: ZoneInfo,
        institutional_provider: InstitutionalFlowProvider | None = None,
    ) -> None:
        self._provider = provider
        self._repo = repo
        self._validator = validator
        self._quarantine = quarantine
        self._config = config
        self._validation_config = validation_config
        self._tzinfo = tzinfo
        self._institutional_provider = institutional_provider

    def run_cycle(self, *, as_of: datetime) -> IngestionResult:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        instruments = self._provider.instruments()
        by_id = {i.instrument_id: i for i in instruments}
        if self._config.instrument_ids:
            missing = [i for i in self._config.instrument_ids if i not in by_id]
            if missing:
                raise DataValidationError(
                    f"ingestion.instrument_ids unknown to provider: {missing}"
                )
            selected = [by_id[i] for i in self._config.instrument_ids]
        else:
            selected = list(instruments)

        for inst in selected:
            self._repo.upsert_instrument(inst)

        ids = [i.instrument_id for i in selected]
        candle_batches: list[tuple[str, Timeframe, list[Candle], datetime, datetime]] = []
        skipped_empty = 0
        candles_fetched = 0

        if self._config.include_daily:
            end_day = as_of.astimezone(self._tzinfo).date()
            start_day = end_day - timedelta(days=self._config.lookback_days - 1)
            for iid in ids:
                candles = self._provider.daily_candles(iid, start_day, end_day)
                candles_fetched += len(candles)
                if not candles:
                    skipped_empty += 1
                    continue
                dataset_id = f"{iid}:1d"
                summary = self._validator.validate_daily(
                    dataset_id, candles, start=start_day, end=end_day, as_of=as_of,
                )
                record = self._quarantine.review(summary)
                if record is not None:
                    if self._config.quarantine_on_failure:
                        self._repo.save_quarantine(record)
                    _raise_for_summary(summary)
                start_ts = datetime.combine(start_day, datetime.min.time(), tzinfo=self._tzinfo)
                end_ts = datetime.combine(end_day, datetime.max.time(), tzinfo=self._tzinfo)
                candle_batches.append((dataset_id, Timeframe.D1, list(candles), start_ts, end_ts))

        for tf_value in self._config.timeframes:
            timeframe = Timeframe(tf_value)
            end_ts = as_of
            start_ts = as_of - timedelta(minutes=self._config.lookback_minutes)
            for iid in ids:
                candles = self._provider.intraday_candles(iid, timeframe, start_ts, end_ts)
                candles_fetched += len(candles)
                if not candles:
                    skipped_empty += 1
                    continue
                dataset_id = f"{iid}:{timeframe.value}"
                summary = self._validator.validate_intraday(
                    dataset_id, timeframe, candles,
                    start=start_ts.astimezone(self._tzinfo).date(),
                    end=end_ts.astimezone(self._tzinfo).date(),
                    as_of=as_of,
                )
                record = self._quarantine.review(summary)
                if record is not None:
                    if self._config.quarantine_on_failure:
                        self._repo.save_quarantine(record)
                    _raise_for_summary(summary)
                candle_batches.append((dataset_id, timeframe, list(candles), start_ts, end_ts))

        quotes: list[Quote] = []
        quotes_fetched = 0
        if self._config.include_quotes:
            if not ids:
                raise DataValidationError("include_quotes is true but no instruments selected")
            quotes = list(self._provider.quotes(ids))
            quotes_fetched = len(quotes)
            q_summary = validate_quotes(
                quotes,
                as_of=as_of,
                max_minutes_behind=(
                    self._validation_config.freshness.intraday_max_minutes_behind
                ),
            )
            record = self._quarantine.review(q_summary)
            if record is not None:
                if self._config.quarantine_on_failure:
                    self._repo.save_quarantine(record)
                _raise_for_summary(q_summary)

        candles_written = 0
        for _dataset_id, timeframe, candles, start_ts, end_ts in candle_batches:
            to_write = candles
            if self._config.skip_existing and candles:
                iid = candles[0].instrument_id
                existing = {
                    (c.instrument_id, c.timeframe.value, c.ts_open.isoformat())
                    for c in self._repo.get_candles(iid, timeframe, start_ts, end_ts)
                }
                to_write = [
                    c for c in candles
                    if (c.instrument_id, c.timeframe.value, c.ts_open.isoformat()) not in existing
                ]
            if to_write:
                candles_written += self._repo.add_candles(to_write)

        quotes_written = 0
        if quotes:
            to_write_q = quotes
            if self._config.skip_existing:
                existing_q: set[tuple[str, str]] = set()
                for iid in {q.instrument_id for q in quotes}:
                    for q in self._repo.get_quotes(iid):
                        existing_q.add((q.instrument_id, q.ts.isoformat()))
                to_write_q = [
                    q for q in quotes
                    if (q.instrument_id, q.ts.isoformat()) not in existing_q
                ]
            if to_write_q:
                quotes_written += self._repo.add_quotes(to_write_q)

        snapshots_written = 0
        caps = self._provider.capabilities()
        if caps.supports_market_snapshot:
            try:
                snapshot = self._provider.market_snapshot()
            except Exception:
                snapshot = None
            if snapshot is not None:
                latest = self._repo.get_latest_snapshot()
                # market_snapshots.ts is UNIQUE — skip identical-timestamp re-ingest
                if latest is None or latest.ts != snapshot.ts:
                    self._repo.add_snapshot(snapshot)
                    snapshots_written = 1

        institutional_written = 0
        institutional_error: str | None = None
        if self._institutional_provider is not None:
            flow = InstitutionalFlowIngestor(
                self._repo, self._institutional_provider
            ).run(as_of=as_of)
            institutional_written = 1 if flow.written else 0
            institutional_error = flow.error

        return IngestionResult(
            as_of=as_of,
            instruments_upserted=len(selected),
            candles_fetched=candles_fetched,
            candles_written=candles_written,
            quotes_fetched=quotes_fetched,
            quotes_written=quotes_written,
            datasets_validated=len(candle_batches) + (1 if self._config.include_quotes else 0),
            datasets_skipped_empty=skipped_empty,
            snapshots_written=snapshots_written,
            institutional_written=institutional_written,
            institutional_error=institutional_error,
        )


def build_ingest_validator(
    calendar, base: ValidationConfig, config: IngestionConfig, tzinfo,
) -> DatasetValidator:
    """DatasetValidator with gap checks optionally disabled for the live loop."""
    return DatasetValidator(calendar, _validation_for_ingest(base, config), tzinfo)
