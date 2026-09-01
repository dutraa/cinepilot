"""Validated domain contracts for CinePilot's cinematic workflows."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, confloat, field_validator


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
