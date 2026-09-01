from event_log import EventLog
from schemas import RecommendationDecision
from state import AppState
from demo_provider import DeterministicDemoProvider


def test_demo_provider_seeds_repeatable_recommendations_and_advances(tmp_path) -> None:
    state = AppState(EventLog(str(tmp_path / "events.jsonl")))
    provider = DeterministicDemoProvider()

    first = provider.seed(state)
    repeated = provider.publish_current(state)

    assert [item.recommendation_id for item in first] == [item.recommendation_id for item in repeated]
    assert all(item.provenance == "deterministic_demo" for item in first)
    assert {item.beat_id for item in first} == {"discovery", "invitation"}

    second_state = AppState(EventLog(str(tmp_path / "second-events.jsonl")))
    second = DeterministicDemoProvider().seed(second_state)
    assert [item.model_dump(mode="json") for item in first] == [
        item.model_dump(mode="json") for item in second
    ]

    state.decide_recommendation(first[0].recommendation_id, RecommendationDecision.SELECTED)
    state.decide_recommendation(first[0].recommendation_id, RecommendationDecision.COMPLETED)
    next_recommendations = provider.publish_current(state)

    assert next_recommendations
    assert {item.beat_id for item in next_recommendations} == {"invitation", "renewal"}
    assert state.snapshot()["provenance"]["mode"] == "deterministic_demo"
