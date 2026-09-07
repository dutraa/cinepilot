"""FastAPI web layer for CinePilot's Director's Monitor.

Exposes:
  GET /            — dark-mode dashboard (templates/index.html)
  GET /video_feed  — MJPEG live monitor stream
  GET /events      — SSE stream of the full app state (every 250ms or on change)
  GET /health      — JSON system status

The thread-safe `AppState` singleton (`app_state`) is shared with the
DirectorAgent and the tool executors in `tools.py`.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional
from uuid import uuid4

import cv2
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

from config import settings
from event_log import EventLog
from schemas import (
    IntentUpdateRequest,
    RecommendationDecisionRequest,
    ShotRecommendationBatchInput,
    ShotUpdateRequest,
    StoryBeatRequest,
    TweakDecisionRequest,
    VisualizationRequestInput,
    VisualizationSourceKind,
)
from state import AppState, InvalidDecisionError, StateNotFoundError
from video_stream import VideoStreamManager, render_status_frame

logger = logging.getLogger("cinepilot.server")

TEMPLATES_DIR = Path(__file__).parent / "templates"


app_state = AppState(EventLog(settings.EVENT_LOG_PATH))

# Injected by main.py before the server starts.
video_manager: Optional[VideoStreamManager] = None
demo_provider = None


def set_video_manager(manager: VideoStreamManager) -> None:
    global video_manager
    video_manager = manager


def set_demo_provider(provider: object | None) -> None:
    global demo_provider
    demo_provider = provider


app = FastAPI(title="CinePilot Director's Monitor")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html_path = TEMPLATES_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


def state_snapshot_with_source() -> dict:
    """App state merged with the live source snapshot (redacted URL only)."""
    snap = app_state.snapshot()
    if video_manager is not None:
        snap["source"] = video_manager.status_snapshot()
    return snap


@app.get("/api/state")
async def state() -> JSONResponse:
    return JSONResponse(state_snapshot_with_source())


@app.get("/api/story")
async def story() -> JSONResponse:
    snapshot = app_state.snapshot()
    return JSONResponse(
        {
            "story": snapshot["story"],
            "story_version": snapshot["story_version"],
            "story_context_version": snapshot["story_context_version"],
            "beats": snapshot["beats"],
            "active_beat": snapshot["active_beat"],
            "beat_statuses": snapshot["beat_statuses"],
            "provenance": snapshot["provenance"],
        }
    )


@app.post("/api/story/beat")
async def update_story_beat(payload: StoryBeatRequest) -> JSONResponse:
    try:
        if payload.action == "skip":
            app_state.skip_active_beat(payload.beat_id)
        else:
            app_state.set_active_beat(payload.beat_id)
    except StateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidDecisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    snapshot = app_state.snapshot()
    return JSONResponse(
        {"ok": True, "active_beat": snapshot["active_beat"], "beats": snapshot["beats"]}
    )


@app.get("/api/coverage")
async def coverage() -> JSONResponse:
    snapshot = app_state.snapshot()
    return JSONResponse(
        {
            "coverage": snapshot["coverage"],
            "covered_coverage": snapshot["covered_coverage"],
            "missing_coverage": snapshot["missing_coverage"],
            "current_shot_contribution": snapshot["current_shot_contribution"],
            "story_version": snapshot["story_version"],
        }
    )


@app.get("/api/recommendations")
async def recommendations() -> JSONResponse:
    snapshot = app_state.snapshot()
    return JSONResponse(
        {
            "latest_recommendations": snapshot["latest_recommendations"],
            "recommendation_history": snapshot["recommendation_history"],
            "recommendation_decisions": snapshot["recommendation_decisions"],
            "story_context_version": snapshot["story_context_version"],
        }
    )


def _visualization_source() -> tuple[VisualizationSourceKind, str]:
    source = video_manager.active_source if video_manager is not None else "unknown"
    if source == "unknown" and app_state.snapshot()["provenance"].get("mode") == "deterministic_demo":
        return VisualizationSourceKind.SYNTHETIC, "synthetic"
    if source == "synthetic" or source.startswith("synthetic"):
        return VisualizationSourceKind.SYNTHETIC, source
    if source == "file":
        return VisualizationSourceKind.FILE, source
    if source == "webcam":
        return VisualizationSourceKind.WEBCAM, source
    if source == "rtsp":
        return VisualizationSourceKind.RTSP, source
    if source == "rtmp":
        return VisualizationSourceKind.RTMP, source
    return VisualizationSourceKind.LIVE, source


def _latest_visualization_frame() -> bytes | None:
    if video_manager is not None:
        frame = video_manager.get_jpeg_bytes(quality=90, max_dim=1024)
        if frame is not None:
            return frame
    snapshot = app_state.snapshot()
    if snapshot["provenance"].get("mode") == "deterministic_demo":
        return VideoStreamManager(source="synthetic").get_deterministic_synthetic_jpeg()
    return None


@app.post("/api/visualizations")
async def create_visualization(payload: VisualizationRequestInput) -> JSONResponse:
    frame = _latest_visualization_frame()
    if frame is None:
        raise HTTPException(status_code=409, detail="current observation is unavailable")
    source_kind, source_label = _visualization_source()
    try:
        job = app_state.request_visualization(
            payload,
            source_frame=frame,
            provenance=app_state.snapshot()["provenance"].get("mode", "live"),
            source_kind=source_kind,
            source_label=source_label,
        )
    except StateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidDecisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse(job.model_dump(mode="json"))


@app.get("/api/visualizations")
async def list_visualizations() -> JSONResponse:
    snapshot = app_state.snapshot()
    return JSONResponse(
        {
            "visualizations": snapshot["visualization_jobs"],
            "jobs": snapshot["visualization_jobs"],
            "latest_visualization_job": snapshot["latest_visualization_job"],
        }
    )


@app.get("/api/visualizations/{job_id}")
async def get_visualization(job_id: str) -> JSONResponse:
    job = next(
        (item for item in app_state.snapshot()["visualization_jobs"] if item["job_id"] == job_id),
        None,
    )
    if job is None:
        raise HTTPException(status_code=404, detail=f"visualization job not found: {job_id}")
    return JSONResponse(job)


@app.get("/api/visualizations/{job_id}/source-frame")
async def get_visualization_source_frame(job_id: str) -> Response:
    try:
        frame = app_state.get_visualization_source_frame(job_id)
    except StateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidDecisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(content=frame, media_type="image/jpeg")


@app.post("/api/recommendations")
async def publish_recommendations(payload: ShotRecommendationBatchInput) -> JSONResponse:
    snapshot = app_state.snapshot()
    observation_id = snapshot["current_shot_contribution"].get("observation_id") or f"manual-observation-{uuid4()}"
    try:
        published = app_state.publish_recommendations(
            payload.recommendations,
            observation_id=observation_id,
            provenance="manual",
        )
    except StateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidDecisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse(
        {
            "ok": True,
            "recommendations": [item.model_dump(mode="json") for item in published],
        }
    )


@app.post("/api/recommendations/{recommendation_id}/decision")
async def decide_recommendation(
    recommendation_id: str, payload: RecommendationDecisionRequest
) -> JSONResponse:
    try:
        status = app_state.decide_recommendation(recommendation_id, payload.decision)
    except StateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidDecisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if status.value == "completed" and demo_provider is not None:
        publish_current = getattr(demo_provider, "publish_current", None)
        if publish_current is not None:
            publish_current(app_state)
    return JSONResponse(
        {"ok": True, "recommendation_id": recommendation_id, "status": status.value}
    )


@app.post("/api/intent")
async def update_intent(payload: IntentUpdateRequest) -> JSONResponse:
    version = app_state.set_intent(payload)
    return JSONResponse(
        {
            "ok": True,
            "intent_version": version,
            "intent": payload.model_dump(mode="json"),
        }
    )


@app.post("/api/critiques/{critique_id}/tweaks/{tweak_id}/decision")
async def decide_tweak(
    critique_id: str,
    tweak_id: str,
    payload: TweakDecisionRequest,
) -> JSONResponse:
    try:
        status = app_state.decide_tweak(critique_id, tweak_id, payload.decision)
    except StateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidDecisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse(
        {
            "ok": True,
            "critique_id": critique_id,
            "tweak_id": tweak_id,
            "status": status.value,
        }
    )


@app.post("/api/shots/{shot_id}")
async def update_shot(shot_id: str, payload: ShotUpdateRequest) -> JSONResponse:
    """Creator-only shot lifecycle update — the only path that can mark a
    shot COMPLETED. Gemini's update_shot_list tool cannot complete shots."""
    try:
        app_state.creator_update_shot(
            shot_id, payload.status.value, payload.feedback
        )
    except StateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidDecisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse(
        {"ok": True, "shot_id": shot_id, "status": payload.status.value}
    )


@app.get("/video_feed")
async def video_feed() -> StreamingResponse:
    boundary = "frame"

    async def mjpeg_generator():
        while True:
            raw = None
            if video_manager is not None:
                # Never present a stale frame as the current view.
                raw = video_manager.get_raw_frame(
                    max_age_sec=video_manager.stale_after_sec
                )
                if raw is None:
                    status = video_manager.status_snapshot()
                    raw = render_status_frame(
                        status["status"], status["status_reason"]
                    )
            else:
                raw = render_status_frame("stopped", "video manager not running")
            ok, encoded = cv2.imencode(
                ".jpg", raw, [int(cv2.IMWRITE_JPEG_QUALITY), 82]
            )
            if ok:
                frame_bytes = encoded.tobytes()
                yield (
                    b"--" + boundary.encode() + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame_bytes)).encode() + b"\r\n\r\n"
                    + frame_bytes
                    + b"\r\n"
                )
            await asyncio.sleep(1.0 / 25.0)

    return StreamingResponse(
        mjpeg_generator(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}",
    )


@app.get("/events")
async def events() -> StreamingResponse:
    async def sse_generator():
        last_version = -1
        last_emit = 0.0
        while True:
            snap = state_snapshot_with_source()
            now = time.monotonic()
            # Push on change, or at least every 250ms as a heartbeat cadence.
            if snap["version"] != last_version or (now - last_emit) >= 0.25:
                last_version = snap["version"]
                last_emit = now
                yield f"data: {json.dumps(snap)}\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health() -> JSONResponse:
    snap = app_state.snapshot()
    source = (
        video_manager.status_snapshot()
        if video_manager is not None
        else {"status": "stopped", "status_reason": "video manager not running"}
    )
    return JSONResponse(
        {
            "status": "ok",
            # Backward-compatible summary field.
            "video_source": source.get("active_source", "none"),
            "source": source,
            "gemini_status": snap["metrics"]["gemini_status"],
            "grafana_status": snap["metrics"]["grafana_status"],
            "frames_sent": snap["metrics"]["frames_sent"],
            "frames_skipped_stale": snap["metrics"]["frames_skipped_stale"],
            "malformed_tool_calls": snap["metrics"]["malformed_tool_calls"],
        }
    )
