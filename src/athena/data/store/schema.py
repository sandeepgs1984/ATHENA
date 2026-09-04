"""SQLite schema for the ATHENA repository (M1.5).

Follows ATHENA-002 §5: one ``candles`` table keyed by (instrument_id, timeframe,
ts_open) serves both daily and intraday data. Adds ``quotes`` and
``quarantine_records`` (persistence for M1.3 results). Prices/decimals are stored
as TEXT to preserve exact Decimal precision (no float drift). History tables are
append-only by discipline (inserts only; duplicates rejected by primary key).
"""

from __future__ import annotations

#: Bump when the schema changes; enables future explicit migrations.
SCHEMA_VERSION = 18

_DDL = (
    "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)",

    # ---------------------------------------------------------------- SU-1
    # The catalogue of what EXISTS on an exchange, kept deliberately separate
    # from `instruments`, which records what has been INGESTED. Conflating the
    # two is the defect ADR-011 exists to fix: today a symbol only "exists" to
    # ATHENA once somebody curates it into a candidate list.
    #
    # `series_source` and `classification_reason` are not decoration. The broker
    # dump types every NSE row "EQ" and ships no series column, so every series
    # here is inferred until an authoritative NSE list is obtained — and an
    # inference recorded without its provenance reads as a fact.
    """
    CREATE TABLE IF NOT EXISTS symbol_master (
        instrument_id         TEXT PRIMARY KEY,
        symbol                TEXT NOT NULL,
        exchange              TEXT NOT NULL,
        name                  TEXT,
        series                TEXT NOT NULL,
        series_source         TEXT NOT NULL,
        board                 TEXT NOT NULL,
        lot_size              INTEGER NOT NULL,
        tick_size             TEXT NOT NULL,
        status                TEXT NOT NULL,
        first_seen            TEXT NOT NULL,
        last_seen             TEXT NOT NULL,
        source                TEXT NOT NULL,
        classification_reason TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_symbol_master_series ON symbol_master(series)",
    "CREATE INDEX IF NOT EXISTS idx_symbol_master_board ON symbol_master(board)",

    # ---------------------------------------------------------------- SU-2
    # Group membership as metadata on the canonical symbol — many-to-many, and
    # deliberately NOT a duplicated symbol row per group (ADR-011 §2).
    #
    # Membership is dated because index constituents change: a screen run before
    # a rebalance must stay reproducible afterwards, which an undated membership
    # would silently break. The primary key therefore includes effective_date,
    # so a new snapshot adds rows rather than overwriting history.
    """
    CREATE TABLE IF NOT EXISTS symbol_group (
        instrument_id  TEXT NOT NULL,
        group_name     TEXT NOT NULL,
        kind           TEXT NOT NULL,
        effective_date TEXT NOT NULL,
        source         TEXT NOT NULL,
        PRIMARY KEY (instrument_id, group_name, effective_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_symbol_group_lookup "
    "ON symbol_group(group_name, effective_date DESC)",

    # ---------------------------------------------------------------- SU-6
    # A resolved universe, materialised so a *scanner* can read it as plain
    # data. This is what lets DarvaX consume a universe without importing an
    # ATHENA resolver: ADR-011 keeps the dependency direction by making a
    # universe data rather than a service call, exactly as ADR-010 §3 already
    # does for candles.
    #
    # Deliberately a snapshot, not a view: a scan must be reproducible against
    # the universe it actually ran on, even after a rebalance or a rule change.
    """
    CREATE TABLE IF NOT EXISTS resolved_universe (
        universe      TEXT NOT NULL,
        instrument_id TEXT NOT NULL,
        resolved_at   TEXT NOT NULL,
        PRIMARY KEY (universe, instrument_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_resolved_universe ON resolved_universe(universe)",

    """
    CREATE TABLE IF NOT EXISTS instruments (
        instrument_id TEXT PRIMARY KEY,
        isin          TEXT,
        symbol        TEXT NOT NULL,
        exchange      TEXT NOT NULL,
        series        TEXT NOT NULL,
        name          TEXT,
        sector        TEXT,
        lot_size      INTEGER NOT NULL,
        tick_size     TEXT NOT NULL,
        status        TEXT NOT NULL,
        listed_date   TEXT,
        delisted_date TEXT
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS candles (
        instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
        timeframe     TEXT NOT NULL,
        ts_open       TEXT NOT NULL,
        open          TEXT NOT NULL,
        high          TEXT NOT NULL,
        low           TEXT NOT NULL,
        close         TEXT NOT NULL,
        volume        INTEGER NOT NULL,
        source        TEXT NOT NULL,
        adjusted      INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (instrument_id, timeframe, ts_open)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_candles_range ON candles(instrument_id, timeframe, ts_open)",

    """
    CREATE TABLE IF NOT EXISTS quotes (
        instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
        ts            TEXT NOT NULL,
        last_price    TEXT NOT NULL,
        volume        INTEGER NOT NULL,
        source        TEXT NOT NULL,
        PRIMARY KEY (instrument_id, ts)
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS market_snapshots (
        ts           TEXT PRIMARY KEY,
        payload_json TEXT NOT NULL
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS institutional_flows (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        session_date  TEXT NOT NULL,
        fii_buy       TEXT NOT NULL,
        fii_sell      TEXT NOT NULL,
        fii_net       TEXT NOT NULL,
        dii_buy       TEXT NOT NULL,
        dii_sell      TEXT NOT NULL,
        dii_net       TEXT NOT NULL,
        provisional   INTEGER NOT NULL,
        source_id     TEXT NOT NULL,
        fetched_at    TEXT NOT NULL,
        run_id        TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_institutional_flows_session "
    "ON institutional_flows(session_date, fetched_at)",

    """
    CREATE TABLE IF NOT EXISTS corporate_actions (
        action_id     TEXT PRIMARY KEY,
        instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
        action_type   TEXT NOT NULL,
        ex_date       TEXT NOT NULL,
        details_json  TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ca_instrument ON corporate_actions(instrument_id, ex_date)",

    """
    CREATE TABLE IF NOT EXISTS quarantine_records (
        dataset_id     TEXT PRIMARY KEY,
        reason         TEXT NOT NULL,
        quarantined_ts TEXT NOT NULL,
        reports_json   TEXT NOT NULL
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id                    TEXT PRIMARY KEY,
        cycle_id                  TEXT NOT NULL,
        trigger                   TEXT NOT NULL,
        started_ts                TEXT NOT NULL,
        finished_ts               TEXT,
        status                    TEXT NOT NULL,
        software_version          TEXT NOT NULL,
        blueprint_version         TEXT NOT NULL,
        strategy_profile          TEXT NOT NULL,
        strategy_profile_version  TEXT NOT NULL,
        indicator_versions_json   TEXT NOT NULL,
        config_snapshot_id        TEXT NOT NULL,
        input_digest              TEXT NOT NULL DEFAULT '',
        detail_json               TEXT NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_runs_trigger_started ON runs(trigger, started_ts)",
    # Perf fix (2026-08-03): list_runs(limit=N) with NO trigger filter — the
    # dashboard's pipeline-runs list, candidates/validate verdict lookups,
    # market summary, diagnostics, notifications, and
    # OwnerValidationPipeline._last_full_universe_summary() all call it this
    # way — had no usable index for `ORDER BY started_ts DESC, run_id DESC`,
    # forcing a full "SCAN runs" that materializes every row's `detail_json`
    # (individual blobs run into single-digit MB as the universe/report size
    # has grown) just to sort and take the top N. Confirmed via EXPLAIN QUERY
    # PLAN + direct timing against the real production database: ~650ms for
    # limit=50 before this index, ~8ms after (~80x) — the dominant cause of
    # the reported "symbol validation went from <10s to 50s+" regression,
    # since every one of those call sites pays this cost.
    "CREATE INDEX IF NOT EXISTS idx_runs_started_ts ON runs(started_ts DESC, run_id DESC)",

    """
    CREATE TABLE IF NOT EXISTS decisions (
        decision_id         TEXT PRIMARY KEY,
        ts                  TEXT NOT NULL,
        run_id              TEXT NOT NULL,
        cycle_id            TEXT NOT NULL,
        decision_type       TEXT NOT NULL,
        explanation         TEXT NOT NULL,
        instrument_id       TEXT,
        direction           TEXT NOT NULL,
        score_ref           TEXT,
        confidence_ref      TEXT,
        risk_ref            TEXT,
        gate_results_json   TEXT NOT NULL,
        trade_plan_json     TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decisions(ts)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_run ON decisions(run_id)",
    # SCHEMA_VERSION 12: list_latest_decisions_by_instrument()'s correlated
    # NOT EXISTS subquery (one "is there a newer row for this instrument"
    # check per row) had no supporting index — owner-reported (2026-08-10),
    # timed at 1.7s against 91,241 decisions. Covers both sides of that
    # correlation (the outer instrument_id/ts/decision_id and the inner
    # newer.instrument_id/ts/decision_id) in one index.
    "CREATE INDEX IF NOT EXISTS idx_decisions_instrument_ts "
    "ON decisions(instrument_id, ts, decision_id)",

    """
    CREATE TABLE IF NOT EXISTS decision_traces (
        decision_ref TEXT PRIMARY KEY REFERENCES decisions(decision_id),
        stages_json  TEXT NOT NULL
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS decision_journal (
        entry_id     TEXT PRIMARY KEY,
        decision_ref TEXT NOT NULL REFERENCES decisions(decision_id),
        user_action  TEXT NOT NULL,
        action_ts    TEXT NOT NULL,
        notes        TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_journal_action_ts ON decision_journal(action_ts)",

    """
    CREATE TABLE IF NOT EXISTS trade_outcomes (
        outcome_id      TEXT PRIMARY KEY,
        decision_ref    TEXT NOT NULL REFERENCES decisions(decision_id),
        entry_price     TEXT NOT NULL,
        exit_price      TEXT NOT NULL,
        quantity        INTEGER NOT NULL,
        pnl             TEXT NOT NULL,
        holding_seconds INTEGER NOT NULL,
        adherence_json  TEXT NOT NULL DEFAULT '{}',
        closed_ts       TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_trade_outcomes_decision ON trade_outcomes(decision_ref)",
    "CREATE INDEX IF NOT EXISTS idx_trade_outcomes_closed ON trade_outcomes(closed_ts)",

    """
    CREATE TABLE IF NOT EXISTS owner_positions (
        position_id   TEXT PRIMARY KEY,
        instrument_id TEXT NOT NULL,
        opened_ts     TEXT NOT NULL,
        quantity      INTEGER NOT NULL,
        avg_price     TEXT NOT NULL,
        closed_ts     TEXT,
        exit_price    TEXT,
        decision_ref  TEXT,
        broker        TEXT NOT NULL DEFAULT '',
        notes         TEXT NOT NULL DEFAULT '',
        sector        TEXT NOT NULL DEFAULT '',
        meta_json     TEXT NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_owner_positions_opened ON owner_positions(opened_ts)",
    "CREATE INDEX IF NOT EXISTS idx_owner_positions_symbol ON owner_positions(instrument_id)",

    # ---------------------------------------------------------------- PS-P1
    # Isolated My Portfolio persistence. These tables model owner-confirmed
    # current holdings snapshots and derived analysis without mutating the
    # legacy/manual `owner_positions` ledger or duplicating ATHENA methodology.
    """
    CREATE TABLE IF NOT EXISTS portfolio_imports (
        import_id       TEXT PRIMARY KEY,
        filename        TEXT NOT NULL,
        source          TEXT NOT NULL,
        uploaded_at     TEXT NOT NULL,
        holdings_as_of  TEXT,
        parser_version  TEXT NOT NULL,
        status          TEXT NOT NULL,
        total_rows      INTEGER NOT NULL,
        accepted_rows   INTEGER NOT NULL,
        rejected_rows   INTEGER NOT NULL,
        unresolved_rows INTEGER NOT NULL,
        ambiguous_rows  INTEGER NOT NULL,
        confirmed_at    TEXT,
        provenance_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_portfolio_imports_uploaded "
    "ON portfolio_imports(uploaded_at)",

    """
    CREATE TABLE IF NOT EXISTS portfolio_import_rows (
        import_id              TEXT NOT NULL REFERENCES portfolio_imports(import_id),
        source_row_id          TEXT NOT NULL,
        source_row_number      INTEGER NOT NULL,
        original_values_json   TEXT NOT NULL,
        normalized_symbol      TEXT NOT NULL,
        raw_symbol             TEXT NOT NULL,
        quantity               INTEGER,
        avg_price              TEXT,
        mapping_state          TEXT NOT NULL,
        resolved_instrument_id TEXT,
        validation_errors_json TEXT NOT NULL DEFAULT '[]',
        warnings_json          TEXT NOT NULL DEFAULT '[]',
        metadata_json          TEXT NOT NULL DEFAULT '{}',
        PRIMARY KEY (import_id, source_row_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_portfolio_import_rows_state "
    "ON portfolio_import_rows(import_id, mapping_state)",
    "CREATE INDEX IF NOT EXISTS idx_portfolio_import_rows_instrument "
    "ON portfolio_import_rows(resolved_instrument_id)",

    """
    CREATE TABLE IF NOT EXISTS portfolio_holdings (
        holding_id        TEXT PRIMARY KEY,
        instrument_id     TEXT NOT NULL,
        quantity          INTEGER NOT NULL,
        avg_price         TEXT NOT NULL,
        imported_at       TEXT NOT NULL,
        updated_at        TEXT NOT NULL,
        source_import_id  TEXT NOT NULL REFERENCES portfolio_imports(import_id),
        source_row_id     TEXT NOT NULL,
        reconciliation_id TEXT,
        provenance_json   TEXT NOT NULL DEFAULT '{}',
        UNIQUE (instrument_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_updated "
    "ON portfolio_holdings(updated_at)",

    """
    CREATE TABLE IF NOT EXISTS portfolio_reconciliations (
        reconciliation_id TEXT PRIMARY KEY,
        import_id         TEXT NOT NULL REFERENCES portfolio_imports(import_id),
        reconciled_at     TEXT NOT NULL,
        action            TEXT NOT NULL,
        instrument_id     TEXT NOT NULL,
        before_json       TEXT,
        after_json        TEXT,
        provenance_json   TEXT NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_portfolio_reconciliations_import "
    "ON portfolio_reconciliations(import_id)",
    "CREATE INDEX IF NOT EXISTS idx_portfolio_reconciliations_instrument "
    "ON portfolio_reconciliations(instrument_id, reconciled_at)",

    """
    CREATE TABLE IF NOT EXISTS portfolio_sync_runs (
        sync_run_id          TEXT PRIMARY KEY,
        started_at           TEXT NOT NULL,
        finished_at          TEXT,
        status               TEXT NOT NULL,
        total_holdings       INTEGER NOT NULL,
        succeeded_holdings   INTEGER NOT NULL,
        failed_holdings      INTEGER NOT NULL,
        market_data_through  TEXT,
        validation_run_id    TEXT,
        analysis_version     TEXT NOT NULL,
        progress_json        TEXT NOT NULL DEFAULT '{}',
        per_symbol_json      TEXT NOT NULL DEFAULT '{}',
        error_json           TEXT NOT NULL DEFAULT '{}',
        provenance_json      TEXT NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_portfolio_sync_runs_started "
    "ON portfolio_sync_runs(started_at)",
    "CREATE INDEX IF NOT EXISTS idx_portfolio_sync_runs_status "
    "ON portfolio_sync_runs(status)",

    """
    CREATE TABLE IF NOT EXISTS portfolio_analysis_snapshots (
        snapshot_id          TEXT PRIMARY KEY,
        sync_run_id          TEXT NOT NULL REFERENCES portfolio_sync_runs(sync_run_id),
        instrument_id        TEXT NOT NULL,
        symbol               TEXT NOT NULL,
        analyzed_at          TEXT NOT NULL,
        price_as_of          TEXT,
        decision_as_of       TEXT,
        market_data_through  TEXT,
        analysis_version     TEXT NOT NULL,
        row_json             TEXT NOT NULL,
        freshness_json       TEXT NOT NULL,
        provenance_json      TEXT NOT NULL,
        unavailable_json     TEXT NOT NULL DEFAULT '[]',
        failure_json         TEXT NOT NULL DEFAULT '[]'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_portfolio_analysis_snapshots_run "
    "ON portfolio_analysis_snapshots(sync_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_portfolio_analysis_snapshots_instrument "
    "ON portfolio_analysis_snapshots(instrument_id, analyzed_at)",

    """
    CREATE TABLE IF NOT EXISTS owner_candidates (
        symbol    TEXT PRIMARY KEY,
        added_ts  TEXT NOT NULL,
        notes     TEXT NOT NULL DEFAULT '',
        active    INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_owner_candidates_active ON owner_candidates(active)",

    """
    CREATE TABLE IF NOT EXISTS saved_symbols (
        symbol    TEXT PRIMARY KEY,
        added_ts  TEXT NOT NULL,
        notes     TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_saved_symbols_added_ts ON saved_symbols(added_ts)",

    # ---------------------------------------------------------------- ID-6C
    # Durable, auditable persistence for EntryQualification (ID-6A/ID-6B.2)
    # observations. Persists what the pure engine already concluded; adds no
    # methodology. Append-only by discipline: an EntryQualification is a
    # point-in-time, non-sticky observation (ID-6B measured ~40% checkpoint
    # flicker), so a later observation for the same instrument/session is a
    # NEW row, never an overwrite of an earlier one.
    #
    # The composite primary key is the logical/idempotent observation
    # identity: instrument + session date + evaluation checkpoint (as_of) +
    # the bound canonical Decision + methodology version. A deterministic
    # engine re-evaluating the identical logical candidate (even under a
    # different run_id/cycle_id) must produce the identical payload, so a
    # repeat write of the same key is a no-op; a write with the same key but
    # a genuinely different payload is an integrity problem the repository
    # rejects loudly (see SqliteRepository.save_entry_qualification).
    # run_id/cycle_id are informational provenance only, deliberately NOT
    # part of the identity key.
    """
    CREATE TABLE IF NOT EXISTS entry_qualifications (
        instrument_id       TEXT NOT NULL,
        session_date        TEXT NOT NULL,
        as_of                TEXT NOT NULL,
        decision_id          TEXT NOT NULL REFERENCES decisions(decision_id),
        methodology_version  TEXT NOT NULL,
        run_id               TEXT NOT NULL,
        cycle_id             TEXT NOT NULL,
        decision_type        TEXT NOT NULL,
        state                TEXT NOT NULL,
        evidence_finality    TEXT NOT NULL,
        confirmation         TEXT NOT NULL,
        reason_codes_json    TEXT NOT NULL,
        evidence_refs_json   TEXT NOT NULL,
        config_snapshot_id   TEXT,
        explanation          TEXT NOT NULL,
        persisted_at         TEXT NOT NULL,
        PRIMARY KEY (instrument_id, session_date, as_of, decision_id, methodology_version)
    )
    """,
    # Supports latest_entry_qualification_for_decision(): decision_id is the
    # 4th column of the primary key's own composite index, so it is not a
    # usable leftmost prefix for a decision_id-only lookup — this explicit
    # index is required. latest_entry_qualification_for_instrument_session()
    # needs no separate index: the primary key's own implicit index already
    # begins (instrument_id, session_date, as_of), which is exactly its
    # WHERE + ORDER BY shape.
    "CREATE INDEX IF NOT EXISTS idx_entry_qualifications_decision "
    "ON entry_qualifications(decision_id, as_of DESC)",

    # ---------------------------------------------------------------- ID-7A
    # Durable, auditable persistence for EntryActionability (ADR-015,
    # ID-7A0/ID-7A0.1, methodology frozen by ID-7B/ID-7B.1/ID-7B.2/
    # ID-7B.2.1) observations. Same append-only discipline as
    # entry_qualifications above: a persisted row is immutable evaluation-
    # time truth (dimension A) and is never updated in place; read-time
    # currentness (dimension B, `is_currently_usable`) is deliberately NOT
    # represented by any column here.
    #
    # Identity is EntryActionability's own full composite key: the
    # upstream EntryQualification's entire identity, copied verbatim
    # (instrument_id, session_date, entry_qualification_as_of, decision_id,
    # entry_qualification_methodology_version — never reduced to
    # decision_id alone), plus this artifact's own
    # entry_actionability_as_of/entry_actionability_methodology_version.
    # There is no surrogate id. run_id/cycle_id are informational
    # provenance only, deliberately NOT part of the identity key, mirroring
    # entry_qualifications. The single-column FK on decision_id alone only
    # proves the canonical Decision exists — it does not prove the full
    # upstream EQ identity is truthful; that binding is validated at the
    # repository layer (see SqliteRepository.save_entry_actionability),
    # exactly mirroring _validate_entry_qualification_decision_binding.
    #
    # Value-object columns (entry_reference/entry_location_context/
    # operative_invalidation/reward) are nested-JSON blobs, one column
    # each, per the existing trade_plan_json precedent — not flattened
    # fields. They are populated iff state == ACTIONABLE; NULL otherwise.
    # opening_range_context_json is always-independently-optional context
    # and may be NULL even when state == ACTIONABLE.
    """
    CREATE TABLE IF NOT EXISTS entry_actionabilities (
        instrument_id                            TEXT NOT NULL,
        session_date                             TEXT NOT NULL,
        entry_qualification_as_of                TEXT NOT NULL,
        decision_id                               TEXT NOT NULL REFERENCES decisions(decision_id),
        entry_qualification_methodology_version   TEXT NOT NULL,
        entry_actionability_as_of                 TEXT NOT NULL,
        entry_actionability_methodology_version   TEXT NOT NULL,
        run_id                                    TEXT NOT NULL,
        cycle_id                                  TEXT NOT NULL,
        decision_type                             TEXT NOT NULL,
        direction                                 TEXT NOT NULL,
        entry_qualification_state                 TEXT NOT NULL,
        state                                      TEXT NOT NULL,
        reason_codes_json                         TEXT NOT NULL,
        evidence_finality                         TEXT NOT NULL,
        evidence_as_of                            TEXT,
        entry_reference_json                      TEXT,
        entry_location_context_json               TEXT,
        operative_invalidation_json                TEXT,
        reward_json                                TEXT,
        opening_range_context_json                 TEXT,
        evaluated_at                               TEXT NOT NULL,
        explanation                                TEXT NOT NULL,
        persisted_at                               TEXT NOT NULL,
        PRIMARY KEY (
            instrument_id, session_date, entry_qualification_as_of,
            decision_id, entry_qualification_methodology_version,
            entry_actionability_as_of, entry_actionability_methodology_version
        )
    )
    """,
    # Supports latest_entry_actionability_for_entry_qualification(): the
    # primary key's own leading columns already cover an exact-EQ-identity
    # lookup ordered by entry_actionability_as_of (its first five columns
    # are exactly that identity), so no separate index is needed for that
    # case. decision_id is not a usable leftmost prefix of the primary
    # key's implicit index for a decision_id-only "latest for this
    # Decision" query, mirroring idx_entry_qualifications_decision above.
    "CREATE INDEX IF NOT EXISTS idx_entry_actionabilities_decision "
    "ON entry_actionabilities(decision_id, entry_actionability_as_of DESC)",
    # Supports latest_entry_actionability_for_instrument_session() and
    # list_entry_actionabilities_for_instrument_session(): unlike
    # entry_qualifications (whose primary key already begins
    # (instrument_id, session_date, as_of)), this table's primary key
    # leads with entry_qualification_as_of, not entry_actionability_as_of,
    # so an explicit index is required for instrument/session history
    # ordered by this artifact's own evaluation instant.
    "CREATE INDEX IF NOT EXISTS idx_entry_actionabilities_instrument_session "
    "ON entry_actionabilities(instrument_id, session_date, entry_actionability_as_of DESC)",

    """
    CREATE TABLE IF NOT EXISTS ops_meta (
        key         TEXT PRIMARY KEY,
        value       TEXT NOT NULL,
        updated_ts  TEXT NOT NULL
    )
    """,
)


def ddl_statements() -> tuple[str, ...]:
    """The ordered DDL statements that build the schema (idempotent)."""
    return _DDL
