"""Deterministic recommendation provider for the explicit local demo mode."""

from __future__ import annotations

from typing import Final

from schemas import ShotRecommendationInput, ShotRecommendation
from state import AppState
from story_demo import load_initial_shot, load_story_fixture


DEMO_PROVENANCE: Final = "deterministic_demo"

_RECOMMENDATION_COPY: dict[str, list[dict[str, str]]] = {
    "isolation": [
        {
            "beat_id": "discovery",
            "title": "Descending reveal",
            "story_purpose": "Let the audience find the lodge inside the landscape.",
            "visual_objective": "Make the lodge grow in frame as the foreground opens up.",
            "why_now": "The current high wide proves isolation, but discovery is still missing.",
            "execution_guidance": "Manually descend slowly while moving forward, keeping the lodge readable and a safe margin from terrain.",
            "safety_notes": "The pilot confirms route, weather, obstacles, people, and a clear return path before capture.",
        },
        {
            "beat_id": "discovery",
            "title": "Forward ridge reveal",
            "story_purpose": "Turn the landscape into a path that leads the audience to the lodge.",
            "visual_objective": "Let the lodge emerge from behind a foreground ridge without losing its scale.",
            "why_now": "A reveal supplies the missing transition between remote context and a discoverable destination.",
            "execution_guidance": "Manually frame the ridge as foreground, then make a restrained forward move while maintaining safe separation.",
            "safety_notes": "The pilot checks terrain clearance, wind, signal, and the planned exit before attempting the move.",
        },
        {
            "beat_id": "invitation",
            "title": "Lateral parallax pass",
            "story_purpose": "Make the route to the lodge feel reachable and welcoming.",
            "visual_objective": "Hold the lodge on the right third while foreground trees create depth toward the entrance.",
            "why_now": "The wide establishes distance; a lateral layer can now translate that distance into an inviting route.",
            "execution_guidance": "Manually move laterally at a restrained pace, preserving the right-third placement and a safe clearance envelope.",
            "safety_notes": "The pilot confirms the lateral corridor is clear and does not treat this guidance as an automated flight command.",
        },
    ],
    "invitation": [
        {
            "beat_id": "invitation",
            "title": "Threshold approach",
            "story_purpose": "Make arrival feel calm and possible rather than abrupt.",
            "visual_objective": "Bring the entrance forward while preserving a welcoming amount of negative space.",
            "why_now": "Discovery is covered; the audience now needs a clear, reachable destination.",
            "execution_guidance": "Manually approach at a restrained pace and hold the entrance in a stable composition.",
            "safety_notes": "The pilot checks people, structures, weather, and stopping distance before capture.",
        },
        {
            "beat_id": "invitation",
            "title": "Entrance-side drift",
            "story_purpose": "Give the lodge a human-scale invitation without losing the mountain context.",
            "visual_objective": "Use a gentle side move to reveal the entrance and preserve a readable route.",
            "why_now": "A second invitation option tests whether the threshold or the route is the stronger welcome.",
            "execution_guidance": "Manually drift sideways with the entrance held in the near third and keep the movement smooth.",
            "safety_notes": "The pilot validates the path and avoids people, structures, and prop wash hazards.",
        },
        {
            "beat_id": "renewal",
            "title": "Warmth beyond the door",
            "story_purpose": "Bridge a welcoming arrival into evidence that the lodge is recovering.",
            "visual_objective": "Reveal a first warm light or moving figure beyond the entrance.",
            "why_now": "The destination is reachable; the next missing proof is life returning inside it.",
            "execution_guidance": "Manually hold the entrance as an anchor and make a small reveal toward the visible activity.",
            "safety_notes": "The pilot verifies privacy, safe distance, lighting conditions, and a stable hover or camera position.",
        },
    ],
    "renewal": [
        {
            "beat_id": "renewal",
            "title": "Recovery orbit",
            "story_purpose": "Show that the lodge is active and recovering after the storm.",
            "visual_objective": "Reveal people, lights, and movement in one coherent layer around the building.",
            "why_now": "The audience has arrived; a visible sign of activity is the strongest missing evidence of renewal.",
            "execution_guidance": "Manually plan a restrained orbit around the safe side of the lodge while keeping activity legible.",
            "safety_notes": "The pilot confirms obstacle clearance, people awareness, wind, and privacy before any orbit.",
        },
        {
            "beat_id": "renewal",
            "title": "Rise over the lights",
            "story_purpose": "Let human activity reconnect the lodge to its landscape.",
            "visual_objective": "Begin at the warm lights, then reveal the wider mountain setting with a measured rise.",
            "why_now": "A vertical reveal makes renewal feel larger without repeating the opening wide.",
            "execution_guidance": "Manually rise at a controlled pace from a safe position while protecting the light-to-landscape transition.",
            "safety_notes": "The pilot checks vertical clearance, weather, people, and exposure before attempting the rise.",
        },
        {
            "beat_id": "confidence",
            "title": "Resolved destination",
            "story_purpose": "Prepare a confident ending after the lodge has come back to life.",
            "visual_objective": "Hold the lodge as a stable destination with enough surrounding scale for closure.",
            "why_now": "Renewal is visible; the remaining story need is a resolved image the audience can leave with.",
            "execution_guidance": "Manually settle into a stable elevated composition and hold long enough for the ending to land.",
            "safety_notes": "The pilot verifies position, weather, battery, and a safe end-of-take path.",
        },
    ],
    "confidence": [
        {
            "beat_id": "confidence",
            "title": "Elevated closing image",
            "story_purpose": "End with confidence that the lodge is a destination worth returning to.",
            "visual_objective": "Use a resolved elevated frame with the lodge and its route clearly connected.",
            "why_now": "All earlier story proof is present; this final image gives it a calm, memorable finish.",
            "execution_guidance": "Manually hold the closing frame or make a restrained pull-away while maintaining safe separation.",
            "safety_notes": "The pilot checks the full operating environment and does not use this as an autonomous flight instruction.",
        },
        {
            "beat_id": "confidence",
            "title": "Quiet pull-away",
            "story_purpose": "Leave the audience with a destination that feels established and enduring.",
            "visual_objective": "Pull back just enough to restore the mountain scale without losing the lodge.",
            "why_now": "A gentle release provides closure after the activity and warmth of renewal.",
            "execution_guidance": "Manually pull away at a measured pace, keeping the lodge legible until the final frame.",
            "safety_notes": "The pilot checks the retreat path, terrain, weather, battery, and people before capture.",
        },
    ],
}


class DeterministicDemoProvider:
    def seed(self, app_state: AppState) -> list[ShotRecommendation]:
        story = load_story_fixture()
        coverage, contribution = load_initial_shot()
        app_state.set_provenance(DEMO_PROVENANCE, "synthetic")
        app_state.load_story(
            story,
            initial_coverage=coverage,
            current_shot_contribution=contribution,
            provenance=DEMO_PROVENANCE,
        )
        return self.publish_current(app_state)

    def publish_current(self, app_state: AppState) -> list[ShotRecommendation]:
        context, _ = app_state.story_context()
        if context is None or context["active_beat"] is None:
            return []
        beat_id = context["active_beat"]["beat_id"]
        copy = _RECOMMENDATION_COPY.get(beat_id, _RECOMMENDATION_COPY["confidence"])
        inputs = [ShotRecommendationInput(**item) for item in copy]
        observation_id = context["current_shot_contribution"].get(
            "observation_id", f"deterministic-observation-{beat_id}"
        )
        return app_state.publish_recommendations(
            inputs,
            observation_id=observation_id,
            provenance=DEMO_PROVENANCE,
        )
