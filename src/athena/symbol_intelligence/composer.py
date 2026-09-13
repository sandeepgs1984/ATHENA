"""Symbol Intelligence composer (SI-P1).

GET composition re-reads persisted sources only.
POST Analyze may hydrate stale/missing D1 for that one symbol, then re-reads.
Never calls DecisionEngine, Portfolio Sync, or DarvaX scan.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from athena.api.darvax_mount import darvax_activation_requested
from athena.api.exceptions import DecisionNotFoundError, MyPortfolioSyncNotFoundError
from athena.api.v1.dtos.intraday_intelligence import IntradayIntelligenceDTO
from athena.api.v1.dtos.portfolio import PortfolioSnapshotDTO, PortfolioSnapshotRowDTO
from athena.api.v1.dtos.symbol_intelligence import (
    SiD1EvidenceDTO,
    SiDarvaxPresentationDTO,
    SiDecisionSummaryDTO,
    SiFreshnessDTO,
    SiHydrationDTO,
    SiIdentityDTO,
    SiLiveQuoteDTO,
    SiMarketState,
    SiNamedEvidenceDTO,
    SiNotIngestedDTO,
    SiOverallFreshnessDTO,
    SiPortfolioContextDTO,
    SiQualityPlaceholderDTO,
    SiQuoteKind,
    SiSearchHitDTO,
    SiSearchResultDTO,
    SiUnavailableDTO,
    SiZoneDTO,
    SymbolIntelligenceBundleDTO,
)
from athena.api.v1.services.decisions_service import DecisionsService
from athena.api.v1.services.my_portfolio_service import MyPortfolioService
from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.providers.kite_ltp import LiveQuoteView, fetch_live_quote_view
from athena.data.store.repository import SqliteRepository
from athena.data.validation.calendar_expectations import latest_trading_day_on_or_before
from athena.domain.enums import Timeframe
from athena.domain.market import Instrument
from athena.errors import AthenaError, ConfigError, ProviderError, RepositoryError
from athena.portfolio.trend_adapter import PortfolioTrendAdapter
from athena.symbol_intelligence.d1_adapter import SiStructuralZone, SymbolIntelligenceD1Adapter
from athena.symbol_intelligence.d1_hydrate import SiHydrationOutcome, SymbolIntelligenceD1Hydrator
from athena.symbols.models import SymbolRecord

SI_METHODOLOGY_UNAVAILABLE = (
    "NOT_YET_METHODOLOGICALLY_DEFINED: SI-P1 exposes named evidence only; "
    "no Momentum Quality or Entry Quality formula is frozen."
)
SI_FUNDAMENTALS_REASON = (
    "ATHENA has no point-in-time-safe fundamental/earnings source in SI-P1. "
    "No provider, scrape, or LLM lookup is used."
)
SI_NEWS_REASON = (
    "ATHENA has no filings/news/catalyst ingestion in SI-P1. "
    "EvidenceCategory.NEWS is unused. No sentiment or placeholder events."
)


class SymbolIntelligenceComposer:
    """Assemble one symbol's current persisted evidence into the SI contract."""

    def __init__(
        self,
        repo: SqliteRepository | None,
        *,
        config_dir: Path,
        decisions_service: DecisionsService | None = None,
        my_portfolio_service: MyPortfolioService | None = None,
        now_fn: Callable[[], datetime] | None = None,
        d1_adapter: SymbolIntelligenceD1Adapter | None = None,
        hydrator: SymbolIntelligenceD1Hydrator | None = None,
        live_quote_fn: Callable[[str], object] | None = None,
    ) -> None:
        self._repo = repo
        self._config_dir = Path(config_dir)
        self._decisions = decisions_service
        self._portfolio = my_portfolio_service
        self._now = now_fn or (lambda: datetime.now(tz=timezone.utc))
        cfg = load_config(self._config_dir)
        self._market_tz = ZoneInfo(cfg.market.timezone)
        self._calendar = CalendarEngine.from_config_dir(self._config_dir, cfg.market)
        trend_adapter = (
            PortfolioTrendAdapter(repo, config_dir=self._config_dir) if repo is not None else None
        )
        self._d1 = d1_adapter or SymbolIntelligenceD1Adapter(trend_adapter=trend_adapter)
        self._hydrator = hydrator or SymbolIntelligenceD1Hydrator(repo, config_dir=self._config_dir)
        self._live_quote_fn = live_quote_fn

    def search(self, query: str, *, limit: int = 20) -> SiSearchResultDTO:
        needle = query.strip().upper()
        if not needle or self._repo is None:
            return SiSearchResultDTO(query=query, hits=())
        hits: list[SiSearchHitDTO] = []
        seen: set[str] = set()
        for instrument in self._iter_resolvable_instruments():
            if instrument.instrument_id in seen:
                continue
            haystacks = (
                instrument.instrument_id.upper(),
                instrument.symbol.upper(),
                (instrument.name or "").upper(),
            )
            if any(needle in value for value in haystacks if value):
                seen.add(instrument.instrument_id)
                hits.append(
                    SiSearchHitDTO(
                        instrument_id=instrument.instrument_id,
                        symbol=instrument.symbol,
                        exchange=instrument.exchange,
                        name=instrument.name,
                        sector=instrument.sector,
                    )
                )
            if len(hits) >= limit:
                break
        return SiSearchResultDTO(query=query, hits=tuple(hits))

    def compose(self, query: str, *, refresh_market: bool = False) -> SymbolIntelligenceBundleDTO:
        read_as_of = self._now()
        if read_as_of.tzinfo is None:
            raise ValueError("Symbol Intelligence read clock must be timezone-aware")
        expected_session = latest_trading_day_on_or_before(
            self._calendar, read_as_of.astimezone(self._market_tz).date()
        )
        identity, instrument = self._resolve(query)
        unavailable: list[SiUnavailableDTO] = []
        hydration = SiHydrationDTO(
            attempted=False,
            status="SKIPPED",
            detail="GET composition re-reads persisted sources only.",
        )
        if not identity.resolved or instrument is None:
            unavailable.append(
                SiUnavailableDTO(
                    code=identity.resolution_code or "UNKNOWN_INSTRUMENT",
                    detail=identity.unresolved_reason or "Symbol could not be resolved.",
                    lineage="SYMBOL_MASTER",
                )
            )
            return self._unresolved_bundle(
                identity, read_as_of, expected_session, unavailable, hydration=hydration
            )

        if refresh_market:
            hydration = self._refresh_d1_if_needed(
                instrument.instrument_id, expected_session, read_as_of
            )
            if hydration.status == "FAILED":
                unavailable.append(
                    SiUnavailableDTO(
                        code="D1_HYDRATION_FAILED",
                        detail=hydration.detail,
                        lineage="D1_CANDLES",
                    )
                )

        live = (
            self._compose_live(instrument.instrument_id, read_as_of)
            if refresh_market
            else self._quote_shell(
                read_as_of,
                present=False,
                null_reason="LIVE_QUOTE_ON_ANALYZE_ONLY",
            )
        )
        d1, d1_freshness = self._compose_d1(
            instrument.instrument_id, expected_session, read_as_of
        )
        if not d1.present:
            unavailable.append(
                SiUnavailableDTO(
                    code="NO_D1_DATA",
                    detail=d1.null_reason or "No persisted D1 candles.",
                    lineage="D1_CANDLES",
                )
            )
        elif refresh_market and hydration.status == "HYDRATED" and d1_freshness.status == "STALE":
            unavailable.append(
                SiUnavailableDTO(
                    code="D1_STILL_STALE",
                    detail=(
                        "Hydration completed but completed D1 still does not match "
                        f"the expected session {expected_session}."
                    ),
                    lineage="D1_CANDLES",
                )
            )

        decision, decision_freshness = self._compose_decision(
            instrument.instrument_id, expected_session, read_as_of
        )
        if not decision.present:
            unavailable.append(
                SiUnavailableDTO(
                    code="NO_DECISION",
                    detail=(
                        "NOT_ANALYZED: valid instrument has no persisted ATHENA Decision. "
                        "Universe membership is not required for Symbol Intelligence."
                    ),
                    lineage="ATHENA_DECISION",
                )
            )

        portfolio, portfolio_freshness = self._compose_portfolio(
            instrument.instrument_id, expected_session
        )
        darvax, darvax_freshness = self._compose_darvax(instrument)
        sources = (
            d1_freshness,
            decision_freshness,
            portfolio_freshness,
            darvax_freshness,
        )
        overall = self._overall_freshness(identity.resolved, sources)
        momentum = self._momentum_placeholder(d1, instrument)
        entry = self._entry_placeholder(decision, d1)
        return SymbolIntelligenceBundleDTO(
            identity=identity,
            read_as_of=read_as_of,
            overall_freshness=overall,
            sources=sources,
            decision=decision,
            d1=d1,
            portfolio=portfolio,
            darvax=darvax,
            momentum_quality=momentum,
            entry_quality=entry,
            fundamentals=SiNotIngestedDTO(reason=SI_FUNDAMENTALS_REASON),
            news=SiNotIngestedDTO(reason=SI_NEWS_REASON),
            unavailable=tuple(unavailable),
            hydration=hydration,
            live=live,
        )

    def _refresh_d1_if_needed(
        self,
        instrument_id: str,
        expected_session: date | None,
        read_as_of: datetime,
    ) -> SiHydrationDTO:
        if not self._hydrator.needs_refresh(
            instrument_id,
            expected_session=expected_session,
            as_of=read_as_of,
            market_tz=self._market_tz,
        ):
            return SiHydrationDTO(
                attempted=False,
                status="CURRENT",
                detail="Persisted D1 already matches the expected completed session.",
            )
        outcome: SiHydrationOutcome = self._hydrator.hydrate(
            instrument_id, as_of=read_as_of
        )
        return SiHydrationDTO(
            attempted=True,
            status=outcome.status,
            detail=outcome.detail,
            candles_written=outcome.candles_written,
        )

    def _market_state(self, read_as_of: datetime) -> SiMarketState:
        local = read_as_of.astimezone(self._market_tz)
        ctx = self._calendar.context_for(local.date())
        if not ctx.is_trading_session or ctx.open_time is None or ctx.close_time is None:
            return "MARKET CLOSED"
        clock = local.time()
        if ctx.open_time <= clock <= ctx.close_time:
            return "MARKET OPEN"
        return "MARKET CLOSED"

    @staticmethod
    def _quote_labels(
        present: bool, market_state: SiMarketState
    ) -> tuple[SiQuoteKind, str]:
        if present and market_state == "MARKET OPEN":
            return "LIVE", "LIVE · MARKET OPEN"
        if present:
            return "LATEST_QUOTE", "LATEST QUOTE · MARKET CLOSED"
        return "UNAVAILABLE", market_state

    def _quote_shell(
        self,
        read_as_of: datetime,
        *,
        present: bool,
        null_reason: str | None,
    ) -> SiLiveQuoteDTO:
        market_state = self._market_state(read_as_of)
        quote_kind, label = self._quote_labels(present, market_state)
        return SiLiveQuoteDTO(
            present=present,
            quote_kind=quote_kind,
            market_state=market_state,
            label=label,
            null_reason=null_reason,
        )

    def _stamp_live_dto(self, raw: SiLiveQuoteDTO, read_as_of: datetime) -> SiLiveQuoteDTO:
        market_state = self._market_state(read_as_of)
        quote_kind, label = self._quote_labels(raw.present, market_state)
        return raw.model_copy(
            update={
                "quote_kind": quote_kind,
                "market_state": market_state,
                "label": label,
            }
        )

    def _compose_live(self, instrument_id: str, read_as_of: datetime) -> SiLiveQuoteDTO:
        if self._live_quote_fn is not None:
            raw = self._live_quote_fn(instrument_id)
            if isinstance(raw, SiLiveQuoteDTO):
                return self._stamp_live_dto(raw, read_as_of)
            if isinstance(raw, LiveQuoteView):
                return self._live_from_view(raw, self._market_state(read_as_of))
        try:
            view = fetch_live_quote_view(instrument_id, config_dir=self._config_dir)
        except (ProviderError, ConfigError, AthenaError) as exc:
            return self._quote_shell(read_as_of, present=False, null_reason=str(exc))
        return self._live_from_view(view, self._market_state(read_as_of))

    @classmethod
    def _live_from_view(cls, view: LiveQuoteView, market_state: SiMarketState) -> SiLiveQuoteDTO:
        quote_kind, label = cls._quote_labels(True, market_state)
        return SiLiveQuoteDTO(
            present=True,
            quote_kind=quote_kind,
            market_state=market_state,
            label=label,
            last_price=view.quote.last_price,
            change_pct=view.change_pct,
            volume=view.quote.volume,
            session_open=view.session_open,
            session_high=view.session_high,
            session_low=view.session_low,
            previous_close=view.previous_close,
            as_of=view.quote.ts,
        )

    def _resolve(self, query: str) -> tuple[SiIdentityDTO, Instrument | None]:
        raw = query.strip().upper()
        if not raw:
            return (
                SiIdentityDTO(
                    query=query,
                    resolved=False,
                    unresolved_reason="Empty symbol query.",
                    resolution_code="EMPTY_QUERY",
                ),
                None,
            )
        if self._repo is None:
            return (
                SiIdentityDTO(
                    query=query,
                    resolved=False,
                    unresolved_reason="Symbol master repository is unavailable.",
                    resolution_code="REPOSITORY_UNAVAILABLE",
                ),
                None,
            )
        if ":" in raw:
            instrument, catalog, ingested = self._lookup_canonical(raw)
            if instrument is not None:
                return self._identity_from_instrument(
                    query, instrument, catalog=catalog, ingested=ingested
                ), instrument
            return (
                SiIdentityDTO(
                    query=query,
                    resolved=False,
                    unresolved_reason=f"No instrument matched {raw!r}.",
                    resolution_code="UNKNOWN_INSTRUMENT",
                ),
                None,
            )
        matches = self._matches_for_bare_symbol(raw)
        if len(matches) == 1:
            instrument, catalog, ingested = matches[0]
            return self._identity_from_instrument(
                query, instrument, catalog=catalog, ingested=ingested
            ), instrument
        if len(matches) > 1:
            ids = ", ".join(item[0].instrument_id for item in matches[:8])
            return (
                SiIdentityDTO(
                    query=query,
                    resolved=False,
                    symbol=raw,
                    unresolved_reason=(
                        "Ambiguous symbol; qualify with EXCHANGE:SYMBOL "
                        f"(matches: {ids})."
                    ),
                    resolution_code="AMBIGUOUS_SYMBOL",
                ),
                None,
            )
        return (
            SiIdentityDTO(
                query=query,
                resolved=False,
                unresolved_reason=f"No instrument matched {raw!r}.",
                resolution_code="UNKNOWN_INSTRUMENT",
            ),
            None,
        )

    def _iter_resolvable_instruments(self) -> list[Instrument]:
        """Ingested instruments plus ADR-011 symbol_master. Not owner_candidates."""
        by_id: dict[str, Instrument] = {}
        if self._repo is None:
            return []
        for record in self._repo.list_symbol_records():
            by_id[record.instrument_id] = self._instrument_from_record(record)
        for instrument in self._repo.list_instruments():
            by_id[instrument.instrument_id] = instrument
        return list(by_id.values())

    def _lookup_canonical(self, instrument_id: str) -> tuple[Instrument | None, str | None, bool]:
        if self._repo is None:
            return None, None, False
        ingested = self._repo.get_instrument(instrument_id)
        master = self._repo.get_symbol_record(instrument_id)
        if ingested is not None and master is not None:
            return ingested, "BOTH", True
        if ingested is not None:
            return ingested, "INSTRUMENTS", True
        if master is not None:
            return self._instrument_from_record(master), "SYMBOL_MASTER", False
        return None, None, False

    def _matches_for_bare_symbol(
        self, raw: str
    ) -> list[tuple[Instrument, str, bool]]:
        found: dict[str, tuple[Instrument, str, bool]] = {}
        if self._repo is None:
            return []
        for instrument in self._repo.list_instruments():
            if instrument.symbol.upper() == raw:
                found[instrument.instrument_id] = (instrument, "INSTRUMENTS", True)
        for record in self._repo.list_symbol_records():
            if record.symbol.upper() != raw:
                continue
            if record.instrument_id in found:
                instrument, _, ingested = found[record.instrument_id]
                found[record.instrument_id] = (instrument, "BOTH", ingested)
            else:
                found[record.instrument_id] = (
                    self._instrument_from_record(record),
                    "SYMBOL_MASTER",
                    False,
                )
        return list(found.values())

    @staticmethod
    def _instrument_from_record(record: SymbolRecord) -> Instrument:
        return Instrument(
            instrument_id=record.instrument_id,
            symbol=record.symbol,
            exchange=record.exchange,
            series=record.series,
            name=record.name,
            lot_size=max(int(record.lot_size), 1),
            tick_size=record.tick_size,
            status=record.status,
        )

    @staticmethod
    def _identity_from_instrument(
        query: str,
        instrument: Instrument,
        *,
        catalog: str | None,
        ingested: bool,
    ) -> SiIdentityDTO:
        return SiIdentityDTO(
            query=query,
            resolved=True,
            instrument_id=instrument.instrument_id,
            symbol=instrument.symbol,
            exchange=instrument.exchange,
            name=instrument.name,
            sector=instrument.sector,
            resolution_code="VALID_INSTRUMENT",
            catalog=catalog,
            ingested=ingested,
        )

    def _compose_d1(
        self,
        instrument_id: str,
        expected_session: date | None,
        read_as_of: datetime,
    ) -> tuple[SiD1EvidenceDTO, SiFreshnessDTO]:
        if self._repo is None:
            d1 = SiD1EvidenceDTO(present=False, null_reason="NO_REPOSITORY")
            return d1, SiFreshnessDTO(
                source="D1_CANDLES",
                status="UNAVAILABLE",
                lineage="D1_CANDLES",
                expected_session=expected_session,
                explanation="No repository is wired for D1 reads.",
            )
        candles = self._repo.list_candles_recent(
            instrument_id, Timeframe.D1, limit=300, as_of=read_as_of
        )
        measured = self._d1.evaluate(
            instrument_id=instrument_id,
            candles=candles,
            market_timezone=self._market_tz,
            expected_session=expected_session,
        )
        latest_date = (
            measured.latest_session.astimezone(self._market_tz).date()
            if measured.latest_session is not None
            else None
        )
        if measured.candles_used == 0:
            status: str = "UNAVAILABLE"
            explanation = "No persisted D1 candles for this instrument."
            present = False
            null_reason: str | None = "NO_D1_DATA"
        elif expected_session is None:
            status = "UNAVAILABLE"
            explanation = "Calendar could not resolve the expected D1 session."
            present = True
            null_reason = None
        elif latest_date == expected_session:
            status = "CURRENT"
            explanation = f"Latest D1 session {latest_date.isoformat()} matches the expected session."
            present = True
            null_reason = None
        else:
            status = "STALE"
            explanation = (
                f"Latest D1 session is {latest_date.isoformat() if latest_date else 'unknown'}; "
                f"expected {expected_session.isoformat()}."
            )
            present = True
            null_reason = None
        d1 = SiD1EvidenceDTO(
            present=present,
            null_reason=null_reason,
            latest_session=measured.latest_session,
            expected_session=expected_session,
            open=measured.latest_open,
            high=measured.latest_high,
            low=measured.latest_low,
            close=measured.latest_close,
            volume=measured.latest_volume,
            adjusted=measured.adjusted,
            candles_used=measured.candles_used,
            rsi14=measured.rsi_value,
            rsi_reason=measured.rsi_reason,
            rsi_is_coherent=measured.rsi_coherent,
            supertrend_direction=measured.supertrend_direction,
            supertrend_value=measured.supertrend_value,
            supertrend_reason=measured.supertrend_reason,
            supertrend_version=measured.supertrend_version,
            supertrend_is_coherent=measured.supertrend_coherent,
            volume_ma20=measured.volume_ma,
            volume_reason=measured.volume_reason,
            volume_is_coherent=measured.volume_coherent,
            available_history_high=measured.available_history_high,
            available_history_high_session=measured.available_history_high_session,
            latest_high_exceeds_prior_history=measured.latest_high_exceeds_prior_history,
            latest_close_above_prior_history_high=measured.latest_close_above_prior_history_high,
            ath_reason=measured.ath_reason,
            ath_is_coherent=measured.ath_coherent,
            symbol_trend=measured.symbol_trend,
            symbol_trend_reason=measured.symbol_trend_reason,
            symbol_trend_is_coherent=measured.symbol_trend_coherent,
            fast_sma=measured.fast_sma,
            slow_sma=measured.slow_sma,
            support_1=self._zone_dto(measured.support_1),
            major_support=self._zone_dto(measured.major_support),
            review_trigger=self._zone_dto(measured.review_trigger),
            target_1=self._zone_dto(measured.target_1),
            target_2=self._zone_dto(measured.target_2),
            target_3=self._zone_dto(measured.target_3),
            structural_reason_codes=measured.structural_reason_codes,
            structural_is_coherent=measured.structural_coherent,
            adapter_version=measured.version,
        )
        freshness = SiFreshnessDTO(
            source="D1_CANDLES",
            status=status,  # type: ignore[arg-type]
            lineage="D1_CANDLES",
            as_of=measured.latest_session,
            expected_session=expected_session,
            explanation=explanation,
        )
        return d1, freshness

    @staticmethod
    def _zone_dto(zone: SiStructuralZone | None) -> SiZoneDTO | None:
        if zone is None:
            return None
        return SiZoneDTO(lower=zone.lower, upper=zone.upper, role=zone.role, lineage=zone.lineage)

    def _compose_decision(
        self,
        instrument_id: str,
        expected_session: date | None,
        read_as_of: datetime,
    ) -> tuple[SiDecisionSummaryDTO, SiFreshnessDTO]:
        missing = SiDecisionSummaryDTO(
            present=False, null_reason="NO_DECISION / NOT_ANALYZED"
        )
        unavailable_freshness = SiFreshnessDTO(
            source="ATHENA_DECISION",
            status="UNAVAILABLE",
            lineage="ATHENA_DECISION",
            expected_session=expected_session,
                explanation="NOT_ANALYZED: no persisted ATHENA Decision for this instrument.",
        )
        if self._repo is None or self._decisions is None:
            return missing, unavailable_freshness
        latest = [
            decision
            for decision in self._repo.list_latest_decisions_by_instrument()
            if decision.instrument_id == instrument_id
        ]
        if not latest:
            return missing, unavailable_freshness
        raw = latest[0]
        dto = self._decisions.get_decision(raw.decision_id)
        plan_freshness = None
        depth = None
        intraday: IntradayIntelligenceDTO | None = None
        try:
            plan_freshness = self._decisions.get_trade_plan_freshness(
                raw.decision_id, as_of=read_as_of
            )
        except (DecisionNotFoundError, RepositoryError, AthenaError, ValueError):
            plan_freshness = None
        try:
            depth = self._decisions.get_decision_depth(raw.decision_id)
        except (DecisionNotFoundError, RepositoryError, AthenaError, ValueError):
            depth = None
        try:
            intraday = self._decisions.get_intraday_intelligence(raw.decision_id)
        except (DecisionNotFoundError, RepositoryError, AthenaError, ValueError):
            intraday = None
        decision_date = raw.ts.astimezone(self._market_tz).date()
        if expected_session is None:
            status: str = "UNAVAILABLE"
            explanation = "Calendar could not resolve the expected session for Decision freshness."
        elif decision_date == expected_session:
            status = "CURRENT"
            explanation = f"Latest Decision ts is on expected session {expected_session.isoformat()}."
        else:
            status = "STALE"
            explanation = (
                f"Latest Decision is dated {decision_date.isoformat()}; "
                f"expected session {expected_session.isoformat()}."
            )
        summary = SiDecisionSummaryDTO(
            present=True,
            decision_id=dto.metadata.decision_id,
            decision_type=dto.metadata.decision_type,
            direction=dto.metadata.direction,
            ts=dto.metadata.ts,
            run_id=dto.metadata.run_id,
            cycle_id=dto.metadata.cycle_id,
            explanation=dto.explanation,
            confidence_level=dto.analysis.confidence_level,
            gates=tuple(dto.analysis.gate_results),
            trade_plan=dto.trade_plan,
            plan_freshness=plan_freshness,
            depth=depth,
            intraday=intraday,
            intraday_horizon="INTRADAY_DECISION_BOUND" if intraday is not None else None,
        )
        freshness = SiFreshnessDTO(
            source="ATHENA_DECISION",
            status=status,  # type: ignore[arg-type]
            lineage="ATHENA_DECISION",
            as_of=raw.ts,
            expected_session=expected_session,
            explanation=explanation,
        )
        return summary, freshness

    def _compose_portfolio(
        self,
        instrument_id: str,
        expected_session: date | None,
    ) -> tuple[SiPortfolioContextDTO, SiFreshnessDTO]:
        not_held = SiPortfolioContextDTO(status="NOT_HELD")
        if self._repo is None:
            return not_held, SiFreshnessDTO(
                source="PORTFOLIO",
                status="UNAVAILABLE",
                lineage="PORTFOLIO",
                expected_session=expected_session,
                explanation="No repository is wired for holdings reads.",
            )
        holding = self._repo.get_portfolio_holding(instrument_id)
        if holding is None:
            return not_held, SiFreshnessDTO(
                source="PORTFOLIO",
                status="CURRENT",
                lineage="PORTFOLIO",
                expected_session=expected_session,
                explanation="Instrument is not in current My Portfolio holdings.",
            )
        snapshot: PortfolioSnapshotDTO | None = None
        row: PortfolioSnapshotRowDTO | None = None
        if self._portfolio is not None:
            try:
                snapshot = self._portfolio.latest_snapshot()
            except MyPortfolioSyncNotFoundError:
                snapshot = None
            if snapshot is not None:
                row = self._matching_snapshot_row(snapshot, instrument_id)
        weight = None
        if (
            row is not None
            and snapshot is not None
            and row.current_value is not None
            and snapshot.summary.total_current_value not in (None, Decimal("0"))
        ):
            weight = (row.current_value / snapshot.summary.total_current_value) * Decimal("100")
        context = SiPortfolioContextDTO(
            status="HELD",
            quantity=holding.quantity if row is None else row.quantity,
            avg_price=holding.avg_price if row is None else row.avg_price,
            last_price=None if row is None else row.last_price,
            current_value=None if row is None else row.current_value,
            investment=None if row is None else row.investment,
            pnl=None if row is None else row.pnl,
            pnl_pct=None if row is None else row.pnl_pct,
            snapshot_id=None if snapshot is None else snapshot.snapshot_id,
            snapshot_currentness=None if snapshot is None else snapshot.currentness.value,
            snapshot_currentness_reason=None if snapshot is None else snapshot.currentness_reason,
            interpretation_status=None if row is None else row.status,
            conviction=None if row is None else row.conviction,
            trend_setup=None if row is None else row.trend_setup,
            next_action=None if row is None else row.next_action,
            daily_review_status=(
                None
                if row is None or row.daily_review is None
                else row.daily_review.review_status
            ),
            display_weight_pct=weight,
        )
        if snapshot is None:
            freshness_status = "STALE"
            explanation = (
                "Holding exists but no completed My Portfolio snapshot is available."
            )
        elif snapshot.currentness.value == "CURRENT":
            freshness_status = "CURRENT"
            explanation = "Holdings digest matches the latest completed snapshot."
        else:
            freshness_status = "STALE"
            explanation = snapshot.currentness_reason or snapshot.currentness.value
        freshness = SiFreshnessDTO(
            source="PORTFOLIO",
            status=freshness_status,  # type: ignore[arg-type]
            lineage="PORTFOLIO",
            as_of=None if snapshot is None else snapshot.generated_at,
            expected_session=expected_session,
            explanation=explanation,
        )
        return context, freshness

    @staticmethod
    def _matching_snapshot_row(
        snapshot: PortfolioSnapshotDTO, instrument_id: str
    ) -> PortfolioSnapshotRowDTO | None:
        bare = instrument_id.split(":", 1)[-1]
        for row in snapshot.rows:
            provenance_id = None
            if row.provenance is not None:
                provenance_id = getattr(row.provenance, "instrument_id", None)
            if provenance_id == instrument_id or row.symbol.upper() == bare:
                return row
        return None

    def _compose_darvax(
        self, instrument: Instrument
    ) -> tuple[SiDarvaxPresentationDTO, SiFreshnessDTO]:
        enabled = darvax_activation_requested(self._config_dir)
        if not enabled:
            presentation = SiDarvaxPresentationDTO(
                enabled=False,
                status="DISABLED",
                explanation=(
                    "DarvaX is disabled or not mounted. ATHENA core does not read "
                    "db/darvax.db. Enable the satellite to load the experimental iframe."
                ),
            )
            freshness = SiFreshnessDTO(
                source="DARVAX",
                status="UNAVAILABLE",
                lineage="DARVAX",
                explanation="DarvaX satellite is not enabled.",
            )
            return presentation, freshness
        url = (
            "/darvax/symbol360?embedded=1&symbol="
            + quote(instrument.instrument_id, safe="")
        )
        presentation = SiDarvaxPresentationDTO(
            enabled=True,
            status="ENABLED_IFRAME",
            iframe_url=url,
            explanation=(
                "DarvaX is presented via the existing Symbol 360 surface (iframe). "
                "EXPERIMENTAL_UNVALIDATED. ATHENA core does not import athena.darvax "
                "or interpret DarvaX ENTER as ATHENA TRADE."
            ),
        )
        freshness = SiFreshnessDTO(
            source="DARVAX",
            status="NOT_READ",
            lineage="DARVAX",
            explanation=(
                "ATHENA core does not read DarvaX artifacts. Freshness is owned by "
                "the DarvaX satellite surface loaded in the iframe."
            ),
        )
        return presentation, freshness

    @staticmethod
    def _named_owned_evidence(
        *,
        name: str,
        value: str | None,
        lineage: str,
        horizon: str,
        is_coherent: bool | None,
        reason: str | None,
    ) -> SiNamedEvidenceDTO:
        usable = value if is_coherent is True else None
        return SiNamedEvidenceDTO(
            name=name,
            value=usable,
            lineage=lineage,
            horizon=horizon,
            is_coherent=is_coherent,
            reason=reason,
        )

    @staticmethod
    def _momentum_placeholder(
        d1: SiD1EvidenceDTO, instrument: Instrument
    ) -> SiQualityPlaceholderDTO:
        evidence = (
            SymbolIntelligenceComposer._named_owned_evidence(
                name="symbol_d1_trend",
                value=d1.symbol_trend,
                lineage="PORTFOLIO_D1_EVIDENCE",
                horizon="D1",
                is_coherent=d1.symbol_trend_is_coherent,
                reason=d1.symbol_trend_reason,
            ),
            SymbolIntelligenceComposer._named_owned_evidence(
                name="rsi14",
                value=None if d1.rsi14 is None else str(d1.rsi14),
                lineage="PORTFOLIO_D1_EVIDENCE",
                horizon="D1",
                is_coherent=d1.rsi_is_coherent,
                reason=d1.rsi_reason,
            ),
            SymbolIntelligenceComposer._named_owned_evidence(
                name="supertrend_10_3",
                value=d1.supertrend_direction,
                lineage="PORTFOLIO_D1_EVIDENCE",
                horizon="D1",
                is_coherent=d1.supertrend_is_coherent,
                reason=d1.supertrend_reason,
            ),
            SiNamedEvidenceDTO(
                name="sector",
                value=instrument.sector,
                lineage="SYMBOL_MASTER",
                horizon="INSTRUMENT",
                is_coherent=None,
                reason=None,
            ),
        )
        return SiQualityPlaceholderDTO(
            reason=SI_METHODOLOGY_UNAVAILABLE
            + " ScoringEngine.momentum is RSI-only and is not Momentum Quality.",
            named_evidence=evidence,
        )

    @staticmethod
    def _entry_placeholder(
        decision: SiDecisionSummaryDTO, d1: SiD1EvidenceDTO
    ) -> SiQualityPlaceholderDTO:
        plan_status = None
        if decision.plan_freshness is not None:
            plan_status = decision.plan_freshness.status
        structural_value = None
        if d1.structural_is_coherent is True and d1.support_1 is not None:
            structural_value = f"{d1.support_1.lower}-{d1.support_1.upper}"
        structural_reason = None
        if d1.structural_reason_codes:
            structural_reason = ",".join(d1.structural_reason_codes)
        evidence = (
            SiNamedEvidenceDTO(
                name="athena_decision_type",
                value=decision.decision_type,
                lineage="ATHENA_DECISION",
                horizon="CYCLE",
                is_coherent=None,
                reason=None,
            ),
            SiNamedEvidenceDTO(
                name="trade_plan_freshness",
                value=plan_status,
                lineage="ATHENA_DECISION",
                horizon="TRADE_PLAN_WINDOW",
                is_coherent=None,
                reason=None,
            ),
            SymbolIntelligenceComposer._named_owned_evidence(
                name="structural_support_1",
                value=structural_value,
                lineage="PORTFOLIO_STRUCTURAL_REVIEW",
                horizon="D1",
                is_coherent=d1.structural_is_coherent,
                reason=structural_reason,
            ),
            SiNamedEvidenceDTO(
                name="entry_qualification_state",
                value=(
                    None
                    if decision.intraday is None
                    else decision.intraday.qualification.state
                ),
                lineage="ENTRY_QUALIFICATION",
                horizon="INTRADAY_DECISION_BOUND",
                is_coherent=None,
                reason=None,
            ),
            SiNamedEvidenceDTO(
                name="entry_actionability_state",
                value=(
                    None
                    if decision.intraday is None
                    else decision.intraday.actionability.state
                ),
                lineage="ENTRY_ACTIONABILITY",
                horizon="INTRADAY_DECISION_BOUND",
                is_coherent=None,
                reason=None,
            ),
        )
        return SiQualityPlaceholderDTO(
            reason=SI_METHODOLOGY_UNAVAILABLE
            + " EntryQualification, EntryActionability, TradePlan, Daily Review, "
            "and DarvaX action are not SI Entry Quality.",
            named_evidence=evidence,
        )

    @staticmethod
    def _overall_freshness(
        resolved: bool, sources: tuple[SiFreshnessDTO, ...]
    ) -> SiOverallFreshnessDTO:
        if not resolved:
            return SiOverallFreshnessDTO(
                status="UNAVAILABLE",
                explanation="Symbol is unresolved; no SI report can be current.",
            )
        material = [
            item
            for item in sources
            if item.source in {"D1_CANDLES", "ATHENA_DECISION", "PORTFOLIO"}
        ]
        d1 = next((item for item in material if item.source == "D1_CANDLES"), None)
        decision = next((item for item in material if item.source == "ATHENA_DECISION"), None)
        if d1 is None or d1.status == "UNAVAILABLE":
            return SiOverallFreshnessDTO(
                status="UNAVAILABLE",
                explanation="Required D1 market evidence is unavailable.",
            )
        if d1.status == "STALE":
            return SiOverallFreshnessDTO(
                status="STALE",
                explanation=(
                    "Completed D1 history is stale after the latest read. "
                    "ATHENA Decision staleness does not by itself mark SI stale."
                ),
            )
        if decision is None or decision.status == "UNAVAILABLE":
            return SiOverallFreshnessDTO(
                status="PARTIAL",
                explanation=(
                    "ATHENA Decision unavailable. Market data can still be current; "
                    "this is SI coverage, not a market-data error."
                ),
            )
        return SiOverallFreshnessDTO(
            status="READY",
            explanation=(
                "Completed D1 evidence is current. DarvaX freshness is "
                "satellite-owned and never averaged into this rollup."
            ),
        )

    def _unresolved_bundle(
        self,
        identity: SiIdentityDTO,
        read_as_of: datetime,
        expected_session: date | None,
        unavailable: list[SiUnavailableDTO],
        *,
        hydration: SiHydrationDTO,
    ) -> SymbolIntelligenceBundleDTO:
        empty_d1 = SiD1EvidenceDTO(present=False, null_reason="UNRESOLVED_SYMBOL")
        empty_decision = SiDecisionSummaryDTO(present=False, null_reason="UNRESOLVED_SYMBOL")
        sources = (
            SiFreshnessDTO(
                source="D1_CANDLES",
                status="UNAVAILABLE",
                lineage="D1_CANDLES",
                expected_session=expected_session,
                explanation="Unresolved symbol.",
            ),
            SiFreshnessDTO(
                source="ATHENA_DECISION",
                status="UNAVAILABLE",
                lineage="ATHENA_DECISION",
                expected_session=expected_session,
                explanation="Unresolved symbol.",
            ),
            SiFreshnessDTO(
                source="PORTFOLIO",
                status="UNAVAILABLE",
                lineage="PORTFOLIO",
                expected_session=expected_session,
                explanation="Unresolved symbol.",
            ),
            SiFreshnessDTO(
                source="DARVAX",
                status="UNAVAILABLE",
                lineage="DARVAX",
                explanation="Unresolved symbol.",
            ),
        )
        return SymbolIntelligenceBundleDTO(
            identity=identity,
            read_as_of=read_as_of,
            overall_freshness=SiOverallFreshnessDTO(
                status="UNAVAILABLE",
                explanation="Symbol could not be resolved against the canonical instrument catalog.",
            ),
            sources=sources,
            decision=empty_decision,
            d1=empty_d1,
            portfolio=None,
            darvax=SiDarvaxPresentationDTO(
                enabled=False,
                status="UNAVAILABLE",
                explanation="Unresolved symbol; DarvaX iframe is not composed.",
            ),
            momentum_quality=SiQualityPlaceholderDTO(
                reason=SI_METHODOLOGY_UNAVAILABLE, named_evidence=()
            ),
            entry_quality=SiQualityPlaceholderDTO(
                reason=SI_METHODOLOGY_UNAVAILABLE, named_evidence=()
            ),
            fundamentals=SiNotIngestedDTO(reason=SI_FUNDAMENTALS_REASON),
            news=SiNotIngestedDTO(reason=SI_NEWS_REASON),
            unavailable=tuple(unavailable),
            hydration=hydration,
            live=self._quote_shell(
                read_as_of,
                present=False,
                null_reason="UNRESOLVED_SYMBOL",
            ),
        )
