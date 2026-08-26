"""Gemini Live tool declarations and in-process execution logic for CinePilot.

This module is intentionally free of imports from `server.py` to avoid
circular dependencies: the execution functions accept the shared application
state object and mutate it through its public methods.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from google.genai import types

logger = logging.getLogger("cinepilot.tools")

# ---------------------------------------------------------------------------
# Shot list domain model
# ---------------------------------------------------------------------------

ALLOWED_SHOT_IDS = [
    "establishing_wide",
    "topdown_property",
    "orbit_pass",
    "low_reveal",
    "pull_away",
]

ALLOWED_STATUSES = ["PENDING", "IN_PROGRESS", "COMPLETED", "REJECTED"]

ALLOWED_PRIORITIES = ["INFO", "WARNING", "URGENT"]

# Human-readable titles for the Director's Monitor UI.
SHOT_DEFINITIONS: Dict[str, str] = {
    "establishing_wide": "Establishing Wide",
    "topdown_property": "Top-Down Property",
    "orbit_pass": "Orbit Pass",
    "low_reveal": "Low Reveal",
    "pull_away": "Pull Away",
}

# ---------------------------------------------------------------------------
# Gemini tool schemas
# ---------------------------------------------------------------------------

SHOT_LIST_SCHEMA = types.FunctionDeclaration(
    name="update_shot_list",
    description=(
        "Update the status and directorial feedback for one shot in the 5-part "
        "aerial shot list. Call this whenever a shot is being attempted, has "
        "been captured well (COMPLETED), or must be re-flown (REJECTED)."
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
                enum=ALLOWED_STATUSES,
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
    types.Tool(function_declarations=[SHOT_LIST_SCHEMA, SPEAK_GUIDANCE_SCHEMA])
]

# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def execute_update_shot_list(app_state: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and apply an `update_shot_list` call against the app state."""
    shot_id = str(args.get("shot_id", "")).strip()
    status = str(args.get("status", "")).strip().upper()
    feedback = str(args.get("feedback", "")).strip()

    if shot_id not in ALLOWED_SHOT_IDS:
        return {
            "ok": False,
            "error": f"Unknown shot_id '{shot_id}'. Allowed: {ALLOWED_SHOT_IDS}",
        }
    if status not in ALLOWED_STATUSES:
        return {
            "ok": False,
            "error": f"Invalid status '{status}'. Allowed: {ALLOWED_STATUSES}",
        }

    app_state.update_shot(shot_id, status, feedback)
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


TOOL_EXECUTORS = {
    "update_shot_list": execute_update_shot_list,
    "speak_director_guidance": execute_speak_director_guidance,
}


def execute_tool(app_state: Any, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a Gemini tool call by name. Always returns a clean dict."""
    executor = TOOL_EXECUTORS.get(name)
    if executor is None:
        logger.warning("Gemini requested unknown tool: %s", name)
        return {"ok": False, "error": f"Unknown tool '{name}'"}
    try:
        return executor(app_state, args or {})
    except Exception as exc:  # noqa: BLE001 - tool results must never raise upstream
        logger.exception("Tool execution failed for %s", name)
        return {"ok": False, "error": f"Tool execution failed: {exc}"}
