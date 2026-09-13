"""Keep narrow-screen hardening scoped and make the browser gate opt-in."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_responsive_rules_are_portfolio_scoped() -> None:
    static = ROOT / "src/athena/api/static"
    css = (static / "css/05d-my-portfolio-responsive.css").read_text()
    assert "@media (max-width: 920px)" in css
    assert "#app:has(#tab-my-portfolio.active) .sidebar" in css
    assert "#tab-my-portfolio .my-portfolio-holdings-thead-dock" in css
    assert "#tab-my-portfolio .my-portfolio-export-panel" in css
    assert "backdrop-filter" not in css
    assert '05d-my-portfolio-responsive.css?v=9.232.0' in (
        static / "dashboard.css"
    ).read_text()


@pytest.mark.skipif(
    os.environ.get("ATHENA_BROWSER_TESTS") != "1",
    reason="Set ATHENA_BROWSER_TESTS=1 with Playwright and Chrome installed",
)
def test_isolated_portfolio_browser_gate() -> None:
    node = shutil.which("node")
    assert node, "Browser gate requires Node"
    subprocess.run(
        [node, str(ROOT / "tests/browser/portfolio-validation.cjs")],
        check=True, cwd=ROOT, timeout=240,
    )
