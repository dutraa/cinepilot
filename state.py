"""Thread-safe active-session state for CinePilot."""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
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
    VisualizationJob,
    VisualizationJobStatus,
    VisualizationRequestInput,
    VisualizationSourceKind,
)
from visualization import (
    RENDERER_VERSION,
    validate_rendered_previews,
    validate_source_frame,
    render_deterministic_previews,
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
        self.visualization_jobs: dict[str, VisualizationJob] = {}
        self._visualization_job_order: list[str] = []
        self._visualization_jobs_by_fingerprint: dict[str, str] = {}
        self._visualization_frames: dict[str, bytes] = {}
        self._visualization_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="cinepilot-visualization"
        )
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
            "frames_skipped_stale": 0,
            "critiques_received": 0,
            "valid_critiques": 0,
            "invalid_critiques": 0,
            "malformed_tool_calls": 0,
            "gemini_reconnects": 0,
            "tweaks_acted": 0,
            "recommendations_received": 0,
            "valid_recommendations": 0,
            "invalid_recommendations": 0,
            "recommendations_selected": 0,
            "recommendations_completed": 0,
            "gemini_status": "Connecting",
            "grafana_status": "Dry Run",
        }
        # Last known source snapshot (updated on every source transition).
        self.source: dict[str, Any] = {
            "requested_source": "unknown",
            "active_source": "unknown",
            "protocol": None,
            "stream_url": None,
            "status": "connecting",
            "status_reason": "not started",
            "is_real_source": False,
            "provenance": "unknown",
            "first_frame_at": None,
            "last_frame_at": None,
            "frame_age_sec": None,
            "fps": 0.0,
            "frames_captured": 0,
            "reconnect_count": 0,
            "fallback_active": False,
            "allow_synthetic_fallback": False,
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
            self.visualization_jobs = {}
            self._visualization_job_order = []
            self._visualization_jobs_by_fingerprint = {}
            self._visualization_frames = {}
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
            if target == ShotRecommendationStatus.SELECTED:
                for job in self.visualization_jobs.values():
                    if any(
                        preview.recommendation_id == recommendation_id
                        for preview in job.previews
                    ) and any(
                        preview.recommendation_id != recommendation_id
                        and preview.recommendation_status == ShotRecommendationStatus.SELECTED
                        for preview in job.previews
                    ):
                        self._record_story_rejection_locked(
                            "visualization_selection",
                            recommendation_id,
                            "only one visualization preview can be selected per job",
                        )
                        raise InvalidDecisionError(
                            "only one visualization preview can be selected per job"
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
            self._sync_visualization_preview_status_locked(recommendation)
            self._story_context_version += 1
            self._version += 1
            self._event_log.record(
                "recommendation_decision",
                recommendation_id=recommendation_id,
                decision=target.value,
                provenance=recommendation.provenance,
            )
            return target

    def _sync_visualization_preview_status_locked(
        self, recommendation: ShotRecommendation
    ) -> None:
        for job in self.visualization_jobs.values():
            for preview in job.previews:
                if preview.recommendation_id == recommendation.recommendation_id:
                    preview.recommendation_status = recommendation.status

    @staticmethod
    def _visualization_fingerprint(
        context: dict[str, Any],
        request: VisualizationRequestInput,
        frame: bytes,
        provenance: str,
        source_kind: VisualizationSourceKind,
        source_label: str,
    ) -> str:
        content = {
            "context": context,
            "request": request.model_dump(mode="json"),
            "observation_frame_sha256": hashlib.sha256(frame).hexdigest(),
            "provenance": provenance,
            "source_kind": source_kind.value,
            "source_label": source_label,
        }
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()

    def request_visualization(
        self,
        request: VisualizationRequestInput,
        source_frame: bytes,
        provenance: str,
        source_kind: VisualizationSourceKind | str = VisualizationSourceKind.UNKNOWN,
        source_label: str | None = None,
    ) -> VisualizationJob:
        """Create one asynchronous visualization job for this session."""
        try:
            source_width, source_height = validate_source_frame(source_frame)
        except ValueError as exc:
            raise InvalidDecisionError(str(exc)) from exc
        try:
            normalized_source_kind = VisualizationSourceKind(source_kind)
        except ValueError as exc:
            raise InvalidDecisionError("visualization source kind is invalid") from exc
        normalized_source_label = source_label or normalized_source_kind.value
        with self._lock:
            if self.story is None or self.active_beat_id is None:
                raise InvalidDecisionError("current story observation is unavailable")
            context = self._story_context_locked()
            fingerprint = self._visualization_fingerprint(
                context,
                request,
                source_frame,
                provenance,
                normalized_source_kind,
                normalized_source_label,
            )
            existing_id = self._visualization_jobs_by_fingerprint.get(fingerprint)
            if existing_id is not None:
                existing = self.visualization_jobs[existing_id]
                if existing.status == VisualizationJobStatus.FAILED:
                    recommendations = [
                        item.model_copy(deep=True) for item in self.latest_recommendations[:3]
                    ]
                    if len(recommendations) != 3:
                        raise InvalidDecisionError(
                            "three existing shot recommendations are required for visualization"
                        )
                    existing.status = VisualizationJobStatus.REQUESTED
                    existing.started_at = None
                    existing.completed_at = None
                    existing.error = None
                    existing.source_frame_available = True
                    existing.source_frame_sha256 = hashlib.sha256(source_frame).hexdigest()
                    existing.source_kind = normalized_source_kind
                    existing.source_label = normalized_source_label
                    existing.renderer_version = RENDERER_VERSION
                    existing.source_width = source_width
                    existing.source_height = source_height
                    existing.previews = []
                    self._visualization_frames[existing_id] = bytes(source_frame)
                    self._version += 1
                    self._event_log.record("visualization_retry", job_id=existing_id)
                    self._visualization_executor.submit(
                        self._render_visualization_job,
                        existing_id,
                        request,
                        recommendations,
                    )
                return copy.deepcopy(existing)

            if self._visualization_job_order:
                active = self.visualization_jobs[self._visualization_job_order[-1]]
                if active.status in {
                    VisualizationJobStatus.REQUESTED,
                    VisualizationJobStatus.RENDERING,
                }:
                    raise InvalidDecisionError("another visualization job is rendering")

            recommendations = [
                item.model_copy(deep=True) for item in self.latest_recommendations[:3]
            ]
            if len(recommendations) != 3:
                raise InvalidDecisionError(
                    "three existing shot recommendations are required for visualization"
                )
            job_id = str(uuid4())
            observation_id = str(uuid4())
            requested_at = self._now_iso()
            job = VisualizationJob(
                job_id=job_id,
                request_fingerprint=fingerprint,
                duration_seconds=10,
                variation_count=3,
                story_version=self._story_version,
                beat_id=self.active_beat_id,
                observation_id=observation_id,
                intent_version=self._intent_version,
                requested_at=requested_at,
                status=VisualizationJobStatus.REQUESTED,
                provenance=provenance,
                source_kind=normalized_source_kind,
                source_label=normalized_source_label,
                renderer_version=RENDERER_VERSION,
                source_frame_sha256=hashlib.sha256(source_frame).hexdigest(),
                source_width=source_width,
                source_height=source_height,
                source_frame_available=True,
            )
            self.visualization_jobs[job_id] = job
            self._visualization_job_order.append(job_id)
            self._visualization_jobs_by_fingerprint[fingerprint] = job_id
            self._visualization_frames[job_id] = bytes(source_frame)
            self._version += 1
            self._event_log.record(
                "visualization_requested",
                job_id=job_id,
                observation_id=observation_id,
                story_version=self._story_version,
                beat_id=self.active_beat_id,
                provenance=provenance,
            )
            self._visualization_executor.submit(
                self._render_visualization_job,
                job_id,
                request,
                recommendations,
            )
            return copy.deepcopy(job)

    def _render_visualization_job(
        self,
        job_id: str,
        request: VisualizationRequestInput,
        recommendations: list[ShotRecommendation],
    ) -> None:
        with self._lock:
            job = self.visualization_jobs.get(job_id)
            if job is None:
                return
            job.status = VisualizationJobStatus.RENDERING
            job.started_at = self._now_iso()
            self._version += 1
            self._event_log.record("visualization_rendering", job_id=job_id)
            job_copy = job.model_copy(deep=True)
        try:
            previews = validate_rendered_previews(
                job_id,
                render_deterministic_previews(job_copy, request, recommendations),
                recommendations,
            )
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                job = self.visualization_jobs.get(job_id)
                if job is None:
                    return
                job.status = VisualizationJobStatus.FAILED
                job.completed_at = self._now_iso()
                job.error = str(exc)[:500] or "visualization renderer failed"
                job.source_frame_available = False
                job.previews = []
                self._visualization_frames.pop(job_id, None)
                self._version += 1
                self._event_log.record(
                    "visualization_failed", job_id=job_id, reason=job.error
                )
            return
        with self._lock:
            job = self.visualization_jobs.get(job_id)
            if job is None:
                return
            job.status = VisualizationJobStatus.READY
            job.completed_at = self._now_iso()
            job.previews = previews
            self._version += 1
            self._event_log.record(
                "visualization_ready",
                job_id=job_id,
                preview_ids=[preview.preview_id for preview in previews],
                provenance=job.provenance,
            )
            self._evict_visualizations_locked()

    def _evict_visualizations_locked(self) -> None:
        while len(self._visualization_job_order) > 10:
            evicted_id = self._visualization_job_order.pop(0)
            self.visualization_jobs.pop(evicted_id, None)
            self._visualization_frames.pop(evicted_id, None)
            for fingerprint, job_id in list(self._visualization_jobs_by_fingerprint.items()):
                if job_id == evicted_id:
                    del self._visualization_jobs_by_fingerprint[fingerprint]
            self._event_log.record("visualization_evicted", job_id=evicted_id)

    def get_visualization_source_frame(self, job_id: str) -> bytes:
        with self._lock:
            if job_id not in self.visualization_jobs:
                raise StateNotFoundError(f"visualization job not found: {job_id}")
            frame = self._visualization_frames.get(job_id)
            if frame is None:
                raise InvalidDecisionError("visualization source frame is unavailable")
            return bytes(frame)

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
            self._event_log.record(
                "critique_rejected", reason=reason, provenance="gemini"
            )

    def record_malformed_tool_call(self, tool_name: str, reason: str) -> None:
        """Count a Gemini tool call that could not be executed as requested."""
        with self._lock:
            self.metrics["malformed_tool_calls"] += 1
            self._version += 1
            self._event_log.record(
                "tool_call_malformed",
                tool=tool_name,
                reason=reason,
                provenance="gemini",
            )

    def record_source_transition(self, snapshot: dict[str, Any]) -> None:
        """Store the latest source snapshot and log the transition as evidence."""
        with self._lock:
            self.source = dict(snapshot)
            self._version += 1
            self._event_log.record(
                "source_transition",
                status=snapshot.get("status"),
                reason=snapshot.get("status_reason"),
                requested_source=snapshot.get("requested_source"),
                active_source=snapshot.get("active_source"),
                provenance=snapshot.get("provenance"),
                reconnect_count=snapshot.get("reconnect_count"),
                fallback_active=snapshot.get("fallback_active"),
            )

    def record_frame_observation(
        self, observation_id: str, provenance: str, source_status: str
    ) -> None:
        """Log one frame observation sent to Gemini, with its provenance stratum."""
        with self._lock:
            self._event_log.record(
                "frame_observation",
                observation_id=observation_id,
                provenance=provenance,
                source_status=source_status,
            )

    def record_stale_frame_skipped(self) -> None:
        with self._lock:
            self.metrics["frames_skipped_stale"] += 1
            self._version += 1

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
                actor="creator",
            )
            return target

    def update_shot(
        self, shot_id: str, status: str, feedback: str, actor: str = "model"
    ) -> None:
        with self._lock:
            if shot_id not in ALLOWED_SHOT_IDS or status not in ALLOWED_STATUSES:
                return
            if self.shots[shot_id]["status"] == status and (
                self.shots[shot_id]["feedback"] == feedback
            ):
                return
            self.shots[shot_id]["status"] = status
            self.shots[shot_id]["feedback"] = feedback
            self._version += 1
            self._event_log.record(
                "shot_updated",
                shot_id=shot_id,
                status=status,
                feedback=feedback,
                actor=actor,
            )

    def creator_update_shot(self, shot_id: str, status: str, feedback: str) -> None:
        """Creator-only shot lifecycle update (the only path to COMPLETED)."""
        if shot_id not in ALLOWED_SHOT_IDS:
            raise StateNotFoundError(f"unknown shot '{shot_id}'")
        if status not in ALLOWED_STATUSES:
            raise InvalidDecisionError(f"invalid shot status '{status}'")
        self.update_shot(shot_id, status, feedback, actor="creator")

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
                "visualization_jobs": [
                    self.visualization_jobs[job_id].model_dump(mode="json")
                    for job_id in self._visualization_job_order
                    if job_id in self.visualization_jobs
                ],
                "latest_visualization_job": (
                    self.visualization_jobs[self._visualization_job_order[-1]].model_dump(mode="json")
                    if self._visualization_job_order
                    and self._visualization_job_order[-1] in self.visualization_jobs
                    else None
                ),
                "provenance": dict(self.provenance),
                "latest_critique": self.latest_critique.model_dump(mode="json") if self.latest_critique else None,
                "critique_history": [item.model_dump(mode="json") for item in self.critique_history],
                "shots": copy.deepcopy(self.shots),
                "latest_guidance": dict(self.latest_guidance),
                "metrics": dict(self.metrics),
                "source": dict(self.source),
            }

    @property
    def version(self) -> int:
        with self._lock:
            return self._version
