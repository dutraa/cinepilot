from event_log import EventLog
from schemas import CinematicIntent
from state import AppState
from story_demo import load_initial_shot, load_story_fixture
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


def test_valid_next_shot_tool_publishes_server_owned_recommendations(tmp_path) -> None:
    state = make_state(tmp_path)
    coverage, contribution = load_initial_shot()
    state.load_story(load_story_fixture(), coverage, contribution, "live")
    args = {
        "recommendations": [
            {
                "beat_id": "discovery",
                "title": "Descending reveal",
                "story_purpose": "Let the audience find the lodge.",
                "visual_objective": "Make the lodge grow in frame.",
                "why_now": "Isolation is already proven.",
                "execution_guidance": "Manually descend slowly while maintaining safe terrain clearance.",
                "safety_notes": "Pilot checks the route and weather before capture.",
                "priority": "WARNING",
            },
            {
                "beat_id": "invitation",
                "title": "Low approach",
                "story_purpose": "Make the destination feel reachable.",
                "visual_objective": "Bring the entrance forward with a calm approach.",
                "why_now": "The wide does not yet invite arrival.",
                "execution_guidance": "Manually approach at a restrained pace with safe stopping distance.",
                "safety_notes": "Pilot checks people, structures, and weather before capture.",
                "priority": "INFO",
            },
        ]
    }

    result = execute_tool(state, "publish_next_shot_recommendations", args, "obs-5")

    assert result["ok"] is True
    assert len(state.snapshot()["latest_recommendations"]) == 2
    assert state.snapshot()["latest_recommendations"][0]["recommendation_id"]
    assert "created_at" not in args["recommendations"][0]


def test_invalid_next_shot_tool_does_not_mutate_state(tmp_path) -> None:
    state = make_state(tmp_path)
    result = execute_tool(state, "publish_next_shot_recommendations", {"recommendations": []})

    assert result["ok"] is False
    assert state.snapshot()["latest_recommendations"] == []
    assert state.snapshot()["metrics"]["invalid_recommendations"] == 1
