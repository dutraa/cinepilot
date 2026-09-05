"""Visualization renderer contracts and the deterministic local renderer."""

from __future__ import annotations

from typing import Protocol, Sequence
from uuid import NAMESPACE_URL, uuid5

import cv2
import numpy as np

from schemas import (
    AnimationProfile,
    AnimationProfileSpec,
    ShotRecommendation,
    VisualizationJob,
    VisualizationPreview,
    VisualizationRequestInput,
    VisualizationQualityStatus,
)


PROFILE_SUMMARIES = {
    AnimationProfile.DESCENDING_REVEAL: (
        "Illustrative 2D reveal: scale from 1.00 to 1.25 while revealing downward."
    ),
    AnimationProfile.LATERAL_PARALLAX: (
        "Illustrative 2D lateral move across a 1.08 scale while holding the subject on the right third."
    ),
    AnimationProfile.RESTRAINED_PULL_AWAY: (
        "Illustrative 2D pull-away: scale from 1.18 to 1.00 with a slight upward drift."
    ),
}

FIXED_PROFILES = (
    AnimationProfile.DESCENDING_REVEAL,
    AnimationProfile.LATERAL_PARALLAX,
    AnimationProfile.RESTRAINED_PULL_AWAY,
)

RENDERER_VERSION = "deterministic-screen-space-v2"


def validate_source_frame(source_frame: bytes) -> tuple[int, int]:
    """Decode the observation before it enters canonical visualization state."""
    if len(source_frame) < 4 or not source_frame.startswith(b"\xff\xd8") or not source_frame.endswith(b"\xff\xd9"):
        raise ValueError("current observation is not a valid JPEG")
    decoded = cv2.imdecode(np.frombuffer(source_frame, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None or decoded.size == 0:
        raise ValueError("current observation is not a valid JPEG")
    height, width = decoded.shape[:2]
    if width < 16 or height < 16:
        raise ValueError("current observation is too small for visualization")
    return width, height


class VisualizationRenderer(Protocol):
    """Small interface shared by deterministic and future provider renderers."""

    version: str

    def render(
        self,
        job: VisualizationJob,
        request: VisualizationRequestInput,
        recommendations: Sequence[ShotRecommendation],
    ) -> list[VisualizationPreview]: ...


def _profile_spec(profile: AnimationProfile) -> AnimationProfileSpec:
    if profile == AnimationProfile.DESCENDING_REVEAL:
        return AnimationProfileSpec(
            profile=profile,
            scale_start=1.0,
            scale_end=1.25,
            horizontal_drift_pct=0.0,
            vertical_drift_pct=14.0,
            subject_anchor="center",
        )
    if profile == AnimationProfile.LATERAL_PARALLAX:
        return AnimationProfileSpec(
            profile=profile,
            scale_start=1.08,
            scale_end=1.08,
            horizontal_drift_pct=12.0,
            vertical_drift_pct=0.0,
            subject_anchor="right_third",
        )
    return AnimationProfileSpec(
        profile=profile,
        scale_start=1.18,
        scale_end=1.0,
        horizontal_drift_pct=0.0,
        vertical_drift_pct=-5.0,
        subject_anchor="center",
    )


def validate_rendered_previews(
    job_id: str,
    previews: Sequence[VisualizationPreview],
    recommendations: Sequence[ShotRecommendation],
) -> list[VisualizationPreview]:
    """Validate renderer output before it can become ready canonical state."""
    recommendation_ids = [item.recommendation_id for item in recommendations]
    preview_ids = [item.preview_id for item in previews]
    if len(previews) != 3 or len(set(preview_ids)) != 3:
        raise ValueError("renderer returned exactly three unique visualization previews")
    if recommendation_ids != [item.recommendation_id for item in previews]:
        raise ValueError("renderer returned previews with invalid recommendation linkage")
    if [item.animation_profile for item in previews] != list(FIXED_PROFILES):
        raise ValueError("renderer returned invalid visualization profiles")
    if any(
        item.job_id != job_id
        or not item.source_frame_available
        or item.duration_seconds != 10
        or item.quality_status == VisualizationQualityStatus.FAIL
        for item in previews
    ):
        raise ValueError("renderer returned a preview that failed validation")
    return [item.model_copy(deep=True) for item in previews]


def render_deterministic_previews(
    job: VisualizationJob,
    request: VisualizationRequestInput,
    recommendations: Sequence[ShotRecommendation],
) -> list[VisualizationPreview]:
    """Build the fixed three-preview contract without inventing a flight path."""
    if request.duration_seconds != 10 or request.variation_count != 3:
        raise ValueError("deterministic visualization requires the fixed request")
    if len(recommendations) != len(FIXED_PROFILES):
        raise ValueError("three existing recommendations are required")

    previews: list[VisualizationPreview] = []
    for profile, recommendation in zip(FIXED_PROFILES, recommendations):
        previews.append(
            VisualizationPreview(
                preview_id=str(uuid5(NAMESPACE_URL, f"{job.job_id}:{profile.value}")),
                job_id=job.job_id,
                recommendation_id=recommendation.recommendation_id,
                recommendation_status=recommendation.status,
                title=recommendation.title,
                cinematography_summary=PROFILE_SUMMARIES[profile],
                story_purpose=recommendation.story_purpose,
                visual_objective=recommendation.visual_objective,
                why_now=recommendation.why_now,
                manual_execution_guidance=recommendation.execution_guidance,
                safety_notes=recommendation.safety_notes,
                duration_seconds=10,
                animation_profile=profile,
                profile_spec=_profile_spec(profile),
                quality_status=VisualizationQualityStatus.PASS,
                quality_reasons=[],
                source_frame_available=True,
                provenance=job.provenance,
                created_at=job.requested_at,
            )
        )
    return previews


class DeterministicVisualizationRenderer:
    """Provider-neutral renderer used when no live generation provider is approved."""

    version = RENDERER_VERSION

    def render(
        self,
        job: VisualizationJob,
        request: VisualizationRequestInput,
        recommendations: Sequence[ShotRecommendation],
    ) -> list[VisualizationPreview]:
        return render_deterministic_previews(job, request, recommendations)
