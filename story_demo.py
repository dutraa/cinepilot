"""Seed and validate the deterministic story-aware demo fixture."""

from __future__ import annotations

import json
from pathlib import Path

from schemas import ShotCoverage, StoryBrief


DEFAULT_STORY_FIXTURE = Path(__file__).parent / "fixtures" / "story.json"


def load_story_fixture(path: Path = DEFAULT_STORY_FIXTURE) -> StoryBrief:
    """Load the story fixture through the same strict contract as model data."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("initial_shot", None)
    return StoryBrief.model_validate(raw)


def load_initial_shot(path: Path = DEFAULT_STORY_FIXTURE) -> tuple[ShotCoverage, dict[str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    initial = raw["initial_shot"]
    coverage = ShotCoverage(
        coverage_id="coverage-isolation-initial",
        beat_id=initial["beat_id"],
        shot_title=initial["shot_title"],
        observation_id=initial["observation_id"],
        captured_at="2026-01-01T00:00:00+00:00",
        source=initial["source"],
        notes=initial["notes"],
    )
    contribution = {
        "beat_id": initial["beat_id"],
        "observation_id": initial["observation_id"],
        "shot_title": initial["shot_title"],
        "source": initial["source"],
        "proves": initial["contribution"],
        "limitations": initial["limitations"],
    }
    return coverage, contribution
