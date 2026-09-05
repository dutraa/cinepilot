# CinePilot Cinematic Tweak Engine Architecture

## Product boundary

CinePilot watches a live, prerecorded, or synthetic video source against a creator-provided story and shot intent. Gemini or the explicit deterministic provider returns one to three prioritized cinematic tweaks or recommendations for missing story coverage. The creator decides whether a recommendation is selected, completed, or dismissed.

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
  -> Gemini Live session or deterministic demo provider
  -> validated critique/recommendation tool
  -> Pydantic validation
  -> AppState publication, story coverage, visualization jobs, and deduplication
  -> EventLog / Grafana
  -> SSE and /api/state (merged with live source snapshot)
  -> critique and coverage UI -> creator decision -> creator marks capture completed
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

Story context follows the same versioned synchronization boundary. The agent
sends the story brief, active beat, covered and missing beats, current-shot
contribution, and previous creator decisions on connection and when the story
context version changes. The deterministic provider uses the same validated
publication method and cannot bypass the state machine.

## Contracts

`CinematicIntent` contains shot name, creative goal, subject, desired feel, camera movement, and up to five constraints.

`CinematicCritiqueInput` contains a summary and one to three `CinematicTweakInput` records. Each tweak contains category, diagnosis, recommendation, rationale, priority, and optional spoken cue.

Server-owned critique fields are critique ID, tweak ID, observation ID, timestamp, prompt version, and intent version.

The story-aware slice adds `StoryBrief`, `StoryBeat`, `ShotCoverage`, and `ShotRecommendation`. A recommendation must include the story purpose, visual objective, why-now explanation, manual execution guidance, and safety notes. Story and recommendation status are server-owned. See `docs/SPEC.md` for the reference contract and `docs/decisions/ADR-001-story-aware-demo-boundary.md` for the boundary decision.

The Visualize slice adds strict `VisualizationRequestInput`,
`VisualizationJobStatus`, `VisualizationQualityStatus`,
`VisualizationSourceKind`, `AnimationProfile`, `AnimationProfileSpec`,
`VisualizationPreview`, and `VisualizationJob` contracts. A single in-process
worker captures one decodeable, session-local observation snapshot and produces
exactly three browser-playable 10-second animations over that JPEG. The
deterministic renderer implements the provider-neutral `VisualizationRenderer`
boundary; provider output must pass the same validation before it can become
ready state. The server owns every job, observation hash, preview, timestamp,
status, recommendation link, version, source label, and provenance. The preview
attaches to an existing recommendation; it does not introduce a second
decision state machine.

## Failure behavior

- Gemini disconnect: preserve the current intent and resend it after reconnect.
- Invalid model payload: record a rejection and leave canonical critique state unchanged.
- Malformed or unknown tool call: count it, log it with `gemini` provenance, keep the agent running.
- Invalid story recommendation payload: record a rejection and leave canonical story coverage unchanged.
- Duplicate critique: suppress within the configured cooldown window.
- Duplicate action: return the existing status without incrementing counters.
- Invalid action transition: return HTTP 409.
- Unknown critique or tweak: return HTTP 404.
- Unknown story beat or recommendation: return HTTP 404; illegal story or recommendation transitions return HTTP 409.
- Event-log failure: log the failure but keep the live director running.
- Real source failure: report `disconnected`/`reconnecting`, drop the stale frame, stop feeding Gemini, retry with backoff. Synthetic fallback only on explicit opt-in, and always labeled `fallback` / `synthetic-fallback`.
- Stale frames: never sent to Gemini as current observations (`frames_skipped_stale` counts them) and never rendered as the current monitor view.
- Visualization renderer failure: mark only the job failed, remove its temporary source frame, and leave story, recommendation, and coverage state unchanged; a retry reuses the failed job ID and is still bounded by the one-worker rule.
- Visualization selection: reuse recommendation transitions; selection exposes a manual capture brief but never marks capture, coverage, or quality improvement.

## Deliberate simplifications

State is session-local and history is capped. The JSONL event log is sufficient for the first evidence run; a database is deferred until multiple users or persistent projects exist.

The first story demo uses one `DirectorAgent`, one seeded story, five beats, a deterministic provider, and manual creator selection. Specialist agents, autonomous flight, screenplay parsing, and editing integrations remain out of scope until recommendation usefulness is evidenced.

Visualization persistence, galleries, live video generation, 3D reconstruction,
and autonomous drone behavior remain out of scope for the deterministic release.
