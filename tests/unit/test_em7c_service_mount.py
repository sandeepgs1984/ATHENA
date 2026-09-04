"""EM-7C: the isolated EMR live-shadow worker's production service-mount
boundary (`athena.cli._mount_emr_worker`).

Never lets a real `EmrWorker` background thread start in these tests --
its immediate first tick would use real wall-clock time and could
attempt a real Kite `/quote` call depending on when the suite happens to
run. The "worker actually mounts" test substitutes a spy for `EmrWorker`
itself; `test_em7b_worker.py` already exhaustively covers the worker's
own tick behavior with injected time and a fake collector.
"""

from __future__ import annotations

import json

from athena.cli import _mount_emr_worker
from athena.config.loader import load_config


def _seed_frozen_model_manifest(config_dir, *, version: str = "v1") -> None:
    manifest_dir = config_dir / "emr" / "frozen_models" / version
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "FROZEN_MODEL_MANIFEST.json").write_text(
        json.dumps({"version": version}), encoding="utf-8",
    )


def _write_operational_config(config_dir, **overrides) -> None:
    payload = {"enabled": False}
    payload.update(overrides)
    (config_dir / "emr" / "operational.json").write_text(json.dumps(payload), encoding="utf-8")


class TestDisabledMountIsInert:
    def test_disabled_config_mounts_nothing_and_touches_nothing(self, config_dir, tmp_path, monkeypatch):
        # An explicit file (as opposed to the "missing file" case covered
        # separately below) still passes through frozen-source validation
        # regardless of `enabled` -- seed a manifest so this test isolates
        # the one thing it actually means to prove: disabled short-circuits
        # before EmrRepository/canonical-repo construction, not before
        # config validation.
        _seed_frozen_model_manifest(config_dir)
        _write_operational_config(config_dir, enabled=False)
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        opened = {"open_repo": 0, "emr_repo_init": 0}

        def _spy_open_repo(*_a, **_k):
            opened["open_repo"] += 1

        monkeypatch.setattr("athena.cli._open_repo", _spy_open_repo)

        import athena.explosive_move.store.repository as emr_repo_module

        real_init = emr_repo_module.EmrRepository.initialize
        monkeypatch.setattr(
            emr_repo_module.EmrRepository, "initialize",
            lambda self: (opened.__setitem__("emr_repo_init", opened["emr_repo_init"] + 1), real_init(self))[1],
        )

        worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert worker is None
        assert athena_repo is None
        assert opened["open_repo"] == 0, "a disabled mount must never open the canonical repository"
        assert opened["emr_repo_init"] == 0, "a disabled mount must never initialize EmrRepository"
        assert not emr_db_path.exists(), "a disabled mount must never create db/emr.db"

    def test_missing_operational_config_file_is_also_inert(self, config_dir, tmp_path):
        """No config/emr/operational.json at all -- the safe, inert
        default (enabled=False) -- must behave identically to an
        explicit disabled file."""
        (config_dir / "emr" / "operational.json").unlink(missing_ok=True)
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert worker is None
        assert athena_repo is None
        assert not emr_db_path.exists()


class TestEnabledMountOwnsAnIndependentWorker:
    def test_enabled_config_constructs_and_starts_an_independent_worker(self, config_dir, tmp_path, monkeypatch):
        _seed_frozen_model_manifest(config_dir)
        _write_operational_config(config_dir, enabled=True)
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        captured: dict = {}

        class _SpyWorker:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def start(self):
                captured["started"] = True

        monkeypatch.setattr("athena.explosive_move.live.worker.EmrWorker", _SpyWorker)

        worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert isinstance(worker, _SpyWorker)
        assert captured.get("started") is True
        assert athena_repo is not None
        assert emr_db_path.exists(), "an enabled mount must create db/emr.db intentionally"
        assert captured["operational_config"].enabled is True
        assert captured["config_dir"] == config_dir
        assert callable(captured["collect_checkpoint_prices"]), (
            "the production mount must wire the real checkpoint-price collector, not omit it"
        )
        athena_repo.close()

    def test_worker_construction_failure_does_not_propagate(self, config_dir, tmp_path, monkeypatch):
        """EMR failure must never fail the canonical service that calls
        _mount_emr_worker -- proven by forcing EmrWorker construction to
        raise and confirming the caller still gets a clean (None, None)."""
        _seed_frozen_model_manifest(config_dir)
        _write_operational_config(config_dir, enabled=True)
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        def _raising_worker(**_kwargs):
            raise RuntimeError("synthetic EMR worker construction failure")

        monkeypatch.setattr("athena.explosive_move.live.worker.EmrWorker", _raising_worker)

        worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert worker is None
        assert athena_repo is None, "the partially-opened canonical repo must be closed, not leaked"

    def test_uses_the_real_authorized_checkpoint_price_collector(self, config_dir, tmp_path, monkeypatch):
        """Confirms production wiring resolves the existing authorized
        live collector (checkpoint_reference_price.collect_checkpoint_reference_prices),
        never a second/new provider client."""
        _seed_frozen_model_manifest(config_dir)
        _write_operational_config(config_dir, enabled=True)
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        captured: dict = {}

        class _SpyWorker:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def start(self):
                pass

        monkeypatch.setattr("athena.explosive_move.live.worker.EmrWorker", _SpyWorker)

        spy_calls = []

        def _spy_collector(**kwargs):
            spy_calls.append(kwargs)
            return ({}, (), 0)

        monkeypatch.setattr(
            "athena.explosive_move.live.checkpoint_reference_price.collect_checkpoint_reference_prices",
            _spy_collector,
        )

        _worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)
        captured["collect_checkpoint_prices"](instrument_ids=(), checkpoint_instant=None, max_delay_seconds=1.0)

        assert len(spy_calls) == 1
        assert spy_calls[0]["config_dir"] == config_dir
        athena_repo.close()


class TestNoDuplicateHistoricalIngestion:
    def test_mounted_worker_reads_candles_through_the_read_only_adapter_never_a_provider(
        self, config_dir, tmp_path, monkeypatch,
    ):
        """ADR-012 isolation/performance invariant: the production mount
        must hand the worker an athena_repo it reads candle history from
        via SqliteEmrMarketDataAdapter -- a read-only wrapper over
        already-ingested SqliteRepository data (no candle-provider
        dependency of its own, structurally proven by
        test_em5_isolation.py's own import-graph scan) -- never a second
        historical-ingestion path. This test confirms the production
        wiring hands the worker the real SqliteRepository (the canonical
        already-ingested store), not some other provider-backed object."""
        _seed_frozen_model_manifest(config_dir)
        _write_operational_config(config_dir, enabled=True)
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        captured: dict = {}

        class _SpyWorker:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def start(self):
                pass

        monkeypatch.setattr("athena.explosive_move.live.worker.EmrWorker", _SpyWorker)

        from athena.data.store.repository import SqliteRepository

        _worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert isinstance(captured["athena_repo"], SqliteRepository), (
            "the worker must be handed the canonical already-ingested repository directly -- "
            "worker.py's own run_once wraps it in SqliteEmrMarketDataAdapter internally, never "
            "a provider client"
        )
        assert captured["athena_repo"] is athena_repo
        athena_repo.close()


class TestFailClosedForEmrFailOpenForCanonical:
    """EM-7C.1: every EMR-specific mount/setup step -- config loading and
    validation included -- must be isolated from `_cmd_serve`. An
    EMR-specific failure means "EMR unavailable for this process," never
    "ATHENA unavailable." Malformed/invalid configuration must never be
    silently reinterpreted as a valid disabled file -- it must surface as
    a bounded warning with EMR simply not mounting."""

    def test_malformed_json_never_propagates_and_mounts_nothing(self, config_dir, tmp_path, capsys):
        (config_dir / "emr" / "operational.json").write_text("{not valid json", encoding="utf-8")
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert worker is None
        assert athena_repo is None
        assert not emr_db_path.exists()
        err = capsys.readouterr().err
        assert "WARNING: EMR unavailable for this process" in err
        assert len(err) < 2000, "the warning must be bounded, never an unbounded traceback dump"

    def test_unapproved_base_universe_never_propagates_and_mounts_nothing(self, config_dir, tmp_path, capsys):
        _seed_frozen_model_manifest(config_dir)
        _write_operational_config(config_dir, enabled=True, base_universe="some-other-universe")
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert worker is None
        assert athena_repo is None
        assert not emr_db_path.exists()
        assert "WARNING: EMR unavailable for this process" in capsys.readouterr().err

    def test_missing_frozen_model_manifest_never_propagates_and_mounts_nothing(self, config_dir, tmp_path, capsys):
        # Deliberately do NOT seed a frozen-model manifest.
        _write_operational_config(config_dir, enabled=True)
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert worker is None
        assert athena_repo is None
        assert not emr_db_path.exists()
        assert "WARNING: EMR unavailable for this process" in capsys.readouterr().err

    def test_manifest_version_mismatch_never_propagates_and_mounts_nothing(self, config_dir, tmp_path, capsys):
        manifest_dir = config_dir / "emr" / "frozen_models" / "v1"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "FROZEN_MODEL_MANIFEST.json").write_text(
            json.dumps({"version": "v0-corrupted"}), encoding="utf-8",
        )
        _write_operational_config(config_dir, enabled=True)
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert worker is None
        assert athena_repo is None
        assert "WARNING: EMR unavailable for this process" in capsys.readouterr().err

    def test_emr_repository_initialize_failure_survives_and_cleans_up(self, config_dir, tmp_path, monkeypatch, capsys):
        """Injects a failure from EmrRepository.initialize() specifically
        -- proves canonical survival AND that the already-opened
        canonical read-repository is closed, not leaked."""
        _seed_frozen_model_manifest(config_dir)
        _write_operational_config(config_dir, enabled=True)
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        import athena.cli as cli_module

        closed = {"count": 0}
        real_open_repo = cli_module._open_repo

        def _spy_open_repo(*a, **k):
            repo = real_open_repo(*a, **k)
            real_close = repo.close

            def _spy_close():
                closed["count"] += 1
                real_close()

            repo.close = _spy_close
            return repo

        monkeypatch.setattr(cli_module, "_open_repo", _spy_open_repo)

        import athena.explosive_move.store.repository as emr_repo_module

        def _raising_initialize(self):
            raise RuntimeError("synthetic EmrRepository.initialize() failure")

        monkeypatch.setattr(emr_repo_module.EmrRepository, "initialize", _raising_initialize)

        worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert worker is None
        assert athena_repo is None
        assert closed["count"] == 1, "the canonical read-repository opened before the failure must be closed"
        assert "WARNING: EMR unavailable for this process" in capsys.readouterr().err

    def test_worker_start_failure_survives_and_cleans_up(self, config_dir, tmp_path, monkeypatch, capsys):
        """A failure AFTER EmrRepository.initialize() succeeds (e.g. in
        EmrWorker construction/start itself) must also be caught, proving
        the protective boundary covers the whole mount sequence, not just
        its first step."""
        _seed_frozen_model_manifest(config_dir)
        _write_operational_config(config_dir, enabled=True)
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        def _raising_worker(**_kwargs):
            raise RuntimeError("synthetic EmrWorker construction failure")

        monkeypatch.setattr("athena.explosive_move.live.worker.EmrWorker", _raising_worker)

        worker, athena_repo = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert worker is None
        assert athena_repo is None, "the canonical read-repository must still be closed on a later-stage failure"
        assert emr_db_path.exists(), (
            "a partially initialized db/emr.db from a failure AFTER schema init succeeded "
            "is legitimate diagnostic evidence -- never auto-deleted"
        )
        assert "WARNING: EMR unavailable for this process" in capsys.readouterr().err

    def test_canonical_bootstrap_path_is_reached_regardless_of_mount_outcome(self, config_dir, tmp_path):
        """Service-level proof (without starting a real uvicorn server):
        _mount_emr_worker itself never raises for any of the failure
        modes above, and always returns a plain (worker, repo) tuple --
        the exact contract _cmd_serve's own subsequent lines (building
        the dashboard URL, printing status, calling uvicorn.run) depend
        on. Since _cmd_serve has no try/except around its call to
        _mount_emr_worker (by design -- the isolation lives inside the
        mount function itself, not as a second outer safety net), the
        mount function returning cleanly IS the proof that control
        reaches _cmd_serve's normal runtime setup afterward. A full
        uvicorn-server integration test would only re-prove this same
        fact at far higher cost and flakiness (real sockets, real
        threads) -- not attempted, per the authorization's own
        instruction not to introduce a large _cmd_serve refactor merely
        for testing."""
        (config_dir / "emr" / "operational.json").write_text("{not valid json", encoding="utf-8")
        cfg = load_config(config_dir)
        emr_db_path = tmp_path / "emr" / "emr.db"

        result = _mount_emr_worker(cfg, config_dir=config_dir, emr_db_path=emr_db_path)

        assert isinstance(result, tuple)
        assert len(result) == 2
        worker, athena_repo = result
        # The exact shape _cmd_serve destructures and later passes to its
        # own finally-block cleanup (`if emr_worker is not None: ...`).
        assert worker is None
        assert athena_repo is None
