"""Thread-safe active-session state for CinePilot."""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from typing import Any
from domain import ALLOWED_SHOT_IDS, ALLOWED_STATUSES, SHOT_DEFINITIONS
from event_log import EventLog
from config import settings
from schemas import (
    CinematicCritique,
    CinematicIntent,
    Decision,
    TweakStatus,
)


class StateNotFoundError(LookupError):
    pass


class InvalidDecisionError(ValueError):
    pass


class AppState:
    """Canonical in-memory state for one local CinePilot run."""

    def __init__(self, event_log: EventLog | None = None) -> None:
        self._lock = threading.Lock()
        self._version = 0
        self._intent_version = 0
        self._last_critique_at = 0.0
        self._last_critique_fingerprint = ""
        self._event_log = event_log or EventLog()
        self.intent: CinematicIntent | None = None
        self.latest_critique: CinematicCritique | None = None
        self.critique_history: list[CinematicCritique] = []
        self.shots: dict[str, dict[str, str]] = {
            shot_id: {
                "title": title,
                "status": "PENDING",
                "feedback": "Awaiting first pass from the director.",
            }
            for shot_id, title in SHOT_DEFINITIONS.items()
        }
        self.latest_guidance: dict[str, str] = {
            "instruction": "Set a shot intent to begin cinematic critique.",
            "priority": "INFO",
            "timestamp": "",
        }
        self.metrics: dict[str, Any] = {
            "fps": 0.0,
            "latency_ms": 0.0,
            "frames_sent": 0,
            "critiques_received": 0,
            "valid_critiques": 0,
            "invalid_critiques": 0,
            "tweaks_acted": 0,
            "gemini_status": "Connecting",
            "grafana_status": "Dry Run",
        }

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _fingerprint(critique: CinematicCritique) -> str:
        content = critique.model_dump(mode="json", exclude={"critique_id", "created_at"})
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()

    def set_intent(self, intent: CinematicIntent) -> int:
        with self._lock:
            if self.intent == intent:
                return self._intent_version
            self.intent = intent
            self._intent_version += 1
            self._version += 1
            version = self._intent_version
            self._event_log.record("intent_set", intent_version=version, intent=intent.model_dump(mode="json"))
            return version

    def intent_context(self) -> tuple[CinematicIntent | None, int]:
        with self._lock:
            return self.intent, self._intent_version

    def publish_critique(self, critique: CinematicCritique) -> bool:
        fingerprint = self._fingerprint(critique)
        now = time.monotonic()
        with self._lock:
            if (
                fingerprint == self._last_critique_fingerprint
                and now - self._last_critique_at < settings.CRITIQUE_COOLDOWN_SEC
            ):
                self._event_log.record("critique_suppressed", critique_id=critique.critique_id, reason="duplicate")
                return False
            self._last_critique_at = now
            self._last_critique_fingerprint = fingerprint
            self.latest_critique = critique
            self.critique_history.append(critique)
            self.critique_history = self.critique_history[-20:]
            self.metrics["critiques_received"] += 1
            self.metrics["valid_critiques"] += 1
            self._version += 1
            self._event_log.record("critique_published", critique=critique.model_dump(mode="json"))
            return True

    def record_invalid_critique(self, reason: str) -> None:
        with self._lock:
            self.metrics["invalid_critiques"] += 1
            self._version += 1
            self._event_log.record("critique_rejected", reason=reason)

    def decide_tweak(self, critique_id: str, tweak_id: str, decision: Decision) -> TweakStatus:
        with self._lock:
            critique = next((item for item in self.critique_history if item.critique_id == critique_id), None)
            if critique is None:
                raise StateNotFoundError("critique not found")
            tweak = next((item for item in critique.tweaks if item.tweak_id == tweak_id), None)
            if tweak is None:
                raise StateNotFoundError("tweak not found")

            target = {
                Decision.ACCEPTED: TweakStatus.ACCEPTED,
                Decision.ACTED: TweakStatus.ACTED,
                Decision.DISMISSED: TweakStatus.DISMISSED,
            }[decision]
            current = tweak.status
            if current == target:
                return current
            if current in (TweakStatus.ACTED, TweakStatus.DISMISSED):
                raise InvalidDecisionError(f"cannot change terminal status {current.value}")
            if target == TweakStatus.ACTED and current not in (TweakStatus.PROPOSED, TweakStatus.ACCEPTED):
                raise InvalidDecisionError("tweak must be proposed or accepted before it is acted")
            if target == TweakStatus.ACCEPTED and current != TweakStatus.PROPOSED:
                raise InvalidDecisionError("only proposed tweaks can be accepted")
            if target == TweakStatus.DISMISSED and current not in (TweakStatus.PROPOSED, TweakStatus.ACCEPTED):
                raise InvalidDecisionError("only proposed or accepted tweaks can be dismissed")

            tweak.status = target
            if target == TweakStatus.ACTED:
                self.metrics["tweaks_acted"] += 1
            self._version += 1
            self._event_log.record(
                "tweak_decision",
                critique_id=critique_id,
                tweak_id=tweak_id,
                decision=decision.value,
            )
            return target

    def update_shot(self, shot_id: str, status: str, feedback: str) -> None:
        with self._lock:
            if shot_id not in ALLOWED_SHOT_IDS or status not in ALLOWED_STATUSES:
                return
            self.shots[shot_id]["status"] = status
            self.shots[shot_id]["feedback"] = feedback
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

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema_version": 1,
                "version": self._version,
                "intent_version": self._intent_version,
                "intent": self.intent.model_dump(mode="json") if self.intent else None,
                "latest_critique": self.latest_critique.model_dump(mode="json") if self.latest_critique else None,
                "critique_history": [item.model_dump(mode="json") for item in self.critique_history],
                "shots": copy.deepcopy(self.shots),
                "latest_guidance": dict(self.latest_guidance),
                "metrics": dict(self.metrics),
            }

    @property
    def version(self) -> int:
        with self._lock:
            return self._version
