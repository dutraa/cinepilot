from pathlib import Path


def test_dashboard_contains_intent_and_critique_surfaces() -> None:
    html = Path(__file__).parents[1].joinpath("templates", "index.html").read_text(encoding="utf-8")
    assert 'id="intentForm"' in html
    assert 'id="critiquePanel"' in html
    assert "/api/intent" in html
    assert "/api/critiques/" in html
