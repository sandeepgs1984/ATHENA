"""EM-5 contract Section 12: no model learning in the live path --
enforced structurally, not just documented. `.fit(`/`LogisticRegression(`/
`Newton`, and any numpy/scikit-learn/scipy import, must never appear
anywhere under `athena.explosive_move.live` -- an AST scan, so this
holds regardless of what happens to be installed in a given
environment (numpy is not even installed here -- confirmed separately
while building the frozen-inference loader)."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_ROOT = REPO_ROOT / "src" / "athena" / "explosive_move" / "live"

_FORBIDDEN_IMPORT_PREFIXES = ("numpy", "sklearn", "scipy")
_FORBIDDEN_CALL_NAMES = {"fit", "LogisticRegression", "partial_fit"}


def _py_files() -> list[Path]:
    return sorted(LIVE_ROOT.rglob("*.py"))


def test_live_module_exists():
    assert _py_files(), f"no live scanner source found under {LIVE_ROOT}"


def test_no_numpy_sklearn_scipy_import_anywhere_in_the_live_module():
    offenders = []
    for py in _py_files():
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if any(name == prefix or name.startswith(f"{prefix}.") for prefix in _FORBIDDEN_IMPORT_PREFIXES):
                    offenders.append(f"{py.relative_to(REPO_ROOT)}:{node.lineno} imports {name}")
    assert offenders == [], f"live scanner must never import a fitting/numerical dependency: {offenders}"


def test_no_fit_or_logistic_regression_call_anywhere_in_the_live_module():
    offenders = []
    for py in _py_files():
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            else:
                name = None
            if name in _FORBIDDEN_CALL_NAMES:
                offenders.append(f"{py.relative_to(REPO_ROOT)}:{node.lineno} calls {name}(")
    assert offenders == [], f"live scanner must never fit/refit a model: {offenders}"


def test_no_newton_reference_anywhere_in_the_live_module():
    offenders = [
        str(py.relative_to(REPO_ROOT)) for py in _py_files() if "Newton" in py.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"live scanner must never reference Newton's method (a fitting concept): {offenders}"
