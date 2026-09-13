"""Portfolio visual tokens must not leak into shared dashboard surfaces."""

from pathlib import Path


def test_typography_scope_and_layout_guardrails() -> None:
    static = Path(__file__).resolve().parents[3] / "src/athena/api/static"
    css = (static / "css/05c-my-portfolio-typography.css").read_text()
    imports = (static / "dashboard.css").read_text()
    assert imports.index("05b-my-portfolio.css") < imports.index("05c-my-portfolio-typography.css")
    for root in (
        "tab-my-portfolio", "my-portfolio-detail-modal", "my-portfolio-preview-modal",
        "my-portfolio-reset-modal", "my-portfolio-sync-overlay",
    ):
        assert f"#{root}" in css
    assert ":root" not in css
    assert "font-variant-numeric: tabular-nums" in css
    assert "font-family: var(--font-sans)" in css
    for forbidden in ("position:", "z-index:", "display: none", "--success:", "--danger:"):
        assert forbidden not in css
    assert "font-family: var(--font-mono)" not in css  # No numeric-font replacement.
    assert "--tone-good-text:" not in css
    html = (static / "index.html").read_text()
    assert "family=Inter:" in html
