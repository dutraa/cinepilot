"""Provenance, health, and fresh-frame gating tests (no hardware needed)."""

import asyncio
import json

from fastapi.testclient import TestClient

import server
from director_agent import DirectorAgent
from event_log import EventLog
from grafana_publisher import GrafanaPublisher
from state import AppState
from tools import execute_tool


def make_state(tmp_path) -> AppState:
    return AppState(EventLog(str(tmp_path / "events.jsonl")))


def read_events(tmp_path) -> list[dict]:
    path = tmp_path / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


LIVE_SNAPSHOT = {
    "requested_source": "rtmp",
    "active_source": "rtmp",
    "protocol": "rtmp",
    "stream_url": "rtmp://127.0.0.1:1935/live/drone",
    "status": "live",
    "status_reason": "receiving frames",
    "is_real_source": True,
    "provenance": "live-rtmp",
    "first_frame_at": "2026-09-05T00:00:00+00:00",
    "last_frame_at": "2026-09-05T00:00:01+00:00",
    "frame_age_sec": 0.2,
    "fps": 24.0,
    "frames_captured": 48,
    "reconnect_count": 1,
    "fallback_active": False,
    "allow_synthetic_fallback": False,
    "stale_after_sec": 3.0,
}


class StubVideoManager:
    def __init__(self, snapshot=None):
        self.snapshot = dict(snapshot or LIVE_SNAPSHOT)
        self.stale_after_sec = 3.0
        self.fresh_jpeg: bytes | None = b"jpeg"

    def status_snapshot(self):
        return dict(self.snapshot)

    def get_raw_frame(self, max_age_sec=None):
        return None

    def get_fresh_jpeg(self, quality=80, max_dim=1024, max_age_sec=None):
        return self.fresh_jpeg


# ---------------------------------------------------------------------------
# AppState provenance
# ---------------------------------------------------------------------------


def test_source_transitions_are_logged_with_provenance(tmp_path) -> None:
    state = make_state(tmp_path)
    state.record_source_transition(LIVE_SNAPSHOT)
    disconnected = dict(LIVE_SNAPSHOT, status="disconnected",
                        status_reason="stream ended")
    state.record_source_transition(disconnected)

    snapshot = state.snapshot()
    assert snapshot["source"]["status"] == "disconnected"

    events = [e for e in read_events(tmp_path) if e["event"] == "source_transition"]
    assert [e["status"] for e in events] == ["live", "disconnected"]
    assert all(e["provenance"] == "live-rtmp" for e in events)


def test_frame_observation_events_keep_provenance_strata(tmp_path) -> None:
    state = make_state(tmp_path)
    state.record_frame_observation("observation-1", "live-rtmp", "live")
    state.record_frame_observation("observation-2", "synthetic", "live")

    events = [e for e in read_events(tmp_path) if e["event"] == "frame_observation"]
    assert {e["provenance"] for e in events} == {"live-rtmp", "synthetic"}


def test_disconnect_during_active_recommendation_preserves_critique(tmp_path) -> None:
    from test_state import make_critique

    state = make_state(tmp_path)
    state.publish_critique(make_critique(state))
    state.record_source_transition(
        dict(LIVE_SNAPSHOT, status="disconnected", status_reason="stream lost")
    )

    snapshot = state.snapshot()
    assert snapshot["latest_critique"]["critique_id"] == "critique-1"
    assert snapshot["source"]["status"] == "disconnected"
    # The creator can still decide on the recommendation after a source loss.
    from schemas import Decision

    assert state.decide_tweak("critique-1", "tweak-1", Decision.DISMISSED)


def test_creator_shot_completion_is_creator_only_and_idempotent(tmp_path) -> None:
    state = make_state(tmp_path)

    # Model path cannot complete a shot.
    result = execute_tool(
        state,
        "update_shot_list",
        {"shot_id": "orbit_pass", "status": "COMPLETED", "feedback": "looks done"},
    )
    assert result["ok"] is False
    assert state.snapshot()["shots"]["orbit_pass"]["status"] == "PENDING"
    assert state.snapshot()["metrics"]["malformed_tool_calls"] == 1

    # Creator path can.
    state.creator_update_shot("orbit_pass", "COMPLETED", "Captured manually.")
    assert state.snapshot()["shots"]["orbit_pass"]["status"] == "COMPLETED"

    # Idempotent: repeating the same completion changes nothing further.
    version = state.version
    state.creator_update_shot("orbit_pass", "COMPLETED", "Captured manually.")
    assert state.version == version

    events = [e for e in read_events(tmp_path) if e["event"] == "shot_updated"]
    assert len(events) == 1
    assert events[0]["actor"] == "creator"


def test_unknown_tool_counts_as_malformed(tmp_path) -> None:
    state = make_state(tmp_path)
    result = execute_tool(state, "engage_autopilot", {"go": True})
    assert result["ok"] is False
    assert state.snapshot()["metrics"]["malformed_tool_calls"] == 1
    events = [e for e in read_events(tmp_path) if e["event"] == "tool_call_malformed"]
    assert events and events[0]["provenance"] == "gemini"


# ---------------------------------------------------------------------------
# API surfaces
# ---------------------------------------------------------------------------


def test_health_exposes_source_provenance(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "app_state", make_state(tmp_path))
    monkeypatch.setattr(server, "video_manager", StubVideoManager())
    client = TestClient(server.app)

    health = client.get("/health").json()
    assert health["source"]["requested_source"] == "rtmp"
    assert health["source"]["status"] == "live"
    assert health["source"]["is_real_source"] is True
    assert health["source"]["frame_age_sec"] == 0.2
    assert health["source"]["reconnect_count"] == 1
    assert health["video_source"] == "rtmp"
    assert "frames_skipped_stale" in health
    assert "malformed_tool_calls" in health


def test_api_state_and_sse_snapshot_include_live_source(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "app_state", make_state(tmp_path))
    monkeypatch.setattr(server, "video_manager", StubVideoManager())
    client = TestClient(server.app)

    state = client.get("/api/state").json()
    assert state["source"]["provenance"] == "live-rtmp"
    assert state["source"]["stream_url"] == "rtmp://127.0.0.1:1935/live/drone"

    # The SSE stream serializes the same merged snapshot.
    merged = server.state_snapshot_with_source()
    assert merged["source"]["status"] == "live"


def test_creator_shot_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "app_state", make_state(tmp_path))
    client = TestClient(server.app)

    ok = client.post(
        "/api/shots/orbit_pass",
        json={"status": "COMPLETED", "feedback": "Captured manually."},
    )
    assert ok.status_code == 200
    assert client.get("/api/state").json()["shots"]["orbit_pass"]["status"] == (
        "COMPLETED"
    )

    missing = client.post("/api/shots/nope", json={"status": "COMPLETED"})
    assert missing.status_code == 404

    invalid = client.post("/api/shots/orbit_pass", json={"status": "DONE"})
    assert invalid.status_code == 422


# ---------------------------------------------------------------------------
# DirectorAgent fresh-frame gating
# ---------------------------------------------------------------------------


def make_agent(tmp_path, manager) -> tuple[DirectorAgent, AppState]:
    state = make_state(tmp_path)
    agent = DirectorAgent(
        manager, state, GrafanaPublisher(url="", user="", api_key="")
    )
    return agent, state


def test_agent_skips_stale_frames_and_counts_them(tmp_path) -> None:
    manager = StubVideoManager(
        dict(LIVE_SNAPSHOT, status="stale", frame_age_sec=9.0)
    )
    manager.fresh_jpeg = None
    agent, state = make_agent(tmp_path, manager)

    assert agent._sample_fresh_jpeg() is None
    assert state.snapshot()["metrics"]["frames_skipped_stale"] == 1
    events = read_events(tmp_path)
    assert not [e for e in events if e["event"] == "frame_observation"]


def test_agent_sends_fresh_frames_with_observation_provenance(tmp_path) -> None:
    manager = StubVideoManager()
    agent, state = make_agent(tmp_path, manager)

    class FakeSession:
        def __init__(self):
            self.frames = []

        async def send_realtime_input(self, **kwargs):
            self.frames.append(kwargs)

    session = FakeSession()
    jpeg = agent._sample_fresh_jpeg()
    assert jpeg == b"jpeg"
    agent._observation_counter += 1
    agent._last_observation_id = "observation-1"
    agent._record_observation()
    asyncio.run(agent._send_frame(session, jpeg))

    assert len(session.frames) == 1
    events = [e for e in read_events(tmp_path) if e["event"] == "frame_observation"]
    assert events[0]["provenance"] == "live-rtmp"
    assert events[0]["source_status"] == "live"
    assert state.snapshot()["metrics"]["frames_skipped_stale"] == 0
