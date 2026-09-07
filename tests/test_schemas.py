import pytest
from pydantic import ValidationError

from schemas import CinematicCritiqueInput, CinematicIntent


def valid_tweak(category: str = "composition") -> dict[str, object]:
    return {
        "category": category,
        "diagnosis": "The subject is centered and loses visual tension.",
        "recommendation": "Shift the subject toward the right third before the reveal.",
        "rationale": "The negative space will make the movement feel intentional.",
        "priority": "WARNING",
    }


def test_intent_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CinematicIntent(
            shot_name="Reveal",
            creative_goal="Make the building feel imposing.",
            subject="Building",
            unexpected="not allowed",
        )


def test_critique_requires_at_most_three_tweaks() -> None:
    with pytest.raises(ValidationError):
        CinematicCritiqueInput(
            summary="The shot is close but needs a stronger visual hierarchy.",
            tweaks=[valid_tweak("composition") for _ in range(4)],
        )


def test_intent_limits_constraints() -> None:
    with pytest.raises(ValidationError):
        CinematicIntent(
            shot_name="Reveal",
            creative_goal="Make the building feel imposing.",
            subject="Building",
            constraints=["too many"] * 6,
        )
