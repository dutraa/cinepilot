"""Google-backed AI previsualization renderer.

One bounded generation request per existing ``ShotRecommendation``, conditioned
on the frozen source frame, returning one short single-take clip that
illustrates the intended visual concept.

Boundaries this module keeps:

- Model output is untrusted. Bytes are written to a session-local temporary
  file and must pass every gate in ``visualization.validate_generated_media``
  before they can back a ready preview.
- The prompt never asks the model to invent a flight route, plan waypoints,
  avoid obstacles, or certify that a shot is safe.
- Nothing here runs inside an HTTP request path; the caller drives it from the
  single visualization worker thread.
- API keys and raw media never reach the log or the event ledger.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol, Sequence
from uuid import NAMESPACE_URL, uuid5

from schemas import (
    AnimationProfile,
    ShotRecommendation,
    VisualizationMediaMimeType,
    VisualizationPreview,
    VisualizationQualityStatus,
    VisualizationRenderKind,
)
from visualization import (
    FIXED_PROFILES,
    MediaValidationError,
    RenderContext,
    validate_generated_media,
)

logger = logging.getLogger("cinepilot.previsualization")

RENDERER_VERSION = "google-video-v1"
PROMPT_VERSION = "previs-prompt-v1"

# Current Google video models emit short clips. The requested 10-second
# deterministic duration is reconciled, never relabeled.
SUPPORTED_DURATIONS = (4, 6, 8)

PROFILE_CONCEPTS = {
    AnimationProfile.DESCENDING_REVEAL: (
        "a single continuous descending reveal that opens the frame downward onto the subject"
    ),
    AnimationProfile.LATERAL_PARALLAX: (
        "a single continuous lateral drift that holds the subject on the right third"
    ),
    AnimationProfile.RESTRAINED_PULL_AWAY: (
        "a single continuous restrained pull-away that lets the surroundings enter the frame"
    ),
}

PROMPT_CONSTRAINTS = (
    "Render one single continuous shot with no cuts, no edits, no transitions, "
    "no split screen, no text overlay, and no on-screen graphics. "
    "This is an illustrative creative reference only. Do not depict, plan, or "
    "imply a drone flight route, waypoints, obstacle avoidance, or any claim "
    "that the shot is safe to fly. Do not add people, vehicles, signage, or "
    "landmarks that are not already visible in the supplied frame."
)


class VisualizationProviderError(RuntimeError):
    """A provider could not return a usable, validated clip."""


@dataclass(frozen=True)
class GeneratedClip:
    """One raw provider response, still untrusted at this point."""

    data: bytes
    mime_type: str


class GoogleVideoClient(Protocol):
    """The narrow provider surface the renderer depends on."""

    model: str

    def generate_clip(
        self,
        *,
        prompt: str,
        source_frame: bytes,
        duration_seconds: int,
        timeout_sec: float,
    ) -> GeneratedClip: ...


def build_prompt(
    *,
    recommendation: ShotRecommendation,
    profile: AnimationProfile,
    duration_seconds: int,
    source_label: str,
    source_kind: str,
    story_title: str,
    beat_id: str,
    provenance: str,
) -> str:
    """Build the constrained, versioned previsualization prompt.

    The prompt is assembled only from the server's own source context and the
    fields of an existing recommendation, so a preview can never drift away
    from the decision it illustrates.
    """
    return "\n".join(
        [
            f"Previsualization concept, {duration_seconds} seconds, "
            f"{PROFILE_CONCEPTS[profile]}.",
            f"Source context: the supplied still frame is the current {source_kind} "
            f"observation ({source_label}, provenance {provenance}) for the story "
            f"'{story_title}', beat '{beat_id}'. Keep the place, terrain, structures, "
            "lighting, and time of day of that frame.",
            f"Story purpose: {recommendation.story_purpose}",
            f"Visual objective: {recommendation.visual_objective}",
            f"Recommended shot: {recommendation.title}",
            f"Why this shot is next: {recommendation.why_now}",
            f"Intended manual execution by the operator: {recommendation.execution_guidance}",
            f"Operator safety notes to respect but never to certify: {recommendation.safety_notes}",
            PROMPT_CONSTRAINTS,
        ]
    )


def _resolve_mime_type(raw: str | None) -> str:
    """Normalize a provider MIME string; unknown values stay unknown."""
    if not raw:
        return "unknown"
    return raw.split(";")[0].strip().lower()


class InteractionsVideoClient:
    """Gemini Omni Flash video generation through the Interactions API.

    Omni Flash is the first candidate because it accepts a text prompt plus a
    source image in one multimodal request and returns a short video, which is
    exactly the shape of the previsualization workflow.
    """

    def __init__(self, *, api_key: str, model: str, resolution: str, aspect_ratio: str) -> None:
        if not api_key:
            raise VisualizationProviderError("Google video provider is unavailable: API key is not configured")
        from google import genai  # imported lazily so the demo never needs credentials

        self._client = genai.Client(api_key=api_key)
        self.model = model
        self._resolution = resolution
        self._aspect_ratio = aspect_ratio

    def generate_clip(
        self,
        *,
        prompt: str,
        source_frame: bytes,
        duration_seconds: int,
        timeout_sec: float,
    ) -> GeneratedClip:
        import base64

        deadline = time.monotonic() + timeout_sec
        try:
            interaction = self._client.interactions.create(
                model=self.model,
                input=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "data": base64.b64encode(source_frame).decode("ascii"),
                        "mime_type": "image/jpeg",
                    },
                ],
                generation_config={"video_config": {"task": "image_to_video"}},
                response_format={
                    "type": "video",
                    "duration": f"{duration_seconds}s",
                    "resolution": self._resolution,
                    "aspect_ratio": self._aspect_ratio,
                    "delivery": "inline",
                },
                background=True,
                timeout=timeout_sec,
            )
        except Exception as exc:  # noqa: BLE001 - provider failures stay job-local
            raise VisualizationProviderError(f"Google video request failed: {exc}") from exc

        while getattr(interaction, "status", "") in {"in_progress", "queued"}:
            if time.monotonic() >= deadline:
                raise VisualizationProviderError("Google video generation timed out")
            time.sleep(min(3.0, max(0.1, deadline - time.monotonic())))
            try:
                interaction = self._client.interactions.get(interaction.id)
            except Exception as exc:  # noqa: BLE001
                raise VisualizationProviderError(f"Google video polling failed: {exc}") from exc

        status = getattr(interaction, "status", "unknown")
        if status != "completed":
            raise VisualizationProviderError(f"Google video generation ended as {status}")
        output = getattr(interaction, "output_video", None)
        data = getattr(output, "data", None) if output is not None else None
        if not data:
            raise VisualizationProviderError("Google video response contained no video content")
        if isinstance(data, str):
            try:
                data = base64.b64decode(data, validate=True)
            except Exception as exc:  # noqa: BLE001
                raise VisualizationProviderError("Google video response was not decodable") from exc
        return GeneratedClip(data=bytes(data), mime_type=_resolve_mime_type(getattr(output, "mime_type", None)))


class VeoVideoClient:
    """Veo 3.1 image-to-video through ``models.generate_videos``.

    Kept as the configurable alternative when Veo gives better image-to-video
    control or cinematic quality for a given shoot.
    """

    def __init__(self, *, api_key: str, model: str, resolution: str, aspect_ratio: str) -> None:
        if not api_key:
            raise VisualizationProviderError("Google video provider is unavailable: API key is not configured")
        from google import genai  # imported lazily so the demo never needs credentials
        from google.genai import types

        self._client = genai.Client(api_key=api_key)
        self._types = types
        self.model = model
        self._resolution = resolution
        self._aspect_ratio = aspect_ratio

    def generate_clip(
        self,
        *,
        prompt: str,
        source_frame: bytes,
        duration_seconds: int,
        timeout_sec: float,
    ) -> GeneratedClip:
        types = self._types
        deadline = time.monotonic() + timeout_sec
        try:
            operation = self._client.models.generate_videos(
                model=self.model,
                prompt=prompt,
                image=types.Image(image_bytes=source_frame, mime_type="image/jpeg"),
                config=types.GenerateVideosConfig(
                    number_of_videos=1,
                    duration_seconds=duration_seconds,
                    aspect_ratio=self._aspect_ratio,
                    resolution=self._resolution,
                    generate_audio=False,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise VisualizationProviderError(f"Google video request failed: {exc}") from exc

        while not getattr(operation, "done", False):
            if time.monotonic() >= deadline:
                raise VisualizationProviderError("Google video generation timed out")
            time.sleep(min(3.0, max(0.1, deadline - time.monotonic())))
            try:
                operation = self._client.operations.get(operation)
            except Exception as exc:  # noqa: BLE001
                raise VisualizationProviderError(f"Google video polling failed: {exc}") from exc

        if getattr(operation, "error", None):
            raise VisualizationProviderError("Google video generation reported an error")
        response = getattr(operation, "response", None)
        videos = getattr(response, "generated_videos", None) if response is not None else None
        if not videos:
            raise VisualizationProviderError("Google video response contained no generated videos")
        video = getattr(videos[0], "video", None)
        data = getattr(video, "video_bytes", None) if video is not None else None
        if not data:
            try:
                data = self._client.files.download(file=video)
            except Exception as exc:  # noqa: BLE001
                raise VisualizationProviderError(f"Google video download failed: {exc}") from exc
        if not data:
            raise VisualizationProviderError("Google video response contained no video content")
        return GeneratedClip(
            data=bytes(data),
            mime_type=_resolve_mime_type(getattr(video, "mime_type", None) or VisualizationMediaMimeType.MP4.value),
        )


class GoogleVideoRenderer:
    """Provider-backed renderer producing three validated previsualizations."""

    name = "google"
    version = RENDERER_VERSION
    prompt_version = PROMPT_VERSION
    render_kind = VisualizationRenderKind.GENERATED_VIDEO

    def __init__(
        self,
        client: GoogleVideoClient,
        *,
        max_bytes: int,
        timeout_sec: float,
        supported_durations: Sequence[int] = SUPPORTED_DURATIONS,
    ) -> None:
        self._client = client
        self.model = getattr(client, "model", "unknown")
        self._max_bytes = max_bytes
        self._timeout_sec = timeout_sec
        self.supported_durations = tuple(supported_durations)

    def render(self, context: RenderContext) -> list[VisualizationPreview]:
        job = context.job
        if len(context.recommendations) != len(FIXED_PROFILES):
            raise VisualizationProviderError("three existing recommendations are required")
        if job.duration_seconds not in self.supported_durations:
            raise VisualizationProviderError(
                f"this provider cannot deliver a {job.duration_seconds}-second clip"
            )
        context.media_dir.mkdir(parents=True, exist_ok=True)

        previews: list[VisualizationPreview] = []
        for profile, recommendation in zip(FIXED_PROFILES, context.recommendations):
            prompt = build_prompt(
                recommendation=recommendation,
                profile=profile,
                duration_seconds=job.duration_seconds,
                source_label=job.source_label,
                source_kind=job.source_kind.value,
                story_title=context.story_title or "untitled story",
                beat_id=job.beat_id,
                provenance=job.provenance,
            )
            clip = self._client.generate_clip(
                prompt=prompt,
                source_frame=context.source_frame,
                duration_seconds=job.duration_seconds,
                timeout_sec=self._timeout_sec,
            )
            if not isinstance(clip, GeneratedClip) or not isinstance(clip.data, (bytes, bytearray)):
                raise VisualizationProviderError("provider returned a malformed generation response")
            media_id = str(uuid5(NAMESPACE_URL, f"{job.job_id}:media:{profile.value}"))
            media_path = context.media_dir / f"{media_id}.bin"
            media_path.write_bytes(bytes(clip.data))
            try:
                media = validate_generated_media(
                    media_path,
                    declared_mime_type=clip.mime_type,
                    max_bytes=self._max_bytes,
                    expected_duration_seconds=job.duration_seconds,
                    media_id=media_id,
                )
            except MediaValidationError as exc:
                media_path.unlink(missing_ok=True)
                # Safe operator signal only: provider, model, and the validation
                # reason. Never the API key, the prompt, or the media itself.
                logger.warning(
                    "Rejected generated previsualization from %s/%s: %s",
                    self.name,
                    self.model,
                    exc,
                )
                raise
            previews.append(
                VisualizationPreview(
                    preview_id=str(uuid5(NAMESPACE_URL, f"{job.job_id}:{profile.value}")),
                    job_id=job.job_id,
                    recommendation_id=recommendation.recommendation_id,
                    recommendation_status=recommendation.status,
                    title=recommendation.title,
                    cinematography_summary=(
                        f"AI previsualization of {PROFILE_CONCEPTS[profile]}. "
                        "Illustrative creative reference, not flight truth."
                    ),
                    story_purpose=recommendation.story_purpose,
                    visual_objective=recommendation.visual_objective,
                    why_now=recommendation.why_now,
                    manual_execution_guidance=recommendation.execution_guidance,
                    safety_notes=recommendation.safety_notes,
                    render_kind=VisualizationRenderKind.GENERATED_VIDEO,
                    duration_seconds=job.duration_seconds,
                    requested_duration_seconds=job.requested_duration_seconds,
                    duration_note=job.duration_note,
                    animation_profile=profile,
                    profile_spec=None,
                    media=media,
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


def build_google_client(
    *,
    backend: str,
    api_key: str,
    model: str,
    resolution: str,
    aspect_ratio: str,
) -> GoogleVideoClient:
    """Construct the configured Google backend without logging the key."""
    normalized = (backend or "").strip().lower()
    if normalized == "interactions":
        return InteractionsVideoClient(
            api_key=api_key, model=model, resolution=resolution, aspect_ratio=aspect_ratio
        )
    if normalized == "veo":
        return VeoVideoClient(
            api_key=api_key, model=model, resolution=resolution, aspect_ratio=aspect_ratio
        )
    raise VisualizationProviderError(f"unknown Google video backend: {backend}")


def build_google_renderer(settings: Any) -> GoogleVideoRenderer:
    """Build the configured renderer, or fail loudly without a key."""
    api_key = settings.GOOGLE_VIDEO_API_KEY or settings.GEMINI_API_KEY
    client = build_google_client(
        backend=settings.GOOGLE_VIDEO_BACKEND,
        api_key=api_key,
        model=settings.GOOGLE_VIDEO_MODEL,
        resolution=settings.GOOGLE_VIDEO_RESOLUTION,
        aspect_ratio=settings.GOOGLE_VIDEO_ASPECT_RATIO,
    )
    return GoogleVideoRenderer(
        client,
        max_bytes=settings.GOOGLE_VIDEO_MAX_BYTES,
        timeout_sec=settings.GOOGLE_VIDEO_TIMEOUT_SEC,
        supported_durations=(settings.GOOGLE_VIDEO_DURATION_SEC,),
    )
