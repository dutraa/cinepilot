import json

import pytest

from event_log import EventLog
from schemas import RecommendationDecision, ShotRecommendationInput
from state import AppState, InvalidDecisionError, StateNotFoundError
from story_demo import load_initial_shot, load_story_fixture


def make_story_state(tmp_path):
    state = AppState(EventLog(str(tmp_path / "events.jsonl")))
    story = load_story_fixture()
    coverage, contribution = load_initial_shot()
    state.load_story(story, initial_coverage=coverage, current_shot_contribution=contribution, provenance="deterministic_demo")
    return state


def recommendation_inputs() -> list[ShotRecommendationInput]:
    common = {
        "beat_id": "discovery",
        "story_purpose": "Let the audience find the lodge.",
        "visual_objective": "Make the lodge grow out of the landscape.",
        "why_now": "Isolation is already visible; discovery is the missing bridge.",
        "execution_guidance": "Manually descend slowly while moving forward, keeping a safe margin from terrain.",
        "safety_notes": "Pilot checks route, weather, obstacles, and people before capture.",
        "priority": "WARNING",
        "confidence": 0.9,
    }
    return [
        ShotRecommendationInput(title="Descending reveal", **common),
        ShotRecommendationInput(title="Forward ridge reveal", visual_objective="Let the lodge emerge behind the foreground ridge.", why_now="A second discovery option keeps the creator in control of the visual rhythm.", **{key: value for key, value in common.items() if key not in {"visual_objective", "why_now"}}),
    ]


def test_story_state_publishes_and_completes_a_recommendation(tmp_path) -> None:
    state = make_story_state(tmp_path)
    published = state.publish_recommendations(recommendation_inputs(), observation_id="synthetic-observation-isolation-001", provenance="deterministic_demo")

    assert len(published) == 2
    assert state.snapshot()["active_beat"]["beat_id"] == "isolation"
    selected = state.decide_recommendation(published[0].recommendation_id, RecommendationDecision.SELECTED)
    completed = state.decide_recommendation(published[0].recommendation_id, RecommendationDecision.COMPLETED)

    assert selected.value == "selected"
    assert completed.value == "completed"
    snapshot = state.snapshot()
    assert snapshot["beat_statuses"]["isolation"] == "covered"
    assert snapshot["beat_statuses"]["discovery"] == "covered"
    assert snapshot["active_beat"]["beat_id"] == "invitation"
    assert snapshot["coverage"][1]["beat_id"] == "discovery"


def test_recommendation_decisions_are_idempotent_and_invalid_transitions_are_logged(tmp_path) -> None:
    state = make_story_state(tmp_path)
    recommendation = state.publish_recommendations(recommendation_inputs(), "obs-1", "deterministic_demo")[0]
    state.decide_recommendation(recommendation.recommendation_id, RecommendationDecision.SELECTED)
    state.decide_recommendation(recommendation.recommendation_id, RecommendationDecision.SELECTED)
    state.decide_recommendation(recommendation.recommendation_id, RecommendationDecision.COMPLETED)
    state.decide_recommendation(recommendation.recommendation_id, RecommendationDecision.COMPLETED)

    before = json.dumps(state.snapshot(), sort_keys=True)
    with pytest.raises(InvalidDecisionError):
        state.decide_recommendation(recommendation.recommendation_id, RecommendationDecision.DISMISSED)
    assert json.dumps(state.snapshot(), sort_keys=True) == before
    events = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "recommendation_transition_rejected" in events


def test_unknown_story_ids_are_typed_not_found_errors(tmp_path) -> None:
    state = make_story_state(tmp_path)
    with pytest.raises(StateNotFoundError):
        state.set_active_beat("missing-beat")
    with pytest.raises(StateNotFoundError):
        state.decide_recommendation("missing-recommendation", RecommendationDecision.SELECTED)
