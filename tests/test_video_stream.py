"""VideoStreamManager tests using a deterministic fake capture adapter.

No hardware, network, or real stream is required: FakeCapture scripts the
exact sequence of open/read outcomes so connection, reconnect, stale, and
fallback behavior can be verified deterministically.
"""

import time

import numpy as np
import pytest

import video_stream
from video_stream import SourceStatus, VideoStreamManager, redact_stream_url

FRAME = np.zeros((24, 32, 3), dtype=np.uint8)


class FakeCapture:
    """Scripted capture: yields `frames` successful reads, then fails."""

    def __init__(self, frames: int, opened: bool = True) -> None:
        self._remaining = frames
        self._opened = opened
        self.released = False

    def isOpened(self) -> bool:  # noqa: N802 - cv2 interface
        return self._opened

    def read(self):
        if self._opened and self._remaining > 0:
            self._remaining -= 1
            return True, FRAME.copy()
        return False, None

    def release(self) -> None:
        self.released = True

    def get(self, _prop) -> float:
        return 30.0

    def set(self, _prop, _value) -> bool:
        return True


class ScriptedFactory:
    """Returns one scripted capture per open attempt."""

    def __init__(self, captures) -> None:
        self._captures = list(captures)
        self.open_attempts = 0

    def __call__(self, _source_kind, _target):
        self.open_attempts += 1
        if not self._captures:
            return FakeCapture(0, opened=False)
        return self._captures.pop(0)


def make_manager(factory, **kwargs):
    defaults = dict(
        source="rtmp",
        rtmp_url="rtmp://user:secret@127.0.0.1/live/key?token=abc",
        allow_synthetic_fallback=False,
        capture_factory=factory,
        reconnect_delay_sec=0.01,
        reconnect_max_delay_sec=0.05,
        stale_after_sec=0.5,
    )
    defaults.update(kwargs)
    return VideoStreamManager(**defaults)


def wait_for(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture(autouse=True)
def fast_failure_threshold(monkeypatch):
    monkeypatch.setattr(video_stream, "MAX_CONSECUTIVE_FAILURES", 3)


# ---------------------------------------------------------------------------
# URL redaction
# ---------------------------------------------------------------------------


def test_redaction_strips_credentials_and_query() -> None:
    redacted = redact_stream_url("rtmp://user:secret@10.0.0.5:1935/live/key?token=abc")
    assert "user" not in redacted
    assert "secret" not in redacted
    assert "token" not in redacted
    assert "abc" not in redacted
    assert "10.0.0.5:1935" in redacted
    assert "/live/key" in redacted


def test_redaction_handles_plain_and_empty_urls() -> None:
    assert redact_stream_url("rtsp://192.168.1.50:554/stream") == (
        "rtsp://192.168.1.50:554/stream"
    )
    assert redact_stream_url("") == ""
    assert redact_stream_url(None) is None


def test_snapshot_never_exposes_credentials() -> None:
    manager = make_manager(ScriptedFactory([]))
    snapshot = manager.status_snapshot()
    assert "secret" not in str(snapshot)
    assert "token=abc" not in str(snapshot)


# ---------------------------------------------------------------------------
# Connection state transitions
# ---------------------------------------------------------------------------


def test_real_source_goes_live_then_disconnects_without_fallback() -> None:
    transitions = []
    factory = ScriptedFactory([FakeCapture(frames=5)])
    manager = make_manager(factory, on_transition=lambda s: transitions.append(s))
    manager.start()
    try:
        assert wait_for(lambda: manager.status_snapshot()["frames_captured"] >= 5)
        assert wait_for(
            lambda: manager.status_snapshot()["status"]
            in ("disconnected", "reconnecting", "connecting")
        )
        snapshot = manager.status_snapshot()
        # A real-drone failure must never silently become a synthetic frame.
        assert snapshot["active_source"] != "synthetic-fallback"
        assert snapshot["fallback_active"] is False
        assert manager.get_raw_frame() is None
    finally:
        manager.stop()

    statuses = [t["status"] for t in transitions]
    assert "live" in statuses
    assert "disconnected" in statuses
    assert "fallback" not in statuses


def test_no_stale_frame_reuse_after_disconnect() -> None:
    factory = ScriptedFactory([FakeCapture(frames=2)])
    manager = make_manager(factory)
    manager.start()
    try:
        assert wait_for(lambda: manager.status_snapshot()["status"] == "disconnected"
                        or manager.status_snapshot()["status"] == "reconnecting")
        assert manager.get_raw_frame() is None
        assert manager.get_fresh_jpeg() is None
        assert manager.status_snapshot()["frame_age_sec"] is None
    finally:
        manager.stop()


def test_reconnect_recovers_live_frames_and_counts_attempts() -> None:
    factory = ScriptedFactory([FakeCapture(frames=2), FakeCapture(frames=10**9)])
    manager = make_manager(factory)
    manager.start()
    try:
        assert wait_for(lambda: factory.open_attempts >= 2)
        assert wait_for(
            lambda: manager.status_snapshot()["status"] == "live"
            and manager.status_snapshot()["frames_captured"] > 2
        )
        snapshot = manager.status_snapshot()
        assert snapshot["reconnect_count"] >= 1
        assert snapshot["active_source"] == "rtmp"
        assert manager.get_raw_frame() is not None
    finally:
        manager.stop()


def test_open_failure_keeps_retrying_with_reconnect_status() -> None:
    factory = ScriptedFactory([])  # every open attempt fails
    manager = make_manager(factory)
    manager.start()
    try:
        assert wait_for(lambda: factory.open_attempts >= 3)
        snapshot = manager.status_snapshot()
        assert snapshot["status"] in ("disconnected", "reconnecting", "connecting")
        assert snapshot["fallback_active"] is False
        assert manager.get_raw_frame() is None
    finally:
        manager.stop()
    assert manager.status_snapshot()["status"] == "stopped"


# ---------------------------------------------------------------------------
# Stale-frame detection
# ---------------------------------------------------------------------------


def test_stale_frame_detection_and_freshness_gating() -> None:
    manager = make_manager(ScriptedFactory([]), stale_after_sec=0.5)
    manager._store_frame(FRAME.copy())
    manager._set_status(SourceStatus.LIVE, "test frame stored")

    assert manager.status_snapshot()["status"] == "live"
    assert manager.get_raw_frame(max_age_sec=10.0) is not None

    # Age the frame artificially past the stale threshold.
    manager._latest_frame_monotonic = time.monotonic() - 5.0
    snapshot = manager.status_snapshot()
    assert snapshot["status"] == "stale"
    assert snapshot["frame_age_sec"] > 0.5
    assert manager.get_raw_frame(max_age_sec=1.0) is None
    assert manager.get_fresh_jpeg(max_age_sec=1.0) is None
    # Without a freshness bound the frame is still retrievable (e.g. debug).
    assert manager.get_raw_frame() is not None


# ---------------------------------------------------------------------------
# Synthetic fallback policy
# ---------------------------------------------------------------------------


def test_explicit_synthetic_fallback_is_labeled() -> None:
    transitions = []
    manager = make_manager(
        ScriptedFactory([]),
        allow_synthetic_fallback=True,
        on_transition=lambda s: transitions.append(s),
    )
    manager.start()
    try:
        assert wait_for(lambda: manager.status_snapshot()["status"] == "fallback")
        assert wait_for(lambda: manager.get_raw_frame() is not None)
        snapshot = manager.status_snapshot()
        assert snapshot["active_source"] == "synthetic-fallback"
        assert snapshot["provenance"] == "synthetic-fallback"
        assert snapshot["fallback_active"] is True
        assert snapshot["requested_source"] == "rtmp"
    finally:
        manager.stop()
    assert any(t["status"] == "fallback" for t in transitions)


def test_synthetic_demo_source_still_works() -> None:
    manager = VideoStreamManager(source="synthetic")
    manager.start()
    try:
        assert wait_for(lambda: manager.get_raw_frame() is not None)
        snapshot = manager.status_snapshot()
        assert snapshot["status"] == "live"
        assert snapshot["provenance"] == "synthetic"
        assert snapshot["is_real_source"] is False
        assert snapshot["stream_url"] is None
        assert manager.get_jpeg_bytes() is not None
    finally:
        manager.stop()


# ---------------------------------------------------------------------------
# Provenance metadata
# ---------------------------------------------------------------------------


def test_provenance_labels_by_source() -> None:
    assert make_manager(ScriptedFactory([]))._provenance() == "live-rtmp"
    rtsp = make_manager(ScriptedFactory([]), source="rtsp", rtsp_url="rtsp://h/s")
    assert rtsp._provenance() == "live-rtsp"
    assert rtsp.status_snapshot()["protocol"] == "rtsp"
    file_mgr = make_manager(ScriptedFactory([]), source="file", video_path="a.mp4")
    assert file_mgr._provenance() == "prerecorded-file"
    webcam = make_manager(ScriptedFactory([]), source="webcam")
    assert webcam._provenance() == "live-webcam"
