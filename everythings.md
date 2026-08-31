# CinePilot: Everything in One Place

This is the compact source-of-truth index for the repository. It is intentionally practical: what CinePilot is, what exists today, what the next demo proves, where behavior lives, and what remains out of scope.

## 1. Product in one sentence

CinePilot is an advisory AI cinematic decision engine that watches a creator's footage, compares it with a story or shot intent, and recommends the highest-impact change to the current shot or the next shot to capture.

## 2. The pain we are testing

Creators often know a shot is not working but cannot turn that feeling into a precise correction. On small productions, vague feedback, missing coverage, unnecessary retakes, and the absence of an experienced cinematographer make the problem expensive.

The focused promise is not “AI flies a drone.” It is:

> CinePilot helps a creator understand what the story needs next and gives them a concrete, visually motivated way to capture it.

This is a hypothesis until creator evidence confirms that recommendations are useful, plausible, and faster than the current manual workflow.

## 3. Current product status

Implemented on `feature/cinematic-tweak-engine`:

- live, prerecorded, webcam, RTSP/RTMP, and synthetic video ingestion;
- Gemini Live frame streaming when `GEMINI_API_KEY` is configured;
- strict cinematic intent, critique, tweak, and decision schemas;
- intent versioning and context synchronization;
- critique deduplication and bounded history;
- creator action lifecycle: proposed, accepted, acted, dismissed;
- append-only JSONL event evidence;
- API and SSE state exposure;
- dashboard centered on intent and current cinematic tweaks;
- optional Grafana Loki telemetry;
- tests and local synthetic/browser smoke verification.

Not implemented yet:

- story brief and story-beat contracts;
- shot-coverage inventory;
- story-aware next-shot recommendations;
- selected/completed next-shot lifecycle;
- a seeded mock story demo that visibly closes the story loop;
- real creator baseline and held-out evidence run.

## 4. Mock demo to build next

### Mock story: “The place worth coming back to”

The film follows a remote mountain lodge reopening after a storm. The audience should move from isolation, to discovery, to warmth, and finally to confidence that the lodge is alive again.

| Beat | Story job | Visual proof |
| --- | --- | --- |
| 1. Isolation | Establish distance and vulnerability | High wide shot; lodge small in a large landscape |
| 2. Discovery | Let the audience find the lodge | Descending or forward reveal; lodge grows in frame |
| 3. Invitation | Make the place feel reachable and welcoming | Smooth approach or lateral move toward entrance |
| 4. Renewal | Show human activity and recovery | Orbit or rise revealing people, lights, or movement |
| 5. Confidence | End with scale and a resolved destination | Pull-away or elevated closing image |

The application should seed this story so the demo can run without asking the user to invent copy on stage.

### Live walkthrough

1. The director opens the seeded story and chooses the current beat.
2. The live or synthetic feed shows the current aerial shot.
3. CinePilot states what the shot currently proves and what it does not prove.
4. The agent identifies the highest-value missing beat or coverage.
5. The dashboard displays two or three possible next shots, each with story purpose, visual objective, why now, and advisory execution guidance.
6. The director selects one recommendation.
7. The pilot attempts the shot manually; CinePilot never sends a flight command.
8. The director marks the shot completed and the coverage board updates.
9. CinePilot evaluates the new result and recommends the next missing beat.

### Example recommendation

Current observation: “The high establishing wide proves that the lodge is isolated, but it does not yet create discovery or invitation.”

Possible next shots:

1. **Descending reveal** — descend slowly while moving forward so the lodge grows out of the landscape; advances Discovery.
2. **Lateral parallax pass** — move sideways with the lodge on the right third; reveals the route and creates visual depth; advances Invitation.
3. **Low approach to entrance** — lower the camera and approach at a restrained pace; makes the destination feel reachable; advances Invitation.

The recommendation must explain the story reason, not only give a mechanical command.

## 5. Proposed story-aware contracts

These are the next contracts; they are not yet implemented.

```text
StoryBrief
  story_id
  title
  logline
  emotional_arc
  visual_style
  must_show[]
  constraints[]
  beats[]

StoryBeat
  beat_id
  title
  story_job
  required_visual_proof
  status: pending | active | covered | skipped

ShotRecommendation
  recommendation_id
  beat_id
  title
  story_purpose
  visual_objective
  why_now
  execution_guidance
  safety_notes
  priority
  confidence
  status: suggested | selected | completed | dismissed
```

Gemini may propose the narrative fields, but the server owns IDs, timestamps, status transitions, and provenance. All model output remains untrusted until validated.

## 6. Repository map

| Path | Responsibility | Canonical? |
| --- | --- | --- |
| `main.py` | Starts video manager, web server, and director agent | No |
| `server.py` | FastAPI routes, MJPEG, SSE, app wiring | API boundary |
| `schemas.py` | Pydantic domain contracts | Yes for payload shape |
| `state.py` | Thread-safe session state and transitions | Yes for runtime state |
| `tools.py` | Gemini tool declarations and validated execution | Yes for tool boundary |
| `director_agent.py` | Gemini Live session, frame sampling, reconnects | Yes for live integration |
| `director_prompt.py` | Versioned system prompt | Yes for prompt version |
| `video_stream.py` | Video sources and synthetic fallback | Yes for ingest |
| `event_log.py` | Append-only local evidence log | Yes for run evidence |
| `grafana_publisher.py` | Optional telemetry sink | No; derived sink |
| `templates/index.html` | Browser monitor and interaction layer | No; never canonical |
| `docs/evidence-frame.md` | Evidence and claim boundary | Yes for claims |
| `docs/eval-protocol.md` | Evaluation design and grading rules | Yes for results |
| `docs/demo-script.md` | Repeatable presentation flow | Yes for demos |
| `docs/issues.md` | Implementation slices and dependencies | Yes for work breakdown |
| `fixtures/eval-manifest.json` | Held-out evaluation asset manifest | Yes for fixture inventory |
| `tests/` | Automated behavior and contract coverage | Yes for regression safety |

## 7. State and data flow

```text
video source -> sampled frame -> Gemini Live
story/intent -> versioned Gemini context
Gemini tool call -> strict validation -> AppState
AppState -> JSONL evidence + optional Grafana
AppState -> SSE/API -> dashboard
creator action -> validated API -> AppState -> evidence
```

The browser is a view and command surface. It must not invent canonical state. Grafana is useful for observability but cannot be used to reconstruct the authoritative product state.

## 8. API currently available

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/` | Director's Monitor dashboard |
| `GET` | `/video_feed` | MJPEG video stream |
| `GET` | `/events` | SSE state stream |
| `GET` | `/api/state` | Current validated session snapshot |
| `POST` | `/api/intent` | Set creator shot intent |
| `POST` | `/api/critiques/{critique_id}/tweaks/{tweak_id}/decision` | Record tweak decision |
| `GET` | `/health` | Source, Gemini, Grafana, and frame status |

The story-aware slice should add the smallest possible API surface: story load/set, coverage snapshot, next-shot recommendation publication, and recommendation decision. Update `docs/architecture.md` and tests in the same change.

## 9. Evidence frame summary

The immediate decision-maker is the founder/team deciding whether to continue pilot and demo work. The external evaluator and creator scoreboard are still discovery items. Until a real scoreboard and baseline are confirmed, all internal metrics remain supporting evidence.

The first honest claim is:

> In a live multimodal workflow, CinePilot can produce structured, story-aware cinematic recommendations for creator review.

The following claims require a comparator and measured baseline: better shots, fewer retakes, reduced production time, improved coverage, or replacement of expert crew.

## 10. Evaluation plan

Before the story-aware demo is presented as evidence:

1. Freeze the mock story, beats, and recommendation rubric.
2. Keep prompt examples separate from evaluation clips and check hashes mechanically.
3. Run a manual “what shot next?” baseline on 5–10 held-out cases before the demo.
4. Run CinePilot on the same cases.
5. Have an independent reviewer score story advancement, specificity, technical plausibility, and usefulness.
6. Report every percentage with numerator, denominator, and `n`; report failures.

Supporting metrics include first recommendation latency, valid recommendation rate, selection time, selected rate, completion rate, and reconnect count.

## 11. Issue sequence

Issues 1–7 cover the existing cinematic critique engine and hardening. The next slice is:

### Issue 8 — Build the story-aware next-shot mock demo

Canonical issue record: `docs/issues.md`.

Goal: Turn the current critique dashboard into a focused story-coverage demo for one seeded story.

Scope: `StoryBrief`, `StoryBeat`, `ShotRecommendation`, seed data, state transitions, Gemini context, API/SSE state, dashboard coverage panel, synthetic demo, and tests.

Acceptance criteria:

- A director can load the seeded mock story and see its beats.
- The current shot is associated with one active beat.
- The system publishes two or three validated next-shot recommendations.
- Each recommendation includes story purpose, visual objective, why now, and manual execution guidance.
- The creator can select, complete, or dismiss a recommendation idempotently.
- The dashboard visibly separates current critique from next-shot coverage.
- The synthetic demo works without a Gemini key through a deterministic mock provider or fixture mode.
- Tests cover validation, state transitions, API responses, and dashboard rendering.

Dependencies: Issues 1–7; in particular, retain the existing evidence and provenance rules.

Likely files: `schemas.py`, `state.py`, `tools.py`, `director_agent.py`, `server.py`, `templates/index.html`, `tests/`, `docs/architecture.md`, `docs/demo-script.md`, `docs/eval-protocol.md`.

## 12. What not to build now

- Do not build multiple cooperating agents for the first story demo. One explicit DirectorAgent is easier to test and explain.
- Do not add autonomous drone control or flight planning.
- Do not parse arbitrary screenplays or promise full continuity management.
- Do not build an editor, automatic retake trigger, or generated-video correction loop.
- Do not add a database, accounts, collaboration, or cloud deployment before the local evidence supports them.
- Do not turn telemetry into the product surface.
- Do not use generic cinematic language without a visible problem, a specific change, and a story reason.

## 13. Run and verify

```text
python main.py --source synthetic
open http://127.0.0.1:8000
python -m pytest -p no:cacheprovider -q
ruff check --no-cache .
```

With no Gemini key, the monitor and synthetic video should still load. That proves the shell and ingest path only; it does not prove live AI reasoning. Live Gemini and real-drone claims require separate verification.
