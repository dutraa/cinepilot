"""Bounded, explicit evidence-burst analysis for the live coverage workflow."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import cv2
import numpy as np
from google import genai
from google.genai import types

from config import settings
from schemas import (
    ObservationBurst,
    ObservationFrame,
    TakeAnalysisResult,
    TakeEvaluationInput,
    TakeRecommendationInput,
)


class AnalysisProviderError(RuntimeError):
    """A provider could not produce a bounded, valid answer."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def capture_fresh_burst(
    video_manager: Any,
    *,
    job_id: str,
    story_version: int,
    intent_version: int,
    beat_id: str,
    provenance: str,
    frame_count: int = 6,
    interval_sec: float = 0.4,
) -> tuple[ObservationBurst, list[bytes]]:
    """Capture only current frames; raw bytes remain in the worker scope."""
    if not 3 <= frame_count <= 8:
        raise ValueError("evidence burst must contain between 3 and 8 frames")
    source = video_manager.status_snapshot()
    started = _now_iso()
    observation_id = str(uuid4())
    frames: list[ObservationFrame] = []
    images: list[bytes] = []
    for index in range(frame_count):
        source = video_manager.status_snapshot()
        age = source.get("frame_age_sec")
        eligible = (
            source.get("status") == "live"
            and age is not None
            and age <= settings.SOURCE_MAX_FRAME_AGE_SEC
            and (
                source.get("is_real_source")
                or source.get("active_source") == "synthetic"
                or source.get("fallback_active")
            )
        )
        jpeg = video_manager.get_fresh_jpeg(
            quality=85,
            max_dim=1280,
            max_age_sec=settings.SOURCE_MAX_FRAME_AGE_SEC,
        )
        if not eligible or jpeg is None:
            raise AnalysisProviderError("fresh live evidence is unavailable")
        decoded = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        if decoded is None:
            raise AnalysisProviderError("captured evidence frame could not be decoded")
        captured_at = _now_iso()
        frames.append(
            ObservationFrame(
                frame_index=index,
                captured_at=captured_at,
                frame_age_ms=max(0, int(round((age or 0.0) * 1000))),
                width=int(decoded.shape[1]),
                height=int(decoded.shape[0]),
                sha256=hashlib.sha256(jpeg).hexdigest(),
            )
        )
        images.append(jpeg)
        if index < frame_count - 1:
            time.sleep(max(0.05, min(interval_sec, 1.0)))
    completed = _now_iso()
    burst = ObservationBurst(
        observation_id=observation_id,
        job_id=job_id,
        story_version=story_version,
        intent_version=intent_version,
        beat_id=beat_id,
        provenance=source.get("provenance", provenance),
        requested_source=source.get("requested_source", "unknown"),
        active_source=source.get("active_source", "unknown"),
        freshness_limit_ms=int(settings.SOURCE_MAX_FRAME_AGE_SEC * 1000),
        capture_started_at=started,
        capture_completed_at=completed,
        frames=frames,
    )
    return burst, images


def deterministic_analysis(context: dict[str, Any]) -> TakeAnalysisResult:
    """A labeled offline provider for synthetic/demo verification only."""
    beat = context["active_beat"]
    title = beat["title"]
    proof = beat["required_visual_proof"]
    beat_id = beat["beat_id"]
    return TakeAnalysisResult(
        observed=["A current synthetic frame burst was captured.", "The requested source is explicitly synthetic."],
        not_established=["The burst does not establish production-quality improvement or pilot safety."],
        missing_coverage=[f"The active beat '{title}' still needs proof: {proof}"],
        recommendations=[
            TakeRecommendationInput(
                beat_id=beat_id,
                title=f"{title}: establish the required proof",
                diagnosis=f"The current evidence does not visibly establish {proof}.",
                story_purpose=beat["story_job"],
                visual_objective=proof,
                why_now="This is the active beat and its required proof remains unestablished.",
                execution_guidance="The pilot manually chooses a safe, stable framing that makes the stated visual proof readable.",
                technical_plausibility="A restrained manual take is plausible if the pilot confirms the route, framing, and operating conditions.",
                safety_notes="Advisory only. The pilot remains responsible for flight decisions, people, obstacles, weather, and battery.",
                priority="WARNING",
                confidence=0.55,
            ),
            TakeRecommendationInput(
                beat_id=beat_id,
                title=f"{title}: hold the visual proof",
                diagnosis="The required proof needs a clearer, more stable presentation than the current burst establishes.",
                story_purpose=beat["story_job"],
                visual_objective=f"Keep the subject readable while showing {proof}.",
                why_now="It is a lower-risk alternative for the same missing coverage.",
                execution_guidance="The pilot manually holds a readable composition long enough for the story beat to land.",
                technical_plausibility="A static or restrained manual take is plausible when a safe position is available.",
                safety_notes="Advisory only. Confirm the operating environment before capture; do not treat this as a flight command.",
                priority="INFO",
                confidence=0.48,
            ),
            TakeRecommendationInput(
                beat_id=beat_id,
                title=f"{title}: reveal the context",
                diagnosis="The active beat may need context around the subject before the required proof reads clearly.",
                story_purpose=beat["story_job"],
                visual_objective=f"Connect the subject to the context needed for {proof}.",
                why_now="This alternative addresses the same gap through context rather than movement.",
                execution_guidance="The pilot manually captures a wider contextual composition from a confirmed safe position.",
                technical_plausibility="A wider manual composition is plausible without requiring autonomous movement.",
                safety_notes="Advisory only. The pilot makes all flight and capture decisions.",
                priority="INFO",
                confidence=0.42,
            ),
        ],
    )


def _prompt(context: dict[str, Any], purpose: str) -> str:
    return (
        "Return JSON only matching the supplied TakeAnalysisResult contract. "
        "This is a bounded between-takes advisory analysis. Never provide flight commands, "
        "autonomy, waypoints, obstacle avoidance, or claims of production improvement. "
        "Recommendations must be concrete, story-specific, and human-language manual guidance. "
        f"Task: {purpose}\nContext:\n{json.dumps(context, sort_keys=True)}"
    )


async def gemini_analysis(images: list[bytes], context: dict[str, Any]) -> TakeAnalysisResult:
    """Make exactly one bounded Gemini request for a frozen evidence burst."""
    if not settings.GEMINI_API_KEY:
        raise AnalysisProviderError("Gemini provider is unavailable: API key is not configured")
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    parts: list[Any] = [types.Part(text=_prompt(context, "identify missing coverage and rank three next shots"))]
    parts.extend(types.Part.from_bytes(data=image, mime_type="image/jpeg") for image in images)
    try:
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        text = getattr(response, "text", None)
        if not text:
            raise AnalysisProviderError("Gemini returned no structured response")
        return TakeAnalysisResult.model_validate(json.loads(text))
    except AnalysisProviderError:
        raise
    except Exception as exc:  # noqa: BLE001 - convert provider failures to a safe job error
        raise AnalysisProviderError(f"Gemini analysis failed: {exc}") from exc


async def gemini_evaluation(images: list[bytes], context: dict[str, Any]) -> TakeEvaluationInput:
    """Make one separate bounded Gemini request for follow-up evaluation."""
    if not settings.GEMINI_API_KEY:
        raise AnalysisProviderError("Gemini provider is unavailable: API key is not configured")
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    parts: list[Any] = [types.Part(text=_prompt(context, "evaluate whether the selected coverage appears addressed"))]
    parts.extend(types.Part.from_bytes(data=image, mime_type="image/jpeg") for image in images)
    try:
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        text = getattr(response, "text", None)
        if not text:
            raise AnalysisProviderError("Gemini returned no evaluation")
        return TakeEvaluationInput.model_validate(json.loads(text))
    except AnalysisProviderError:
        raise
    except Exception as exc:  # noqa: BLE001 - convert provider failures to a safe job error
        raise AnalysisProviderError(f"Gemini evaluation failed: {exc}") from exc
