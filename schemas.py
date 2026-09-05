"""Validated domain contracts for CinePilot's cinematic workflows."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, confloat, field_validator, model_validator


class TweakCategory(str, Enum):
    COMPOSITION = "composition"
    CAMERA_MOVEMENT = "camera_movement"
    CAMERA_ANGLE = "camera_angle"
    LENS_FEEL = "lens_feel"
    PERSPECTIVE = "perspective"
    LIGHTING = "lighting"
    SUBJECT = "subject"
    PACING = "pacing"
    CONTINUITY = "continuity"
    EXPRESSION = "expression"


class Priority(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    URGENT = "URGENT"


class Decision(str, Enum):
    ACCEPTED = "accepted"
    ACTED = "acted"
    DISMISSED = "dismissed"


class TweakStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    ACTED = "ACTED"
    DISMISSED = "DISMISSED"


class StoryBeatStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COVERED = "covered"
    SKIPPED = "skipped"


class ShotRecommendationStatus(str, Enum):
    SUGGESTED = "suggested"
    SELECTED = "selected"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class RecommendationDecision(str, Enum):
    SELECTED = "selected"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class VisualizationJobStatus(str, Enum):
    REQUESTED = "requested"
    RENDERING = "rendering"
    READY = "ready"
    FAILED = "failed"


class VisualizationQualityStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class VisualizationSourceKind(str, Enum):
    UNKNOWN = "unknown"
    SYNTHETIC = "synthetic"
    FILE = "file"
    WEBCAM = "webcam"
    RTSP = "rtsp"
    RTMP = "rtmp"
    LIVE = "live"


class AnimationProfile(str, Enum):
    DESCENDING_REVEAL = "descending_reveal"
    LATERAL_PARALLAX = "lateral_parallax"
    RESTRAINED_PULL_AWAY = "restrained_pull_away"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CinematicIntent(StrictModel):
    shot_name: str = Field(min_length=1, max_length=120)
    creative_goal: str = Field(min_length=1, max_length=500)
    subject: str = Field(min_length=1, max_length=200)
    desired_feel: str = Field(default="cinematic", max_length=160)
    camera_move: str = Field(default="unspecified", max_length=120)
    constraints: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("constraints")
    @classmethod
    def validate_constraints(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            if not value or len(value) > 160:
                raise ValueError("each constraint must be between 1 and 160 characters")
            cleaned.append(value)
        return cleaned


class CinematicTweakInput(StrictModel):
    category: TweakCategory
    diagnosis: str = Field(min_length=1, max_length=400)
    recommendation: str = Field(min_length=1, max_length=400)
    rationale: str = Field(min_length=1, max_length=400)
    priority: Priority = Priority.INFO
    confidence: confloat(ge=0.0, le=1.0) | None = None
    spoken_cue: str | None = Field(default=None, max_length=180)


class CinematicCritiqueInput(StrictModel):
    summary: str = Field(min_length=1, max_length=500)
    tweaks: list[CinematicTweakInput] = Field(min_length=1, max_length=3)


class CinematicTweak(StrictModel):
    tweak_id: str = Field(min_length=1, max_length=80)
    category: TweakCategory
    diagnosis: str = Field(min_length=1, max_length=400)
    recommendation: str = Field(min_length=1, max_length=400)
    rationale: str = Field(min_length=1, max_length=400)
    priority: Priority = Priority.INFO
    confidence: confloat(ge=0.0, le=1.0) | None = None
    spoken_cue: str | None = Field(default=None, max_length=180)
    status: TweakStatus = TweakStatus.PROPOSED


class CinematicCritique(StrictModel):
    critique_id: str = Field(min_length=1, max_length=80)
    observation_id: str = Field(min_length=1, max_length=80)
    created_at: str = Field(min_length=1, max_length=80)
    intent_version: int = Field(ge=1)
    prompt_version: str = Field(min_length=1, max_length=80)
    intent: CinematicIntent
    summary: str = Field(min_length=1, max_length=500)
    tweaks: list[CinematicTweak] = Field(min_length=1, max_length=3)


class StoryBeat(StrictModel):
    beat_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    story_job: str = Field(min_length=1, max_length=500)
    required_visual_proof: str = Field(min_length=1, max_length=500)
    status: StoryBeatStatus = StoryBeatStatus.PENDING


class StoryBrief(StrictModel):
    story_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    logline: str = Field(min_length=1, max_length=500)
    emotional_arc: str = Field(min_length=1, max_length=300)
    visual_style: str = Field(min_length=1, max_length=500)
    must_show: list[str] = Field(default_factory=list, max_length=12)
    constraints: list[str] = Field(default_factory=list, max_length=12)
    beats: list[StoryBeat] = Field(min_length=1, max_length=12)

    @field_validator("must_show", "constraints")
    @classmethod
    def validate_story_lists(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value or len(value) > 240:
                raise ValueError("story list items must be between 1 and 240 characters")
        return values


class ShotCoverage(StrictModel):
    coverage_id: str = Field(min_length=1, max_length=80)
    beat_id: str = Field(min_length=1, max_length=80)
    shot_title: str = Field(min_length=1, max_length=160)
    observation_id: str = Field(min_length=1, max_length=100)
    captured_at: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=40)
    notes: str = Field(default="", max_length=500)


class ShotRecommendationInput(StrictModel):
    """Untrusted Gemini/browser input; server-owned fields are intentionally absent."""

    beat_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    story_purpose: str = Field(min_length=1, max_length=500)
    visual_objective: str = Field(min_length=1, max_length=500)
    why_now: str = Field(min_length=1, max_length=500)
    execution_guidance: str = Field(min_length=1, max_length=600)
    safety_notes: str = Field(min_length=1, max_length=600)
    priority: Priority = Priority.INFO
    confidence: confloat(ge=0.0, le=1.0) | None = None
    category: TweakCategory = TweakCategory.COMPOSITION


class ShotRecommendationBatchInput(StrictModel):
    recommendations: list[ShotRecommendationInput] = Field(min_length=2, max_length=3)


class ShotRecommendation(ShotRecommendationInput):
    recommendation_id: str = Field(min_length=1, max_length=80)
    observation_id: str = Field(min_length=1, max_length=100)
    intent_version: int = Field(ge=0)
    prompt_version: str = Field(min_length=1, max_length=80)
    created_at: str = Field(min_length=1, max_length=80)
    provenance: str = Field(default="gemini", min_length=1, max_length=40)
    status: ShotRecommendationStatus = ShotRecommendationStatus.SUGGESTED


class TweakDecisionRequest(StrictModel):
    decision: Decision


class RecommendationDecisionRequest(StrictModel):
    decision: RecommendationDecision


class VisualizationRequestInput(StrictModel):
    """The only browser/provider input accepted by the visualize workflow."""

    duration_seconds: Literal[10]
    variation_count: Literal[3]


class AnimationProfileSpec(StrictModel):
    """Server-owned screen-space motion metadata for one concept preview."""

    profile: AnimationProfile
    scale_start: confloat(ge=1.0, le=2.0)
    scale_end: confloat(ge=1.0, le=2.0)
    horizontal_drift_pct: confloat(ge=-25.0, le=25.0)
    vertical_drift_pct: confloat(ge=-25.0, le=25.0)
    subject_anchor: Literal["center", "right_third"]

    @model_validator(mode="after")
    def validate_fixed_motion(self) -> "AnimationProfileSpec":
        expected = {
            AnimationProfile.DESCENDING_REVEAL: (1.0, 1.25, 0.0, 14.0, "center"),
            AnimationProfile.LATERAL_PARALLAX: (1.08, 1.08, 12.0, 0.0, "right_third"),
            AnimationProfile.RESTRAINED_PULL_AWAY: (1.18, 1.0, 0.0, -5.0, "center"),
        }[self.profile]
        actual = (
            self.scale_start,
            self.scale_end,
            self.horizontal_drift_pct,
            self.vertical_drift_pct,
            self.subject_anchor,
        )
        if actual != expected:
            raise ValueError("animation profile parameters are server-fixed")
        return self


class VisualizationPreview(StrictModel):
    """Server-owned metadata for a browser animation over a frozen JPEG."""

    preview_id: str = Field(min_length=1, max_length=80)
    job_id: str = Field(min_length=1, max_length=80)
    recommendation_id: str = Field(min_length=1, max_length=80)
    recommendation_status: ShotRecommendationStatus = ShotRecommendationStatus.SUGGESTED
    title: str = Field(min_length=1, max_length=160)
    cinematography_summary: str = Field(min_length=1, max_length=500)
    story_purpose: str = Field(min_length=1, max_length=500)
    visual_objective: str = Field(min_length=1, max_length=500)
    why_now: str = Field(min_length=1, max_length=500)
    manual_execution_guidance: str = Field(min_length=1, max_length=600)
    safety_notes: str = Field(min_length=1, max_length=600)
    duration_seconds: Literal[10]
    animation_profile: AnimationProfile
    profile_spec: AnimationProfileSpec | None = None
    quality_status: VisualizationQualityStatus = VisualizationQualityStatus.PASS
    quality_reasons: list[str] = Field(default_factory=list, max_length=5)
    source_frame_available: bool
    provenance: str = Field(min_length=1, max_length=40)
    created_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def populate_profile_spec(self) -> "VisualizationPreview":
        if self.profile_spec is not None:
            if self.profile_spec.profile != self.animation_profile:
                raise ValueError("profile spec must match animation profile")
            return self
        defaults = {
            AnimationProfile.DESCENDING_REVEAL: AnimationProfileSpec(
                profile=AnimationProfile.DESCENDING_REVEAL,
                scale_start=1.0,
                scale_end=1.25,
                horizontal_drift_pct=0.0,
                vertical_drift_pct=14.0,
                subject_anchor="center",
            ),
            AnimationProfile.LATERAL_PARALLAX: AnimationProfileSpec(
                profile=AnimationProfile.LATERAL_PARALLAX,
                scale_start=1.08,
                scale_end=1.08,
                horizontal_drift_pct=12.0,
                vertical_drift_pct=0.0,
                subject_anchor="right_third",
            ),
            AnimationProfile.RESTRAINED_PULL_AWAY: AnimationProfileSpec(
                profile=AnimationProfile.RESTRAINED_PULL_AWAY,
                scale_start=1.18,
                scale_end=1.0,
                horizontal_drift_pct=0.0,
                vertical_drift_pct=-5.0,
                subject_anchor="center",
            ),
        }
        object.__setattr__(self, "profile_spec", defaults[self.animation_profile])
        return self

    @field_validator("quality_reasons")
    @classmethod
    def validate_quality_reasons(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value or len(value) > 240:
                raise ValueError("quality reasons must be between 1 and 240 characters")
        return values


class VisualizationJob(StrictModel):
    job_id: str = Field(min_length=1, max_length=80)
    request_fingerprint: str = Field(min_length=1, max_length=128)
    duration_seconds: Literal[10]
    variation_count: Literal[3]
    story_version: int = Field(ge=0)
    beat_id: str = Field(min_length=1, max_length=80)
    observation_id: str = Field(min_length=1, max_length=100)
    intent_version: int = Field(ge=0)
    requested_at: str = Field(min_length=1, max_length=80)
    started_at: str | None = Field(default=None, max_length=80)
    completed_at: str | None = Field(default=None, max_length=80)
    status: VisualizationJobStatus = VisualizationJobStatus.REQUESTED
    provenance: str = Field(min_length=1, max_length=40)
    source_kind: VisualizationSourceKind = VisualizationSourceKind.UNKNOWN
    source_label: str = Field(default="unknown", min_length=1, max_length=80)
    renderer_version: str = Field(default="unknown", min_length=1, max_length=80)
    source_frame_sha256: str = Field(default="", max_length=64, pattern=r"^[0-9a-f]{64}$|^$")
    source_width: int = Field(default=0, ge=0, le=8192)
    source_height: int = Field(default=0, ge=0, le=8192)
    source_frame_available: bool = False
    previews: list[VisualizationPreview] = Field(default_factory=list, max_length=3)
    error: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_ready_previews(self) -> "VisualizationJob":
        if self.status == VisualizationJobStatus.READY and len(self.previews) != 3:
            raise ValueError("ready visualization jobs must contain exactly three previews")
        if self.status == VisualizationJobStatus.READY and not self.source_frame_available:
            raise ValueError("ready visualization jobs must retain the source frame")
        if self.status == VisualizationJobStatus.FAILED and (
            self.previews or self.source_frame_available
        ):
            raise ValueError("failed visualization jobs cannot retain previews or source frames")
        return self


class StoryBeatRequest(StrictModel):
    beat_id: str = Field(min_length=1, max_length=80)
    action: str = Field(default="activate", pattern="^(activate|skip)$")


class IntentUpdateRequest(CinematicIntent):
    pass


class HealthMetrics(StrictModel):
    fps: float = 0.0
    latency_ms: float = 0.0
    frames_sent: int = 0
    critiques_received: int = 0
    valid_critiques: int = 0
    invalid_critiques: int = 0
    tweaks_acted: int = 0
    gemini_status: str
    grafana_status: str
