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
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from config import settings
from event_log import EventLog
from schemas import (
    IntentUpdateRequest,
    RecommendationDecisionRequest,
    ShotRecommendationBatchInput,
    StoryBeatRequest,
    TweakDecisionRequest,
)
from state import AppState, InvalidDecisionError, StateNotFoundError
from video_stream import VideoStreamManager

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


@app.get("/api/state")
async def state() -> JSONResponse:
    return JSONResponse(app_state.snapshot())


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


@app.get("/video_feed")
async def video_feed() -> StreamingResponse:
    boundary = "frame"

    async def mjpeg_generator():
        placeholder_sent = False
        while True:
            frame_bytes: Optional[bytes] = None
            if video_manager is not None:
                raw = video_manager.get_raw_frame()
                if raw is not None:
                    ok, encoded = cv2.imencode(
                        ".jpg", raw, [int(cv2.IMWRITE_JPEG_QUALITY), 82]
                    )
                    if ok:
                        frame_bytes = encoded.tobytes()
            if frame_bytes is not None:
                placeholder_sent = False
                yield (
                    b"--" + boundary.encode() + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame_bytes)).encode() + b"\r\n\r\n"
                    + frame_bytes
                    + b"\r\n"
                )
            elif not placeholder_sent:
                placeholder_sent = True
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
            snap = app_state.snapshot()
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
    return JSONResponse(
        {
            "status": "ok",
            "video_source": (
                video_manager.active_source if video_manager is not None else "none"
            ),
            "gemini_status": snap["metrics"]["gemini_status"],
            "grafana_status": snap["metrics"]["grafana_status"],
            "frames_sent": snap["metrics"]["frames_sent"],
        }
    )
