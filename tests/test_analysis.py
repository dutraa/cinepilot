"""Provider-boundary tests for bounded take analysis."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import analysis
from schemas import TakeAnalysisResult, TakeEvaluationInput


def _valid_analysis_payload() -> dict[str, object]:
    recommendation = {
        "beat_id": "discovery",
        "diagnosis": "The lodge is not yet readable as the destination.",
        "story_purpose": "Reveal the destination after establishing isolation.",
        "visual_objective": "Make the lodge grow clearly in frame.",
        "why_now": "The isolation beat is established and discovery is still missing.",
        "execution_guidance": "The pilot manually holds a stable composition from a confirmed safe position.",
        "technical_plausibility": "A restrained static composition is feasible from a safe position.",
        "safety_notes": "Advisory only; the pilot remains responsible for every flight decision.",
        "priority": "WARNING",
        "confidence": 0.7,
    }
    return {
        "observed": ["The lodge is small in a wide landscape."],
        "not_established": ["The current burst does not establish a destination reveal."],
        "missing_coverage": ["The discovery beat still needs the lodge to become visually prominent."],
        "recommendations": [
            {"title": "Hold a closer destination frame", **recommendation},
            {"title": "Reveal the lodge with foreground context", **recommendation},
            {"title": "Frame the lodge as the visual endpoint", **recommendation},
        ],
    }


def test_gemini_analysis_supplies_the_strict_result_schema(monkeypatch) -> None:
    monkeypatch.setattr(analysis.settings, "GEMINI_API_KEY", "test-key")
    captured: dict[str, object] = {}

    async def generate_content(**kwargs):
        captured["config"] = kwargs["config"]
        return SimpleNamespace(text=json.dumps(_valid_analysis_payload()))

    fake_client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    monkeypatch.setattr(analysis.genai, "Client", lambda **_kwargs: fake_client)

    result = asyncio.run(analysis.gemini_analysis([b"jpeg"], {"active_beat": {}}))

    assert isinstance(result, TakeAnalysisResult)
    assert captured["config"].response_schema is TakeAnalysisResult


def test_gemini_evaluation_supplies_the_strict_result_schema(monkeypatch) -> None:
    monkeypatch.setattr(analysis.settings, "GEMINI_API_KEY", "test-key")
    captured: dict[str, object] = {}

    async def generate_content(**kwargs):
        captured["config"] = kwargs["config"]
        return SimpleNamespace(
            text=json.dumps(
                {
                    "outcome": "unclear",
                    "explanation": "The new burst does not clearly establish the intended coverage.",
                }
            )
        )

    fake_client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    monkeypatch.setattr(analysis.genai, "Client", lambda **_kwargs: fake_client)

    result = asyncio.run(analysis.gemini_evaluation([b"jpeg"], {"active_beat": {}}))

    assert isinstance(result, TakeEvaluationInput)
    assert captured["config"].response_schema is TakeEvaluationInput
