import pytest
import time
import asyncio
from types import SimpleNamespace
from fastapi.testclient import TestClient
from pydantic import ValidationError

import server
from event_log import EventLog
from schemas import (
    CinematicIntent,
    ObservationBurst,
    ObservationFrame,
    RecommendationDecision,
    StoryContextInput,
    TakeAnalysisResult,
)
from state import AppState
from director_agent import DirectorAgent
from grafana_publisher import GrafanaPublisher
from story_demo import load_initial_shot, load_story_fixture
from video_stream import SourceStatus, VideoStreamManager


def make_state(tmp_path) -> AppState:
    state = AppState(EventLog(str(tmp_path / "events.jsonl")))
    coverage, contribution = load_initial_shot()
    state.load_story(
        load_story_fixture(),
        initial_coverage=coverage,
        current_shot_contribution=contribution,
        provenance="deterministic_demo",
    )
    return state


def recommendation_inputs() -> list[dict[str, object]]:
    common = {
        "beat_id": "discovery",
        "story_purpose": "Let the audience find the lodge.",
        "visual_objective": "Make the lodge grow in frame.",
        "why_now": "Isolation is already proven; discovery is missing.",
        "execution_guidance": "Manually move slowly while maintaining safe clearance.",
        "safety_notes": "Pilot checks route, weather, obstacles, and people first.",
        "priority": "WARNING",
    }
    return [
        {"title": "Descending reveal", **common},
        {"title": "Forward reveal", **common},
    ]


def test_completing_a_recommendation_does_not_cover_unrelated_active_beat(tmp_path) -> None:
    state = make_state(tmp_path)
    from schemas import ShotRecommendationInput

    recommendations = state.publish_recommendations(
        [ShotRecommendationInput(**item) for item in recommendation_inputs()],
        observation_id="observation-1",
        provenance="deterministic_demo",
    )

    state.decide_recommendation(recommendations[0].recommendation_id, RecommendationDecision.SELECTED)
    state.decide_recommendation(recommendations[0].recommendation_id, RecommendationDecision.COMPLETED)

    snapshot = state.snapshot()
    assert snapshot["beat_statuses"]["discovery"] == "covered"
    assert snapshot["beat_statuses"]["isolation"] == "active"


def test_disconnected_real_source_is_not_reported_as_real_source() -> None:
    manager = VideoStreamManager(source="rtmp", allow_synthetic_fallback=False)
    manager._set_status(SourceStatus.DISCONNECTED, "stream ended")

    snapshot = manager.status_snapshot()

    assert snapshot["is_real_source"] is False


def test_malformed_function_arguments_are_rejected_without_killing_receiver(tmp_path) -> None:
    state = AppState(EventLog(str(tmp_path / "events.jsonl")))
    agent = DirectorAgent(object(), state, GrafanaPublisher(url="", user="", api_key=""))

    class Session:
        def __init__(self):
            self.responses = []

        async def send_tool_response(self, **kwargs):
            self.responses.extend(kwargs["function_responses"])

    session = Session()
    tool_call = SimpleNamespace(
        function_calls=[SimpleNamespace(name="publish_cinematic_critique", args="not-an-object", id="call-1")]
    )
    asyncio.run(agent._handle_tool_call(session, tool_call))

    assert len(session.responses) == 1
    assert session.responses[0].response["ok"] is False
    assert state.snapshot()["metrics"]["malformed_tool_calls"] == 1


def test_story_context_input_rejects_server_owned_fields() -> None:
    with pytest.raises(ValidationError):
        StoryContextInput(
            title="A lodge returns to life",
            logline="A remote lodge reopens after a storm.",
            emotional_arc="isolation to confidence",
            visual_style="Restrained aerial cinema.",
            must_show=["The lodge"],
            constraints=["Manual guidance only."],
            beats=[
                {
                    "title": "Isolation",
                    "story_job": "Establish distance.",
                    "required_visual_proof": "A high wide.",
                }
            ],
            active_beat_index=0,
            shot_intent=CinematicIntent(
                shot_name="Opening wide",
                creative_goal="Establish isolation.",
                subject="The lodge",
            ),
            story_id="client-owned",
        )


def test_analysis_result_rejects_generic_or_control_like_guidance() -> None:
    with pytest.raises(ValidationError):
        TakeAnalysisResult(
            observed=["The subject is visible."],
            not_established=["Safety is not established."],
            missing_coverage=["The story beat remains incomplete."],
            recommendations=[
                {
                    "beat_id": "beat-1",
                    "title": "Make it more cinematic",
                    "diagnosis": "The shot needs work.",
                    "story_purpose": "Advance the story.",
                    "visual_objective": "Make it more cinematic.",
                    "why_now": "Now.",
                    "execution_guidance": "Fly to the waypoint autonomously.",
                    "technical_plausibility": "Unknown.",
                    "safety_notes": "Pilot decides.",
                },
                {
                    "beat_id": "beat-1", "title": "Option two", "diagnosis": "A gap remains.",
                    "story_purpose": "Advance the story.", "visual_objective": "Show the subject.",
                    "why_now": "The gap remains.", "execution_guidance": "Manually hold a safe frame.",
                    "technical_plausibility": "Plausible.", "safety_notes": "Pilot decides.",
                },
                {
                    "beat_id": "beat-1", "title": "Option three", "diagnosis": "A gap remains.",
                    "story_purpose": "Advance the story.", "visual_objective": "Show the context.",
                    "why_now": "The gap remains.", "execution_guidance": "Manually hold a safe frame.",
                    "technical_plausibility": "Plausible.", "safety_notes": "Pilot decides.",
                },
            ],
        )


def test_live_story_route_and_consent_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "app_state", AppState(EventLog(str(tmp_path / "events.jsonl"))))
    client = TestClient(server.app)

    context = {
        "title": "A lodge returns to life",
        "logline": "A remote lodge reopens after a storm.",
        "emotional_arc": "isolation to confidence",
        "visual_style": "Restrained aerial cinema.",
        "must_show": ["The lodge"],
        "constraints": ["Manual guidance only."],
        "beats": [
            {
                "title": "Isolation",
                "story_job": "Establish distance.",
                "required_visual_proof": "A high wide.",
            }
        ],
        "active_beat_index": 0,
        "shot_intent": {
            "shot_name": "Opening wide",
            "creative_goal": "Establish isolation.",
            "subject": "The lodge",
        },
    }

    response = client.post("/api/story", json=context)
    assert response.status_code == 200
    assert response.json()["story"]["story_id"]
    assert response.json()["intent_version"] == 1

    blocked = client.post("/api/analysis", json={})
    assert blocked.status_code == 409
    assert "consent" in blocked.json()["detail"].lower()

    consent = client.post("/api/consent", json={"granted": True})
    assert consent.status_code == 200
    assert consent.json()["consent"]["granted"] is True


def test_explicit_analysis_selection_capture_and_follow_up_are_separate(tmp_path, monkeypatch) -> None:
    state = AppState(EventLog(str(tmp_path / "events.jsonl")))
    state.set_provenance("deterministic_demo", "synthetic")
    monkeypatch.setattr(server, "app_state", state)

    class SyntheticSource:
        active_source = "synthetic"

        @staticmethod
        def status_snapshot():
            return {
                "status": "live",
                "frame_age_sec": 0.0,
                "is_real_source": False,
                "active_source": "synthetic",
                "requested_source": "synthetic",
                "provenance": "synthetic",
                "fallback_active": False,
            }

    source = SyntheticSource()
    monkeypatch.setattr(server, "video_manager", source)

    def fake_burst(manager, *, job_id, story_version, intent_version, beat_id, provenance, **_kwargs):
        frames = [
            ObservationFrame(
                frame_index=index,
                captured_at=f"2026-09-08T00:00:0{index}+00:00",
                frame_age_ms=0,
                width=1280,
                height=720,
                sha256=f"{index + 1:064x}",
            )
            for index in range(3)
        ]
        return (
            ObservationBurst(
                observation_id=f"observation-{job_id}",
                job_id=job_id,
                story_version=story_version,
                intent_version=intent_version,
                beat_id=beat_id,
                provenance="synthetic",
                requested_source="synthetic",
                active_source="synthetic",
                freshness_limit_ms=2000,
                capture_started_at="2026-09-08T00:00:00+00:00",
                capture_completed_at="2026-09-08T00:00:01+00:00",
                frames=frames,
            ),
            [b"frame-1", b"frame-2", b"frame-3"],
        )

    monkeypatch.setattr(server, "capture_fresh_burst", fake_burst)
    client = TestClient(server.app)
    context = {
        "title": "A lodge returns to life",
        "logline": "A remote lodge reopens after a storm.",
        "emotional_arc": "isolation to confidence",
        "visual_style": "Restrained aerial cinema.",
        "must_show": ["The lodge"],
        "constraints": ["Manual guidance only."],
        "beats": [{"title": "Isolation", "story_job": "Establish distance.", "required_visual_proof": "A high wide."}],
        "active_beat_index": 0,
        "shot_intent": {"shot_name": "Opening wide", "creative_goal": "Establish isolation.", "subject": "The lodge"},
    }
    assert client.post("/api/story", json=context).status_code == 200
    assert client.post("/api/consent", json={"granted": True}).status_code == 200

    with TestClient(server.app) as persistent_client:
        response = persistent_client.post("/api/analysis", json={})
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        for _ in range(30):
            job = persistent_client.get(f"/api/analysis/{job_id}").json()
            if job["status"] in {"ready", "failed"}:
                break
            time.sleep(0.01)
        assert job["status"] == "ready"
        recommendations = persistent_client.get("/api/state").json()["take_recommendations"]
        assert len(recommendations) == 3
        alternative = recommendations[1]
        selected = persistent_client.post(
            f"/api/take-recommendations/{alternative['recommendation_id']}/decision",
            json={"decision": "selected", "reason": "Safer option for this take."},
        )
        assert selected.status_code == 200
        capture = persistent_client.post(
            f"/api/take-recommendations/{alternative['recommendation_id']}/capture",
            json={"notes": "Pilot captured manually."},
        )
        assert capture.status_code == 200
        capture_id = capture.json()["capture"]["capture_id"]
        conflicting = persistent_client.post(
            f"/api/take-recommendations/{recommendations[0]['recommendation_id']}/decision",
            json={"decision": "selected"},
        )
        assert conflicting.status_code == 409
        assert persistent_client.get("/api/state").json()["beat_statuses"]
        evaluation = persistent_client.post(f"/api/captures/{capture_id}/evaluate", json={})
        assert evaluation.status_code == 202
        assert evaluation.json()["kind"] == "follow_up_evaluation"
        evaluation_job_id = evaluation.json()["job_id"]
        for _ in range(30):
            evaluated = persistent_client.get(f"/api/analysis/{evaluation_job_id}").json()
            if evaluated["status"] in {"ready", "failed"}:
                break
            time.sleep(0.01)
        assert evaluated["status"] == "ready"
        snapshot = persistent_client.get("/api/state").json()
        assert len(snapshot["observation_bursts"]) == 2
        assert snapshot["observation_bursts"][0]["observation_id"] != snapshot["observation_bursts"][1]["observation_id"]
