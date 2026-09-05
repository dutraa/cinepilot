from fastapi.testclient import TestClient

import server
from event_log import EventLog
from state import AppState
from story_demo import load_initial_shot, load_story_fixture


def test_intent_api_updates_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "app_state", AppState(EventLog(str(tmp_path / "events.jsonl"))))
    client = TestClient(server.app)

    response = client.post(
        "/api/intent",
        json={
            "shot_name": "Low reveal",
            "creative_goal": "Make the structure feel imposing.",
            "subject": "Main structure",
            "desired_feel": "Deliberate",
            "camera_move": "Slow push in",
            "constraints": ["Keep the horizon level"],
        },
    )

    assert response.status_code == 200
    assert response.json()["intent_version"] == 1
    assert client.get("/api/state").json()["intent"]["shot_name"] == "Low reveal"


def test_unknown_tweak_returns_not_found(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "app_state", AppState(EventLog(str(tmp_path / "events.jsonl"))))
    client = TestClient(server.app)

    response = client.post(
        "/api/critiques/missing/tweaks/missing/decision",
        json={"decision": "acted"},
    )
    assert response.status_code == 404


def story_client(tmp_path, monkeypatch):
    state = AppState(EventLog(str(tmp_path / "events.jsonl")))
    coverage, contribution = load_initial_shot()
    state.set_provenance("deterministic_demo", "synthetic")
    state.load_story(load_story_fixture(), coverage, contribution, "deterministic_demo")
    monkeypatch.setattr(server, "app_state", state)
    return TestClient(server.app)


def recommendation_payload():
    def item(title, beat_id="discovery"):
        return {
            "beat_id": beat_id,
            "title": title,
            "story_purpose": "Let the audience find the lodge.",
            "visual_objective": "Make the lodge grow in frame.",
            "why_now": "Isolation is already proven, so discovery is missing.",
            "execution_guidance": "Manually move slowly while maintaining safe clearance.",
            "safety_notes": "Pilot checks route, weather, obstacles, and people first.",
            "priority": "WARNING",
        }
    return {"recommendations": [item("Descending reveal"), item("Forward reveal")]}


def test_story_api_publishes_and_completes_recommendation(tmp_path, monkeypatch) -> None:
    client = story_client(tmp_path, monkeypatch)

    story_response = client.get("/api/story")
    assert story_response.status_code == 200
    assert story_response.json()["active_beat"]["beat_id"] == "isolation"
    assert client.get("/api/coverage").json()["coverage"][0]["beat_id"] == "isolation"

    published = client.post("/api/recommendations", json=recommendation_payload())
    assert published.status_code == 200
    recommendation_id = published.json()["recommendations"][0]["recommendation_id"]
    assert "created_at" in published.json()["recommendations"][0]

    assert client.post(
        f"/api/recommendations/{recommendation_id}/decision", json={"decision": "completed"}
    ).status_code == 409
    assert client.post(
        f"/api/recommendations/{recommendation_id}/decision", json={"decision": "selected"}
    ).status_code == 200
    completed = client.post(
        f"/api/recommendations/{recommendation_id}/decision", json={"decision": "completed"}
    )
    assert completed.status_code == 200
    assert client.post(
        f"/api/recommendations/{recommendation_id}/decision", json={"decision": "completed"}
    ).status_code == 200
    assert client.get("/api/state").json()["beat_statuses"]["discovery"] == "covered"


def test_story_api_returns_validation_and_not_found_errors(tmp_path, monkeypatch) -> None:
    client = story_client(tmp_path, monkeypatch)
    assert client.post("/api/recommendations", json={"recommendations": []}).status_code == 422
    assert client.post("/api/story/beat", json={"beat_id": "missing"}).status_code == 404
    assert client.get("/api/recommendations").status_code == 200
    assert client.post(
        "/api/recommendations/missing/decision", json={"decision": "selected"}
    ).status_code == 404
