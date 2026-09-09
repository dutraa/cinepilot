"""Provider-backed AI previsualization contracts.

Every test here uses a fake Google client. No test requires a live Google API
key, and nothing in this file makes a network call.
"""

import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import server
from demo_provider import DeterministicDemoProvider
from event_log import EventLog
from google_video import (
    GeneratedClip,
    GoogleVideoRenderer,
    PROMPT_VERSION,
    VisualizationProviderError,
    build_google_client,
    build_prompt,
)
from schemas import (
    AnimationProfile,
    RecommendationDecision,
    ShotRecommendationStatus,
    VisualizationRenderKind,
    VisualizationRequestInput,
)
from state import AppState, InvalidDecisionError, StateNotFoundError
from visualization import (
    DeterministicVisualizationRenderer,
    MediaValidationError,
    reconcile_duration,
    select_renderer,
)


REQUEST = VisualizationRequestInput(duration_seconds=10, variation_count=3)


def jpeg_bytes(value: int = 0) -> bytes:
    ok, encoded = cv2.imencode(".jpg", np.full((64, 64, 3), value, dtype=np.uint8))
    assert ok
    return encoded.tobytes()


def _write_clip(path, codec, seconds, fps, size) -> bytes:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), fps, (size, size))
    assert writer.isOpened(), codec
    for index in range(int(round(seconds * fps))):
        writer.write(np.full((size, size, 3), (index * 3) % 255, dtype=np.uint8))
    writer.release()
    return path.read_bytes()


def playable_clip(tmp_path, *, seconds: float = 8.0, fps: float = 8.0, size: int = 64) -> bytes:
    """A genuinely decodable, genuinely browser-playable VP9 WebM clip."""
    return _write_clip(
        tmp_path / f"clip-{seconds}-{fps}-{size}.webm", "VP90", seconds, fps, size
    )


def unplayable_codec_clip(tmp_path) -> bytes:
    """A valid MP4 container carrying MPEG-4 Part 2, which browsers cannot play."""
    return _write_clip(tmp_path / "unplayable.mp4", "mp4v", 8.0, 8.0, 64)


class FakeGoogleClient:
    """A scripted stand-in for the Google video backend."""

    model = "fake-omni-flash"

    def __init__(self, clip: bytes = b"", *, mime_type: str = "video/webm", behavior=None) -> None:
        self.clip = clip
        self.mime_type = mime_type
        self._behavior = behavior
        self.prompts: list[str] = []
        self.thread_names: list[str] = []
        self.calls = 0

    def generate_clip(self, *, prompt, source_frame, duration_seconds, timeout_sec):
        self.calls += 1
        self.prompts.append(prompt)
        self.thread_names.append(threading.current_thread().name)
        if self._behavior is not None:
            outcome = self._behavior(self)
            if outcome is not None:
                return outcome
        return GeneratedClip(data=self.clip, mime_type=self.mime_type)


def google_renderer(client, *, max_bytes: int = 8_000_000, timeout_sec: float = 5.0):
    return GoogleVideoRenderer(
        client, max_bytes=max_bytes, timeout_sec=timeout_sec, supported_durations=(8,)
    )


def make_state(tmp_path, renderer) -> AppState:
    state = AppState(
        EventLog(str(tmp_path / "events.jsonl")), visualization_renderer=renderer
    )
    DeterministicDemoProvider().seed(state)
    return state


def wait_for_status(state: AppState, job_id: str, expected: str = "ready") -> dict:
    deadline = time.monotonic() + 5
    job = None
    while time.monotonic() < deadline:
        job = next(
            item for item in state.snapshot()["visualization_jobs"] if item["job_id"] == job_id
        )
        if job["status"] == expected:
            return job
        time.sleep(0.01)
    return job


# --- renderer selection and deterministic fallback -------------------------


def settings_stub(**overrides) -> SimpleNamespace:
    base = {
        "VISUALIZATION_PROVIDER": "google",
        "ENABLE_GENERATED_PREVISUALIZATION": True,
        "GOOGLE_VIDEO_API_KEY": "test-key",
        "GEMINI_API_KEY": "",
        "GOOGLE_VIDEO_BACKEND": "interactions",
        "GOOGLE_VIDEO_MODEL": "gemini-omni-1.1-flash",
        "GOOGLE_VIDEO_RESOLUTION": "720p",
        "GOOGLE_VIDEO_ASPECT_RATIO": "16:9",
        "GOOGLE_VIDEO_MAX_BYTES": 1024,
        "GOOGLE_VIDEO_TIMEOUT_SEC": 5.0,
        "GOOGLE_VIDEO_DURATION_SEC": 8,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_missing_api_key_falls_back_to_the_deterministic_renderer() -> None:
    renderer = select_renderer(settings_stub(GOOGLE_VIDEO_API_KEY="", GEMINI_API_KEY=""))
    assert isinstance(renderer, DeterministicVisualizationRenderer)
    assert renderer.name == "deterministic"
    assert renderer.render_kind == VisualizationRenderKind.DETERMINISTIC_ANIMATION
    # Deterministic output is never labeled as a Google model.
    assert renderer.model == "none"


def test_generation_stays_off_until_it_is_explicitly_enabled() -> None:
    assert isinstance(
        select_renderer(settings_stub(ENABLE_GENERATED_PREVISUALIZATION=False)),
        DeterministicVisualizationRenderer,
    )
    assert isinstance(
        select_renderer(settings_stub(VISUALIZATION_PROVIDER="deterministic")),
        DeterministicVisualizationRenderer,
    )


def test_building_a_google_client_without_a_key_is_an_explicit_failure() -> None:
    with pytest.raises(VisualizationProviderError, match="API key is not configured"):
        build_google_client(
            backend="interactions", api_key="", model="m", resolution="720p", aspect_ratio="16:9"
        )
    with pytest.raises(VisualizationProviderError, match="unknown Google video backend"):
        build_google_client(
            backend="magic", api_key="k", model="m", resolution="720p", aspect_ratio="16:9"
        )


def test_veo_backend_is_a_configurable_alternative() -> None:
    with pytest.raises(VisualizationProviderError, match="API key is not configured"):
        build_google_client(
            backend="veo", api_key="", model="veo-3.1-generate-preview",
            resolution="720p", aspect_ratio="16:9",
        )


# --- duration reconciliation ----------------------------------------------


def test_duration_reconciliation_never_relabels_a_shorter_clip() -> None:
    assert reconcile_duration(10, (10,)) == (10, "")
    effective, note = reconcile_duration(10, (4, 6, 8))
    assert effective == 8
    assert "not 10" in note
    effective, note = reconcile_duration(4, (6, 8))
    assert effective == 6
    assert "not 4" in note


def test_generated_job_reports_the_real_duration_and_a_reconciliation_note(tmp_path) -> None:
    client = FakeGoogleClient(playable_clip(tmp_path))
    state = make_state(tmp_path, google_renderer(client))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    ready = wait_for_status(state, job.job_id)

    assert ready["status"] == "ready"
    assert ready["requested_duration_seconds"] == 10
    assert ready["duration_seconds"] == 8
    assert "not 10" in ready["duration_note"]
    assert all(item["duration_seconds"] == 8 for item in ready["previews"])
    assert all(item["render_kind"] == "generated_video" for item in ready["previews"])


# --- provider-neutral renderer behavior ------------------------------------


def test_both_renderers_satisfy_the_same_job_and_preview_contract(tmp_path) -> None:
    deterministic = make_state(tmp_path / "a", DeterministicVisualizationRenderer())
    generated = make_state(
        tmp_path / "b", google_renderer(FakeGoogleClient(playable_clip(tmp_path)))
    )
    ready = [
        wait_for_status(
            state, state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo").job_id
        )
        for state in (deterministic, generated)
    ]

    assert [job["status"] for job in ready] == ["ready", "ready"]
    assert {key for key in ready[0]} == {key for key in ready[1]}
    for job in ready:
        assert len(job["previews"]) == 3
        assert [item["animation_profile"] for item in job["previews"]] == [
            "descending_reveal",
            "lateral_parallax",
            "restrained_pull_away",
        ]
        assert {key for key in job["previews"][0]} == {key for key in ready[0]["previews"][0]}
    assert ready[0]["provider"] == "deterministic" and ready[0]["model"] == "none"
    assert ready[1]["provider"] == "google" and ready[1]["model"] == "fake-omni-flash"
    assert ready[0]["previews"][0]["media"] is None
    assert ready[1]["previews"][0]["media"]["mime_type"] == "video/webm"


def test_generated_previews_carry_full_provenance(tmp_path) -> None:
    client = FakeGoogleClient(playable_clip(tmp_path))
    state = make_state(tmp_path, google_renderer(client))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    ready = wait_for_status(state, job.job_id)

    assert ready["prompt_version"] == PROMPT_VERSION
    assert ready["renderer_version"] == "google-video-v1"
    assert len(ready["source_frame_sha256"]) == 64
    for preview in ready["previews"]:
        assert preview["provider"] == "google"
        assert preview["model"] == "fake-omni-flash"
        assert preview["prompt_version"] == PROMPT_VERSION
        assert preview["source_frame_sha256"] == ready["source_frame_sha256"]
        assert preview["provenance"] == "deterministic_demo"
        assert preview["media"]["measured_duration_seconds"] == pytest.approx(8.0, abs=0.2)
        assert preview["media"]["byte_size"] > 0
        assert len(preview["media"]["sha256"]) == 64
        assert preview["profile_spec"] is None
        assert preview["quality_status"] == "pass"


def test_the_prompt_is_constrained_and_never_asks_for_a_flight_route(tmp_path) -> None:
    client = FakeGoogleClient(playable_clip(tmp_path))
    state = make_state(tmp_path, google_renderer(client))
    wait_for_status(
        state, state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo").job_id
    )

    assert len(client.prompts) == 3
    for prompt in client.prompts:
        assert "single continuous shot with no cuts" in prompt
        assert "Do not depict, plan, or imply a drone flight route" in prompt
        assert "Story purpose:" in prompt
        assert "Visual objective:" in prompt
        assert "Why this shot is next:" in prompt
        assert "Intended manual execution by the operator:" in prompt
        assert "Source context:" in prompt
        assert "8 seconds" in prompt


def test_prompt_builder_refuses_to_certify_safety(tmp_path) -> None:
    state = make_state(tmp_path, DeterministicVisualizationRenderer())
    recommendation = state.latest_recommendations[0]
    prompt = build_prompt(
        recommendation=recommendation,
        profile=AnimationProfile.DESCENDING_REVEAL,
        duration_seconds=8,
        source_label="synthetic",
        source_kind="synthetic",
        story_title="A lodge returns to life",
        beat_id="discovery",
        provenance="deterministic_demo",
    )
    assert "never to certify" in prompt
    assert "obstacle avoidance" in prompt
    assert "A lodge returns to life" in prompt


# --- untrusted provider output --------------------------------------------


def test_malformed_provider_response_fails_only_the_job(tmp_path) -> None:
    client = FakeGoogleClient(behavior=lambda self: {"video": "not-a-clip"})
    state = make_state(tmp_path, google_renderer(client))
    before = state.snapshot()
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, job.job_id, expected="failed")

    assert "malformed generation response" in failed["error"]
    assert failed["previews"] == []
    after = state.snapshot()
    assert after["beat_statuses"] == before["beat_statuses"]
    assert after["latest_recommendations"] == before["latest_recommendations"]
    assert after["recommendation_decisions"] == before["recommendation_decisions"]


def test_invalid_media_mime_type_is_rejected(tmp_path) -> None:
    client = FakeGoogleClient(playable_clip(tmp_path), mime_type="video/quicktime")
    state = make_state(tmp_path, google_renderer(client))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, job.job_id, expected="failed")

    assert "unsupported media type" in failed["error"]


def test_undecodable_media_is_rejected(tmp_path) -> None:
    client = FakeGoogleClient(
        b"\x00\x00\x00\x1cftypisom" + b"\x00" * 512, mime_type="video/mp4"
    )
    state = make_state(tmp_path, google_renderer(client))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, job.job_id, expected="failed")

    assert "could not be decoded" in failed["error"] or "no playable timeline" in failed["error"]


def test_media_that_is_not_a_real_container_is_rejected(tmp_path) -> None:
    client = FakeGoogleClient(b"this is plainly not a video file")
    state = make_state(tmp_path, google_renderer(client))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, job.job_id, expected="failed")

    assert "not a decodable WebM container" in failed["error"]


def test_mp4_media_that_is_not_a_real_container_is_rejected(tmp_path) -> None:
    client = FakeGoogleClient(b"this is plainly not a video file", mime_type="video/mp4")
    state = make_state(tmp_path, google_renderer(client))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, job.job_id, expected="failed")

    assert "not a decodable MP4 container" in failed["error"]


def test_media_in_a_codec_no_browser_can_play_is_rejected(tmp_path) -> None:
    """A well-formed MP4 carrying MPEG-4 Part 2 decodes with OpenCV but not in a browser."""
    client = FakeGoogleClient(unplayable_codec_clip(tmp_path), mime_type="video/mp4")
    state = make_state(tmp_path, google_renderer(client))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, job.job_id, expected="failed")

    assert "is not playable in a browser" in failed["error"]


def test_oversized_media_is_rejected(tmp_path) -> None:
    client = FakeGoogleClient(playable_clip(tmp_path))
    state = make_state(tmp_path, google_renderer(client, max_bytes=256))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, job.job_id, expected="failed")

    assert "byte ceiling" in failed["error"]


def test_media_with_the_wrong_duration_is_rejected(tmp_path) -> None:
    client = FakeGoogleClient(playable_clip(tmp_path, seconds=2.0))
    state = make_state(tmp_path, google_renderer(client))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, job.job_id, expected="failed")

    assert "not the expected 8s" in failed["error"]


def test_provider_timeout_fails_only_the_job_and_permits_retry(tmp_path) -> None:
    clip = playable_clip(tmp_path)

    def timeout_once(client):
        if client.calls == 1:
            raise VisualizationProviderError("Google video generation timed out")
        return None

    client = FakeGoogleClient(clip, behavior=timeout_once)
    state = make_state(tmp_path, google_renderer(client))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, job.job_id, expected="failed")
    assert "timed out" in failed["error"]
    assert failed["source_frame_available"] is False
    with pytest.raises(InvalidDecisionError, match="source frame is unavailable"):
        state.get_visualization_source_frame(job.job_id)

    retry = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    assert retry.job_id == job.job_id
    ready = wait_for_status(state, job.job_id)
    assert ready["status"] == "ready"
    assert ready["retry_count"] == 1


def test_wrong_recommendation_linkage_is_rejected(tmp_path) -> None:
    clip = playable_clip(tmp_path)

    class MislinkingRenderer(GoogleVideoRenderer):
        def render(self, context):
            previews = super().render(context)
            previews[1] = previews[1].model_copy(
                update={"recommendation_id": "someone-elses-recommendation"}
            )
            return previews

    renderer = MislinkingRenderer(
        FakeGoogleClient(clip), max_bytes=8_000_000, timeout_sec=5.0, supported_durations=(8,)
    )
    state = make_state(tmp_path, renderer)
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, job.job_id, expected="failed")

    assert "invalid recommendation linkage" in failed["error"]


def test_media_validation_error_is_a_value_error() -> None:
    assert issubclass(MediaValidationError, ValueError)


# --- job lifecycle and API -------------------------------------------------


def test_generated_job_is_idempotent_for_the_same_observation(tmp_path) -> None:
    client = FakeGoogleClient(playable_clip(tmp_path))
    state = make_state(tmp_path, google_renderer(client))
    frame = jpeg_bytes()
    first = state.request_visualization(REQUEST, frame, "deterministic_demo")
    wait_for_status(state, first.job_id)
    second = state.request_visualization(REQUEST, frame, "deterministic_demo")

    assert second.job_id == first.job_id
    # Three clips for three recommendations, and no second round of billing.
    assert client.calls == 3


def test_the_http_request_path_never_calls_the_provider_synchronously(tmp_path, monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()

    def block(client):
        started.set()
        release.wait(timeout=5)
        return None

    client = FakeGoogleClient(playable_clip(tmp_path), behavior=block)
    state = make_state(tmp_path, google_renderer(client))
    monkeypatch.setattr(server, "app_state", state)
    monkeypatch.setattr(server, "video_manager", None)
    http = TestClient(server.app)

    request_thread = threading.current_thread().name
    response = http.post("/api/visualizations", json={"duration_seconds": 10, "variation_count": 3})
    assert response.status_code == 200
    # The response is returned while the provider is still blocked.
    assert response.json()["status"] in {"requested", "rendering"}
    assert started.wait(timeout=5)
    assert client.thread_names
    assert request_thread not in client.thread_names
    assert all(name.startswith("cinepilot-visualization") for name in client.thread_names)

    release.set()
    ready = wait_for_status(state, response.json()["job_id"])
    assert ready["status"] == "ready"


def test_generated_media_is_served_and_scoped_to_its_preview(tmp_path, monkeypatch) -> None:
    client = FakeGoogleClient(playable_clip(tmp_path))
    state = make_state(tmp_path, google_renderer(client))
    monkeypatch.setattr(server, "app_state", state)
    monkeypatch.setattr(server, "video_manager", None)
    http = TestClient(server.app)

    job_id = http.post(
        "/api/visualizations", json={"duration_seconds": 10, "variation_count": 3}
    ).json()["job_id"]
    ready = wait_for_status(state, job_id)
    preview_id = ready["previews"][0]["preview_id"]

    media = http.get(f"/api/visualizations/{job_id}/previews/{preview_id}/media")
    assert media.status_code == 200
    assert media.headers["content-type"] == "video/webm"
    assert len(media.content) == ready["previews"][0]["media"]["byte_size"]

    assert http.get(f"/api/visualizations/{job_id}/previews/missing/media").status_code == 404
    assert http.get(f"/api/visualizations/missing/previews/{preview_id}/media").status_code == 404


def test_failed_generation_drops_media_and_keeps_creator_decisions(tmp_path) -> None:
    clip = playable_clip(tmp_path)

    def fail_on_the_last_clip(client):
        if client.calls == 3:
            raise VisualizationProviderError("provider rejected the third concept")
        return None

    client = FakeGoogleClient(clip, behavior=fail_on_the_last_clip)
    state = make_state(tmp_path, google_renderer(client))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    failed = wait_for_status(state, job.job_id, expected="failed")

    assert failed["status"] == "failed"
    assert failed["previews"] == []
    assert not list(state._visualization_media_dir(job.job_id).glob("*.bin"))
    with pytest.raises(StateNotFoundError, match="visualization preview not found"):
        state.get_visualization_media(job.job_id, "preview-1")


def test_deterministic_previews_expose_no_generated_media(tmp_path) -> None:
    state = make_state(tmp_path, DeterministicVisualizationRenderer())
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    ready = wait_for_status(state, job.job_id)

    assert ready["render_kind"] == "deterministic_animation"
    assert ready["duration_seconds"] == 10 and ready["duration_note"] == ""
    with pytest.raises(InvalidDecisionError, match="no generated media"):
        state.get_visualization_media(job.job_id, ready["previews"][0]["preview_id"])


def test_selecting_a_generated_preview_does_not_mark_the_shot_captured(tmp_path) -> None:
    client = FakeGoogleClient(playable_clip(tmp_path))
    state = make_state(tmp_path, google_renderer(client))
    before = state.snapshot()
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    ready = wait_for_status(state, job.job_id)
    recommendation_id = ready["previews"][0]["recommendation_id"]

    assert (
        state.decide_recommendation(recommendation_id, RecommendationDecision.SELECTED).value
        == "selected"
    )
    after = state.snapshot()
    assert after["beat_statuses"] == before["beat_statuses"]
    assert after["coverage"] == before["coverage"]
    assert after["capture_records"] == before["capture_records"]
    preview = next(
        item
        for item in after["visualization_jobs"][0]["previews"]
        if item["recommendation_id"] == recommendation_id
    )
    assert preview["recommendation_status"] == ShotRecommendationStatus.SELECTED.value
    assert preview["recommendation_status"] != ShotRecommendationStatus.COMPLETED.value


def test_the_event_ledger_records_the_full_previsualization_record(tmp_path) -> None:
    import json

    client = FakeGoogleClient(playable_clip(tmp_path))
    state = make_state(tmp_path, google_renderer(client))
    job = state.request_visualization(REQUEST, jpeg_bytes(), "deterministic_demo")
    ready = wait_for_status(state, job.job_id)
    state.decide_recommendation(
        ready["previews"][0]["recommendation_id"], RecommendationDecision.SELECTED
    )

    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    requested = next(item for item in events if item["event"] == "visualization_requested")
    ready_event = next(item for item in events if item["event"] == "visualization_ready")
    decision = next(item for item in events if item["event"] == "recommendation_decision")

    for field in (
        "job_id",
        "recommendation_ids",
        "provider",
        "model",
        "prompt_version",
        "source_frame_sha256",
        "source_provenance",
        "requested_at",
        "requested_duration_seconds",
        "duration_seconds",
        "retry_count",
    ):
        assert field in requested, field
    for field in ("ready_at", "output_validation", "duration_seconds", "media_sha256"):
        assert field in ready_event, field
    assert ready_event["output_validation"] == "passed"
    assert decision["decision"] == "selected"
    # Failed and malformed attempts must stay countable in the denominator.
    assert requested["retry_count"] == 0
    # The API key never reaches the ledger.
    assert "test-key" not in (tmp_path / "events.jsonl").read_text(encoding="utf-8")
