"""Hot-swappable video source manager for CinePilot.

Supported sources: "rtmp", "rtsp", "webcam", "file", "synthetic".

A daemon thread continuously grabs frames from the active source. If a live
source (rtmp/rtsp/webcam/file) cannot be opened or stops delivering frames,
the manager logs a warning and hot-swaps to a "synthetic-fallback" generator
so the pipeline (and Gemini) always has frames to work with.
"""

import logging
import math
import threading
import time
from datetime import datetime
from typing import Optional

import cv2
import numpy as np

from config import settings

logger = logging.getLogger("cinepilot.video")

SYNTH_WIDTH = 1280
SYNTH_HEIGHT = 720

# Consecutive read failures on a real source before falling back to synthetic.
MAX_CONSECUTIVE_FAILURES = 30


class VideoStreamManager:
    """Thread-safe background frame grabber with automatic synthetic fallback."""

    def __init__(
        self,
        source: str = "rtmp",
        rtmp_url: Optional[str] = None,
        rtsp_url: Optional[str] = None,
        video_path: Optional[str] = None,
        webcam_index: int = 0,
    ) -> None:
        self.requested_source = source.lower()
        self.active_source = self.requested_source
        self.rtmp_url = rtmp_url or settings.RTMP_URL
        self.rtsp_url = rtsp_url or ""
        self.video_path = video_path or ""
        self.webcam_index = webcam_index

        self._capture: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[np.ndarray] = None
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
        logger.info("VideoStreamManager stopped")

    # ------------------------------------------------------------------
    # Frame accessors
    # ------------------------------------------------------------------

    def get_raw_frame(self) -> Optional[np.ndarray]:
        """Latest BGR frame (a copy), or None if nothing captured yet."""
        with self._frame_lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def get_jpeg_bytes(self, quality: int = 80, max_dim: int = 1024) -> Optional[bytes]:
        """Latest frame encoded as JPEG for Gemini, downscaled to max_dim."""
        frame = self.get_raw_frame()
        if frame is None:
            return None
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

    # ------------------------------------------------------------------
    # Capture loop
    # ------------------------------------------------------------------

    def _grab_loop(self) -> None:
        failures = 0
        while self._running.is_set():
            if self.active_source == "synthetic" or self.active_source.startswith(
                "synthetic"
            ):
                frame = self._render_synthetic_frame()
                self._store_frame(frame)
                time.sleep(1.0 / 30.0)
                continue

            if self._capture is None:
                if not self._open_capture():
                    self._fallback_to_synthetic(
                        f"Could not open source '{self.active_source}'"
                    )
                    continue
                failures = 0

            ok, frame = self._capture.read()
            if ok and frame is not None:
                failures = 0
                self._store_frame(frame)
                # Pace file playback roughly at its native rate.
                if self.active_source == "file":
                    fps = self._capture.get(cv2.CAP_PROP_FPS) or 30.0
                    time.sleep(1.0 / max(fps, 1.0))
                continue

            # Read failure handling.
            failures += 1
            if self.active_source == "file":
                # Loop the file endlessly.
                self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    self._fallback_to_synthetic("Video file unreadable")
                continue
            if failures >= MAX_CONSECUTIVE_FAILURES:
                self._fallback_to_synthetic(
                    f"Source '{self.active_source}' stopped delivering frames"
                )
            else:
                time.sleep(0.1)

    def _open_capture(self) -> bool:
        self._release_capture()
        target: object
        if self.active_source == "rtmp":
            target = self.rtmp_url
        elif self.active_source == "rtsp":
            target = self.rtsp_url or self.rtmp_url
        elif self.active_source == "file":
            target = self.video_path
        elif self.active_source == "webcam":
            target = self.webcam_index
        else:
            return False

        logger.info("Opening video source '%s' -> %r", self.active_source, target)
        capture = cv2.VideoCapture(target)
        if not capture.isOpened():
            capture.release()
            return False
        self._capture = capture
        return True

    def _release_capture(self) -> None:
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:  # noqa: BLE001
                pass
            self._capture = None

    def _fallback_to_synthetic(self, reason: str) -> None:
        logger.warning(
            "%s — switching to synthetic-fallback aerial generator", reason
        )
        self._release_capture()
        self.active_source = "synthetic-fallback"

    def _store_frame(self, frame: np.ndarray) -> None:
        with self._frame_lock:
            self._latest_frame = frame

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
        cv2.putText(
            frame,
            "SUBJECT",
            (subj_x - 40, subj_y - subj_r - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        # Rule-of-thirds composition guides.
        third_color = (200, 200, 200)
        for fx in (1 / 3, 2 / 3):
            x = int(SYNTH_WIDTH * fx)
            cv2.line(frame, (x, 0), (x, SYNTH_HEIGHT), third_color, 1, cv2.LINE_AA)
        for fy in (1 / 3, 2 / 3):
            y = int(SYNTH_HEIGHT * fy)
            cv2.line(frame, (0, y), (SYNTH_WIDTH, y), third_color, 1, cv2.LINE_AA)

        # HUD: frame counter, timestamp, source badge.
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame,
            f"FRAME {self._synthetic_tick:07d}",
            (18, 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 180),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            stamp,
            (18, SYNTH_HEIGHT - 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"SRC: {self.active_source.upper()}",
            (SYNTH_WIDTH - 320, 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 200, 255),
            2,
            cv2.LINE_AA,
        )
        return frame
