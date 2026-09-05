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
        "connectionStatus",
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


def test_dashboard_contains_story_coverage_decision_surface() -> None:
    html = Path(__file__).parents[1].joinpath("templates", "index.html").read_text(encoding="utf-8")
    for element_id in [
        "storyTitle",
        "storyLogline",
        "beatRail",
        "currentShotContribution",
        "coveragePanel",
        "recommendationPanel",
        "provenancePill",
        "visualizationPanel",
        "visualizeBtn",
        "visualizationStatus",
    ]:
        assert f'id="{element_id}"' in html
    assert "/api/recommendations/" in html
    assert "/api/visualizations" in html
    assert "AI visualization — illustrative creative reference, not flight truth." in html
    assert "duration_seconds:10, variation_count:3" in html
    assert "renderer_version" in html
    assert "quality_status" in html
    assert "source_frame_available" in html
    assert "textContent" in html
    assert "EventSource(\"/events\")" in html
