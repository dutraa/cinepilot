# CinePilot Agent Instructions

## Mission

CinePilot is a local, advisory AI cinematic decision engine. It watches live, prerecorded, or synthetic footage against a creator's intent and turns visual observations into specific, prioritized decisions: improve the current shot or recommend the next shot needed to tell the story.

The product is not an autonomous drone pilot, an editor, or a replacement for a director or cinematographer. The creator remains responsible for flight safety, creative approval, and marking whether a recommendation was actually acted on.

## Creator problem being solved

Creators often know that a shot does not feel right but cannot identify exactly what to change. Feedback is frequently vague: “make it more cinematic,” “this feels flat,” or “the shot is not working.” On smaller productions there may be no experienced cinematographer, continuity person, or director available to give immediate feedback, so weak framing, unsuitable camera movement, bad pacing, lighting problems, continuity issues, or missing coverage may only be discovered after the shoot. Creators may also generate several versions without a reliable way to understand which version is better or why.

CinePilot must turn that uncertainty into a small number of high-impact, explainable cinematic decisions across composition, camera angle, movement, lens feel, lighting, pacing, subject placement, continuity, and expression. The recommendation must state the visible or story-level problem, the concrete change to try, and why that change serves the intended result. A drone command such as “move left” is only useful when it is connected to that creative reasoning.

The intended product loop is:

```text
watch the shot -> understand the story/shot intent -> identify what is wrong or missing
  -> recommend the highest-impact tweak or next shot
  -> creator optionally applies it -> evaluate the result again
```

Drone footage is the initial hero input, not the permanent product boundary. The same decision engine should eventually support uploaded footage, generated video, phones, webcams, and other cameras. Do not claim that this broader intelligence exists until each input path has been implemented and evaluated.

## Product priorities

Use this cut order whenever scope is constrained:

1. **P0 — Story-aware demo loop:** enter a mock story, show the current live/synthetic shot, identify the current story beat and missing coverage, recommend two or three plausible next shots, and let the creator select one.
2. **P0 — Current cinematic critique loop:** compare footage with shot intent and return one to three structured tweaks with diagnosis, recommendation, rationale, priority, and optional spoken cue.
3. **P0 — Evidence integrity:** preserve intent versions, observation IDs, prompt version, all eligible attempts, creator decisions, and event-log provenance.
4. **P1 — Real creator validation:** run a manual comparator and CinePilot on held-out clips with a non-prompt author scoring actionability.
5. **P2 — Persistence and integrations:** databases, multi-user projects, autonomous controls, editing APIs, and production deployment.

Do not add a feature merely because it is technically interesting. It must improve a creator's ability to choose a useful next shot or make a current shot better.

## Core user loop

```text
director enters story brief and current beat
  -> agent watches the current shot
  -> agent explains what the shot contributes
  -> agent identifies the strongest missing story coverage
  -> agent recommends 2–3 next shots with why-now and flight guidance
  -> director selects, captures, and marks the result
  -> agent evaluates the new coverage
```

The first story-aware demo uses one mock story with three to five beats. Recommendations are suggestions, not flight commands. The UI must distinguish:

- **Observed:** grounded in the current frame or clip.
- **Recommended:** proposed by Gemini and not yet approved.
- **Selected:** accepted by the creator for the next take.
- **Acted:** explicitly marked by the creator after the take.
- **Completed:** creator confirms the shot was captured and added to coverage.

## Evidence and claims

Read `docs/evidence-frame.md` before changing success criteria, KPIs, or demo claims. Do not claim improved production outcomes, fewer retakes, or replacement of a cinematographer until a manual baseline and a comparator exist.

Every reported rate includes numerator, denominator, and sample size. Failed or malformed model attempts stay in denominators. Evaluation clips must be mechanically disjoint from prompt examples. Engineering metrics such as latency, FPS, and schema validity are supporting metrics, never headline outcomes without a verified decision-maker scoreboard.

For the story-aware demo, the immediate evidence question is:

> Given a story brief and a current shot, can a creator quickly choose a technically plausible next shot that advances a missing story beat?

Measure selection time, recommendation validity, creator selection, flyability, and independent usefulness. Label synthetic, roleplayed, and live evidence separately.

## Technical boundaries

- Python 3.10+.
- FastAPI serves the dashboard, MJPEG feed, API, and SSE state stream.
- Gemini Live is the multimodal reasoning layer; its output is untrusted input.
- Pydantic models in `schemas.py` validate every external/model payload.
- `AppState` in `state.py` is the canonical session state.
- `EventLog` in `event_log.py` is append-only JSONL evidence for local runs.
- Grafana is optional observability, never canonical state.
- Video sources are implemented in `video_stream.py`; the synthetic source is the deterministic fallback.
- Browser speech is advisory only. No API may move a drone.

Reference detail lives in:

```text
everythings.md            complete project map and current truth
docs/architecture.md     boundaries, state flow, and contracts
docs/demo-script.md       repeatable story-aware and critique demos
docs/eval-protocol.md     comparator, grading, and integrity rules
docs/evidence-frame.md    decision-maker, scoreboard, baseline, claims
docs/issues.md            issue-sized implementation slices
```

## Implementation rules

1. Start with a failing test for each new contract or state transition.
2. Keep domain models strict. Reject unknown fields and invalid enum values.
3. Keep server-owned IDs, timestamps, prompt versions, and intent versions out of model-supplied payloads.
4. Treat model text as unsafe display data. Render it as text, not HTML.
5. Preserve backward compatibility for the existing critique and shot-list demo while adding story coverage.
6. Prefer one well-scoped `DirectorAgent` with explicit context over a multi-agent orchestration layer.
7. Keep external calls out of synchronous HTTP request paths. In the live loop, handle disconnects and malformed tool calls without killing the process.
8. Make state transitions idempotent where a browser retry is expected.
9. Keep state session-local until persistence is justified by evidence from multiple runs or users.
10. Do not hide source provenance. The dashboard must show synthetic, file, webcam, RTSP, or RTMP.
11. Track implementation issues in `docs/issues.md`. Do not create GitHub issues unless the user explicitly requests it.

## UI quality bar

The primary surface is the decision, not telemetry. The right side of the dashboard should answer, in order:

1. What story are we telling?
2. What beat are we in?
3. What does the current shot contribute?
4. What coverage is missing?
5. Which next shot should we take, and why now?
6. What exact advisory action can the pilot attempt?

Every async surface needs loading, empty, error, and stale/disconnected states. Keep the interface readable during a live shoot. Do not use emojis in code, UI, or docs.

## Required verification

Before declaring work complete, run the repository's available checks and report their actual results:

- `python -m pytest -p no:cacheprovider -q`
- `ruff check --no-cache .`
- Python AST parsing for all project modules
- JavaScript parsing for the dashboard script
- Synthetic-server smoke check for `/`, `/health`, `/api/state`, `/api/intent`, `/video_feed`
- Browser screenshot or interaction check when dashboard behavior changes
- `git diff --check`, secret scan, and clean-worktree check

Do not call live Gemini verification complete unless a real API key is configured and a live session was exercised. Do not call drone verification complete without a real drone/source test.

## Definition of done

A change is done only when:

- its contract and rationale are documented;
- tests cover the behavior and failure paths;
- the synthetic demo can run without external hardware;
- the UI makes provenance and state visible;
- evidence limitations and denominators are recorded;
- all required checks pass;
- the branch has a reviewable commit and pushed remote state when shipping was requested.
