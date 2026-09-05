import json
from pathlib import Path

from story_demo import load_story_fixture


def test_story_fixture_has_stable_order_and_initial_coverage() -> None:
    fixture_path = Path(__file__).parents[1] / "fixtures" / "story.json"

    story = load_story_fixture(fixture_path)

    assert story.story_id == "place-worth-coming-back-to"
    assert story.title == "The place worth coming back to"
    assert [beat.beat_id for beat in story.beats] == [
        "isolation",
        "discovery",
        "invitation",
        "renewal",
        "confidence",
    ]
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert raw["initial_shot"]["beat_id"] == "isolation"
    assert raw["initial_shot"]["source"] == "synthetic"
