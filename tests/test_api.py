from fastapi.testclient import TestClient

import server
from event_log import EventLog
from state import AppState


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
