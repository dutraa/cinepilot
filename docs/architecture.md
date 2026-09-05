# CinePilot Cinematic Tweak Engine Architecture

## Product boundary

CinePilot watches a live or prerecorded video source against a creator-provided shot intent. Gemini returns one to three prioritized cinematic tweaks. The creator decides whether each tweak is accepted, acted, or dismissed.

The system is advisory. It does not control a drone, edit footage, or claim that a recommendation was executed unless the creator marks it acted.

## Source of truth

- `schemas.py`: validated domain contracts.
- `state.py`: active run state and lifecycle rules.
- `event_log.py`: append-only evidence events for the current local run.
- `director_agent.py`: Gemini session and context synchronization.
- `templates/index.html`: rendering and user actions only; never canonical state.
- Grafana: optional observability sink, never the source of truth.

## Data flow

```text
drone camera -> DJI Fly/Pilot or bridge -> RTMP/RTSP server
  -> VideoStreamManager (status machine + provenance)
  -> DirectorAgent fresh-frame sample (stale frames withheld)
  -> Gemini Live session
  -> publish_cinematic_critique tool
  -> Pydantic validation
  -> AppState publication and deduplication
  -> EventLog / Grafana
  -> SSE and /api/state (merged with live source snapshot)
  -> critique UI -> creator decision -> creator marks capture completed
```

## Source status machine

`VideoStreamManager` tracks real sources (rtmp, rtsp, webcam, file) through
an explicit status machine exposed on `/health`, `/api/state`, and SSE:

```text
connecting -> live -> stale -> disconnected -> reconnecting -> ...
                                 -> fallback (only when explicitly allowed)
stopped (terminal)
```

Each snapshot carries requested vs. active source, protocol, a redacted
stream URL (credentials and query strings are never logged or exposed),
frame age, measured FPS, frame counters, reconnect count, fallback flag, and
the failure reason. On disconnect the last frame is dropped so stale imagery
is never presented as current; reconnects use exponential backoff. Synthetic
fallback for a real source requires explicit opt-in
(`--allow-synthetic-fallback`, `--demo-mode`, or `ALLOW_SYNTHETIC_FALLBACK`);
otherwise a real-drone failure stays visible and fails safely.

## Advisory-only boundary

CinePilot never controls the drone. There are no flight commands, waypoint
or gimbal APIs, takeoff/landing calls, or SDK control paths anywhere in the
system, and the Gemini system prompt states the model must not generate
them or certify that any route is safe. The model cannot mark a shot
COMPLETED — only the creator can, via `POST /api/shots/{shot_id}`, after
manually flying and capturing the shot.

Intent flows in the opposite direction:

```text
Intent form
  -> POST /api/intent
  -> validated AppState intent_version
  -> DirectorAgent detects version change
  -> Gemini text context update
```

## Contracts

`CinematicIntent` contains shot name, creative goal, subject, desired feel, camera movement, and up to five constraints.

`CinematicCritiqueInput` contains a summary and one to three `CinematicTweakInput` records. Each tweak contains category, diagnosis, recommendation, rationale, priority, and optional spoken cue.

Server-owned critique fields are critique ID, tweak ID, observation ID, timestamp, prompt version, and intent version.

## Failure behavior

- Gemini disconnect: preserve the current intent and resend it after reconnect.
- Invalid model payload: record a rejection and leave canonical critique state unchanged.
- Malformed or unknown tool call: count it, log it with `gemini` provenance, keep the agent running.
- Duplicate critique: suppress within the configured cooldown window.
- Duplicate action: return the existing status without incrementing counters.
- Invalid action transition: return HTTP 409.
- Unknown critique or tweak: return HTTP 404.
- Event-log failure: log the failure but keep the live director running.
- Real source failure: report `disconnected`/`reconnecting`, drop the stale frame, stop feeding Gemini, retry with backoff. Synthetic fallback only on explicit opt-in, and always labeled `fallback` / `synthetic-fallback`.
- Stale frames: never sent to Gemini as current observations (`frames_skipped_stale` counts them) and never rendered as the current monitor view.

## Deliberate simplifications

State is session-local and history is capped. The JSONL event log is sufficient for the first evidence run; a database is deferred until multiple users or persistent projects exist.
