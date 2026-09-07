"""Append-only local run log used for reproducible demo evidence."""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("cinepilot.events")


class EventLog:
    """Thread-safe JSONL writer; failures never interrupt the live director."""

    def __init__(self, path: str = "runs/cinepilot-events.jsonl") -> None:
        self.path = Path(path) if path else None
        self._lock = threading.Lock()

    def record(self, event: str, **payload: Any) -> None:
        if self.path is None:
            return
        record = {
            "event_id": str(uuid4()),
            "schema_version": 1,
            "event": event,
            "timestamp_ms": int(time.time() * 1000),
            **payload,
        }
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, default=str) + "\n")
        except OSError:
            logger.exception("Could not write event log entry")
