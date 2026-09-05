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

import cv2
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from config import settings
from event_log import EventLog
from schemas import IntentUpdateRequest, ShotUpdateRequest, TweakDecisionRequest
from state import AppState, InvalidDecisionError, StateNotFoundError
from video_stream import VideoStreamManager, render_status_frame

logger = logging.getLogger("cinepilot.server")

TEMPLATES_DIR = Path(__file__).parent / "templates"


app_state = AppState(EventLog(settings.EVENT_LOG_PATH))

# Injected by main.py before the server starts.
video_manager: Optional[VideoStreamManager] = None


def set_video_manager(manager: VideoStreamManager) -> None:
    global video_manager
    video_manager = manager


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
