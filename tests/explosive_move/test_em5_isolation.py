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
_FORBIDDEN_CANONICAL_IMPORTS = (
    "athena.decision",
    "athena.risk",
    "athena.portfolio",
    "athena.orders",
    "athena.execution",
    "athena.orchestration",
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
    canonical_roots = ("decision", "risk", "portfolio", "orders", "execution", "orchestration", "scoring", "confidence")
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
