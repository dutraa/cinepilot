# CinePilot Reference Specification

This file contains reference detail for implementation. `AGENTS.md` contains behavioral instructions; `docs/evidence-frame.md` governs claims and evaluation.

## Runtime contract

- Python 3.10+.
- FastAPI serves the browser and JSON/SSE interfaces.
- Gemini is optional at startup. The primary workflow calls it only after an
  explicit between-takes analysis request; the legacy continuous Gemini Live
  path is disabled unless explicitly enabled for compatibility experiments.
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

## Story-aware contracts

The story-aware demo adds these models without weakening current contracts:

- `StoryBrief`: seeded story metadata, emotional arc, must-show items, constraints, and ordered beats.
- `StoryBeat`: story job, required visual proof, and server-managed coverage status.
- `ShotRecommendation`: story purpose, visual objective, why-now explanation, manual execution guidance, safety notes, priority, confidence, and server-managed status.

The exact field names and limits must be introduced with tests and documented in an ADR or this section in the same commit. Model-provided IDs and statuses remain forbidden.

### Primary live coverage contracts

`StoryContextInput` is the creator-entered story form. It accepts story
metadata, ordered beat inputs, an active beat index, and current shot intent;
the server assigns the story ID, beat IDs, and versions. A story or intent
loaded only by demo seeding is not sufficient for the primary live path.

`ConsentState` is session-scoped and starts absent. `POST /api/consent` records
the creator's explicit decision. No cloud analysis request is accepted without
granted consent.

`ObservationBurst` contains a server-owned observation ID, job ID, story and
intent versions, source requested/active values, source provenance, freshness
limit, timestamps, and three to eight frame metadata records. Raw bytes are
not written to the event log or retained after the bounded analysis worker
ends. Only frames within `SOURCE_MAX_FRAME_AGE_SEC` are eligible. A follow-up
evaluation must have a different observation ID.

`AnalysisJob` uses `requested -> capturing -> analyzing -> ready` with terminal
`failed`, `timed_out`, or `cancelled` states. A job is accepted only when the
story, active beat, intent, consent, and current source are ready. One job
performs at most one bounded Gemini multimodal request. Duplicate active
requests return `409`; failed jobs may be retried explicitly.

`TakeAnalysisResult` separates `observed`, `not_established`, and
`missing_coverage`, then requires exactly three strict recommendation inputs.
The server adds IDs, ranking, role, observation reference, timestamp, and
provenance, enforcing one primary at rank 1 and two alternatives at ranks 2
and 3. Generic or unsafe control-like advice is rejected without mutation.

The creator workflow uses separate records and routes:

| Action | Route | Meaning |
| --- | --- | --- |
| Select/dismiss | `POST /api/take-recommendations/{id}/decision` | Creator decision only |
| Mark captured | `POST /api/take-recommendations/{id}/capture` | Creator says the manual take was captured |
| Evaluate | `POST /api/captures/{id}/evaluate` | Starts a new fresh observation and model evaluation |

Selection creates a manual capture brief. Capture does not create observed
proof or mark a beat covered. Evaluation returns `addressed`,
`not_addressed`, `unclear`, or `insufficient_evidence`; it is model judgment,
not independent usefulness review or proof that production quality improved.

`ShotRecommendationInput` is the untrusted Gemini/browser shape. It accepts no
recommendation ID, timestamp, status, intent version, or prompt version. The
server adds those fields when it publishes a validated batch of two or three
recommendations. Supported cinematic categories include composition, camera
angle and movement, lens feel, lighting, pacing, subject placement, continuity,
and expression.

The seeded fixture is `fixtures/story.json`. Explicit deterministic demo mode
loads it and publishes repeatable recommendations through the same state,
event-log, API, SSE, and dashboard paths as live Gemini:

```text
python main.py --source synthetic --demo-mode
```

Story beats use `pending -> active -> covered` or `active -> skipped`.
The legacy recommendation path retains `suggested -> selected -> completed`
for backward compatibility, but completion cannot cover an unrelated active
beat. The primary live path uses `recommended -> selected -> acted`, with the
creator capture record and follow-up evaluation separate from coverage
completion.

## Previsualization contracts and API

The previsualization slice accepts only
`{"duration_seconds": <4|6|8|10>, "variation_count": 3}`. The server decodes
and freezes the latest available frame, or the seeded synthetic scene when
deterministic demo mode has no live frame, and creates one session-local job
with status `requested -> rendering -> ready|failed`. A repeated fingerprint
returns the existing job; an invalid observation or a different observation
while a job is active returns `409`. The fingerprint includes the active
renderer identity, so switching provider or model never reuses another
renderer's artifacts.

Each ready job contains exactly three previews linked one-to-one with existing
`ShotRecommendation` records. The fixed concept profiles remain
`descending_reveal`, `lateral_parallax`, and `restrained_pull_away`. A preview
is one of two render kinds, and the two are never conflated:

- `deterministic_animation` — a browser animation over the frozen JPEG, exactly
  10 seconds, with a server-fixed `profile_spec` and no generated media. It
  invents no pixels and needs no credentials.
- `generated_video` — a provider-generated clip, served as its own media
  artifact, with no `profile_spec`. The profile name only labels the intended
  visual concept.

Neither kind is executable camera or flight instruction.

### Duration reconciliation

`duration_seconds` on the request is what the creator *asks for*. The job
carries both `requested_duration_seconds` and the delivered `duration_seconds`,
plus a plain-text `duration_note` whenever they differ. The deterministic
renderer delivers exactly 10 seconds. Current Google video models deliver 4-,
6-, or 8-second clips (`GOOGLE_VIDEO_DURATION_SEC`, default 8). A 10-second
request against a Google renderer therefore produces 8-second previews, and
every preview, the job, the event ledger, and the dashboard all report 8
seconds with the note stating it is not 10. A shorter clip is never relabeled.

### Untrusted provider output

Provider media is untrusted until the server has written it to a session-local
temporary file and validated: response structure, declared MIME type against
the browser-playable set (`video/mp4`, `video/webm`), file existence, maximum
file size (`GOOGLE_VIDEO_MAX_BYTES`), container magic bytes, decodability,
dimensions, frame count, and playable duration within tolerance. Renderer
output is then validated as a set: exactly three unique previews, one-to-one
recommendation linkage, fixed profiles, job linkage, retained source frame,
matching render kind, honest duration, consistent provider/model provenance,
matching source-frame hash, and, for generated clips, that the referenced media
file still exists. Anything that fails marks only the job failed.

### Routes

`POST /api/visualizations`, `GET /api/visualizations`,
`GET /api/visualizations/{job_id}`,
`GET /api/visualizations/{job_id}/source-frame`, and
`GET /api/visualizations/{job_id}/previews/{preview_id}/media`. The last route
is new: a generated preview is a separate per-preview video artifact, which the
shared frozen-JPEG route cannot serve. It returns `404` for an unknown job or
preview and `409` when a preview has no generated media (every deterministic
preview, and any preview whose artifact has been dropped).

Visualization jobs and linked preview statuses are included in `/api/state` and
`/events`. Unknown fields, client-owned IDs/statuses/timestamps/assets, invalid
payloads, unknown jobs, and conflicting observations are rejected at the API
boundary with `422`, `404`, or `409` as appropriate. A failed job may be retried
with the same request and job fingerprint; the server reuses the job ID,
increments `retry_count`, drops the failed attempt's media, and renders again.

The provider call never happens inside an HTTP request path. One in-process
worker with `max_workers=1` owns every render, so the request path returns
`requested` while generation is still running.

### Renderer selection

The deterministic renderer is the default and the test double. The Google
renderer is used only when `VISUALIZATION_PROVIDER=google` **and**
`ENABLE_GENERATED_PREVISUALIZATION=true` **and** a key is configured
(`GOOGLE_VIDEO_API_KEY`, falling back to `GEMINI_API_KEY`). Otherwise the
application continues on the deterministic renderer and labels it
`provider: deterministic`, `model: none`. Deterministic output is never
presented as Google output. No test requires a live key.

The existing recommendation decision route is the only selection lifecycle; at
most one preview in a job may be selected at once. Selecting a preview exposes
the manual capture brief but does not complete coverage, mark the shot
captured, or prove that a resulting shot improved.

## Story-aware API

`GET /api/story`, `POST /api/story/beat`, `GET /api/coverage`,
`GET /api/recommendations`, `POST /api/recommendations`, and
`POST /api/recommendations/{id}/decision` expose the canonical story loop.
Unknown IDs return 404, invalid transitions return 409, invalid payloads return
422, and safe repeats return 200. `/api/state` and `/events` include the same
story, coverage, recommendation, and provenance fields.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | empty | Enables live Gemini reasoning |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Bounded Gemini model |
| `VISUALIZATION_PROVIDER` | `deterministic` | `deterministic` or `google` |
| `ENABLE_GENERATED_PREVISUALIZATION` | `false` | Explicit opt-in for provider-backed previsualization |
| `GOOGLE_VIDEO_API_KEY` | empty | Falls back to `GEMINI_API_KEY` |
| `GOOGLE_VIDEO_BACKEND` | `interactions` | `interactions` (Gemini Omni Flash) or `veo` (Veo 3.1) |
| `GOOGLE_VIDEO_MODEL` | `gemini-omni-1.1-flash` | Generation model |
| `GOOGLE_VIDEO_TIMEOUT_SEC` | `180.0` | Maximum time for one generation request |
| `GOOGLE_VIDEO_MAX_BYTES` | `33554432` | Hard ceiling for one generated clip |
| `GOOGLE_VIDEO_DURATION_SEC` | `8` | Provider clip length; reconciled, never relabeled |
| `GOOGLE_VIDEO_RESOLUTION` | `720p` | Requested output resolution |
| `GOOGLE_VIDEO_ASPECT_RATIO` | `16:9` | Requested output aspect ratio |
| `ENABLE_CONTINUOUS_LIVE` | `false` | Explicit opt-in for legacy continuous Gemini Live |
| `ANALYSIS_TIMEOUT_SEC` | `30.0` | Maximum time for one bounded provider request |
| `RTMP_URL` | local RTMP URL | Default RTMP/RTSP input |
| `GRAFANA_URL` | empty | Optional Loki endpoint |
| `GRAFANA_USER` | empty | Loki tenant/user |
| `GRAFANA_API_KEY` | empty | Loki token |
| `FRAME_INTERVAL_SEC` | `0.8` | Legacy Live sampling interval |
| `CRITIQUE_COOLDOWN_SEC` | `5.0` | Duplicate critique suppression window |
| `EVENT_LOG_PATH` | `runs/cinepilot-events.jsonl` | Local append-only evidence log |
| `HOST` | `127.0.0.1` | Server bind host |
| `PORT` | `8000` | Server port |

## Error and fallback rules

- Invalid model output is recorded and cannot mutate canonical state.
- Gemini reconnects with the current intent context.
- A dropped real source stays disconnected/reconnecting and exposes `NO LIVE SIGNAL`; synthetic fallback requires explicit opt-in and is prominently labeled.
- A source is eligible for analysis only when status is live and the newest frame is within the shared freshness limit.
- Event-log failures are logged but do not stop the live loop.
- Missing Gemini credentials leave the shell usable and report a visible disconnected state.
- No safety-critical flight advice is presented as an automated command or guarantee.
- The Visual Reference tab is secondary to Coverage Desk. Previsualization concepts are labeled `AI previsualization — illustrative creative reference, not flight truth.` and retain deterministic, generated, and live-source provenance separately. The tab is enabled only when the current context, fresh source, consent, and three recommendations are available.
- A provider failure — timeout, malformed response, invalid MIME type, undecodable or oversized media, wrong recommendation linkage — marks only the visualization job failed. Story state, recommendations, creator decisions, and the live director loop are untouched, and the job can be retried.
- API keys and raw generated media never reach the log or the event ledger.
