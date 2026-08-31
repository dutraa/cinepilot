from event_log import EventLog
from schemas import CinematicCritique, CinematicIntent, Decision
from state import AppState, InvalidDecisionError


def make_state(tmp_path):
    return AppState(EventLog(str(tmp_path / "events.jsonl")))


def make_critique(state: AppState) -> CinematicCritique:
    state.set_intent(
        CinematicIntent(
            shot_name="Reveal",
            creative_goal="Make the building feel imposing.",
            subject="Building",
        )
    )
    return CinematicCritique(
        critique_id="critique-1",
        observation_id="observation-1",
        created_at="2026-08-31T00:00:00+00:00",
        intent_version=1,
        prompt_version="test",
        intent=state.intent,
        summary="The shot is visually flat.",
        tweaks=[
            {
                "tweak_id": "tweak-1",
                "category": "composition",
                "diagnosis": "The building is centered.",
                "recommendation": "Move it to the right third.",
                "rationale": "The negative space creates tension.",
                "priority": "WARNING",
            }
        ],
    )


def test_snapshot_contains_intent_and_bounded_critique_history(tmp_path) -> None:
    state = make_state(tmp_path)
    critique = make_critique(state)
    assert state.publish_critique(critique) is True

    snapshot = state.snapshot()
    assert snapshot["intent_version"] == 1
    assert snapshot["latest_critique"]["critique_id"] == "critique-1"
    assert len(snapshot["critique_history"]) == 1


def test_duplicate_decision_is_idempotent(tmp_path) -> None:
    state = make_state(tmp_path)
    state.publish_critique(make_critique(state))

    first = state.decide_tweak("critique-1", "tweak-1", Decision.ACCEPTED)
    second = state.decide_tweak("critique-1", "tweak-1", Decision.ACCEPTED)
    assert first == second


def test_terminal_tweak_cannot_be_changed(tmp_path) -> None:
    state = make_state(tmp_path)
    state.publish_critique(make_critique(state))
    state.decide_tweak("critique-1", "tweak-1", Decision.DISMISSED)

    try:
        state.decide_tweak("critique-1", "tweak-1", Decision.ACTED)
    except InvalidDecisionError:
        pass
    else:
        raise AssertionError("terminal tweak status was changed")
