from event_log import EventLog
from schemas import CinematicIntent
from state import AppState
from tools import execute_tool


def make_state(tmp_path) -> AppState:
    state = AppState(EventLog(str(tmp_path / "events.jsonl")))
    state.set_intent(
        CinematicIntent(
            shot_name="Reveal",
            creative_goal="Make the building feel imposing.",
            subject="Building",
        )
    )
    return state


def valid_args() -> dict[str, object]:
    return {
        "summary": "The shot is visually flat.",
        "tweaks": [
            {
                "category": "composition",
                "diagnosis": "The building is centered.",
                "recommendation": "Move it toward the right third.",
                "rationale": "Negative space will create stronger tension.",
                "priority": "WARNING",
                "spoken_cue": "Ease the building toward the right third.",
            }
        ],
    }


def test_valid_critique_is_published_with_server_ids(tmp_path) -> None:
    state = make_state(tmp_path)
    result = execute_tool(state, "publish_cinematic_critique", valid_args(), "observation-4")

    assert result["ok"] is True
    assert result["suppressed"] is False
    snapshot = state.snapshot()
    assert snapshot["latest_critique"]["observation_id"] == "observation-4"
    assert snapshot["latest_critique"]["tweaks"][0]["tweak_id"]


def test_invalid_critique_does_not_mutate_state(tmp_path) -> None:
    state = make_state(tmp_path)
    result = execute_tool(state, "publish_cinematic_critique", {"tweaks": []})

    assert result["ok"] is False
    assert state.snapshot()["latest_critique"] is None
    assert state.snapshot()["metrics"]["invalid_critiques"] == 1
