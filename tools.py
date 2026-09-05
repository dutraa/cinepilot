"""Gemini Live tool declarations and in-process execution logic for CinePilot.

This module is intentionally free of imports from `server.py` to avoid
circular dependencies: the execution functions accept the shared application
state object and mutate it through its public methods.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from google.genai import types
from pydantic import ValidationError

from director_prompt import PROMPT_VERSION
from domain import (
    ALLOWED_PRIORITIES,
    ALLOWED_SHOT_IDS,
    ALLOWED_STATUSES,
)
from schemas import CinematicCritique, CinematicCritiqueInput

logger = logging.getLogger("cinepilot.tools")

# ---------------------------------------------------------------------------
# Shot list domain model
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Gemini tool schemas
# ---------------------------------------------------------------------------

CRITIQUE_SCHEMA = types.FunctionDeclaration(
    name="publish_cinematic_critique",
    description=(
        "Publish the one to three highest-impact cinematic tweaks for the "
        "creator's stated shot intent. Never use vague advice."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "summary": types.Schema(
                type=types.Type.STRING,
                description="One concise assessment of the current shot.",
            ),
            "tweaks": types.Schema(
                type=types.Type.ARRAY,
                min_items=1,
                max_items=3,
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "category": types.Schema(
                            type=types.Type.STRING,
                            enum=[
                                "composition",
                                "camera_movement",
                                "perspective",
                                "lighting",
                                "subject",
                                "pacing",
                                "continuity",
                            ],
                        ),
                        "diagnosis": types.Schema(type=types.Type.STRING),
                        "recommendation": types.Schema(type=types.Type.STRING),
                        "rationale": types.Schema(type=types.Type.STRING),
                        "priority": types.Schema(
                            type=types.Type.STRING,
                            enum=list(ALLOWED_PRIORITIES),
                        ),
                        "confidence": types.Schema(type=types.Type.NUMBER),
                        "spoken_cue": types.Schema(type=types.Type.STRING),
                        "safety_note": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "What the human pilot must verify themselves "
                                "before acting (obstacles, altitude, people)."
                            ),
                        ),
                    },
                    required=[
                        "category",
                        "diagnosis",
                        "recommendation",
                        "rationale",
                        "priority",
                    ],
                ),
            ),
        },
        required=["summary", "tweaks"],
    ),
)

"""Shot statuses Gemini may set. COMPLETED is creator-only: only the human
who flew and captured the shot can mark it complete (via /api/shots)."""
MODEL_ALLOWED_SHOT_STATUSES = tuple(
    status for status in ALLOWED_STATUSES if status != "COMPLETED"
)

SHOT_LIST_SCHEMA = types.FunctionDeclaration(
    name="update_shot_list",
    description=(
        "Update the status and directorial feedback for one shot in the 5-part "
        "aerial shot list. Call this when a shot is being attempted "
        "(IN_PROGRESS) or must be re-flown (REJECTED). Only the creator can "
        "mark a shot COMPLETED after flying and capturing it."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "shot_id": types.Schema(
                type=types.Type.STRING,
                description="Identifier of the shot being updated.",
                enum=ALLOWED_SHOT_IDS,
            ),
            "status": types.Schema(
                type=types.Type.STRING,
                description="New status for the shot.",
                enum=list(MODEL_ALLOWED_SHOT_STATUSES),
            ),
            "feedback": types.Schema(
                type=types.Type.STRING,
                description=(
                    "Direct directorial reasoning for the status change, e.g. "
                    "'Horizon is level and the subject sits on the right third; "
                    "this take is a keeper.'"
                ),
            ),
        },
        required=["shot_id", "status", "feedback"],
    ),
)

SPEAK_GUIDANCE_SCHEMA = types.FunctionDeclaration(
    name="speak_director_guidance",
    description=(
        "Issue a short, direct, spoken flight cue to the drone pilot. Use for "
        "real-time corrections of framing, tilt, altitude, speed, or lighting. "
        "Keep instructions concise and actionable."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "instruction": types.Schema(
                type=types.Type.STRING,
                description=(
                    "The spoken cue for the pilot, e.g. 'Tilt down 15 degrees, "
                    "subject is drifting off-center'."
                ),
            ),
            "priority": types.Schema(
                type=types.Type.STRING,
                description="Urgency of the cue.",
                enum=ALLOWED_PRIORITIES,
            ),
        },
        required=["instruction", "priority"],
    ),
)

DIRECTOR_TOOLS = [
    types.Tool(
        function_declarations=[
            CRITIQUE_SCHEMA,
            SHOT_LIST_SCHEMA,
            SPEAK_GUIDANCE_SCHEMA,
        ]
    )
]

# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_malformed(app_state: Any, tool_name: str, reason: str) -> None:
    if hasattr(app_state, "record_malformed_tool_call"):
        app_state.record_malformed_tool_call(tool_name, reason)


def execute_update_shot_list(app_state: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and apply an `update_shot_list` call against the app state."""
    shot_id = str(args.get("shot_id", "")).strip()
    status = str(args.get("status", "")).strip().upper()
    feedback = str(args.get("feedback", "")).strip()

    if shot_id not in ALLOWED_SHOT_IDS:
        _record_malformed(app_state, "update_shot_list", "unknown_shot_id")
        return {
            "ok": False,
            "error": f"Unknown shot_id '{shot_id}'. Allowed: {ALLOWED_SHOT_IDS}",
        }
    if status not in MODEL_ALLOWED_SHOT_STATUSES:
        if status == "COMPLETED":
            _record_malformed(
                app_state, "update_shot_list", "model_attempted_completion"
            )
            return {
                "ok": False,
                "error": (
                    "Only the creator can mark a shot COMPLETED after they "
                    "have flown and captured it. You may set IN_PROGRESS or "
                    "REJECTED with feedback."
                ),
            }
        _record_malformed(app_state, "update_shot_list", "invalid_status")
        return {
            "ok": False,
            "error": (
                f"Invalid status '{status}'. Allowed: {MODEL_ALLOWED_SHOT_STATUSES}"
            ),
        }

    app_state.update_shot(shot_id, status, feedback, actor="model")
    logger.info("Shot list updated: %s -> %s (%s)", shot_id, status, feedback)
    return {
        "ok": True,
        "shot_id": shot_id,
        "status": status,
        "feedback": feedback,
        "timestamp": _utc_now_iso(),
    }


def execute_speak_director_guidance(
    app_state: Any, args: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate and apply a `speak_director_guidance` call against the app state."""
    instruction = str(args.get("instruction", "")).strip()
    priority = str(args.get("priority", "INFO")).strip().upper()

    if not instruction:
        return {"ok": False, "error": "instruction must be a non-empty string"}
    if priority not in ALLOWED_PRIORITIES:
        priority = "INFO"

    timestamp = _utc_now_iso()
    app_state.set_guidance(instruction, priority, timestamp)
    logger.info("Director guidance [%s]: %s", priority, instruction)
    return {
        "ok": True,
        "instruction": instruction,
        "priority": priority,
        "timestamp": timestamp,
    }


def execute_publish_cinematic_critique(
    app_state: Any,
    args: Dict[str, Any],
    observation_id: str = "unknown-observation",
) -> Dict[str, Any]:
    """Validate and publish a structured critique from Gemini."""
    try:
        parsed = CinematicCritiqueInput.model_validate(args)
    except ValidationError as exc:
        if hasattr(app_state, "record_invalid_critique"):
            app_state.record_invalid_critique("schema_validation_failed")
        return {"ok": False, "error": "Invalid critique schema", "details": exc.errors()}

    intent, intent_version = app_state.intent_context()
    if intent is None:
        if hasattr(app_state, "record_invalid_critique"):
            app_state.record_invalid_critique("intent_not_set")
        return {"ok": False, "error": "Set a shot intent before publishing a critique"}

    critique = CinematicCritique(
        critique_id=str(uuid4()),
        observation_id=observation_id,
        created_at=_utc_now_iso(),
        intent_version=intent_version,
        prompt_version=PROMPT_VERSION,
        intent=intent,
        summary=parsed.summary,
        tweaks=[
            {
                **tweak.model_dump(mode="json"),
                "tweak_id": str(uuid4()),
            }
            for tweak in parsed.tweaks
        ],
    )
    published = app_state.publish_critique(critique)
    return {
        "ok": True,
        "critique_id": critique.critique_id,
        "tweak_ids": [tweak.tweak_id for tweak in critique.tweaks],
        "suppressed": not published,
        "timestamp": critique.created_at,
    }


TOOL_EXECUTORS = {
    "publish_cinematic_critique": execute_publish_cinematic_critique,
    "update_shot_list": execute_update_shot_list,
    "speak_director_guidance": execute_speak_director_guidance,
}


def execute_tool(
    app_state: Any,
    name: str,
    args: Dict[str, Any],
    observation_id: str = "unknown-observation",
) -> Dict[str, Any]:
    """Dispatch a Gemini tool call by name. Always returns a clean dict."""
    executor = TOOL_EXECUTORS.get(name)
    if executor is None:
        logger.warning("Gemini requested unknown tool: %s", name)
        _record_malformed(app_state, name, "unknown_tool")
        return {"ok": False, "error": f"Unknown tool '{name}'"}
    try:
        if name == "publish_cinematic_critique":
            return executor(app_state, args or {}, observation_id=observation_id)
        return executor(app_state, args or {})
    except Exception as exc:  # noqa: BLE001 - tool results must never raise upstream
        logger.exception("Tool execution failed for %s", name)
        _record_malformed(app_state, name, "execution_error")
        return {"ok": False, "error": f"Tool execution failed: {exc}"}
