# CinePilot Cinematic Tweak Engine Architecture

## Product boundary

CinePilot watches a live or prerecorded video source against a creator-provided story and shot intent. Gemini returns one to three prioritized cinematic tweaks for the current shot and, in the planned next slice, recommendations for missing story coverage. The creator decides whether a recommendation is selected, acted, completed, or dismissed.

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
VideoStreamManager
  -> DirectorAgent frame sample
  -> Gemini Live session
  -> publish_cinematic_critique tool
  -> Pydantic validation
  -> AppState publication and deduplication
  -> EventLog / Grafana
  -> SSE and /api/state
  -> critique and coverage UI
```

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

The next story-aware slice adds `StoryBrief`, `StoryBeat`, and `ShotRecommendation`. A recommendation must include the story purpose, visual objective, why-now explanation, manual execution guidance, and safety notes. Story and recommendation status are server-owned. See `docs/SPEC.md` for the reference contract and `docs/decisions/ADR-001-story-aware-demo-boundary.md` for the boundary decision.

## Failure behavior

- Gemini disconnect: preserve the current intent and resend it after reconnect.
- Invalid model payload: record a rejection and leave canonical critique state unchanged.
- Duplicate critique: suppress within the configured cooldown window.
- Duplicate action: return the existing status without incrementing counters.
- Invalid action transition: return HTTP 409.
- Unknown critique or tweak: return HTTP 404.
- Event-log failure: log the failure but keep the live director running.
- Source failure: retain the existing synthetic fallback, but expose the active source visibly.

## Deliberate simplifications

State is session-local and history is capped. The JSONL event log is sufficient for the first evidence run; a database is deferred until multiple users or persistent projects exist.

The first story demo uses one `DirectorAgent`, one seeded story, three to five beats, and manual creator selection. Specialist agents, autonomous flight, screenplay parsing, and editing integrations remain out of scope until recommendation usefulness is evidenced.
