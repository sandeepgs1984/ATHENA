"""Top Opportunities Today — sector-first, presentation-only aggregation.

Ranks today's best-performing sectors (already-computed sector-index
``change_pct`` from ``MarketHistoryService.index_intelligence()``, joined
against SD-2's ``sector_index_mapping.json``), and for each of the leading
sectors surfaces its highest-conviction ATHENA-qualified (WATCH/TRADE)
symbols — composite score, relative strength vs. its own sector, ATHENA's
own already-computed confidence level, and M-X3's plan-freshness clock.
Every value is read from an already-persisted Decision/ScoringResult/
ConfidenceAssessment; this module computes no score, confidence, risk, or
decision of its own, and never writes anything.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.api.v1.dtos.market import (
    OpportunitiesSummaryDTO,
    OpportunityRemovedDTO,
    OpportunitySectorDTO,
    OpportunitySymbolDTO,
    TopOpportunitiesDTO,
)
from athena.api.v1.services.market_history_service import MarketHistoryService
from athena.config.loader import (
    load_config,
    load_decision_config,
    load_index_intelligence_config,
    load_sector_index_mapping_config,
)
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Timeframe
from athena.ops.owner_candidates import display_symbol

_DECISION_LOOKBACK = 2000  # matches OwnerValidationPipeline._qualified_from_repo's own cap
_FRESHNESS_RANK = {"FRESH": 4, "AGING": 3, "STALE": 2, "EXPIRED": 1, "NO_PLAN": 0}
_DECISION_RANK = {"TRADE": 1, "WATCH": 0}


@dataclass(frozen=True, slots=True)
class _QualifiedRow:
    """One qualified decision, enriched — internal working shape, not the DTO."""

    decision: Decision
    composite_score: Decimal | None
    confidence_level: str | None
    confidence_overall: Decimal | None
    relative_strength_pct: Decimal | None
    freshness_status: str
    freshness_summary: str | None

    @property
    def sort_key(self) -> tuple:
        return (
            self.composite_score if self.composite_score is not None else Decimal("-1"),
            self.relative_strength_pct if self.relative_strength_pct is not None else Decimal("-999"),
            _FRESHNESS_RANK.get(self.freshness_status, 0),
            _DECISION_RANK.get(self.decision.decision_type.value, 0),
        )


@dataclass(frozen=True, slots=True)
class _RankedSector:
    sector: str
    index_key: str
    change_pct: Decimal | None


class OpportunitiesService:
    """Composes MarketHistoryService + already-persisted decisions/scores
    into the Top Opportunities Today view. Read-only: only ever calls
    `repo.list_decisions`/`get_instrument`/`get_run_detail`/
    `list_candles_recent` and `MarketHistoryService`'s own read methods.
    """

    def __init__(
        self,
        repo: SqliteRepository,
        *,
        market_history: MarketHistoryService,
        config_dir: Path,
    ) -> None:
        self._repo = repo
        self._market_history = market_history
        self._config_dir = Path(config_dir)
        # Perf (2026-08-03): per-request cache, reset at the top of
        # get_top_opportunities(). Many qualifying decisions across a
        # sector's candidates (or across the today/previous-day passes)
        # share the same run_id — in production, `runs.detail_json` blobs
        # run into single-digit MB, so re-parsing the identical JSON once
        # per decision (rather than once per unique run) was the dominant
        # cost measured end-to-end (~4.3s), not the decision/instrument
        # scan itself (~30ms once de-duplicated, see
        # `_qualified_decisions_by_sector`).
        self._run_detail_cache: dict[str, Mapping] = {}

    # ------------------------------------------------------------- public

    def get_top_opportunities(
        self,
        *,
        as_of: datetime | None = None,
        sector_count: int = 5,
        symbols_per_sector: int = 2,
    ) -> TopOpportunitiesDTO:
        self._run_detail_cache = {}
        if sector_count < 1 or symbols_per_sector < 1:
            raise ValueError("sector_count and symbols_per_sector must be >= 1")
        tz = ZoneInfo(load_config(self._config_dir).market.timezone)
        as_of = as_of or datetime.now(tz=tz)
        # Bug fix (2026-08-03): "today" must be the market-timezone calendar
        # date, not a raw UTC one — and plan freshness must be measured
        # against this REAL as_of, not a hardcoded stand-in. An earlier cut
        # of this method computed a fake `datetime.combine(today, time(15,
        # 30), tzinfo=timezone.utc)` (15:30 UTC = 21:00 IST) for freshness,
        # so every TRADE decision's plan compared against "9pm tonight" —
        # always past `valid_until`, hence every card showed EXPIRED
        # regardless of how fresh the plan actually was. Confirmed against a
        # real live dashboard screenshot (every "Top Opportunities" symbol
        # showing EXPIRED) before this fix.
        today = as_of.astimezone(tz).date()

        sector_groups = self._build_today_groups(as_of, sector_count, symbols_per_sector)

        compared_as_of: datetime | None = None
        board: dict[str, tuple[str, Decimal | None]] = {}
        prev_date = self._previous_decision_date(before=today)
        if prev_date is not None:
            compared_as_of = datetime.combine(prev_date, time(15, 30), tzinfo=tz)
            board = self._previous_day_scoreboard(prev_date, sector_count, symbols_per_sector)
            # Only attach NEW/IMPROVED/DROPPED once there's a real prior day
            # to diff against — with no prior day at all, every symbol would
            # otherwise be labeled "NEW" against an empty board, which isn't
            # a meaningful signal (nothing to be new relative to).
            sector_groups = self._attach_change_badges(sector_groups, board)
        removed = self._removed_since(board, sector_groups)
        summary = self._summarize(sector_groups)

        return TopOpportunitiesDTO(
            as_of=as_of,
            compared_as_of=compared_as_of,
            summary=summary,
            sectors=tuple(sector_groups),
            removed=tuple(removed),
        )

    # ------------------------------------------------------------- sector ranking

    def _rank_sectors_today(self) -> list[_RankedSector]:
        mapping = load_sector_index_mapping_config(self._config_dir)
        sectors_by_index_key: dict[str, list[str]] = {}
        for entry in mapping.mappings:
            sectors_by_index_key.setdefault(entry.index_key, []).append(entry.sector)

        intelligence = self._market_history.index_intelligence()
        ranked: list[_RankedSector] = []
        for item in intelligence.indices:
            if item.family != "sectoral" or item.data_status != "AVAILABLE":
                continue
            for sector in sectors_by_index_key.get(item.key, ()):
                ranked.append(_RankedSector(sector=sector, index_key=item.key, change_pct=item.change_pct))
        ranked.sort(key=lambda r: r.change_pct if r.change_pct is not None else Decimal("-999"), reverse=True)
        return ranked

    def _rank_sectors_for_date(self, target: date) -> list[_RankedSector]:
        """Same ranking rule as `_rank_sectors_today`, but the sector-index
        `change_pct` is recomputed from persisted daily candles anchored at
        `target` instead of `index_intelligence()`'s always-latest snapshot
        — a best-effort historical reconstruction used only to diff against
        today, not rendered as its own section."""
        config = load_sector_index_mapping_config(self._config_dir)
        idx_cfg = load_index_intelligence_config(self._config_dir)
        instrument_by_key = {
            item.key: item.instrument_id for item in idx_cfg.tracked_indices if item.family == "sectoral"
        }
        sectors_by_index_key: dict[str, list[str]] = {}
        for entry in config.mappings:
            sectors_by_index_key.setdefault(entry.index_key, []).append(entry.sector)

        ranked: list[_RankedSector] = []
        for index_key, instrument_id in instrument_by_key.items():
            change_pct = self._historical_change_pct(instrument_id, target)
            for sector in sectors_by_index_key.get(index_key, ()):
                ranked.append(_RankedSector(sector=sector, index_key=index_key, change_pct=change_pct))
        ranked.sort(key=lambda r: r.change_pct if r.change_pct is not None else Decimal("-999"), reverse=True)
        return ranked

    def _historical_change_pct(self, instrument_id: str, target: date) -> Decimal | None:
        candles = [
            c for c in self._repo.list_candles_recent(instrument_id, Timeframe.D1, limit=500)
            if c.ts_open.date() <= target
        ]
        if len(candles) < 2:
            return None
        level, baseline = candles[-1].close, candles[-2].close
        if baseline <= 0:
            return None
        return (level - baseline) / baseline * Decimal(100)

    # ------------------------------------------------------------- qualified rows

    def _qualified_decisions_by_sector(self, target: date) -> dict[str, list[Decision]]:
        """Perf (2026-08-03): mirrors `OwnerValidationPipeline
        ._qualified_from_repo`'s own dedupe-to-newest-same-day-verdict
        logic, grouped by sector in ONE pass. Originally this was a
        per-sector method re-scanning `list_decisions(limit=2000)` and
        calling `get_instrument()` per decision from scratch for every
        candidate sector (up to ~8 sectors, x2 for the day-over-day diff)
        — an O(sectors x decisions) redundant rescan measured at ~2.2-2.4s
        end-to-end against the real production database. Now O(decisions)
        — one repository scan, one `list_instruments()` call to build an
        instrument_id -> sector map, instead of one `get_instrument()` round
        trip per qualifying decision.
        """
        sector_by_instrument = {
            inst.instrument_id: inst.sector
            for inst in self._repo.list_instruments()
            if inst.sector
        }
        by_sector: dict[str, list[Decision]] = defaultdict(list)
        seen: set[str] = set()
        for decision in self._repo.list_decisions(limit=_DECISION_LOOKBACK):
            if decision.ts.date() != target:
                continue
            if decision.instrument_id is None or decision.instrument_id in seen:
                continue
            seen.add(decision.instrument_id)
            if decision.decision_type not in (DecisionType.WATCH, DecisionType.TRADE):
                continue
            sector = sector_by_instrument.get(decision.instrument_id)
            if sector is None:
                continue
            by_sector[sector].append(decision)
        return dict(by_sector)

    def _fetch_report(self, decision: Decision) -> Mapping:
        """Same lookup `DecisionsService._fetch_report` uses: `decision_id`
        is literally the `decision_reports` key (`decision/engine.py:83`).
        Caches the parsed run detail per `run_id` for the lifetime of one
        `get_top_opportunities()` call — many qualifying decisions across a
        sector (or between the today/previous-day passes) share the same
        run, and its `detail_json` is not cheap to re-parse repeatedly in
        production (see the cache's own docstring on `__init__`)."""
        reports = self._run_detail_cache.get(decision.run_id)
        if reports is None:
            detail = self._repo.get_run_detail(decision.run_id)
            pipeline = detail.get("pipeline", detail)
            candidate = pipeline.get("decision_reports") if isinstance(pipeline, Mapping) else None
            reports = candidate if isinstance(candidate, Mapping) else {}
            self._run_detail_cache[decision.run_id] = reports
        report = reports.get(decision.decision_id)
        return report if isinstance(report, Mapping) else {}

    def _plan_freshness(self, decision: Decision, as_of: datetime) -> tuple[str, str | None]:
        """Same arithmetic as `DecisionsService.get_trade_plan_freshness`
        (M-X3) — replicated rather than routed through that service, since
        the caller here already holds the `Decision` object directly and a
        second provider-based lookup by id would be redundant."""
        plan = decision.trade_plan
        if plan is None:
            return "NO_PLAN", None
        cfg = load_decision_config(self._config_dir).plan
        total = (plan.valid_until - plan.valid_from).total_seconds()
        elapsed = max(0.0, min(total, (as_of - plan.valid_from).total_seconds()))
        decay_fraction = Decimal(str(elapsed / total)) if total > 0 else Decimal(1)
        if as_of >= plan.valid_until:
            status = "EXPIRED"
        elif decay_fraction >= Decimal(str(cfg.freshness_stale_fraction)):
            status = "STALE"
        elif decay_fraction >= Decimal(str(cfg.freshness_warn_fraction)):
            status = "AGING"
        else:
            status = "FRESH"
        pct = int((decay_fraction * 100).to_integral_value())
        summary = f"{pct}% of the validity window elapsed — plan is {status}."
        return status, summary

    @staticmethod
    def _confidence_stars(overall: Decimal | None) -> int | None:
        """Pure presentation math over ConfidenceEngine's own already-
        computed overall_value (0-100) — no new scoring."""
        if overall is None:
            return None
        stars = int((overall / Decimal(100) * Decimal(5)).to_integral_value(rounding=ROUND_HALF_UP))
        return max(1, min(5, stars))

    def _enrich(
        self,
        decision: Decision,
        sector_change_pct: Decimal | None,
        as_of: datetime,
        quotes_by_id: Mapping[str, object],
    ) -> _QualifiedRow:
        report = self._fetch_report(decision)
        score_block = report.get("score") if isinstance(report, Mapping) else None
        confidence_block = report.get("confidence") if isinstance(report, Mapping) else None
        composite = None
        if isinstance(score_block, Mapping) and score_block.get("status") == "OK":
            raw = score_block.get("composite")
            composite = Decimal(str(raw)) if raw is not None else None
        confidence_level = None
        confidence_overall = None
        if isinstance(confidence_block, Mapping) and confidence_block.get("status") == "OK":
            confidence_level = confidence_block.get("level")
            raw_overall = confidence_block.get("overall")
            confidence_overall = Decimal(str(raw_overall)) if raw_overall is not None else None

        relative_strength = None
        if decision.instrument_id is not None and sector_change_pct is not None:
            quote = quotes_by_id.get(decision.instrument_id.upper())
            if quote is not None and quote.change_pct is not None:
                relative_strength = quote.change_pct - sector_change_pct

        freshness_status, freshness_summary = self._plan_freshness(decision, as_of)

        return _QualifiedRow(
            decision=decision,
            composite_score=composite,
            confidence_level=confidence_level,
            confidence_overall=confidence_overall,
            relative_strength_pct=relative_strength,
            freshness_status=freshness_status,
            freshness_summary=freshness_summary,
        )

    # ------------------------------------------------------------- today assembly

    def _build_today_groups(
        self, as_of_dt: datetime, sector_count: int, symbols_per_sector: int
    ) -> list[OpportunitySectorDTO]:
        today = as_of_dt.date()
        ranked = self._rank_sectors_today()
        by_sector = self._qualified_decisions_by_sector(today)
        # Perf fix (owner-reported, 2026-08-04): _enrich() previously called
        # MarketHistoryService.instrument_quote() once per qualifying
        # decision — each a separate live Kite round trip, measured at
        # 7-13s end to end for ~10-20 symbols. Collect every candidate's
        # instrument_id across all sectors (before the sector_count/
        # symbols_per_sector trim, since relative_strength_pct feeds the
        # sort that decides the trim) and fetch them in one batched call.
        candidate_ids = [
            d.instrument_id
            for sector_decisions in by_sector.values()
            for d in sector_decisions
            if d.instrument_id is not None
        ]
        quotes_by_id = self._market_history.instrument_quotes(candidate_ids)
        groups: list[OpportunitySectorDTO] = []
        for ranked_sector in ranked:
            if len(groups) >= sector_count:
                break
            decisions = by_sector.get(ranked_sector.sector, [])
            if not decisions:
                continue
            rows = [
                self._enrich(d, ranked_sector.change_pct, as_of_dt, quotes_by_id)
                for d in decisions
            ]
            rows.sort(key=lambda r: r.sort_key, reverse=True)
            top_rows = rows[:symbols_per_sector]
            symbols = tuple(
                OpportunitySymbolDTO(
                    symbol=display_symbol(r.decision.instrument_id),
                    instrument_id=r.decision.instrument_id,
                    decision_id=r.decision.decision_id,
                    decision_type=r.decision.decision_type.value,
                    athena_score=r.composite_score,
                    relative_strength_pct=r.relative_strength_pct,
                    confidence_level=r.confidence_level,
                    confidence_stars=self._confidence_stars(r.confidence_overall),
                    plan_freshness_status=r.freshness_status,
                    plan_freshness_summary=r.freshness_summary,
                )
                for r in top_rows
            )
            groups.append(
                OpportunitySectorDTO(
                    sector=ranked_sector.sector,
                    sector_rank=len(groups) + 1,
                    sector_change_pct=ranked_sector.change_pct,
                    symbols=symbols,
                )
            )
        return groups

    # ------------------------------------------------------------- day-over-day diff

    def _previous_decision_date(self, *, before: date) -> date | None:
        prior_dates = {
            d.ts.date() for d in self._repo.list_decisions(limit=_DECISION_LOOKBACK)
            if d.ts.date() < before
        }
        return max(prior_dates) if prior_dates else None

    def _previous_day_scoreboard(
        self, prev_date: date, sector_count: int, symbols_per_sector: int
    ) -> dict[str, tuple[str, Decimal | None]]:
        """Lightweight instrument_id -> (sector, composite_score) map for
        the most recent prior day with real decisions — used only to
        compute NEW/IMPROVED/DROPPED/removed, never rendered as its own
        section, so it skips the relative-strength/confidence/freshness
        enrichment `_build_today_groups` does (not needed for the diff)."""
        ranked = self._rank_sectors_for_date(prev_date)
        by_sector = self._qualified_decisions_by_sector(prev_date)
        board: dict[str, tuple[str, Decimal | None]] = {}
        contributing = 0
        for ranked_sector in ranked:
            if contributing >= sector_count:
                break
            decisions = by_sector.get(ranked_sector.sector, [])
            if not decisions:
                continue
            contributing += 1
            scored: list[tuple[Decision, Decimal | None]] = []
            for d in decisions:
                report = self._fetch_report(d)
                score_block = report.get("score") if isinstance(report, Mapping) else None
                composite = None
                if isinstance(score_block, Mapping) and score_block.get("status") == "OK":
                    raw = score_block.get("composite")
                    composite = Decimal(str(raw)) if raw is not None else None
                scored.append((d, composite))
            scored.sort(
                key=lambda pair: (
                    pair[1] if pair[1] is not None else Decimal("-1"),
                    _DECISION_RANK.get(pair[0].decision_type.value, 0),
                ),
                reverse=True,
            )
            for d, composite in scored[:symbols_per_sector]:
                board[d.instrument_id] = (ranked_sector.sector, composite)
        return board

    @staticmethod
    def _attach_change_badges(
        groups: Sequence[OpportunitySectorDTO], board: Mapping[str, tuple[str, Decimal | None]]
    ) -> list[OpportunitySectorDTO]:
        updated_groups: list[OpportunitySectorDTO] = []
        for group in groups:
            updated_symbols = []
            for sym in group.symbols:
                badge = None
                prior = board.get(sym.instrument_id)
                if prior is None:
                    badge = "NEW"
                elif sym.athena_score is not None and prior[1] is not None:
                    if sym.athena_score > prior[1]:
                        badge = "IMPROVED"
                    elif sym.athena_score < prior[1]:
                        badge = "DROPPED"
                updated_symbols.append(sym.model_copy(update={"change_badge": badge}))
            updated_groups.append(group.model_copy(update={"symbols": tuple(updated_symbols)}))
        return updated_groups

    @staticmethod
    def _removed_since(
        board: Mapping[str, tuple[str, Decimal | None]], groups: Sequence[OpportunitySectorDTO]
    ) -> list[OpportunityRemovedDTO]:
        today_ids = {sym.instrument_id for group in groups for sym in group.symbols}
        removed = [
            OpportunityRemovedDTO(
                symbol=display_symbol(instrument_id),
                instrument_id=instrument_id,
                sector=sector,
                last_seen_score=score,
            )
            for instrument_id, (sector, score) in board.items()
            if instrument_id not in today_ids
        ]
        removed.sort(key=lambda r: r.symbol)
        return removed

    @staticmethod
    def _summarize(groups: Sequence[OpportunitySectorDTO]) -> OpportunitiesSummaryDTO:
        all_symbols = [(group, sym) for group in groups for sym in group.symbols]
        if not groups:
            return OpportunitiesSummaryDTO()
        strongest_sector_group = groups[0]
        scored = [(sym, group) for group, sym in all_symbols if sym.athena_score is not None]
        strongest_symbol = max(scored, key=lambda pair: pair[0].athena_score, default=(None, None))[0]
        scores = [sym.athena_score for _, sym in all_symbols if sym.athena_score is not None]
        return OpportunitiesSummaryDTO(
            strongest_sector=strongest_sector_group.sector,
            strongest_sector_change_pct=strongest_sector_group.sector_change_pct,
            strongest_symbol=strongest_symbol.symbol if strongest_symbol else None,
            highest_athena_score=max(scores) if scores else None,
            average_athena_score=(sum(scores) / len(scores)) if scores else None,
            qualified_sector_count=len(groups),
            qualified_symbol_count=len(all_symbols),
        )
