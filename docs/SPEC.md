# CinePilot Reference Specification

This file contains reference detail for implementation. `AGENTS.md` contains behavioral instructions; `docs/evidence-frame.md` governs claims and evaluation.

## Runtime contract

- Python 3.10+.
- FastAPI serves the browser and JSON/SSE interfaces.
- Gemini Live is optional at startup and required only for live AI reasoning.
- Session state is in memory; evidence is appended to `EVENT_LOG_PATH` as JSONL.
- Video source values are `synthetic`, `rtmp`, `rtsp`, `webcam`, or `file`.
- The application is advisory-only. No route or tool may issue drone-control commands.

## Current domain contracts

The canonical Pydantic definitions are in `schemas.py`.

### `CinematicIntent`

| Field | Type | Rule |
| --- | --- | --- |
| `shot_name` | string | 1–120 chars |
| `creative_goal` | string | 1–500 chars |
| `subject` | string | 1–200 chars |
| `desired_feel` | string | max 160 chars |
| `camera_move` | string | max 120 chars |
| `constraints` | string[] | max 5 items, 1–160 chars each |

### `CinematicCritiqueInput`

Contains a summary and one to three `CinematicTweakInput` records. Each tweak has a category, diagnosis, recommendation, rationale, priority, optional confidence, and optional spoken cue.

### Server-owned `CinematicCritique`

Adds `critique_id`, `tweak_id`, `observation_id`, `created_at`, `intent_version`, `prompt_version`, and server-managed tweak status. Gemini cannot provide or override those fields.

### Tweak lifecycle

```text
PROPOSED -> ACCEPTED -> ACTED
PROPOSED -> DISMISSED
ACCEPTED -> DISMISSED
```

Repeated decisions are idempotent. Invalid transitions return a conflict at the HTTP layer.

## Current HTTP API

### `GET /api/state`

Returns the validated session snapshot: current intent and version, latest critique, bounded critique history, tweak action records, legacy shot list/guidance, metrics, and state version.

### `POST /api/intent`

Accepts a strict `CinematicIntent` JSON body. A semantically changed intent increments `intent_version`; a repeat does not. The live agent synchronizes the new version with Gemini.

### `POST /api/critiques/{critique_id}/tweaks/{tweak_id}/decision`

Accepts `{ "decision": "accepted" | "acted" | "dismissed" }`. Returns the resulting server-owned status. Unknown records return 404; invalid transitions return 409.

### `GET /events`

Returns an SSE stream containing the same state snapshot shape as `/api/state`. The browser treats events as state replacement, not as an append-only UI command log.

### `GET /video_feed`

Returns an MJPEG stream. The synthetic source is valid for shell/demo verification but must be labeled synthetic in evidence.

### `GET /health`

Returns source provenance, Gemini status, Grafana status, and frames sent.

## Next story-aware contracts

The next-shot demo should add these models without weakening current contracts:

- `StoryBrief`: seeded story metadata, emotional arc, must-show items, constraints, and ordered beats.
- `StoryBeat`: story job, required visual proof, and server-managed coverage status.
- `ShotRecommendation`: story purpose, visual objective, why-now explanation, manual execution guidance, safety notes, priority, confidence, and server-managed status.

The exact field names and limits must be introduced with tests and documented in an ADR or this section in the same commit. Model-provided IDs and statuses remain forbidden.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | empty | Enables live Gemini reasoning |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini Live model |
| `RTMP_URL` | local RTMP URL | Default RTMP/RTSP input |
| `GRAFANA_URL` | empty | Optional Loki endpoint |
| `GRAFANA_USER` | empty | Loki tenant/user |
| `GRAFANA_API_KEY` | empty | Loki token |
| `FRAME_INTERVAL_SEC` | `0.8` | Frame sampling interval |
| `CRITIQUE_COOLDOWN_SEC` | `5.0` | Duplicate critique suppression window |
| `EVENT_LOG_PATH` | `runs/cinepilot-events.jsonl` | Local append-only evidence log |
| `HOST` | `127.0.0.1` | Server bind host |
| `PORT` | `8000` | Server port |

## Error and fallback rules

- Invalid model output is recorded and cannot mutate canonical state.
- Gemini reconnects with the current intent context.
- A dropped source falls back to synthetic video and exposes provenance.
- Event-log failures are logged but do not stop the live loop.
- Missing Gemini credentials leave the shell usable and report a visible disconnected state.
- No safety-critical flight advice is presented as an automated command or guarantee.

