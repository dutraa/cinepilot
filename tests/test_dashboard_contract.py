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
    assert "AI previsualization — illustrative creative reference, not flight truth." in html
    assert "duration_seconds:10, variation_count:3" in html
    assert "renderer_version" in html
    assert "quality_status" in html
    assert "source_frame_available" in html
    assert "textContent" in html
    assert "EventSource(\"/events\")" in html


def test_dashboard_previsualization_states_and_provenance_are_visible() -> None:
    html = Path(__file__).parents[1].joinpath("templates", "index.html").read_text(encoding="utf-8")
    # Loading, ready, failed, and retry states.
    assert "Requesting three illustrative previsualizations from the frozen source frame." in html
    assert "Previsualization failed: " in html
    assert "Retry previsualization" in html
    assert "previsualizations are ready from " in html
    # Provider, model, prompt, duration, and source provenance are all shown.
    assert '"Provider and model"' in html
    assert '"Source provenance"' in html
    assert '"Output validation"' in html
    assert '"Duration"' in html
    # Generated clips play as video; deterministic previews stay screen-space.
    assert '/previews/" + encodeURIComponent(preview.preview_id) + "/media"' in html
    assert 'createElement("video")' in html
    assert 'previsLabel' in html
    # Selection never implies capture or completion.
    assert "Selecting a preview never marks the shot captured or completed." in html
    assert "Selection is not capture." in html
    # The four surfaces the creator must be able to tell apart.
    assert "not observed current footage" in html
    assert "not proof that the recommendation was acted on" in html


def test_dashboard_renders_model_text_as_text_never_as_markup() -> None:
    html = Path(__file__).parents[1].joinpath("templates", "index.html").read_text(encoding="utf-8")
    assert "innerHTML" not in html
    assert "insertAdjacentHTML" not in html
    assert "document.write" not in html


def test_dashboard_exposes_visual_reference_as_a_secondary_tab() -> None:
    html = Path(__file__).parents[1].joinpath("templates", "index.html").read_text(encoding="utf-8")
    for marker in (
        'role="tablist"',
        'id="coverageDeskTab"',
        'id="visualReferenceTab"',
        'id="coverageDeskPanel"',
        'id="visualReferencePanel"',
        'id="visualizeBtn"',
        'id="visualizationStatus"',
    ):
        assert marker in html
    assert "Illustrative only" in html
    assert "function requestVisualization" in html
    assert '"/api/visualizations"' in html


def test_hidden_tab_panel_cannot_be_overridden_by_panel_layout() -> None:
    html = Path(__file__).parents[1].joinpath("templates", "index.html").read_text(encoding="utf-8")

    assert "[hidden] { display:none !important; }" in html


def test_dashboard_uses_an_inline_favicon_without_a_missing_asset_request() -> None:
    html = Path(__file__).parents[1].joinpath("templates", "index.html").read_text(encoding="utf-8")

    assert '<link rel="icon" href="data:," />' in html
