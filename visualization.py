"""Renderer contracts, duration reconciliation, and the deterministic renderer.

CinePilot renders three illustrative previsualization concepts for the three
existing shot recommendations. Two renderers implement the same contract:

- ``DeterministicVisualizationRenderer`` animates the frozen JPEG in screen
  space. It invents no pixels, needs no credentials, and is the fallback and
  the test double.
- ``GoogleVideoRenderer`` (see ``google_video.py``) asks a Google video model
  for one short generated clip per recommendation.

Neither is live evidence, guaranteed camera movement, drone-flight guidance,
proof that a shot is safe, proof that production quality improved, or proof
that a recommendation was acted on.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence
from uuid import NAMESPACE_URL, uuid5

import cv2
import numpy as np

from schemas import (
    AnimationProfile,
    AnimationProfileSpec,
    GeneratedMediaRef,
    ShotRecommendation,
    VisualizationJob,
    VisualizationMediaMimeType,
    VisualizationPreview,
    VisualizationRenderKind,
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

# Only containers a browser can play inline are accepted from a provider.
ALLOWED_MEDIA_MIME_TYPES = {
    VisualizationMediaMimeType.MP4.value,
    VisualizationMediaMimeType.WEBM.value,
}

# Video codecs a browser can actually decode inline. A correct container with
# an unplayable codec (for example MPEG-4 Part 2 inside an MP4) is rejected:
# the creator would otherwise get a black box labeled "ready".
BROWSER_PLAYABLE_CODECS = {"avc1", "h264", "av01", "vp08", "vp09", "vp80", "vp90"}

# Measured duration may drift from the requested duration by this much before
# the clip is rejected. The measured value is always the one published.
MEDIA_DURATION_TOLERANCE_SEC = 1.5


class MediaValidationError(ValueError):
    """Provider media failed a server-side validation gate."""


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


def reconcile_duration(requested: int, supported: Sequence[int]) -> tuple[int, str]:
    """Return the duration a renderer can actually deliver plus a plain note.

    A shorter provider clip is never relabeled as the requested duration; the
    difference is stated explicitly so the UI, events, and docs agree.
    """
    if not supported:
        raise ValueError("a renderer must declare at least one supported duration")
    if requested in supported:
        return requested, ""
    shorter = [value for value in supported if value < requested]
    effective = max(shorter) if shorter else min(supported)
    note = (
        f"Requested {requested} seconds; this renderer delivers {effective}-second "
        f"clips. Each preview is {effective} seconds, not {requested}."
    )
    return effective, note


@dataclass(frozen=True)
class RenderContext:
    """Everything one bounded render attempt is allowed to see."""

    job: VisualizationJob
    request: VisualizationRequestInput
    recommendations: tuple[ShotRecommendation, ...]
    # The frozen JPEG observation this job is pinned to.
    source_frame: bytes
    # A session-local directory for temporary generated artifacts.
    media_dir: Path
    # The creator-entered story this concept has to serve.
    story_title: str = ""


class VisualizationRenderer(Protocol):
    """Small provider-neutral interface shared by every renderer."""

    name: str
    version: str
    model: str
    prompt_version: str
    render_kind: VisualizationRenderKind
    supported_durations: tuple[int, ...]

    def render(self, context: RenderContext) -> list[VisualizationPreview]: ...


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


def validate_generated_media(
    path: Path,
    *,
    declared_mime_type: str,
    max_bytes: int,
    expected_duration_seconds: int,
    media_id: str,
) -> GeneratedMediaRef:
    """Validate one untrusted provider clip before it can back a preview.

    Checks MIME type, file existence, maximum size, container magic bytes,
    decodability, dimensions, frame count, and playable duration. Raises
    ``MediaValidationError`` with a safe, quotable reason on any failure.
    """
    if declared_mime_type not in ALLOWED_MEDIA_MIME_TYPES:
        raise MediaValidationError(f"provider returned an unsupported media type: {declared_mime_type}")
    if not path.is_file():
        raise MediaValidationError("provider media file is missing")
    byte_size = path.stat().st_size
    if byte_size <= 0:
        raise MediaValidationError("provider media file is empty")
    if byte_size > max_bytes:
        raise MediaValidationError(
            f"provider media is {byte_size} bytes, above the {max_bytes} byte ceiling"
        )
    header = path.read_bytes()[:32]
    if declared_mime_type == VisualizationMediaMimeType.MP4.value and b"ftyp" not in header:
        raise MediaValidationError("provider media is not a decodable MP4 container")
    if declared_mime_type == VisualizationMediaMimeType.WEBM.value and not header.startswith(
        b"\x1a\x45\xdf\xa3"
    ):
        raise MediaValidationError("provider media is not a decodable WebM container")

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise MediaValidationError("provider media could not be decoded")
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fourcc = int(capture.get(cv2.CAP_PROP_FOURCC) or 0)
        readable, frame = capture.read()
    finally:
        capture.release()

    codec = "".join(chr((fourcc >> (8 * index)) & 0xFF) for index in range(4)).strip()
    if codec.lower() not in BROWSER_PLAYABLE_CODECS:
        raise MediaValidationError(
            f"provider media codec '{codec}' is not playable in a browser"
        )
    if not readable or frame is None:
        raise MediaValidationError("provider media contains no readable frames")
    if frame_count < 1 or fps <= 0.0:
        raise MediaValidationError("provider media reports no playable timeline")
    if width < 16 or height < 16:
        raise MediaValidationError("provider media is too small to be a usable reference")
    measured = frame_count / fps
    if abs(measured - expected_duration_seconds) > MEDIA_DURATION_TOLERANCE_SEC:
        raise MediaValidationError(
            f"provider media is {measured:.1f}s, not the expected {expected_duration_seconds}s"
        )
    return GeneratedMediaRef(
        media_id=media_id,
        mime_type=VisualizationMediaMimeType(declared_mime_type),
        byte_size=byte_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        measured_duration_seconds=round(measured, 2),
        frame_count=frame_count,
        width=width,
        height=height,
        available=True,
    )


def validate_rendered_previews(
    job: VisualizationJob,
    previews: Sequence[VisualizationPreview],
    recommendations: Sequence[ShotRecommendation],
    *,
    media_dir: Path | None = None,
) -> list[VisualizationPreview]:
    """Validate renderer output before it can become ready canonical state.

    Applies to deterministic and provider output alike: preview count and
    uniqueness, one-to-one recommendation linkage, fixed concept profiles, job
    linkage, retained source frame, quality gate, honest duration, declared
    provenance, and — for generated clips — that the referenced session-local
    media file still exists.
    """
    recommendation_ids = [item.recommendation_id for item in recommendations]
    preview_ids = [item.preview_id for item in previews]
    if len(previews) != 3 or len(set(preview_ids)) != 3:
        raise ValueError("renderer returned exactly three unique visualization previews")
    if recommendation_ids != [item.recommendation_id for item in previews]:
        raise ValueError("renderer returned previews with invalid recommendation linkage")
    if [item.animation_profile for item in previews] != list(FIXED_PROFILES):
        raise ValueError("renderer returned invalid visualization profiles")
    if any(
        item.job_id != job.job_id
        or not item.source_frame_available
        or item.quality_status == VisualizationQualityStatus.FAIL
        for item in previews
    ):
        raise ValueError("renderer returned a preview that failed validation")
    if any(item.render_kind != job.render_kind for item in previews):
        raise ValueError("renderer returned previews with the wrong render kind")
    if any(item.duration_seconds != job.duration_seconds for item in previews):
        raise ValueError("renderer returned a preview whose duration contradicts the job")
    if any(item.provider != job.provider or item.model != job.model for item in previews):
        raise ValueError("renderer returned previews with inconsistent provider provenance")
    if any(item.source_frame_sha256 != job.source_frame_sha256 for item in previews):
        raise ValueError("renderer returned previews with an unlinked source frame")
    if job.render_kind == VisualizationRenderKind.GENERATED_VIDEO:
        for item in previews:
            if item.media is None or not item.media.available:
                raise ValueError("generated previews must reference available media")
            if media_dir is not None and not (media_dir / f"{item.media.media_id}.bin").is_file():
                raise ValueError("generated preview media is missing from the session workspace")
    return [item.model_copy(deep=True) for item in previews]


def render_deterministic_previews(
    job: VisualizationJob,
    request: VisualizationRequestInput,
    recommendations: Sequence[ShotRecommendation],
) -> list[VisualizationPreview]:
    """Build the fixed three-preview contract without inventing a flight path."""
    if request.variation_count != 3:
        raise ValueError("deterministic visualization requires three variations")
    if job.duration_seconds != 10:
        raise ValueError("deterministic visualization renders exactly 10 seconds")
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
                render_kind=VisualizationRenderKind.DETERMINISTIC_ANIMATION,
                duration_seconds=10,
                requested_duration_seconds=request.duration_seconds,
                duration_note=job.duration_note,
                animation_profile=profile,
                profile_spec=_profile_spec(profile),
                provider=job.provider,
                model=job.model,
                prompt_version=job.prompt_version,
                source_frame_sha256=job.source_frame_sha256,
                quality_status=VisualizationQualityStatus.PASS,
                quality_reasons=[],
                source_frame_available=True,
                provenance=job.provenance,
                created_at=job.requested_at,
            )
        )
    return previews


class DeterministicVisualizationRenderer:
    """Screen-space fallback renderer. Requires no credentials or network."""

    name = "deterministic"
    version = RENDERER_VERSION
    model = "none"
    prompt_version = "none"
    render_kind = VisualizationRenderKind.DETERMINISTIC_ANIMATION
    supported_durations = (10,)

    def render(self, context: RenderContext) -> list[VisualizationPreview]:
        return render_deterministic_previews(
            context.job, context.request, context.recommendations
        )


def select_renderer(settings) -> VisualizationRenderer:
    """Pick the renderer this run is actually allowed to use.

    Provider-backed previsualization requires both an explicit opt-in and a
    configured key. Anything else falls back to the deterministic renderer,
    which is always labeled as deterministic; deterministic output is never
    presented as Google output.
    """
    provider = (getattr(settings, "VISUALIZATION_PROVIDER", "") or "").strip().lower()
    enabled = bool(getattr(settings, "ENABLE_GENERATED_PREVISUALIZATION", False))
    api_key = getattr(settings, "GOOGLE_VIDEO_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", "")
    if provider != "google" or not enabled or not api_key:
        return DeterministicVisualizationRenderer()
    from google_video import build_google_renderer  # lazy: keeps the demo import-light

    return build_google_renderer(settings)
