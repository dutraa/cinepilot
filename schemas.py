"""Validated domain contracts for CinePilot's cinematic critique workflow."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, confloat, field_validator


class TweakCategory(str, Enum):
    COMPOSITION = "composition"
    CAMERA_MOVEMENT = "camera_movement"
    PERSPECTIVE = "perspective"
    LIGHTING = "lighting"
    SUBJECT = "subject"
    PACING = "pacing"
    CONTINUITY = "continuity"


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
    safety_note: str | None = Field(default=None, max_length=300)


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
    safety_note: str | None = Field(default=None, max_length=300)
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


class ShotStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class ShotUpdateRequest(StrictModel):
    """Creator-driven shot lifecycle update (the only path to COMPLETED)."""

    status: ShotStatus
    feedback: str = Field(default="", max_length=400)


class TweakDecisionRequest(StrictModel):
    decision: Decision


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
