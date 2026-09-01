"""Thread-safe active-session state for CinePilot."""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5
from domain import ALLOWED_SHOT_IDS, ALLOWED_STATUSES, SHOT_DEFINITIONS
from event_log import EventLog
from config import settings
from schemas import (
    CinematicCritique,
    CinematicIntent,
    Decision,
    RecommendationDecision,
    ShotCoverage,
    ShotRecommendation,
    ShotRecommendationInput,
    ShotRecommendationStatus,
    StoryBeatStatus,
    StoryBrief,
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
        self._last_recommendation_fingerprint = ""
        self._event_log = event_log or EventLog()
        self.intent: CinematicIntent | None = None
        self.story: StoryBrief | None = None
        self._story_version = 0
        self._story_context_version = 0
        self.active_beat_id: str | None = None
        self.beat_statuses: dict[str, StoryBeatStatus] = {}
        self.coverage: list[ShotCoverage] = []
        self.current_shot_contribution: dict[str, str] = {}
        self.latest_recommendations: list[ShotRecommendation] = []
        self.recommendation_history: list[ShotRecommendation] = []
        self.recommendation_decisions: list[dict[str, str]] = []
        self.provenance: dict[str, str] = {"mode": "live", "source": "unknown"}
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
            "recommendations_received": 0,
            "valid_recommendations": 0,
            "invalid_recommendations": 0,
            "recommendations_selected": 0,
            "recommendations_completed": 0,
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

    def set_provenance(self, mode: str, source: str) -> None:
        with self._lock:
            updated = {"mode": mode, "source": source}
            if self.provenance == updated:
                return
            self.provenance = updated
            self._version += 1
            self._event_log.record("provenance_set", provenance=dict(self.provenance))

    def load_story(
        self,
        story: StoryBrief,
        initial_coverage: ShotCoverage | None = None,
        current_shot_contribution: dict[str, str] | None = None,
        provenance: str = "live",
    ) -> int:
        """Load one validated story into the canonical session state."""
        beat_ids = [beat.beat_id for beat in story.beats]
        if len(set(beat_ids)) != len(beat_ids):
            raise ValueError("story beat IDs must be unique")
        with self._lock:
            self.story = story.model_copy(deep=True)
            self._story_version += 1
            self._story_context_version += 1
            self.beat_statuses = {beat.beat_id: beat.status for beat in story.beats}
            self.active_beat_id = next(
                (beat.beat_id for beat in story.beats if beat.status == StoryBeatStatus.ACTIVE),
                next((beat.beat_id for beat in story.beats if beat.status == StoryBeatStatus.PENDING), None),
            )
            self.coverage = [initial_coverage] if initial_coverage is not None else []
            self.current_shot_contribution = dict(current_shot_contribution or {})
            self.latest_recommendations = []
            self.recommendation_history = []
            self.recommendation_decisions = []
            self._last_recommendation_fingerprint = ""
            self.provenance["mode"] = provenance
            self._version += 1
            self._event_log.record(
                "story_loaded",
                story_version=self._story_version,
                story_id=story.story_id,
                provenance=provenance,
                initial_coverage=initial_coverage.model_dump(mode="json") if initial_coverage else None,
            )
            return self._story_version

    def story_context(self) -> tuple[dict[str, Any] | None, int]:
        with self._lock:
            if self.story is None:
                return None, self._story_context_version
            return self._story_context_locked(), self._story_context_version

    def _story_context_locked(self) -> dict[str, Any]:
        assert self.story is not None
        beats = []
        for beat in self.story.beats:
            data = beat.model_dump(mode="json")
            data["status"] = self.beat_statuses[beat.beat_id].value
            beats.append(data)
        active = next((beat for beat in beats if beat["beat_id"] == self.active_beat_id), None)
        covered = [beat for beat in beats if beat["status"] == StoryBeatStatus.COVERED.value]
        missing = [
            beat for beat in beats
            if beat["status"] in {StoryBeatStatus.ACTIVE.value, StoryBeatStatus.PENDING.value}
        ]
        story_data = self.story.model_dump(mode="json")
        story_data["beats"] = beats
        return {
            "story": story_data,
            "story_version": self._story_version,
            "intent_version": self._intent_version,
            "current_cinematic_intent": self.intent.model_dump(mode="json") if self.intent else None,
            "active_beat": active,
            "covered_beats": covered,
            "missing_beats": missing,
            "current_shot_contribution": dict(self.current_shot_contribution),
            "current_footage_observation": dict(self.current_shot_contribution),
            "previous_creator_decisions": copy.deepcopy(self.recommendation_decisions[-20:]),
        }

    def _require_beat_locked(self, beat_id: str) -> None:
        if beat_id not in self.beat_statuses:
            raise StateNotFoundError(f"beat not found: {beat_id}")

    def _record_story_rejection_locked(self, transition: str, entity_id: str, reason: str) -> None:
        self._event_log.record(
            "recommendation_transition_rejected",
            transition=transition,
            entity_id=entity_id,
            reason=reason,
        )

    def _next_pending_beat_locked(self) -> str | None:
        if self.story is None:
            return None
        for beat in self.story.beats:
            if self.beat_statuses[beat.beat_id] == StoryBeatStatus.PENDING:
                return beat.beat_id
        return None

    def set_active_beat(self, beat_id: str) -> StoryBeatStatus:
        with self._lock:
            self._require_beat_locked(beat_id)
            current = self.beat_statuses[beat_id]
            if self.active_beat_id == beat_id:
                return current
            if current != StoryBeatStatus.PENDING:
                self._record_story_rejection_locked("beat_transition", beat_id, "only pending beats can become active")
                raise InvalidDecisionError("only pending beats can become active")
            if self.active_beat_id is not None and self.beat_statuses[self.active_beat_id] == StoryBeatStatus.ACTIVE:
                self._record_story_rejection_locked("beat_transition", beat_id, "another beat is active")
                raise InvalidDecisionError("another beat is active")
            self.beat_statuses[beat_id] = StoryBeatStatus.ACTIVE
            self.active_beat_id = beat_id
            self._story_context_version += 1
            self._version += 1
            self._event_log.record("beat_transition", beat_id=beat_id, status="pending", new_status="active")
            return StoryBeatStatus.ACTIVE

    def skip_active_beat(self, beat_id: str) -> StoryBeatStatus:
        with self._lock:
            self._require_beat_locked(beat_id)
            if self.active_beat_id != beat_id or self.beat_statuses[beat_id] != StoryBeatStatus.ACTIVE:
                self._record_story_rejection_locked("beat_transition", beat_id, "only the active beat can be skipped")
                raise InvalidDecisionError("only the active beat can be skipped")
            self.beat_statuses[beat_id] = StoryBeatStatus.SKIPPED
            self.active_beat_id = self._next_pending_beat_locked()
            if self.active_beat_id:
                self.beat_statuses[self.active_beat_id] = StoryBeatStatus.ACTIVE
            self._story_context_version += 1
            self._version += 1
            self._event_log.record("beat_transition", beat_id=beat_id, status="active", new_status="skipped")
            return StoryBeatStatus.SKIPPED

    def record_invalid_recommendations(self, reason: str) -> None:
        with self._lock:
            self.metrics["invalid_recommendations"] += 1
            self._version += 1
            self._event_log.record("recommendations_rejected", reason=reason)

    @staticmethod
    def _recommendation_fingerprint(inputs: list[ShotRecommendationInput]) -> str:
        return hashlib.sha256(
            json.dumps([item.model_dump(mode="json") for item in inputs], sort_keys=True).encode()
        ).hexdigest()

    def publish_recommendations(
        self,
        inputs: list[ShotRecommendationInput],
        observation_id: str,
        provenance: str = "gemini",
        prompt_version: str = "cinematic-tweak-v1",
    ) -> list[ShotRecommendation]:
        with self._lock:
            if self.story is None:
                raise StateNotFoundError("story not found")
            for item in inputs:
                self._require_beat_locked(item.beat_id)
                if self.beat_statuses[item.beat_id] in {
                    StoryBeatStatus.COVERED,
                    StoryBeatStatus.SKIPPED,
                }:
                    raise InvalidDecisionError("recommendations must target missing story coverage")
            fingerprint = self._recommendation_fingerprint(inputs)
            if fingerprint == self._last_recommendation_fingerprint:
                self._event_log.record("recommendations_suppressed", reason="duplicate")
                return copy.deepcopy(self.latest_recommendations)
            self._last_recommendation_fingerprint = fingerprint
            recommendations = []
            for index, item in enumerate(inputs):
                if provenance == "deterministic_demo":
                    recommendation_id = str(
                        uuid5(
                            NAMESPACE_URL,
                            f"cinepilot:{self.story.story_id}:{self._story_context_version}:{index}:{item.title}",
                        )
                    )
                else:
                    recommendation_id = str(uuid4())
                recommendations.append(
                    ShotRecommendation(
                        **item.model_dump(mode="json"),
                        recommendation_id=recommendation_id,
                        observation_id=observation_id,
                        created_at=(
                            "2026-01-01T00:00:00+00:00"
                            if provenance == "deterministic_demo"
                            else self._now_iso()
                        ),
                        intent_version=self._intent_version,
                        prompt_version=prompt_version,
                        provenance=provenance,
                    )
                )
            self.latest_recommendations = recommendations
            self.recommendation_history.extend(recommendations)
            self.recommendation_history = self.recommendation_history[-30:]
            self.metrics["recommendations_received"] += 1
            self.metrics["valid_recommendations"] += 1
            self._story_context_version += 1
            self._version += 1
            self._event_log.record(
                "recommendations_published",
                recommendation_ids=[item.recommendation_id for item in recommendations],
                observation_id=observation_id,
                provenance=provenance,
            )
            return copy.deepcopy(recommendations)

    def decide_recommendation(
        self, recommendation_id: str, decision: RecommendationDecision
    ) -> ShotRecommendationStatus:
        with self._lock:
            recommendation = next(
                (item for item in self.recommendation_history if item.recommendation_id == recommendation_id),
                None,
            )
            if recommendation is None:
                raise StateNotFoundError(f"recommendation not found: {recommendation_id}")
            current = recommendation.status
            target = ShotRecommendationStatus(decision.value)
            if current == target:
                self._event_log.record(
                    "recommendation_decision_idempotent",
                    recommendation_id=recommendation_id,
                    status=current.value,
                )
                return current
            allowed = {
                ShotRecommendationStatus.SUGGESTED: {
                    ShotRecommendationStatus.SELECTED,
                    ShotRecommendationStatus.DISMISSED,
                },
                ShotRecommendationStatus.SELECTED: {
                    ShotRecommendationStatus.COMPLETED,
                    ShotRecommendationStatus.DISMISSED,
                },
            }
            if target not in allowed.get(current, set()):
                self._record_story_rejection_locked(
                    "recommendation_transition",
                    recommendation_id,
                    f"{current.value} to {target.value} is invalid",
                )
                raise InvalidDecisionError(
                    f"cannot change recommendation from {current.value} to {target.value}"
                )
            if target == ShotRecommendationStatus.COMPLETED:
                self._require_beat_locked(recommendation.beat_id)
                if self.beat_statuses[recommendation.beat_id] in {
                    StoryBeatStatus.COVERED,
                    StoryBeatStatus.SKIPPED,
                }:
                    self._record_story_rejection_locked(
                        "recommendation_transition",
                        recommendation_id,
                        "recommendation beat is already terminal",
                    )
                    raise InvalidDecisionError("recommendation beat is already terminal")
            recommendation.status = target
            self.recommendation_decisions.append(
                {
                    "recommendation_id": recommendation_id,
                    "decision": target.value,
                    "provenance": recommendation.provenance,
                }
            )
            if target == ShotRecommendationStatus.SELECTED:
                self.metrics["recommendations_selected"] += 1
            if target == ShotRecommendationStatus.COMPLETED:
                self.metrics["recommendations_completed"] += 1
                self._complete_recommendation_locked(recommendation)
            self._story_context_version += 1
            self._version += 1
            self._event_log.record(
                "recommendation_decision",
                recommendation_id=recommendation_id,
                decision=target.value,
                provenance=recommendation.provenance,
            )
            return target

    def _complete_recommendation_locked(self, recommendation: ShotRecommendation) -> None:
        beat_id = recommendation.beat_id
        self._require_beat_locked(beat_id)
        if self.active_beat_id and self.active_beat_id != beat_id:
            if self.beat_statuses[self.active_beat_id] == StoryBeatStatus.ACTIVE:
                self.beat_statuses[self.active_beat_id] = StoryBeatStatus.COVERED
        self.beat_statuses[beat_id] = StoryBeatStatus.COVERED
        coverage_id = (
            str(uuid5(NAMESPACE_URL, f"coverage:{recommendation.recommendation_id}"))
            if recommendation.provenance == "deterministic_demo"
            else str(uuid4())
        )
        self.coverage.append(
            ShotCoverage(
                coverage_id=coverage_id,
                beat_id=beat_id,
                shot_title=recommendation.title,
                observation_id=recommendation.observation_id,
                captured_at=self._now_iso(),
                source=self.provenance.get("source", "unknown"),
                notes=recommendation.visual_objective,
            )
        )
        self._event_log.record(
            "coverage_added",
            coverage_id=coverage_id,
            beat_id=beat_id,
            recommendation_id=recommendation.recommendation_id,
            provenance=recommendation.provenance,
        )
        self._event_log.record(
            "beat_transition",
            beat_id=beat_id,
            new_status="covered",
            recommendation_id=recommendation.recommendation_id,
        )
        self.current_shot_contribution = {
            "beat_id": beat_id,
            "observation_id": recommendation.observation_id,
            "shot_title": recommendation.title,
            "source": self.provenance.get("source", "unknown"),
            "proves": recommendation.visual_objective,
            "limitations": "The next result must be evaluated separately; completion records capture, not quality improvement.",
        }
        self.active_beat_id = self._next_pending_beat_locked()
        if self.active_beat_id:
            self.beat_statuses[self.active_beat_id] = StoryBeatStatus.ACTIVE

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
            story_context = self._story_context_locked() if self.story is not None else None
            return {
                "schema_version": 2,
                "version": self._version,
                "intent_version": self._intent_version,
                "intent": self.intent.model_dump(mode="json") if self.intent else None,
                "story": story_context["story"] if story_context else None,
                "story_version": self._story_version,
                "story_context_version": self._story_context_version,
                "active_beat": story_context["active_beat"] if story_context else None,
                "beats": story_context["story"]["beats"] if story_context else [],
                "beat_statuses": {key: value.value for key, value in self.beat_statuses.items()},
                "coverage": [item.model_dump(mode="json") for item in self.coverage],
                "covered_coverage": [item.model_dump(mode="json") for item in self.coverage],
                "missing_coverage": story_context["missing_beats"] if story_context else [],
                "current_shot_contribution": copy.deepcopy(self.current_shot_contribution),
                "latest_recommendations": [item.model_dump(mode="json") for item in self.latest_recommendations],
                "recommendation_history": [item.model_dump(mode="json") for item in self.recommendation_history],
                "recommendation_decisions": copy.deepcopy(self.recommendation_decisions),
                "provenance": dict(self.provenance),
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
