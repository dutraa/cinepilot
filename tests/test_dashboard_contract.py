from pathlib import Path


def test_dashboard_contains_intent_and_critique_surfaces() -> None:
    html = Path(__file__).parents[1].joinpath("templates", "index.html").read_text(encoding="utf-8")
    assert 'id="intentForm"' in html
    assert 'id="critiquePanel"' in html
    assert "/api/intent" in html
    assert "/api/critiques/" in html


def test_dashboard_contains_source_provenance_surfaces() -> None:
    html = Path(__file__).parents[1].joinpath("templates", "index.html").read_text(encoding="utf-8")
    # Source status strip and real/synthetic badge.
    for element_id in (
        "sourcePill",
        "ssePill",
        "realBadge",
        "srcStatus",
        "srcFrameAge",
        "srcReconnects",
        "monitorOverlay",
        "critiqueWarning",
    ):
        assert f'id="{element_id}"' in html
    # Creator-only completion path and safety surfaces.
    assert "/api/shots/" in html
    assert "advisory" in html.lower()
    # Model text must be rendered as text, never as markup.
    assert "textContent" in html
