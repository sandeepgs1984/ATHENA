"""Risk workspace structure and heatmap tone coverage preserve existing controls."""

from html.parser import HTMLParser
from pathlib import Path


class Sections(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[dict[str, str | None]] = []
        self.heatmap_in_risk = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "section":
            return
        attributes = dict(attrs)
        if attributes.get("id") == "my-portfolio-heatmap-section":
            self.heatmap_in_risk = any(
                "my-portfolio-risk-panel" in str(parent.get("class"))
                for parent in self.stack
            )
        self.stack.append(attributes)

    def handle_endtag(self, tag: str) -> None:
        if tag == "section":
            self.stack.pop()


def test_risk_workspace_preserves_heatmap_controls_and_tone_coverage() -> None:
    static = Path(__file__).resolve().parents[3] / "src/athena/api/static"
    html = (static / "index.html").read_text()
    css = (static / "css/05b-my-portfolio.css").read_text()
    js = (static / "js/08b-my-portfolio.js").read_text()
    sections = Sections()
    sections.feed(html)
    assert sections.heatmap_in_risk
    assert not sections.stack
    for control in ("size", "color", "toggle"):
        assert html.count(f'id="my-portfolio-heatmap-{control}"') == 1
    assert "--heatmap-label-color, var(--tone-neutral-text)" in css
    for tone in ("positive", "negative", "danger", "neutral", "muted", "mixed"):
        assert f".tone-{tone}" in css
    for tone in ("good", "bad", "warn"):
        assert f"--heatmap-label-color: var(--tone-{tone}-text)" in css
    assert "my-portfolio-risk-top { grid-column: span 2; }" in css
    assert "privateMode || !Number.isFinite(item.value) || !max" in js
    assert 'style="flex-grow: ${weight}"' in js
    assert "highConviction.slice(0, 5)" in js
    assert 'myPortfolioExposureValue, "desc", 5' in js
    assert 'myPortfolioPnlValue, "desc", 3, "positive"' in js
    assert 'myPortfolioPnlValue, "asc", 3, "negative"' in js
    assert "${removedHtml}" in js
