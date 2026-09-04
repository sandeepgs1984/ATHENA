"""EM-5 isolation contract -- proves the boundaries ADR-012 requires,
the same way DarvaX's own DX-1 suite proves ADR-010's (test_dx1_isolation.py):
static import-graph scans, not runtime checks that only cover one code
path. This closes the real gap found while grounding the EM-5 contract
proposal: ADR-012's own "Required Controls" section already claimed
this test existed; it did not until now.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "athena"
EXPLOSIVE_MOVE_ROOT = SRC_ROOT / "explosive_move"

#: The one file allowed to import Kite provider/transport machinery from
#: within explosive_move -- EM-5's own narrow, auditable, batched
#: checkpoint-reference-price collector (Owner-approved amendment,
#: 2026-08-28: "only the checkpoint-reference-price collector may call
#: the existing batched Kite /quote capability").
APPROVED_QUOTE_ADAPTER = EXPLOSIVE_MOVE_ROOT / "live" / "checkpoint_reference_price.py"

#: Canonical ATHENA modules whose decisions/risk/execution/orchestration
#: EMR must never influence or be influenced by (ADR-012 sections 1, 11).
#: Extended by EM-7A (ADR-014 Section 22) to close a real coverage gap
#: the EM-7 discovery found: the original list checked
#: decision/risk/portfolio/orders/execution/orchestration only, leaving
#: scoring/confidence/intraday/darvax and canonical ops/scheduling
#: runtime completely unpoliced in this direction.
_FORBIDDEN_CANONICAL_IMPORTS = (
    "athena.decision",
    "athena.risk",
    "athena.portfolio",
    "athena.orders",
    "athena.execution",
    "athena.orchestration",
    "athena.scoring",
    "athena.confidence",
    "athena.intraday",
    "athena.darvax",
    "athena.ops",
    "athena.scheduling",
)

#: EM-7A (ADR-014 Section 22) / EM-7B (ADR-014 Section 34): the only
#: files allowed to import canonical `SqliteRepository` from within the
#: *live runtime* path (`explosive_move/live/`) -- EM-5's own narrow,
#: read-only market-data adapter (`market_data_port.py`, no write method
#: of any kind: "a narrow Protocol over already-ingested SqliteRepository
#: data, with no write method of any kind"), and EM-7B's worker
#: (`worker.py`), which needs the type only to accept the caller-supplied
#: `athena_repo` object and forward it, unexamined, to
#: `SqliteEmrMarketDataAdapter` -- never to call a write method on it
#: itself (verified below, the same grep-based proof already applied to
#: `market_data_port.py`). Deliberately scoped to `live/` only:
#: `em1r2_materialize.py` (an offline, argparse-driven research-
#: materialization script, not part of any live path) also imports
#: `SqliteRepository` directly, but that is legitimate research tooling
#: outside the runtime boundary this test polices -- never silently
#: exempted by widening this constant, only by living outside `live/` in
#: the first place.
APPROVED_LIVE_RUNTIME_SQLITE_REPOSITORY_IMPORTERS = (
    EXPLOSIVE_MOVE_ROOT / "live" / "market_data_port.py",
    EXPLOSIVE_MOVE_ROOT / "live" / "worker.py",
)

#: Kite-quote-touching import targets -- only the approved quote adapter
#: may reference these anywhere in explosive_move. Deliberately narrow:
#: athena.data.providers has other, already-approved adapters (e.g. the
#: NSE corporate-action provider EM-1r2 legitimately imports) that have
#: nothing to do with the live checkpoint-price concern this test polices.
_KITE_QUOTE_TOUCHING_IMPORTS = (
    "athena.data.providers.kite_provider",
    "athena.data.providers.kite_transport",
    "athena.data.providers.kite_ltp",
    "athena.data.em5_checkpoint_price_diagnostic",
)


def _imported_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    if isinstance(node, ast.ImportFrom):
        return [node.module or ""]
    return []


def _scan(py_files: list[Path]) -> dict[Path, list[tuple[int, str]]]:
    """Returns {file: [(lineno, imported_name), ...]} for every import
    statement in every given file."""

    result: dict[Path, list[tuple[int, str]]] = {}
    for py in py_files:
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        imports = []
        for node in ast.walk(tree):
            for name in _imported_names(node):
                if name:
                    imports.append((node.lineno, name))
        result[py] = imports
    return result


def test_explosive_move_never_imports_canonical_decision_risk_execution():
    offenders: list[str] = []
    files = list(EXPLOSIVE_MOVE_ROOT.rglob("*.py"))
    for py, imports in _scan(files).items():
        for lineno, name in imports:
            if any(name == forbidden or name.startswith(f"{forbidden}.") for forbidden in _FORBIDDEN_CANONICAL_IMPORTS):
                offenders.append(f"{py.relative_to(REPO_ROOT)}:{lineno} imports {name}")
    assert offenders == [], (
        "athena.explosive_move must never import canonical decision/risk/"
        f"portfolio/orders/execution/orchestration modules; found: {offenders}"
    )


def test_canonical_decision_modules_never_import_explosive_move():
    """The other direction of the same boundary: ADR-012 Section 1
    requires EMR never contribute to or be reachable from canonical
    ATHENA scoring/confidence/risk/decision/TradePlan. Research
    orchestration under athena.data.* legitimately imports
    athena.explosive_move (that's the whole EM-1..EM-4E pattern) -- this
    check is scoped to the canonical decision-adjacent packages only,
    not "nothing outside explosive_move," which would be the wrong rule."""

    offenders: list[str] = []
    canonical_roots = (
        "decision", "risk", "portfolio", "orders", "execution", "orchestration",
        "scoring", "confidence", "intraday", "darvax",
    )
    files = [py for root in canonical_roots for py in (SRC_ROOT / root).rglob("*.py") if (SRC_ROOT / root).is_dir()]
    for py, imports in _scan(files).items():
        for lineno, name in imports:
            if name == "athena.explosive_move" or name.startswith("athena.explosive_move."):
                offenders.append(f"{py.relative_to(REPO_ROOT)}:{lineno} imports {name}")
    assert offenders == [], f"canonical decision-adjacent modules must not import athena.explosive_move: {offenders}"


def test_only_the_approved_quote_adapter_touches_kite_quote_machinery():
    offenders: list[str] = []
    files = [py for py in EXPLOSIVE_MOVE_ROOT.rglob("*.py") if py != APPROVED_QUOTE_ADAPTER]
    for py, imports in _scan(files).items():
        for lineno, name in imports:
            matches = any(name == target or name.startswith(f"{target}.") for target in _KITE_QUOTE_TOUCHING_IMPORTS)
            if matches:
                offenders.append(f"{py.relative_to(REPO_ROOT)}:{lineno} imports {name}")
    assert offenders == [], (
        "only the approved checkpoint-reference-price collector may import "
        f"Kite quote provider/transport machinery within explosive_move; found: {offenders}"
    )


def test_approved_quote_adapter_exists_and_is_the_only_exception():
    assert APPROVED_QUOTE_ADAPTER.is_file(), (
        f"the approved quote adapter {APPROVED_QUOTE_ADAPTER} must exist -- this "
        "test's exemption list has nothing to police otherwise"
    )


def test_only_the_approved_market_data_adapter_touches_sqlite_repository_in_live_runtime():
    """EM-7A (ADR-014 Section 22), extended by EM-7B (Section 34): no
    canonical write-capable repository may reach the *live runtime* path
    through any file other than the two approved importers. Scoped
    deliberately to `explosive_move/live/` only -- offline research
    scripts elsewhere in the package (e.g. `em1r2_materialize.py`)
    legitimately construct `SqliteRepository` for one-shot materialization
    and are out of scope for this specific runtime-boundary guarantee,
    not silently exempted."""

    live_root = EXPLOSIVE_MOVE_ROOT / "live"
    offenders: list[str] = []
    files = [py for py in live_root.rglob("*.py") if py not in APPROVED_LIVE_RUNTIME_SQLITE_REPOSITORY_IMPORTERS]
    for py, imports in _scan(files).items():
        for lineno, name in imports:
            if name == "athena.data.store.repository" or name.startswith("athena.data.store.repository."):
                offenders.append(f"{py.relative_to(REPO_ROOT)}:{lineno} imports {name}")
    assert offenders == [], (
        "only the approved read-only market-data adapter / EM-7B worker may import canonical "
        f"SqliteRepository within explosive_move/live/; found: {offenders}"
    )


def test_approved_live_runtime_sqlite_importers_exist_and_are_read_only_by_construction():
    # No write-method name may appear as an attribute call anywhere in
    # either approved module -- each must remain structurally read-only,
    # never gaining a write capability merely because it imports the
    # canonical (read+write-capable) class.
    forbidden_write_calls = (
        "add_candles(", "add_quotes(", "add_snapshot(", "save_decision(",
        "save_run(", "upsert_instrument(", "save_quarantine(",
    )
    for approved in APPROVED_LIVE_RUNTIME_SQLITE_REPOSITORY_IMPORTERS:
        assert approved.is_file(), (
            f"the approved live-runtime SqliteRepository importer {approved} must exist -- "
            "this test's exemption list has nothing to police otherwise"
        )
        source = approved.read_text(encoding="utf-8")
        offenders = [call for call in forbidden_write_calls if call in source]
        assert offenders == [], (
            f"{approved.relative_to(REPO_ROOT)} must remain read-only; "
            f"found forbidden write-method call(s): {offenders}"
        )
