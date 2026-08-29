"""ADR-003 Amendment 1 (ID-P0) — one canonical pipeline mechanism, not two.

ID-0's runtime audit found `domain.context.PipelineContext`/`ContextDelta`/
`IntelligenceModule` had zero non-test production callers, while
`runtime.workflow.WorkflowContext`/`WorkflowStage`/`WorkflowEngine` is
ATHENA's real, live pipeline runtime (ADR-003 Amendment 1). This is a static
import-graph scan — the same technique ADR-010's DX-1 isolation suite uses
for the DarvaX boundary (`tests/darvax/test_dx1_isolation.py`) — that fails
the moment any new production code (most importantly, a future Intraday
Intelligence stage) starts using the dormant contract instead of the
canonical one, so the ambiguity ID-0 found cannot silently reappear.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "athena"

#: The dormant types' own definition/re-export sites — the only files allowed
#: to name them (ADR-003 Amendment 1: not deleted yet, just must not be used).
_DEFINITION_SITES = {
    SRC_ROOT / "domain" / "context.py",
    SRC_ROOT / "domain" / "interfaces.py",
    SRC_ROOT / "domain" / "__init__.py",
}

_DORMANT_NAMES = {"PipelineContext", "ContextDelta", "IntelligenceModule"}


def _imported_names(node: ast.Import | ast.ImportFrom) -> set[str]:
    if isinstance(node, ast.ImportFrom) and node.module == "athena.domain.context":
        return {alias.asname or alias.name for alias in node.names}
    if isinstance(node, ast.ImportFrom) and node.module == "athena.domain":
        return {
            alias.asname or alias.name
            for alias in node.names
            if alias.name in _DORMANT_NAMES
        }
    if isinstance(node, ast.ImportFrom) and node.module == "athena.domain.interfaces":
        return {
            alias.asname or alias.name
            for alias in node.names
            if alias.name == "IntelligenceModule"
        }
    return set()


def test_no_production_module_uses_the_dormant_pipeline_context_contract():
    offenders: list[str] = []
    for py in SRC_ROOT.rglob("*.py"):
        if py in _DEFINITION_SITES:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = _imported_names(node) if isinstance(node, ast.ImportFrom) else set()
                if names:
                    offenders.append(
                        f"{py.relative_to(REPO_ROOT)}:{node.lineno} imports {sorted(names)}"
                    )
    assert offenders == [], (
        "PipelineContext/ContextDelta/IntelligenceModule are dormant/legacy "
        "(ADR-003 Amendment 1) — new production code, including Intraday "
        "Intelligence stages, must use athena.runtime.workflow instead. "
        f"Offending import(s): {offenders}"
    )


def test_canonical_runtime_is_the_one_actually_wired_into_the_live_scan():
    """`OwnerValidationPipeline._scan_eligible` — the real per-instrument
    pipeline every PREMARKET/REFRESH/FAST/CLOSING/Revalidate/full-validation
    cycle runs — must build its stage graph from `athena.runtime.workflow`,
    not the dormant contract. A cheap source-level check: importing the
    dormant names is already forbidden repo-wide by the test above, so this
    only needs to confirm the canonical names are genuinely present here."""
    owner_validation_src = (SRC_ROOT / "ops" / "owner_validation.py").read_text(encoding="utf-8")
    for expected in ("WorkflowEngine", "WorkflowStage", "build_definition"):
        assert expected in owner_validation_src, (
            f"OwnerValidationPipeline no longer references {expected} — "
            "the canonical pipeline runtime (ADR-003 Amendment 1) may have "
            "been replaced; if intentional, update this test and ADR-003 together"
        )
