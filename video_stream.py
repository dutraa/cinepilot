"""Hot-swappable video source manager for CinePilot.

Supported sources: "rtmp", "rtsp", "webcam", "file", "synthetic".

A daemon thread continuously grabs frames from the active source and exposes
an explicit source status machine:

    connecting -> live -> stale -> disconnected -> reconnecting -> ...
                                     -> fallback (only when explicitly allowed)
    stopped (terminal, after stop())

Real sources (rtmp/rtsp/webcam/file) never silently become synthetic frames:
on failure the manager reports `disconnected`/`reconnecting` and keeps
retrying with exponential backoff. Synthetic fallback happens only when the
manager was created with `allow_synthetic_fallback=True` (CLI opt-in or demo
mode). Stream URLs are always redacted before logging or exposure.
"""

import logging
import math
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional
from urllib.parse import urlsplit, urlunsplit

import cv2
import numpy as np

from config import settings

logger = logging.getLogger("cinepilot.video")

SYNTH_WIDTH = 1280
SYNTH_HEIGHT = 720

# Consecutive read failures on a real source before declaring it disconnected.
MAX_CONSECUTIVE_FAILURES = 30

# Sources that observe the real world (as opposed to generated imagery).
REAL_SOURCES = ("rtmp", "rtsp", "webcam", "file")
NETWORK_SOURCES = ("rtmp", "rtsp")


class SourceStatus(str, Enum):
    CONNECTING = "connecting"
    LIVE = "live"
    STALE = "stale"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    FALLBACK = "fallback"
    STOPPED = "stopped"


def redact_stream_url(url: Optional[str]) -> Optional[str]:
    """Strip credentials and query-string secrets from a stream URL.

    Keeps scheme/host/port/path so operators can still recognize the target.
    """
    if not url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<unparseable-url>"
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    if parts.username or parts.password:
        host = f"****@{host}"
    query = "<redacted>" if parts.query else ""
    return urlunsplit((parts.scheme, host, parts.path, query, ""))


def default_capture_factory(source_kind: str, target: object) -> Any:
    """Open a cv2.VideoCapture tuned for the source kind."""
    if source_kind in NETWORK_SOURCES:
        params = [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            int(settings.SOURCE_CONNECT_TIMEOUT_SEC * 1000),
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            int(max(settings.SOURCE_STALE_AFTER_SEC, 1.0) * 1000),
        ]
        capture = cv2.VideoCapture(str(target), cv2.CAP_FFMPEG, params)
        if settings.SOURCE_LOW_LATENCY:
            # Keep the driver-side queue minimal so frames stay current.
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return capture
    return cv2.VideoCapture(target)


class VideoStreamManager:
    """Thread-safe background frame grabber with explicit source provenance."""

    def __init__(
        self,
        source: str = "rtmp",
        rtmp_url: Optional[str] = None,
        rtsp_url: Optional[str] = None,
        video_path: Optional[str] = None,
        webcam_index: int = 0,
        allow_synthetic_fallback: Optional[bool] = None,
        capture_factory: Optional[Callable[[str, object], Any]] = None,
        on_transition: Optional[Callable[[dict], None]] = None,
        stale_after_sec: Optional[float] = None,
        reconnect_delay_sec: Optional[float] = None,
        reconnect_max_delay_sec: Optional[float] = None,
    ) -> None:
        self.requested_source = source.lower()
        self.active_source = self.requested_source
        self.rtmp_url = rtmp_url or settings.RTMP_URL
        self.rtsp_url = rtsp_url or settings.RTSP_URL
        self.video_path = video_path or ""
        self.webcam_index = webcam_index
        self.allow_synthetic_fallback = (
            settings.ALLOW_SYNTHETIC_FALLBACK
            if allow_synthetic_fallback is None
            else allow_synthetic_fallback
        )
        self._capture_factory = capture_factory or default_capture_factory
        self._on_transition = on_transition
        self.stale_after_sec = (
            settings.SOURCE_STALE_AFTER_SEC if stale_after_sec is None else stale_after_sec
        )
        self.reconnect_delay_sec = (
            settings.SOURCE_RECONNECT_DELAY_SEC
            if reconnect_delay_sec is None
            else reconnect_delay_sec
        )
        self.reconnect_max_delay_sec = (
            settings.SOURCE_RECONNECT_MAX_DELAY_SEC
            if reconnect_max_delay_sec is None
            else reconnect_max_delay_sec
        )

        self._capture: Optional[Any] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_frame_monotonic = 0.0
        self._latest_frame_wall: Optional[str] = None
        self._first_frame_wall: Optional[str] = None
        self._frames_captured = 0
        self._measured_fps = 0.0
        self._reconnect_count = 0
        self._status = SourceStatus.CONNECTING
        self._status_reason = "not started"
        self._frame_lock = threading.Lock()
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._synthetic_tick = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._running.set()
        self._set_status(SourceStatus.CONNECTING, "starting capture thread")
        self._thread = threading.Thread(
            target=self._grab_loop, name="video-grabber", daemon=True
        )
        self._thread.start()
        logger.info("VideoStreamManager started (source=%s)", self.requested_source)

    def stop(self) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._release_capture()
        self._set_status(SourceStatus.STOPPED, "stopped by operator")
        logger.info("VideoStreamManager stopped")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _set_status(self, status: SourceStatus, reason: str) -> None:
        notify = False
        with self._frame_lock:
            if self._status != status:
                self._status = status
                self._status_reason = reason
                notify = True
            else:
                self._status_reason = reason
        if notify:
            logger.info(
                "Source status: %s (%s) [requested=%s active=%s]",
                status.value,
                reason,
                self.requested_source,
                self.active_source,
            )
            if self._on_transition is not None:
                try:
                    self._on_transition(self.status_snapshot())
                except Exception:  # noqa: BLE001 - observers must not kill capture
                    logger.exception("Source transition observer failed")

    def _effective_status(self) -> SourceStatus:
        """Live status downgraded to stale when the newest frame is too old."""
        if self._status == SourceStatus.LIVE and self.requested_source in REAL_SOURCES:
            age = self._frame_age_locked()
            if age is None or age > self.stale_after_sec:
                return SourceStatus.STALE
        return self._status

    def _frame_age_locked(self) -> Optional[float]:
        if self._latest_frame_monotonic <= 0.0 or self._latest_frame is None:
            return None
        return time.monotonic() - self._latest_frame_monotonic

    @property
    def status(self) -> SourceStatus:
        with self._frame_lock:
            return self._effective_status()

    def _protocol(self) -> Optional[str]:
        if self.requested_source in NETWORK_SOURCES:
            return self.requested_source
        return None

    def _stream_url_for_source(self) -> Optional[str]:
        if self.requested_source == "rtmp":
            return self.rtmp_url
        if self.requested_source == "rtsp":
            return self.rtsp_url or self.rtmp_url
        return None

    def _provenance(self) -> str:
        if self.active_source == "synthetic-fallback":
            return "synthetic-fallback"
        if self.requested_source == "synthetic":
            return "synthetic"
        if self.requested_source in NETWORK_SOURCES:
            return f"live-{self.requested_source}"
        if self.requested_source == "file":
            return "prerecorded-file"
        if self.requested_source == "webcam":
            return "live-webcam"
        return self.requested_source

    def status_snapshot(self) -> dict:
        """Everything /health, /api/state, and the dashboard need to show."""
        with self._frame_lock:
            age = self._frame_age_locked()
            status = self._effective_status()
            return {
                "requested_source": self.requested_source,
                "active_source": self.active_source,
                "protocol": self._protocol(),
                "stream_url": redact_stream_url(self._stream_url_for_source()),
                "status": status.value,
                "status_reason": self._status_reason,
                "is_real_source": self.requested_source in REAL_SOURCES,
                "provenance": self._provenance(),
                "first_frame_at": self._first_frame_wall,
                "last_frame_at": self._latest_frame_wall,
                "frame_age_sec": round(age, 3) if age is not None else None,
                "fps": round(self._measured_fps, 2),
                "frames_captured": self._frames_captured,
                "reconnect_count": self._reconnect_count,
                "fallback_active": self.active_source == "synthetic-fallback",
                "allow_synthetic_fallback": self.allow_synthetic_fallback,
                "stale_after_sec": self.stale_after_sec,
            }

    # ------------------------------------------------------------------
    # Frame accessors
    # ------------------------------------------------------------------

    def get_raw_frame(
        self, max_age_sec: Optional[float] = None
    ) -> Optional[np.ndarray]:
        """Latest BGR frame (a copy), or None if nothing current is available.

        When `max_age_sec` is given, frames older than that are treated as
        unavailable so stale imagery is never presented as current.
        """
        with self._frame_lock:
            if self._latest_frame is None:
                return None
            if max_age_sec is not None:
                age = self._frame_age_locked()
                if age is None or age > max_age_sec:
                    return None
            return self._latest_frame.copy()

    def get_fresh_jpeg(
        self,
        quality: int = 80,
        max_dim: int = 1024,
        max_age_sec: Optional[float] = None,
    ) -> Optional[bytes]:
        """JPEG of the latest frame only if it is fresh enough for analysis."""
        if max_age_sec is None:
            max_age_sec = settings.SOURCE_MAX_FRAME_AGE_SEC
        frame = self.get_raw_frame(max_age_sec=max_age_sec)
        if frame is None:
            return None
        return self._encode_jpeg(frame, quality, max_dim)

    def get_jpeg_bytes(self, quality: int = 80, max_dim: int = 1024) -> Optional[bytes]:
        """Latest frame encoded as JPEG (no freshness constraint)."""
        frame = self.get_raw_frame()
        if frame is None:
            return None
        return self._encode_jpeg(frame, quality, max_dim)

    @staticmethod
    def _encode_jpeg(frame: np.ndarray, quality: int, max_dim: int) -> Optional[bytes]:
        h, w = frame.shape[:2]
        longest = max(h, w)
        if longest > max_dim:
            scale = max_dim / float(longest)
            frame = cv2.resize(
                frame,
                (int(round(w * scale)), int(round(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        ok, encoded = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
        )
        if not ok:
            return None
        return encoded.tobytes()

    def get_deterministic_synthetic_jpeg(self) -> Optional[bytes]:
        """Return the seeded synthetic scene used when demo mode has no frame yet."""
        frame = self._render_synthetic_frame()
        ok, encoded = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        )
        return encoded.tobytes() if ok else None

    # ------------------------------------------------------------------
    # Capture loop
    # ------------------------------------------------------------------

    def _grab_loop(self) -> None:
        if self.requested_source == "synthetic":
            self._run_synthetic_loop("synthetic")
            return

        reconnect_delay = self.reconnect_delay_sec
        first_attempt = True
        while self._running.is_set():
            self._set_status(
                SourceStatus.CONNECTING if first_attempt else SourceStatus.RECONNECTING,
                f"opening source '{self.requested_source}'",
            )
            if not first_attempt:
                with self._frame_lock:
                    self._reconnect_count += 1
            if not self._open_capture():
                self._handle_source_failure(
                    f"could not open source '{self.requested_source}'"
                )
                if not self._running.is_set():
                    return
                if self._maybe_enter_fallback():
                    return
                first_attempt = False
                self._sleep_interruptible(reconnect_delay)
                reconnect_delay = min(
                    reconnect_delay * 2.0, self.reconnect_max_delay_sec
                )
                continue

            reconnect_delay = self.reconnect_delay_sec
            connected_ok = self._read_until_failure()
            if not self._running.is_set():
                return
            if connected_ok:
                # At least one frame was delivered before the drop.
                first_attempt = False
            if self._maybe_enter_fallback():
                return
            first_attempt = False
            self._sleep_interruptible(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2.0, self.reconnect_max_delay_sec)

    def _read_until_failure(self) -> bool:
        """Read frames until the source fails. Returns True if any frame arrived."""
        failures = 0
        got_frame = False
        while self._running.is_set():
            ok, frame = self._capture.read()
            if ok and frame is not None:
                failures = 0
                got_frame = True
                self._store_frame(frame)
                self._set_status(SourceStatus.LIVE, "receiving frames")
                if self.requested_source == "file":
                    fps = self._capture.get(cv2.CAP_PROP_FPS) or 30.0
                    time.sleep(1.0 / max(fps, 1.0))
                continue

            failures += 1
            if self.requested_source == "file":
                # Loop the file endlessly.
                self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    self._handle_source_failure("video file unreadable")
                    return got_frame
                continue
            if failures >= MAX_CONSECUTIVE_FAILURES:
                self._handle_source_failure(
                    f"source '{self.requested_source}' stopped delivering frames"
                )
                return got_frame
            time.sleep(0.1)
        return got_frame

    def _handle_source_failure(self, reason: str) -> None:
        self._release_capture()
        with self._frame_lock:
            # Never reuse a stale frame once the source is disconnected.
            self._latest_frame = None
            self._latest_frame_monotonic = 0.0
        self._set_status(SourceStatus.DISCONNECTED, reason)

    def _maybe_enter_fallback(self) -> bool:
        if not self.allow_synthetic_fallback:
            return False
        self.active_source = "synthetic-fallback"
        self._set_status(
            SourceStatus.FALLBACK,
            "synthetic fallback engaged (explicitly allowed)",
        )
        self._run_synthetic_loop("synthetic-fallback")
        return True

    def _run_synthetic_loop(self, label: str) -> None:
        self.active_source = label
        if label == "synthetic":
            self._set_status(SourceStatus.LIVE, "synthetic generator running")
        while self._running.is_set():
            frame = self._render_synthetic_frame()
            self._store_frame(frame)
            time.sleep(1.0 / 30.0)

    def _sleep_interruptible(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while self._running.is_set() and time.monotonic() < deadline:
            time.sleep(min(0.1, max(deadline - time.monotonic(), 0.0)))

    def _open_capture(self) -> bool:
        self._release_capture()
        target: object
        if self.requested_source == "rtmp":
            target = self.rtmp_url
        elif self.requested_source == "rtsp":
            target = self.rtsp_url or self.rtmp_url
        elif self.requested_source == "file":
            target = self.video_path
        elif self.requested_source == "webcam":
            target = self.webcam_index
        else:
            return False

        logger.info(
            "Opening video source '%s' -> %s",
            self.requested_source,
            redact_stream_url(target) if isinstance(target, str) else target,
        )
        try:
            capture = self._capture_factory(self.requested_source, target)
        except Exception:  # noqa: BLE001 - open failures become reconnects
            logger.exception("Capture factory failed for '%s'", self.requested_source)
            return False
        if capture is None or not capture.isOpened():
            if capture is not None:
                capture.release()
            return False
        self._capture = capture
        self.active_source = self.requested_source
        return True

    def _release_capture(self) -> None:
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:  # noqa: BLE001
                pass
            self._capture = None

    def _store_frame(self, frame: np.ndarray) -> None:
        now = time.monotonic()
        wall = datetime.now(timezone.utc).isoformat()
        with self._frame_lock:
            if self._latest_frame_monotonic > 0.0:
                dt = now - self._latest_frame_monotonic
                if dt > 0:
                    instant = 1.0 / dt
                    self._measured_fps = (
                        0.8 * self._measured_fps + 0.2 * instant
                        if self._measured_fps > 0
                        else instant
                    )
            # Bounded buffering: only the newest frame is retained.
            self._latest_frame = frame
            self._latest_frame_monotonic = now
            self._latest_frame_wall = wall
            if self._first_frame_wall is None:
                self._first_frame_wall = wall
            self._frames_captured += 1

    # ------------------------------------------------------------------
    # Synthetic aerial scene
    # ------------------------------------------------------------------

    def _render_synthetic_frame(self) -> np.ndarray:
        """Draw a dynamic aerial-style scene: sky, terrain, drifting subject."""
        self._synthetic_tick += 1
        t = self._synthetic_tick / 30.0
        frame = np.zeros((SYNTH_HEIGHT, SYNTH_WIDTH, 3), dtype=np.uint8)

        # Gently oscillating horizon (simulates gimbal roll/tilt drift).
        horizon_y = int(SYNTH_HEIGHT * 0.42 + 22.0 * math.sin(t * 0.35))
        tilt = 14.0 * math.sin(t * 0.22)

        # Sky: vertical blue gradient above the horizon.
        for y in range(0, max(horizon_y, 1)):
            shade = y / max(horizon_y, 1)
            frame[y, :] = (
                int(180 - 60 * shade),  # B
                int(120 - 40 * shade),  # G
                int(70 - 30 * shade),  # R
            )

        # Terrain: green gradient below the horizon.
        for y in range(horizon_y, SYNTH_HEIGHT):
            depth = (y - horizon_y) / max(SYNTH_HEIGHT - horizon_y, 1)
            frame[y, :] = (
                int(40 + 20 * depth),  # B
                int(110 + 60 * depth),  # G
                int(40 + 15 * depth),  # R
            )

        # Perspective field lines converging toward the horizon.
        vanish_x = int(SYNTH_WIDTH / 2 + 120 * math.sin(t * 0.15))
        for i in range(-6, 7):
            x_bottom = int(SYNTH_WIDTH / 2 + i * 170)
            cv2.line(
                frame,
                (x_bottom, SYNTH_HEIGHT),
                (vanish_x, horizon_y),
                (35, 90, 35),
                2,
                cv2.LINE_AA,
            )

        # Tilted horizon line.
        dx = SYNTH_WIDTH // 2
        dy = int(math.tan(math.radians(tilt)) * dx)
        cv2.line(
            frame,
            (0, horizon_y + dy),
            (SYNTH_WIDTH, horizon_y - dy),
            (230, 240, 250),
            2,
            cv2.LINE_AA,
        )

        # Moving circular "subject" (e.g. a vehicle / structure of interest).
        subj_x = int(SYNTH_WIDTH / 2 + (SYNTH_WIDTH * 0.30) * math.sin(t * 0.5))
        subj_y = int(
            horizon_y
            + (SYNTH_HEIGHT - horizon_y) * (0.55 + 0.25 * math.sin(t * 0.33 + 1.2))
        )
        subj_r = int(26 + 8 * math.sin(t * 0.8))
        cv2.circle(frame, (subj_x, subj_y), subj_r, (30, 30, 200), -1, cv2.LINE_AA)
        cv2.circle(frame, (subj_x, subj_y), subj_r + 8, (255, 255, 255), 2, cv2.LINE_AA)
        return frame


def render_status_frame(status: str, reason: str) -> np.ndarray:
    """A clearly-labeled placeholder card shown when no current frame exists.

    This is a status card, not footage: it must never be mistaken for a live
    or synthetic observation.
    """
    frame = np.zeros((SYNTH_HEIGHT, SYNTH_WIDTH, 3), dtype=np.uint8)
    frame[:] = (18, 14, 12)
    cv2.putText(
        frame,
        "NO LIVE SIGNAL",
        (SYNTH_WIDTH // 2 - 260, SYNTH_HEIGHT // 2 - 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.6,
        (60, 76, 231),
        3,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"source status: {status}"[:70],
        (SYNTH_WIDTH // 2 - 260, SYNTH_HEIGHT // 2 + 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (200, 200, 200),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        str(reason)[:80],
        (SYNTH_WIDTH // 2 - 260, SYNTH_HEIGHT // 2 + 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (140, 140, 140),
        1,
        cv2.LINE_AA,
    )
    return frame
