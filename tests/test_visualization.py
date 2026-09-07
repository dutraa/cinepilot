import time
import threading

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import server
import state as state_module
from visualization import render_deterministic_previews
from demo_provider import DeterministicDemoProvider
from event_log import EventLog
from schemas import (
    AnimationProfile,
    AnimationProfileSpec,
    VisualizationQualityStatus,
    RecommendationDecision,
    VisualizationJob,
    VisualizationJobStatus,
    VisualizationRequestInput,
    VisualizationPreview,
)
from state import AppState, InvalidDecisionError


def jpeg_bytes(value: int = 0) -> bytes:
    ok, encoded = cv2.imencode(".jpg", np.full((32, 32, 3), value, dtype=np.uint8))
    assert ok
    return encoded.tobytes()


def make_state(tmp_path) -> AppState:
    state = AppState(EventLog(str(tmp_path / "events.jsonl")))
    DeterministicDemoProvider().seed(state)
    return state


def wait_for_status(state: AppState, job_id: str, expected: str = "ready") -> dict:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = next(item for item in state.snapshot()["visualization_jobs"] if item["job_id"] == job_id)
        if job["status"] == expected:
            return job
        time.sleep(0.01)
    return job


def test_visualization_request_accepts_only_the_fixed_request() -> None:
    assert VisualizationRequestInput(duration_seconds=10, variation_count=3)


@pytest.mark.parametrize("payload", [{"duration_seconds": 9, "variation_count": 3}, {"duration_seconds": 10, "variation_count": 2}])
def test_visualization_request_rejects_non_fixed_values(payload) -> None:
    with pytest.raises(ValidationError):
        VisualizationRequestInput(**payload)


def test_visualization_request_rejects_unknown_and_server_owned_fields() -> None:
    with pytest.raises(ValidationError):
        VisualizationRequestInput(duration_seconds=10, variation_count=3, job_id="client-job")


def test_visualization_job_and_profile_reject_invalid_status_and_profile() -> None:
    with pytest.raises(ValidationError):
        VisualizationJob(
            job_id="job-1",
            request_fingerprint="fingerprint",
            story_version=1,
            beat_id="discovery",
            observation_id="observation-1",
            intent_version=1,
            requested_at="2026-09-05T00:00:00+00:00",
            status="complete",
            provenance="deterministic_demo",
        )
    with pytest.raises(ValidationError):
        VisualizationPreview(
            preview_id="preview-1",
            job_id="job-1",
            recommendation_id="recommendation-1",
            title="Concept",
            cinematography_summary="A restrained concept.",
            story_purpose="Advance discovery.",
            visual_objective="Reveal the lodge.",
            why_now="Discovery is missing.",
            manual_execution_guidance="Attempt manually and cautiously.",
            safety_notes="Pilot checks the environment first.",
            duration_seconds=10,
            animation_profile="flight_plan",
            source_frame_available=True,
            provenance="deterministic_demo",
            created_at="2026-09-05T00:00:00+00:00",
        )
    assert AnimationProfile.DESCENDING_REVEAL.value == "descending_reveal"


def test_visualization_profile_contract_is_server_owned_and_bounded() -> None:
    preview = VisualizationPreview(
        preview_id="preview-1",
        job_id="job-1",
        recommendation_id="recommendation-1",
        title="Concept",
        cinematography_summary="A restrained concept.",
        story_purpose="Advance discovery.",
        visual_objective="Reveal the lodge.",
        why_now="Discovery is missing.",
        manual_execution_guidance="Attempt manually and cautiously.",
        safety_notes="Pilot checks the environment first.",
        duration_seconds=10,
        animation_profile="descending_reveal",
        source_frame_available=True,
        provenance="deterministic_demo",
        created_at="2026-09-05T00:00:00+00:00",
    )
    assert preview.quality_status == VisualizationQualityStatus.PASS
    assert preview.profile_spec.scale_start == 1.0
    assert preview.profile_spec.scale_end == 1.25
    with pytest.raises(ValidationError):
        AnimationProfileSpec(
            profile=AnimationProfile.DESCENDING_REVEAL,
            scale_start=1.0,
            scale_end=4.0,
            horizontal_drift_pct=0.0,
            vertical_drift_pct=14.0,
            subject_anchor="center",
        )


def test_visualization_rejects_undecodable_jpeg_bytes(tmp_path) -> None:
    state = make_state(tmp_path)
    with pytest.raises(InvalidDecisionError, match="valid JPEG"):
        state.request_visualization(
            VisualizationRequestInput(duration_seconds=10, variation_count=3),
            b"\xff\xd8not-a-real-jpeg\xff\xd9",
            "deterministic_demo",
        )


def test_renderer_rejects_malformed_provider_output(tmp_path) -> None:
    state = make_state(tmp_path)
    recommendations = state.latest_recommendations[:2]
    request = VisualizationRequestInput(duration_seconds=10, variation_count=3)
    job = VisualizationJob(
        job_id="job-1",
        request_fingerprint="fingerprint",
        duration_seconds=10,
        variation_count=3,
        story_version=1,
        beat_id="discovery",
        observation_id="observation-1",
        intent_version=1,
        requested_at="2026-09-05T00:00:00+00:00",
        provenance="deterministic_demo",
    )
    with pytest.raises(ValueError, match="three existing recommendations"):
        render_deterministic_previews(job, request, recommendations)


def test_visualization_job_lifecycle_freezes_frame_and_renders_three_previews(tmp_path) -> None:
    state = make_state(tmp_path)
    job = state.request_visualization(
        VisualizationRequestInput(duration_seconds=10, variation_count=3),
        source_frame=jpeg_bytes(),
        provenance="deterministic_demo",
    )

    ready = wait_for_status(state, job.job_id)
    assert ready["status"] == VisualizationJobStatus.READY.value
    assert len(ready["previews"]) == 3
    assert [item["animation_profile"] for item in ready["previews"]] == [
        "descending_reveal",
        "lateral_parallax",
        "restrained_pull_away",
    ]
    assert all(item["recommendation_id"] for item in ready["previews"])
    assert ready["source_frame_sha256"]
    assert len(ready["source_frame_sha256"]) == 64
    assert (ready["source_width"], ready["source_height"]) == (32, 32)
    assert ready["renderer_version"] == "deterministic-screen-space-v2"
    assert all(item["profile_spec"]["profile"] == item["animation_profile"] for item in ready["previews"])
    assert state.get_visualization_source_frame(job.job_id) == jpeg_bytes()


def test_duplicate_visualization_request_returns_existing_job(tmp_path) -> None:
    state = make_state(tmp_path)
    request = VisualizationRequestInput(duration_seconds=10, variation_count=3)
    first = state.request_visualization(request, jpeg_bytes(), "deterministic_demo")
    second = state.request_visualization(request, jpeg_bytes(), "deterministic_demo")
    assert first.job_id == second.job_id


def test_failed_visualization_request_can_retry_same_job(tmp_path, monkeypatch) -> None:
    state = make_state(tmp_path)
    calls = {"count": 0}

    def flaky_renderer(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary provider failure")
        return render_deterministic_previews(*args, **kwargs)

    monkeypatch.setattr(state_module, "render_deterministic_previews", flaky_renderer)
    request = VisualizationRequestInput(duration_seconds=10, variation_count=3)
    first = state.request_visualization(request, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, first.job_id, expected="failed")
    assert failed["status"] == "failed"
    retry = state.request_visualization(request, jpeg_bytes(), "deterministic_demo")
    assert retry.job_id == first.job_id
    ready = wait_for_status(state, first.job_id)
    assert ready["status"] == "ready"
    assert calls["count"] == 2


def test_selecting_linked_preview_is_idempotent_and_does_not_complete_coverage(tmp_path) -> None:
    state = make_state(tmp_path)
    before = state.snapshot()
    job = state.request_visualization(
        VisualizationRequestInput(duration_seconds=10, variation_count=3), jpeg_bytes(), "deterministic_demo"
    )
    ready = wait_for_status(state, job.job_id)
    recommendation_id = ready["previews"][0]["recommendation_id"]
    assert state.decide_recommendation(recommendation_id, RecommendationDecision.SELECTED).value == "selected"
    assert state.decide_recommendation(recommendation_id, RecommendationDecision.SELECTED).value == "selected"
    after = state.snapshot()
    assert after["beat_statuses"] == before["beat_statuses"]
    assert after["recommendation_decisions"].count({"recommendation_id": recommendation_id, "decision": "selected", "provenance": "deterministic_demo"}) == 1
    preview = next(item for item in after["visualization_jobs"][0]["previews"] if item["recommendation_id"] == recommendation_id)
    assert preview["recommendation_status"] == "selected"


def test_visualization_allows_only_one_selected_preview_per_job(tmp_path) -> None:
    state = make_state(tmp_path)
    job = state.request_visualization(
        VisualizationRequestInput(duration_seconds=10, variation_count=3), jpeg_bytes(), "deterministic_demo"
    )
    ready = wait_for_status(state, job.job_id)
    first_id = ready["previews"][0]["recommendation_id"]
    second_id = ready["previews"][1]["recommendation_id"]
    state.decide_recommendation(first_id, RecommendationDecision.SELECTED)
    with pytest.raises(InvalidDecisionError, match="one visualization preview"):
        state.decide_recommendation(second_id, RecommendationDecision.SELECTED)
    state.decide_recommendation(first_id, RecommendationDecision.DISMISSED)
    assert state.decide_recommendation(second_id, RecommendationDecision.SELECTED).value == "selected"


def test_visualization_api_supports_request_duplicate_source_frame_and_not_found(tmp_path, monkeypatch) -> None:
    state = make_state(tmp_path)
    monkeypatch.setattr(server, "app_state", state)
    monkeypatch.setattr(server, "video_manager", None)
    client = TestClient(server.app)

    response = client.post("/api/visualizations", json={"duration_seconds": 10, "variation_count": 3})
    assert response.status_code == 200
    job = response.json()
    ready = client.get(f"/api/visualizations/{job['job_id']}")
    deadline = time.monotonic() + 2
    while ready.json()["status"] not in {"ready", "failed"} and time.monotonic() < deadline:
        time.sleep(0.01)
        ready = client.get(f"/api/visualizations/{job['job_id']}")
    assert ready.json()["status"] == "ready"
    assert len(ready.json()["previews"]) == 3
    duplicate = client.post("/api/visualizations", json={"duration_seconds": 10, "variation_count": 3})
    assert duplicate.status_code == 200
    assert duplicate.json()["job_id"] == job["job_id"]
    assert duplicate.json()["source_kind"] == "synthetic"
    frame = client.get(f"/api/visualizations/{job['job_id']}/source-frame")
    assert frame.status_code == 200
    assert frame.headers["content-type"] == "image/jpeg"
    assert client.get("/api/visualizations/missing").status_code == 404
    assert client.get("/api/visualizations/missing/source-frame").status_code == 404


def test_visualization_api_rejects_invalid_payload_and_missing_observation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "app_state", AppState(EventLog(str(tmp_path / "events.jsonl"))))
    monkeypatch.setattr(server, "video_manager", None)
    client = TestClient(server.app)
    assert client.post("/api/visualizations", json={"duration_seconds": 9, "variation_count": 3}).status_code == 422
    assert client.post("/api/visualizations", json={"duration_seconds": 10, "variation_count": 3}).status_code == 409


def test_different_observation_conflicts_while_rendering(tmp_path, monkeypatch) -> None:
    state = make_state(tmp_path)
    started = threading.Event()
    release = threading.Event()
    original = state_module.render_deterministic_previews

    def slow_renderer(*args, **kwargs):
        started.set()
        release.wait(timeout=2)
        return original(*args, **kwargs)

    monkeypatch.setattr(state_module, "render_deterministic_previews", slow_renderer)
    request = VisualizationRequestInput(duration_seconds=10, variation_count=3)
    state.request_visualization(request, jpeg_bytes(1), "deterministic_demo")
    assert started.wait(timeout=1)
    with pytest.raises(InvalidDecisionError, match="another visualization job is rendering"):
        state.request_visualization(request, jpeg_bytes(2), "deterministic_demo")
    release.set()


def test_renderer_failure_marks_job_failed_and_removes_temporary_frame(tmp_path, monkeypatch) -> None:
    state = make_state(tmp_path)

    def failing_renderer(*args, **kwargs):
        raise RuntimeError("deterministic renderer unavailable")

    monkeypatch.setattr(state_module, "render_deterministic_previews", failing_renderer)
    job = state.request_visualization(
        VisualizationRequestInput(duration_seconds=10, variation_count=3), jpeg_bytes(3), "deterministic_demo"
    )
    failed = wait_for_status(state, job.job_id, expected="failed")
    assert failed["error"] == "deterministic renderer unavailable"
    with pytest.raises(InvalidDecisionError, match="source frame is unavailable"):
        state.get_visualization_source_frame(job.job_id)
    assert "visualization_failed" in (tmp_path / "events.jsonl").read_text(encoding="utf-8")


def test_state_snapshot_exposes_visualization_jobs(tmp_path) -> None:
    state = make_state(tmp_path)
    assert "visualization_jobs" in state.snapshot()
    assert "visualization_jobs" in state.snapshot()
