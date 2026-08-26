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
import copy
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from tools import SHOT_DEFINITIONS
from video_stream import VideoStreamManager

logger = logging.getLogger("cinepilot.server")

TEMPLATES_DIR = Path(__file__).parent / "templates"


class AppState:
    """Thread-safe shared application state with a change-version counter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._version = 0
        self.shots: Dict[str, Dict[str, str]] = {
            shot_id: {
                "title": title,
                "status": "PENDING",
                "feedback": "Awaiting first pass from the director.",
            }
            for shot_id, title in SHOT_DEFINITIONS.items()
        }
        self.latest_guidance: Dict[str, str] = {
            "instruction": "Standing by for the live feed. Bring the drone up when ready.",
            "priority": "INFO",
            "timestamp": "",
        }
        self.metrics: Dict[str, Any] = {
            "fps": 0.0,
            "latency_ms": 0.0,
            "frames_sent": 0,
            "gemini_status": "Connecting",
            "grafana_status": "Dry Run",
        }

    # -- mutators -------------------------------------------------------

    def update_shot(self, shot_id: str, status: str, feedback: str) -> None:
        with self._lock:
            shot = self.shots.get(shot_id)
            if shot is None:
                return
            shot["status"] = status
            shot["feedback"] = feedback
            self._version += 1

    def set_guidance(self, instruction: str, priority: str, timestamp: str) -> None:
        with self._lock:
            self.latest_guidance = {
                "instruction": instruction,
                "priority": priority,
                "timestamp": timestamp,
            }
            self._version += 1

    def update_metrics(self, **kwargs: Any) -> None:
        with self._lock:
            changed = False
            for key, value in kwargs.items():
                if key in self.metrics and self.metrics[key] != value:
                    self.metrics[key] = value
                    changed = True
            if changed:
                self._version += 1

    # -- accessors ------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "version": self._version,
                "shots": copy.deepcopy(self.shots),
                "latest_guidance": dict(self.latest_guidance),
                "metrics": dict(self.metrics),
            }

    @property
    def version(self) -> int:
        with self._lock:
            return self._version


app_state = AppState()

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
