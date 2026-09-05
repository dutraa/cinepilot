import pytest
from pydantic import ValidationError

from schemas import (
    RecommendationDecisionRequest,
    ShotCoverage,
    ShotRecommendation,
    ShotRecommendationBatchInput,
    ShotRecommendationInput,
    StoryBeat,
    StoryBrief,
)


def valid_story() -> dict[str, object]:
    return {
        "story_id": "story-1",
        "title": "The place worth coming back to",
        "logline": "A lodge returns to life.",
        "emotional_arc": "isolation to confidence",
        "visual_style": "Restrained aerial cinema.",
        "must_show": ["The lodge"],
        "constraints": ["Manual advisory guidance only."],
        "beats": [
            {
                "beat_id": "isolation",
                "title": "Isolation",
                "story_job": "Establish distance.",
                "required_visual_proof": "A high wide.",
                "status": "active",
            }
        ],
    }


def valid_recommendation() -> dict[str, object]:
    return {
        "beat_id": "discovery",
        "title": "Descending reveal",
        "story_purpose": "Let the audience find the lodge.",
        "visual_objective": "Make the lodge grow out of the landscape.",
        "why_now": "The current wide proves isolation but not discovery.",
        "execution_guidance": "Manually descend slowly while moving forward, keeping a safe margin from terrain.",
        "safety_notes": "Pilot confirms route, weather, obstacles, and people before capture.",
        "priority": "WARNING",
        "confidence": 0.9,
    }


def test_story_contracts_reject_unknown_fields_and_invalid_enums() -> None:
    with pytest.raises(ValidationError):
        StoryBrief(**valid_story(), unexpected="nope")
    with pytest.raises(ValidationError):
        StoryBeat(
            beat_id="isolation",
            title="Isolation",
            story_job="Establish distance.",
            required_visual_proof="A high wide.",
            status="finished",
        )


def test_recommendation_input_excludes_server_owned_fields() -> None:
    with pytest.raises(ValidationError):
        ShotRecommendationInput(**valid_recommendation(), recommendation_id="client-id")
    with pytest.raises(ValidationError):
        ShotRecommendationInput(**valid_recommendation(), status="selected")


def test_recommendation_batch_requires_two_or_three_items() -> None:
    with pytest.raises(ValidationError):
        ShotRecommendationBatchInput(recommendations=[valid_recommendation()])
    with pytest.raises(ValidationError):
        ShotRecommendationBatchInput(
            recommendations=[valid_recommendation() for _ in range(4)]
        )


def test_recommendation_output_and_coverage_validate_server_shape() -> None:
    story = StoryBrief(**valid_story())
    assert story.beats[0].status.value == "active"
    recommendation = ShotRecommendation(
        recommendation_id="rec-1",
        observation_id="obs-1",
        created_at="2026-09-01T00:00:00+00:00",
        intent_version=1,
        prompt_version="test",
        provenance="deterministic_demo",
        **valid_recommendation(),
    )
    coverage = ShotCoverage(
        coverage_id="coverage-1",
        beat_id="isolation",
        shot_title="High wide",
        observation_id="obs-1",
        captured_at="2026-09-01T00:00:00+00:00",
        source="synthetic",
        notes="The lodge is small in the landscape.",
    )
    assert recommendation.status.value == "suggested"
    assert coverage.beat_id == "isolation"


def test_recommendation_decision_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RecommendationDecisionRequest(decision="completed", timestamp="client")
