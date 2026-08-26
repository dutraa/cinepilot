"""Non-blocking Grafana Loki telemetry publisher for CinePilot.

If Grafana Cloud credentials are configured, events are pushed to the Loki
`/loki/api/v1/push` endpoint from a background worker thread so the hot path
(the Gemini Live loop) never blocks on network I/O. Without credentials the
publisher runs in "Dry Run" mode and emits structured JSON telemetry lines to
stdout instead.
"""

import json
import logging
import queue
import threading
import time
from typing import Any, Dict, Optional

import requests

from config import settings

logger = logging.getLogger("cinepilot.grafana")

_BASE_LABELS = {"app": "cinepilot", "env": "production"}


class GrafanaPublisher:
    """Queue-backed, thread-based Loki publisher with a stdout dry-run mode."""

    def __init__(
        self,
        url: Optional[str] = None,
        user: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.url = (url if url is not None else settings.GRAFANA_URL).strip()
        self.user = (user if user is not None else settings.GRAFANA_USER).strip()
        self.api_key = (
            api_key if api_key is not None else settings.GRAFANA_API_KEY
        ).strip()

        self.dry_run = not (self.url and self.user and self.api_key)
        self._queue: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue(maxsize=1000)
        self._worker: Optional[threading.Thread] = None
        self._stopped = threading.Event()

        if self.dry_run:
            logger.info(
                "GrafanaPublisher running in DRY RUN mode "
                "(missing GRAFANA_URL / GRAFANA_USER / GRAFANA_API_KEY). "
                "Telemetry will be printed to stdout."
            )
        else:
            self._worker = threading.Thread(
                target=self._worker_loop, name="grafana-publisher", daemon=True
            )
            self._worker.start()
            logger.info("GrafanaPublisher streaming to %s", self.url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def status(self) -> str:
        return "Dry Run" if self.dry_run else "Live"

    def publish_tool_call(
        self, tool_name: str, args: Dict[str, Any], result: Dict[str, Any]
    ) -> None:
        """Publish a Gemini tool-call event."""
        self._publish(
            labels={**_BASE_LABELS, "event": "tool_call", "tool": tool_name},
            line={
                "event": "tool_call",
                "tool": tool_name,
                "args": args,
                "result": result,
            },
        )

    def publish_frame_metrics(
        self, fps: float, latency_ms: float, frames_sent: int
    ) -> None:
        """Publish rolling frame/latency metrics."""
        self._publish(
            labels={**_BASE_LABELS, "event": "frame_metrics"},
            line={
                "event": "frame_metrics",
                "fps": round(fps, 3),
                "latency_ms": round(latency_ms, 1),
                "frames_sent": frames_sent,
            },
        )

    def close(self) -> None:
        """Flush and stop the background worker (no-op in dry-run mode)."""
        self._stopped.set()
        if self._worker is not None:
            self._queue.put(None)  # sentinel to unblock the worker
            self._worker.join(timeout=3.0)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _publish(self, labels: Dict[str, str], line: Dict[str, Any]) -> None:
        record = {
            "labels": labels,
            "line": line,
            "ts_ns": str(time.time_ns()),
        }
        if self.dry_run:
            print(json.dumps({"grafana_dry_run": record}, default=str), flush=True)
            return
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            logger.warning("Grafana telemetry queue full; dropping event")

    def _worker_loop(self) -> None:
        session = requests.Session()
        session.auth = (self.user, self.api_key)
        session.headers.update({"Content-Type": "application/json"})

        while not self._stopped.is_set() or not self._queue.empty():
            try:
                record = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if record is None:  # shutdown sentinel
                break
            try:
                self._push_record(session, record)
            except Exception:  # noqa: BLE001 - telemetry must never crash the app
                logger.exception("Failed to push telemetry to Grafana Loki")
            finally:
                self._queue.task_done()

    def _push_record(self, session: requests.Session, record: Dict[str, Any]) -> None:
        payload = {
            "streams": [
                {
                    "stream": record["labels"],
                    "values": [
                        [record["ts_ns"], json.dumps(record["line"], default=str)]
                    ],
                }
            ]
        }
        response = session.post(self.url, data=json.dumps(payload), timeout=5)
        if response.status_code >= 300:
            logger.warning(
                "Grafana Loki push failed: HTTP %s %s",
                response.status_code,
                response.text[:300],
            )
