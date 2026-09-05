# Issue Breakdown

These are the implementation issues for the cinematic tweak engine. Dependencies are intentionally explicit so each issue can be implemented and verified independently.

## Issue 1: Lock the Evidence Frame and evaluation fixtures

GitHub: https://github.com/dutraa/cinepilot/issues/1

**Goal:** Ratify the decision-maker, scoreboard, baseline, claim boundaries, and held-out evaluation set.

**Acceptance criteria:**

- Evidence Frame has a named decision-maker and date.
- Baseline is scheduled before the demo.
- Evaluation and prompt-example manifests are mechanically disjoint.
- No outcome claim is made without a numerator and denominator.

**Files:** `docs/evidence-frame.md`, `docs/eval-protocol.md`, `fixtures/eval-manifest.json`

**Dependencies:** None

## Issue 2: Add strict cinematic domain contracts

GitHub: https://github.com/dutraa/cinepilot/issues/2

**Goal:** Validate creator intent, critiques, tweaks, and action requests at every boundary.

**Acceptance criteria:**

- Unknown fields and invalid enum values are rejected.
- Critiques contain one to three tweaks.
- Length and constraint limits are enforced.
- Server-owned IDs and timestamps cannot be supplied by Gemini.

**Files:** `schemas.py`, `tests/test_schemas.py`

**Dependencies:** Issue 1

## Issue 3: Move active state into a critique-aware state model

GitHub: https://github.com/dutraa/cinepilot/issues/3

**Goal:** Add intent versioning, bounded critique history, deduplication, and tweak state transitions.

**Acceptance criteria:**

- Critiques are immutable after publication.
- Decisions follow `PROPOSED → ACCEPTED → ACTED` or `DISMISSED`.
- Duplicate actions are idempotent.
- State snapshots include intent, critique data, and supporting metrics.

**Files:** `state.py`, `event_log.py`, `tests/test_state.py`

**Dependencies:** Issue 2

## Issue 4: Expose intent and tweak decision APIs

GitHub: https://github.com/dutraa/cinepilot/issues/4

**Goal:** Connect the browser workflow to validated state.

**Acceptance criteria:**

- `POST /api/intent` increments intent version only when intent changes.
- `GET /api/state` and `/events` expose the same contract.
- Tweak decision route returns 404, 409, or 200 deterministically.

**Files:** `server.py`, `tests/test_api.py`

**Dependencies:** Issue 3

## Issue 5: Integrate structured critiques into Gemini Live

GitHub: https://github.com/dutraa/cinepilot/issues/5

**Goal:** Send intent updates to Gemini and validate `publish_cinematic_critique` calls.

**Acceptance criteria:**

- Intent is sent on connection and after version changes.
- Invalid tool calls do not mutate state or kill the session.
- Duplicate critiques are suppressed.
- Observation, prompt, and intent versions are recorded.

**Files:** `director_agent.py`, `tools.py`, `director_prompt.py`, `tests/test_tools.py`, `tests/test_director_agent.py`

**Dependencies:** Issue 4

## Issue 6: Recenter the dashboard on intent and cinematic tweaks

GitHub: https://github.com/dutraa/cinepilot/issues/6

**Goal:** Make the recommendation quality, not telemetry, the primary user experience.

**Acceptance criteria:**

- Intent can be entered without editing `.env`.
- Critiques render safely as text.
- Actions are visible and functional.
- Source provenance and audio state are visible.

**Files:** `templates/index.html`, `tests/test_dashboard_contract.py`

**Dependencies:** Issue 4

## Issue 7: Harden setup, demo, and verification

GitHub: https://github.com/dutraa/cinepilot/issues/7

**Goal:** Make the repository reproducible and the demo evidence-led.

**Acceptance criteria:**

- Dependencies are installable and pinned or explicitly verified.
- `.env.example` and `.gitignore` exist.
- README documents both the old live path and the new critique path.
- Focused tests, full tests, syntax checks, and browser smoke checks are documented.

**Files:** `README.md`, `.env.example`, `.gitignore`, `requirements-dev.txt`, `docs/demo-script.md`

**Dependencies:** Issues 1–6

## Issue 8: Build the story-aware next-shot mock demo

This is a repository planning issue. `docs/issues.md` is the canonical issue tracker; do not create a separate GitHub issue unless explicitly requested.

**Goal:** Help creators turn “this feels flat,” “make it more cinematic,” or “the shot is not working” into a specific, story-aware decision. Connect one seeded mock story and ordered story beats to the live or synthetic shot so CinePilot explains the current shot's story contribution, identifies missing coverage, and recommends the next useful shots for the creator to capture manually.

**Vertical-slice definition:** A director can load “The place worth coming back to,” see the active beat, view a synthetic or live shot, receive two or three recommendations, select one, mark it completed, and see the coverage state advance. The same state is visible in the dashboard, `/api/state`, `/events`, and the local event log. Each recommendation connects a visible or story-level problem to a concrete change and explains why that change serves the intended result.

**Parent dependencies:** Issues 1–7. Existing critique, intent, event-log, API, SSE, and dashboard behavior must remain working.

**Global acceptance criteria:**

- A seeded mock story loads without external hardware or a Gemini key.
- The dashboard shows the story, ordered beats, active beat, covered beats, missing coverage, and the current shot's story contribution.
- The system publishes two or three strict `ShotRecommendation` records.
- Every recommendation contains story purpose, visual objective, why now, manual execution guidance, safety notes, priority, and optional confidence; supported categories include composition, camera angle and movement, lens feel, lighting, pacing, subject placement, continuity issues, and expression.
- Server-owned IDs, timestamps, versions, and statuses cannot be supplied by Gemini or the browser.
- The creator can select, complete, or dismiss a recommendation idempotently.
- Coverage state changes are visible through `/api/state` and `/events` and are recorded in JSONL evidence.
- Gemini context includes the story brief, active beat, coverage history, current footage, and current cinematic intent.
- Deterministic fixture mode exercises the same validation and state boundaries as live Gemini.
- Tests cover valid and invalid contracts, state transitions, API behavior, Gemini context synchronization, fixture mode, and dashboard behavior.
- Documentation labels implemented, deterministic fixture, synthetic, and live Gemini behavior separately.

**Out of scope:** autonomous flight, flight-plan generation, multiple cooperating agents, screenplay parsing, automatic editing, automatic retake triggers, persistence, collaboration, accounts, and cloud deployment.

### Issue 8.1: Freeze the story fixture and grading rubric

**Goal:** Make the demo narrative and evaluation unit stable before implementation changes the prompt or UI.

**Files:** `fixtures/story.json`, `fixtures/eval-manifest.json`, `docs/demo-script.md`, `docs/eval-protocol.md`, `docs/evidence-frame.md`

**Implementation:**

- Seed “The place worth coming back to.”
- Define five ordered beats: Isolation, Discovery, Invitation, Renewal, Confidence.
- Give every beat a story job and required visual proof.
- Define which initial synthetic shot covers Isolation and which beats remain missing.
- Define two or three expected recommendation archetypes for the fixture, without copying the exact evaluation wording into the Gemini prompt.
- Freeze an independent review rubric for story advancement, specificity, technical plausibility, and usefulness.
- Keep the fixture narrative separate from the broader product hypothesis: uploaded footage, generated video, phones, webcams, and other cameras are future input paths, not part of this slice.

**Acceptance criteria:**

- The fixture is valid JSON with stable IDs and deterministic ordering.
- The fixture contains no secrets, real-person data, or unsafe flight instructions.
- Prompt examples and evaluation assets remain in separate manifests.
- The rubric can grade a recommendation without relying on whether the creator clicked a button.

**Verification:** JSON parse, stable fixture snapshot test, mechanical prompt/evaluation disjointness check, and documentation review.

**Dependencies:** Issue 1.

### Issue 8.2: Add strict story and recommendation contracts

**Goal:** Define the validated boundary for story context, coverage, and next-shot recommendations.

**Files:** `schemas.py`, `docs/SPEC.md`, `tests/test_schemas.py`

**Contracts:**

```text
StoryBrief
  story_id, title, logline, emotional_arc, visual_style
  must_show[], constraints[], beats[]

StoryBeat
  beat_id, title, story_job, required_visual_proof
  status: pending | active | covered | skipped

ShotCoverage
  coverage_id, beat_id, shot_title, observation_id
  captured_at, source, notes

ShotRecommendationInput
  beat_id, title, story_purpose, visual_objective
  why_now, execution_guidance, safety_notes
  priority, confidence

ShotRecommendation
  recommendation_id, beat_id, title, story_purpose
  visual_objective, why_now, execution_guidance, safety_notes
  priority, confidence, status, observation_id
  intent_version, prompt_version, created_at
```

**Implementation rules:**

- Extend the existing strict Pydantic base model.
- Use bounded strings and bounded lists.
- Reject unknown fields and invalid enum values.
- Keep model input separate from server-owned output models.
- Do not allow recommendations to contain autonomous control verbs as executable commands; they are manual guidance only.
- Require enough context for the recommendation loop: watch the shot, understand intent, identify what is wrong or missing, recommend the highest-impact tweak or next shot, optionally apply it, and evaluate the result again.

**Acceptance criteria:** Every field has a validation test, server-owned fields cannot be injected, two or three recommendations are valid, zero or four recommendations are rejected, and malformed model output cannot mutate state.

**Dependencies:** Issue 8.1 and existing Issue 2 implementation.

### Issue 8.3: Add seeded story loading and deterministic fixture mode

**Goal:** Make the complete story loop runnable and repeatable without Gemini, a drone, RTMP, or Grafana.

**Files:** `story_demo.py`, `demo_provider.py`, `config.py`, `main.py`, `fixtures/story.json`, `tests/test_demo_provider.py`

**Implementation:**

- Load the seeded story from `fixtures/story.json` at startup in demo mode.
- Add an explicit `--demo-mode` or equivalent configuration switch; do not infer demo mode from missing credentials alone.
- Provide deterministic recommendations for the initial Isolation shot and the next beat after completion.
- Use the same `AppState` publication methods and schemas as live Gemini.
- Label fixture recommendations as `deterministic_demo` in state and event evidence.
- Preserve the existing `--source synthetic` behavior and current critique path.

**Acceptance criteria:** The application starts with `--source synthetic --demo-mode`, returns story state, publishes stable recommendation IDs/content for the same fixture state, and remains usable with demo mode off and no Gemini key.

**Verification:** Provider unit tests, repeat-run snapshot comparison, synthetic server smoke, and visible source/mode provenance in the dashboard.

**Dependencies:** Issue 8.1 and Issue 8.2.

### Issue 8.4: Add story, coverage, and recommendation state transitions

**Goal:** Make story progress canonical, thread-safe, auditable, and idempotent.

**Files:** `state.py`, `event_log.py`, `tests/test_state.py`

**State additions:**

- active `StoryBrief` and `story_version`;
- active beat ID;
- beat status map;
- coverage records and current shot contribution;
- missing coverage calculation;
- latest recommendations and bounded recommendation history;
- recommendation action records and counters.

**Transitions:**

```text
beat: pending -> active -> covered
beat: active -> skipped

recommendation: suggested -> selected -> completed
recommendation: suggested -> dismissed
recommendation: selected -> dismissed
```

**Implementation rules:**

- The server owns transition timestamps and actor/source metadata.
- Repeating the same decision returns the existing status without duplicate counters.
- Unknown story, beat, coverage, or recommendation IDs return a typed not-found error.
- Invalid transitions leave canonical state unchanged and record the rejection.
- Critique state and story state remain compatible in one snapshot.

**Acceptance criteria:** All legal transitions work, illegal transitions are rejected, retries are idempotent, event records contain the transition and provenance, and a completed recommendation updates beat/coverage state deterministically.

**Dependencies:** Issue 8.2.

### Issue 8.5: Integrate recommendations into tools and Gemini context

**Goal:** Give Gemini enough narrative and coverage context to replace vague cinematic feedback with story-relevant next-shot recommendations and concrete current-shot tweaks.

**Files:** `tools.py`, `director_agent.py`, `director_prompt.py`, `tests/test_tools.py`, `tests/test_director_agent.py`

**Implementation:**

- Add a `publish_next_shot_recommendations` tool declaration.
- Validate input with `ShotRecommendationInput` before publication.
- Generate server-owned recommendation IDs, timestamps, observation IDs, intent versions, and prompt versions.
- Extend the versioned prompt with the story, active beat, covered beats, missing beats, current shot contribution, and current intent.
- Synchronize story context once per story/beat/coverage version, just as intent is synchronized once per intent version.
- Keep the current `publish_cinematic_critique`, `update_shot_list`, and `speak_director_guidance` tools working.
- Treat safety notes as advisory warnings and never expose them as control APIs.
- Preserve the option to evaluate the next result after the creator applies a recommendation; publication is not proof that the shot improved.

**Acceptance criteria:** Context is sent on connect and only when its version changes; valid recommendations publish; invalid recommendations are rejected without killing the session; duplicate recommendations are suppressed; provenance is recorded.

**Dependencies:** Issue 8.4.

### Issue 8.6: Expose story and coverage APIs

**Goal:** Connect the browser to canonical story state using a small, explicit API surface.

**Files:** `server.py`, `tests/test_api.py`, `docs/SPEC.md`

**Routes:**

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/story` | Return the active story, beats, active beat, and versions |
| `POST` | `/api/story/beat` | Set or advance the active beat through validation |
| `GET` | `/api/coverage` | Return covered and missing story coverage |
| `GET` | `/api/recommendations` | Return current and bounded recommendation history |
| `POST` | `/api/recommendations` | Publish a deterministic/manual recommendation through validation |
| `POST` | `/api/recommendations/{id}/decision` | Select, complete, or dismiss one recommendation |

**Implementation rules:**

- Keep `/api/state` as the complete snapshot and include the new fields there.
- Keep `/events` shape-compatible with `/api/state`.
- Return `404` for unknown IDs, `409` for invalid transitions, `422` for invalid payloads, and `200` for idempotent repeats.
- Do not let clients directly set covered status without a validated recommendation or explicit coverage action.

**Acceptance criteria:** Each route has success, validation, not-found, conflict, and retry tests where applicable; API responses contain only server-owned canonical state; SSE includes story changes.

**Dependencies:** Issue 8.4 and Issue 8.5.

### Issue 8.7: Build the story-aware dashboard surface

**Goal:** Make the story decision visible and usable during a live shoot.

**Files:** `templates/index.html`, `tests/test_dashboard_contract.py`, browser smoke artifact/configuration

**Layout:**

- story header: title, logline, source, mode, and story version;
- beat rail: ordered beats with pending, active, covered, skipped states;
- current shot panel: observed contribution and limitations;
- coverage panel: covered proof and missing proof;
- next-shot cards: story purpose, visual objective, why now, execution guidance, safety notes, priority, confidence;
- actions: Select, Complete, Dismiss;
- existing critique panel: current-shot tweaks remain available but secondary to the story decision.

**Implementation rules:**

- Render all model-generated text with safe text APIs.
- Keep deterministic/demo/live provenance visible.
- Add loading, empty, error, stale SSE, and disconnected source states.
- Make action feedback immediate but reconcile from the server snapshot.
- Keep telemetry subordinate to the decision surface.

**Acceptance criteria:** A user can complete the full story loop without editing environment files, actions visibly update state, mobile/desktop layouts remain legible, and no browser console errors occur in the smoke run.

**Dependencies:** Issue 8.6.

### Issue 8.8: Integrate, verify, and run the evidence gate

**Goal:** Prove the slice is repeatable and state the strongest claim the evidence supports about reducing ambiguity in cinematic decisions. Do not claim fewer retakes, better shots, faster production, or replacement of expert crew without comparator evidence.

**Files:** `tests/`, `docs/demo-script.md`, `docs/eval-protocol.md`, `docs/evidence-frame.md`, `README.md`, `docs/SPEC.md`

**Implementation:**

- Add an end-to-end test from story load through recommendation completion and next-beat activation.
- Run the deterministic synthetic demo from a clean environment.
- Run the live Gemini path only when a real key is configured; label it separately from fixture mode.
- Prepare 5–10 held-out cases and complete a timed manual baseline before presenting results.
- Have an independent reviewer score story advancement, specificity, technical plausibility, and usefulness.
- Record selection time, recommendation validity, selected/completed decisions, failures, and provenance.
- Update docs to distinguish implemented behavior from planned extensions.

**Acceptance criteria:**

- Full automated suite passes.
- Ruff, AST, dashboard parsing, synthetic server smoke, browser verification, secret scan, and `git diff --check` pass.
- Deterministic demo can be repeated with the same fixture result.
- Evidence includes numerator, denominator, and `n` for every reported rate.
- The final claim is limited to what the comparator and reviewer evidence support.
- The branch has a reviewable commit and pushed remote state when shipping is requested.

**Dependencies:** Issues 8.1–8.7.

## Issue 8 execution order and cut line

Implement in this order: `8.1 → 8.2 → 8.3 → 8.4 → 8.6 → 8.5 → 8.7 → 8.8`.

The deterministic path is the release cut line. If time is limited, stop after `8.4` and `8.7` with fixture recommendations wired through state/API/UI; Gemini integration is valuable but must not block a repeatable demo. Do not claim live story understanding until `8.5` has been exercised with a real Gemini session.

## Issue 8 risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Recommendations sound generic | Require story purpose, visible proof, why-now, and concrete manual guidance in the schema and rubric |
| Fixture content is mistaken for AI quality | Show mode/source provenance and report fixture, synthetic, and live evidence separately |
| Story state diverges from critique state | Keep one `AppState` snapshot and one event log; test both in the same flow |
| Recommendations imply unsafe control | Advisory wording, safety notes, manual selection, and no flight-control API |
| Multi-agent scope expands | Keep one `DirectorAgent` until usefulness evidence justifies decomposition |
| Demo claims outrun evidence | Complete the manual baseline and independent grading before outcome claims |

## Issue 8 implementation status — 2026-09-01

Implemented locally on `feature/cinematic-tweak-engine`: 8.1 story fixture,
8.2 strict story/coverage/recommendation contracts, 8.3 explicit deterministic
demo mode, 8.4 canonical story and recommendation transitions, 8.5 Gemini tool
and versioned story context, 8.6 API/SSE routes, and 8.7 story-first dashboard.
The 8.8 verification gates are run for this change; the manual held-out
baseline and independent reviewer evidence remain pending, so no production
outcome claim is made.

## Issue 9: Add advisory 10-second cinematography visualization

This is a repository planning issue. `docs/issues.md` is the canonical issue
tracker; do not create a separate GitHub issue unless explicitly requested.

**Goal:** Let a creator request exactly three illustrative 10-second
cinematography concepts for the current place, story beat, and shot intent,
select one, and receive a concrete manual capture brief. The feature is a
creative reference, not a flight plan, obstacle map, camera-path guarantee, or
proof that the resulting shot improved.

**Vertical-slice definition:** In the deterministic synthetic demo, the creator
opens the existing story-first dashboard, requests visualizations for the
current shot, receives exactly three visibly labeled 10-second concept previews,
selects one, and sees the selected concept handed off to the manual next-shot
workflow. The creator can later capture and mark the shot completed through the
existing story loop; visualization selection itself never marks coverage
complete. The same job, preview, decision, and provenance state is visible via
the dashboard, `/api/state`, `/events`, and the local event log.

**Product boundary:** Keep visualization in the existing dashboard as a panel
or drawer. Generation is asynchronous and should be requested from a safe
hover or after a short evidence burst, not treated as continuous guidance while
the drone is maneuvering. The deterministic release cut line must work without
Gemini, a drone, RTMP, or Grafana. A live video-generation provider is optional
and separately labeled.

**Global acceptance criteria:**

- The deterministic demo produces exactly three repeatable, browser-playable
  10-second concept animations over a server-frozen source frame for the
  current story context.
- Every preview states its story purpose, visual objective, why it is useful
  now, manual execution guidance, and safety notes.
- Preview provenance distinguishes deterministic demo, synthetic, and any live
  provider output; no preview is presented as spatially accurate flight truth.
- Browser and provider input cannot supply server-owned IDs, timestamps,
  statuses, asset references, prompt versions, intent versions, or story
  versions.
- A creator can select or dismiss the linked `ShotRecommendation` idempotently.
  Selection exposes a manual next-shot brief; it does not complete coverage or
  assert that a shot was captured.
- Visualization jobs and decisions are included in `/api/state` and `/events`
  and every state change or rejection is recorded in the JSONL event log.
- Existing critique, recommendation, beat, coverage, API, SSE, and dashboard
  behavior remains working.
- No autonomous drone control, flight-plan generation, automatic retake, asset
  persistence, accounts, collaboration, or cloud deployment is added.

### Issue 9.1: Freeze visualization semantics, provenance, fixture, and rubric

**Type:** HITL — boundary and evidence review.

**Goal:** Define what “visualize 10 seconds of different cinematography” means
for this release before implementation or model prompting begins.

**What to build:** Extend the existing evidence frame with the visualization
decision question, claim boundaries, baseline plan, and evidence strata. Add a
fixture separate from prompt examples and evaluation assets describing the
current place, the active story beat, and three initial cinematography
archetypes: descending reveal, lateral parallax, and restrained pull-away or
orbit. Freeze an independent rubric for story advancement, specificity,
technical plausibility, usefulness, and preview-to-captured-shot fidelity.

**Acceptance criteria:**

- The fixture has stable IDs and explicitly records that its previews are
  illustrative, not spatially faithful flight simulations.
- On 2026-09-06, 5–10 held-out cases are frozen in `fixtures/eval-manifest.json`
  with asset hashes and the timed manual “what shot next/how would you
  visualize this?” baseline is run before any CinePilot run on those cases.
- By 2026-09-07, an independent reviewer scores the manual and CinePilot
  records. No outcome presentation is permitted before 2026-09-08, and if the
  dates slip only deterministic behavior may be shown.
- Prompt examples and evaluation assets are separate and mechanically checked
  for disjointness.
- No outcome claim about better shots, fewer retakes, or faster production is
  allowed from deterministic or synthetic previews alone.

**Verification:** JSON/schema snapshot, manifest disjointness check, rubric
review, and evidence-frame review.

**Dependencies:** Issue 8 and the existing `docs/evidence-frame.md` frame.

## Issue 9 deterministic cut-line status — 2026-09-05

Issues 9.2–9.6 are implemented locally on
`feature/cinematic-tweak-engine`: strict server-owned contracts, frozen
observation capture, one-worker deterministic rendering, recommendation
linkage, idempotent selection/dismissal through the existing route, API/SSE
exposure, and the existing-dashboard visualization panel. Issues 9.7 and 9.8
remain deferred: no live provider or outcome evidence claim is made. The
scheduled manual baseline and independent review remain required before any
presentation beyond deterministic behavior.

### Issue 9.2: Add strict visualization job and preview contracts

**Type:** AFK.

**Goal:** Define an untrusted request/output boundary that prevents visual
  concepts from becoming hidden flight commands or client-owned canonical state.

**What to build:** Add strict Pydantic models for a visualization request,
  visualization job, visualization preview, and job statuses. A visualization
  preview is a visual attachment to exactly one existing
  `ShotRecommendation`; the recommendation remains the only canonical
  selected/completed/dismissed decision record. The request derives the current
  story, beat, observation, and intent from server state. The preview carries
  the story and manual-execution fields needed by the existing recommendation
  loop.

**Acceptance criteria:**

- The initial request is exactly `{ "duration_seconds": 10,
  "variation_count": 3 }`; unknown fields and invalid enum values are
  rejected.
- Model/browser input cannot provide IDs, timestamps, statuses, source-frame
  references, story/intent versions, prompt versions, or provenance.
- Job status is `requested | rendering | ready | failed`; transitions are
  `requested -> rendering -> ready|failed` and cannot be reversed.
- Preview text is bounded and validated; `animation_profile` is one of the
  fixed server-owned profiles `descending_reveal`, `lateral_parallax`, or
  `restrained_pull_away` and is not an executable control payload.
- Each preview has exactly one server-owned `recommendation_id`; no separate
  visualization decision request or preview decision state is introduced.
- Tests are written first for valid contracts, invalid fields/enums, server-
  owned field injection, and malformed output.

**Verification:** Focused schema tests and a proof that rejected payloads do
not mutate state.

**Dependencies:** Issue 9.1.

### Issue 9.3: Capture an observation and render deterministic concept previews

**Type:** AFK.

**Goal:** Give the synthetic demo a repeatable end-to-end visualization result
  without an external generation service.

**What to build:** At request time, freeze the latest available video frame as
  a session-local observation snapshot. In deterministic mode, use the seeded
  synthetic scene when no live frame is available. Run one in-process worker
  with at most one active job per session. Render exactly three browser-playable
  10-second concept animations over the frozen JPEG using fixed screen-space
  recipes: `descending_reveal` scales 1.00→1.25 while revealing downward,
  `lateral_parallax` pans across a 1.08 scale while holding the subject on the
  right third, and `restrained_pull_away` scales 1.18→1.00 with slight upward
  drift. These are 2D illustrations, not physical camera paths. Store only the
  bounded job metadata and temporary source frame;
  the browser performs the validated animation profile over the source image.
  No external queue or generic provider framework is required for this slice.

**Acceptance criteria:**

- Repeating the same story context, observation snapshot, and exact request
  fingerprint returns the existing job and does not start duplicate work.
- A different request while one job is rendering returns `409`; a missing
  current observation returns `409`; process restart discards jobs because this
  release is session-local.
- The job transitions through `requested -> rendering -> ready|failed` and
  records request, observation, ready, and failure events with deterministic-
  demo provenance.
- The result is visibly marked synthetic/illustrative and cannot be interpreted
  as an accurate route through the real place.
- A snapshot or renderer failure leaves story, recommendation, and coverage
  state unchanged; temporary files are removed on eviction or process exit.

**Verification:** Provider unit tests, repeat-run snapshot test, generated
  artifact inspection, and synthetic server smoke test.

**Dependencies:** Issue 9.2.

### Issue 9.4: Link concepts to recommendations and hand off to manual capture

**Type:** AFK.

**Goal:** Connect a selected visualization to the existing story-aware manual
  execution loop without falsely claiming that the shot was captured.

**What to build:** Attach each ready preview to one server-owned
  `ShotRecommendation` and reuse the existing recommendation decision route.
  Selecting or dismissing the recommendation updates the linked preview view.
  On selection, expose the existing server-owned manual next-shot brief
  containing the selected visual objective, why-now rationale, execution
  guidance, and safety notes. Keep capture completion and coverage advancement
  on the existing recommendation/coverage transition path.

**Acceptance criteria:**

- Valid recommendation decisions update the linked preview view; repeated
  decisions return the existing state without duplicate counters or action
  events.
- Unknown recommendation or preview IDs return typed not-found errors; invalid
  transitions return a conflict and leave state unchanged while logging the
  rejection.
- Selecting a concept never marks a beat covered, a recommendation completed,
  or a shot improved. Completion remains a later manual capture action.
- The handoff preserves the preview, recommendation, context versions, and
  provenance in the canonical snapshot and event log.

**Verification:** State transition, idempotency, not-found, conflict, and
  end-to-end handoff tests.

**Dependencies:** Issue 9.3 and Issue 8.4.

### Issue 9.5: Expose visualization jobs through API and SSE

**Type:** AFK.

**Goal:** Provide the smallest useful browser-facing surface for requesting,
  monitoring, listing, and deciding on visualizations.

**Routes:**

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/api/visualizations` | Create or return the current job from the exact request fingerprint |
| `GET` | `/api/visualizations` | Return the bounded session-local job history |
| `GET` | `/api/visualizations/{job_id}` | Return one job and its three previews |
| `GET` | `/api/visualizations/{job_id}/source-frame` | Return the temporary frozen JPEG used by browser concept animations |
| `POST` | `/api/recommendations/{recommendation_id}/decision` | Reuse the existing canonical select/complete/dismiss lifecycle |

**What to build:** Add the routes above and include visualization jobs and
  linked previews in `/api/state` and in the same-shaped SSE snapshots from
  `/events`. Do not add a second visualization decision route.

**Acceptance criteria:**

- New or idempotent `POST /api/visualizations` requests return `200` with the
  job; malformed payloads return `422`; unknown jobs/recommendations return
  `404`; conflicting active jobs or missing observations return `409`.
- The browser cannot directly invent canonical preview assets, provenance,
  completion, coverage, recommendation IDs, or status.
- `requested`, `rendering`, `ready`, `failed`, transport-stale, and source-
  disconnected states are represented in API/SSE data without breaking the
  existing story or critique snapshot.
- API tests cover success, validation, not-found, conflict, duplicate request,
  missing observation, source-frame retrieval, retry, and SSE state shape.

**Verification:** FastAPI tests plus a synthetic server smoke test consuming
  `/api/state` and `/events`.

**Dependencies:** Issue 9.4.

### Issue 9.6: Add the visualization panel to the story-first dashboard

**Type:** AFK.

**Goal:** Make the visualization decision understandable during a shoot without
  taking the creator away from story and coverage context.

**What to build:** Add a “Visualize this place” action near the current-shot and
  missing-coverage panels. Render job progress, exactly three preview cards over
  the frozen source JPEG from `/api/visualizations/{job_id}/source-frame`,
  provenance, 10-second duration, story purpose, why now, manual guidance, and
  safety notes. Add Select and Dismiss actions by reusing the linked
  recommendation route, then show the manual brief. Keep current cinematic
  critique secondary but available.

**Acceptance criteria:**

- The full deterministic flow works in one dashboard session without editing
  environment files or navigating to a separate visualization page.
- All model/generated text uses safe text rendering; no model text is injected
  as HTML or executable JavaScript.
- Loading, empty, error, stale SSE, disconnected source, and generation-failed
  states are visible and recoverable.
- The selected concept is clearly distinct from captured/completed coverage and
  from proof that the actual shot improved; preview selection uses the existing
  recommendation action state rather than a duplicate preview state machine.
- Browser tests verify actions, state reconciliation, no console errors, and a
  screenshot or interaction artifact.

**Verification:** Dashboard contract tests, JavaScript parsing, and browser
  interaction verification on the synthetic demo.

**Dependencies:** Issue 9.5.

### Issue 9.7: Evaluate whether a live video-generation provider is justified

**Type:** HITL — later scope decision.

**Goal:** Decide whether measured demand and evidence justify adding a live
  video-generation provider after the deterministic concept-animation path is
  usable. This issue is not part of the deterministic release cut line.

**What to build:** First run a provider comparison using held-out cases and
  record latency, cost, exact output duration, spatial drift, content failures,
  and asset handling. Only if the decision-maker approves, add one named
  provider behind the existing job contract and one in-process worker. Do not
  add a generic provider marketplace or a second queue.

**Acceptance criteria:**

- No live provider is added unless the comparison and approval record exist.
- If approved, live output uses the same job contract and existing
  recommendation lifecycle as deterministic output.
- Provider timeout, disconnect, malformed response, content rejection, and
  cancellation leave canonical coverage unchanged and are visible in events.
- A provider must produce exactly 10 seconds or the job fails; shorter output is
  not silently relabeled as 10 seconds.
- Live output is labeled separately from deterministic fixture and synthetic
  evidence; no test requires a real API key.
- The feature does not claim instant generation, spatial accuracy, obstacle
  awareness, or a safe flight route.

**Verification:** Provider comparison record, mock-provider tests only if
approved, failure-path tests, configuration-off tests, and manual live
verification only when a real key/service is available.

**Dependencies:** Issue 9.2 and Issue 9.5; does not block the deterministic cut
  line.

### Issue 9.8: Verify the flow, update docs, and run the evidence gate

**Type:** HITL — evidence review.

**Goal:** Verify the complete visualize loop and make the strongest defensible
  claim about it.

**What to build:** Add full end-to-end coverage from story/current shot through
  request, preview readiness, selection, manual handoff, capture completion, and
  separate result evaluation. Update `docs/SPEC.md`, `docs/architecture.md`,
  `docs/demo-script.md`, `docs/eval-protocol.md`, `docs/evidence-frame.md`,
  `everythings.md`, `README.md`, and this issue tracker with implemented
  behavior, limitations, and verification results.

**Acceptance criteria:**

- Full tests, Ruff, AST parse, dashboard JavaScript parse, synthetic server
  smoke, browser interaction, secret scan, `git diff --check`, and clean
  worktree checks pass.
- Held-out manual baseline is run before the CinePilot demo, with an independent
  reviewer scoring story advancement, specificity, technical plausibility, and
  usefulness.
- The internal live-provider gate is explicit: do not add a live provider unless
  at least 4 of the minimum 5 held-out cases are independently scored useful
  and no case produces safety-critical flight advice. This is sequencing
  evidence, not an external outcome KPI.
- Selection time, generation validity, selected/dismissed decisions, capture
  completion, preview-to-shot fidelity, failures, and provenance are recorded
  with numerators, denominators, and `n` where applicable.
- Results keep deterministic fixture, synthetic footage, live provider, and
  real-drone evidence separate.
- The final claim is limited to the measured evidence; no better-shot,
  fewer-retakes, faster-production, or expert-replacement claim is made without
  comparator evidence.

**Verification:** Required repository checks, end-to-end test, evidence ledger
review, manual baseline, independent grading, and hostile claim review.

**Dependencies:** Issues 9.1–9.6 for deterministic release; Issue 9.7 only for
live-provider evidence.

## Issue 9 execution order and cut line

Implement in this order:

`9.1 → 9.2 → 9.3 → 9.4 → 9.5 → 9.6 → 9.8`

Issue 9.7 is intentionally deferred until the deterministic path has been
measured and a provider decision is approved. The deterministic cut line is
complete when a creator can request, view, select, and manually act on a clearly
labeled 10-second concept over a frozen source frame while story coverage
remains canonical and separate from preview generation.

## Issue 9 risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A generated preview invents geography, obstacles, or a flyable path | Label it as a creative reference; require manual safety notes; never expose a flight-control API |
| A preview is mistaken for proof the shot improved | Separate preview selection, capture completion, and result evaluation in state, events, UI, and metrics |
| Generation latency makes in-flight use distracting | Make generation asynchronous; recommend safe-hover/short-burst capture; show pending and stale states |
| Deterministic artifacts are mistaken for live AI quality | Show deterministic, synthetic, live, and real-drone provenance separately |
| The feature becomes a gallery or asset-management product | Keep state session-local and bounded; defer persistence, history browsing, accounts, and collaboration |
| Concepts are generic despite being visually attractive | Require active beat, missing coverage, visual objective, why-now, and independent grading |

## Issue 10: Production-grade real-place cinematography previs

**Status:** In progress after the Issue 9 deterministic cut line. The local
foundation from 10.1–10.3 and the dashboard safety pass are implemented; live
provider qualification, spatial previs, and pilot evidence remain gated.

**Goal:** Help a creator visualize the current real place through exactly three
illustrative 10-second cinematography concepts, then choose one concept and
receive a manual capture brief grounded in the current story beat and shot.
The feature remains advisory: it does not control a drone, generate a flight
plan, certify obstacle clearance, or prove that a captured shot improved.

**Why this is a separate issue:** Issue 9 proves the story-first interaction
and deterministic browser preview over a frozen frame. Production-grade real-
place previs adds source-asset handling, a qualified generation provider,
temporal and place-consistency gates, privacy and cost controls, and held-out
evaluation. It must not silently turn a deterministic illustration into a
claim of physical or geographic truth.

### Product modes and evidence boundary

The implementation must expose an explicit mode and eligibility contract:

| Mode | Required source | What the creator may infer | What CinePilot must not imply |
| --- | --- | --- | --- |
| `creative_reference` | Current still or short source clip | A visual direction for composition, reveal, parallax, or pull-away | That the place geometry, camera path, or obstacles are accurate |
| `place_consistent_previs` | Short source clip with sufficient visual continuity | A place-grounded visual reference whose quality checks passed | That the output is a safe or executable flight path |
| `spatial_previs` | Explicit multi-view capture and a validated depth or scene representation | A more spatially consistent reference for human planning | That reconstruction quality equals obstacle awareness or flight certification |

The first production release should target `creative_reference` and
`place_consistent_previs`. `spatial_previs` is a later gated capability, not a
requirement for the first provider integration. Every mode must retain the
visible statement:

> AI visualization — illustrative creative reference, not flight truth.

All evidence must distinguish deterministic demo, synthetic source, live
source, and provider-generated output. Any outcome claim requires a dated
manual baseline, an independent reviewer, mechanically disjoint held-out
cases, numerator/denominator/sample size, and a ratified update to
`docs/evidence-frame.md` before public presentation.

### Issue 10.1 — Freeze the production product and source contract

**Type:** Decision and contract

**Goal:** Define what “real-place visualization” means at each mode boundary
before choosing a provider or changing the dashboard.

**Work:**

- Specify accepted still, short-clip, and optional multi-view inputs, including
  duration, resolution, frame-rate, orientation, maximum bytes, and supported
  codecs.
- Define source provenance values for deterministic, synthetic, file, webcam,
  RTSP, RTMP, and provider-generated assets.
- Define minimum source-quality checks: readable subject, stable exposure,
  sufficient scene detail, no unsupported panorama assumptions, and no claim
  of depth unless the spatial mode is active.
- Define the exact server-owned fields for jobs, previews, observation
  snapshots, recommendation links, versions, timestamps, and provenance.
- Preserve the Issue 9 request body exactly:
  `{"duration_seconds": 10, "variation_count": 3}`.
- Keep the recommendation lifecycle as the only decision state machine.

**Acceptance criteria:** Contracts reject unknown fields and server-owned field
injection. Mode and source eligibility are explicit in API and UI copy. No
new gallery, account, persistence, flight-control, or autonomous behavior is
introduced.

**Verification:** Contract tests, API examples, claim-boundary review, and an
evidence-frame amendment only if the ratified decision-maker or success
criteria change.

**Dependencies:** Issue 9.2–9.6; `docs/evidence-frame.md`.

### Issue 10.2 — Ingest and freeze real-place source assets

**Type:** Backend and security

**Goal:** Make a creator-provided place observable, reproducible, and safely
available to an asynchronous visualization job.

**Work:**

- Add session-local source ingestion for a still and a bounded short clip;
  extract the server-owned observation snapshot at request time.
- Hash and label the source without accepting client IDs, timestamps, status,
  prompt versions, intent versions, asset references, or provenance fields.
- Validate content type, byte size, duration, dimensions, frame rate, and
  decodeability before enqueueing work.
- Store temporary source and rendered assets under a bounded session directory
  with restrictive names, TTL cleanup, and cleanup on success, failure, and
  cancellation.
- Return a clear `409` when no eligible observation exists and keep the
  deterministic synthetic fallback explicit in demo mode.

**Acceptance criteria:** A request always references one server-created,
immutable observation snapshot. A repeated request with the same fingerprint
uses the same snapshot and job. Temporary files are removed on every terminal
path and source provenance remains visible.

**Verification:** Upload and decode tests, snapshot immutability tests, hash
repeatability, cleanup tests, malformed-file tests, size-limit tests, and a
secret/PII and path-traversal review.

**Dependencies:** 10.1; existing `video_stream.py`, `state.py`, and event log.

### Issue 10.3 — Provider-neutral rendering runtime

**Type:** Backend architecture

**Goal:** Replace the demo-only renderer boundary with a provider-neutral,
retryable runtime without coupling the HTTP request path to an external call.

**Work:**

- Keep one canonical visualization job contract and one worker interface for
  deterministic and provider-backed renderers.
- Support at most one active job per session, idempotent duplicate requests,
  `409` for a conflicting request, bounded retries, timeout, cancellation,
  and terminal failure with an actionable reason.
- Record provider name/version, renderer version, source snapshot hash,
  profile, duration, output validation result, and timing as provenance owned
  by the server.
- Keep malformed provider output untrusted: validate MIME type, duration,
  frame rate, dimensions, decodeability, and preview count before `ready`.
- Add cost and concurrency budgets so a production deployment cannot create an
  unbounded provider bill.

**Acceptance criteria:** Deterministic and provider-backed renderers produce
  the same strict job/preview response shape. Worker failures do not kill the
  server. Retry behavior cannot create duplicate recommendation links or
  orphaned assets.

**Verification:** Lifecycle state-machine tests, duplicate/concurrency tests,
retry tests, cancellation tests, malformed output tests, timeout tests, and
event-log assertions.

**Dependencies:** 10.1–10.2; Issue 9 job and SSE contracts.

### Issue 10.4 — Qualify one real-place video provider

**Type:** Decision gate / external integration

**Goal:** Select one provider only if it can render three browser-playable,
10-second concepts conditioned on a real source without weakening CinePilot’s
claims boundary.

**Work:**

- Define a provider scorecard before testing: source conditioning, exact
  duration control, output format, temporal stability, subject/place
  preservation, profile adherence, latency, rate limits, cost, data retention,
  content policy, regional availability, and failure behavior.
- Test providers against a fixed internal fixture set plus held-out real-place
  cases authored by someone other than the prompt author.
- Keep provider prompts and fixtures separate from evaluation cases and record
  all attempted outputs, including failures and malformed responses.
- Obtain an explicit product decision on provider, budget ceiling, retention
  policy, and fallback behavior before integration.

**Acceptance criteria:** There is one approved provider or a documented “no
provider yet” decision. No live provider is enabled merely because its demo
looks attractive. Provider output is still labeled illustrative and never
translated into flight coordinates or safety claims.

**Verification:** Provider scorecard, legal/privacy review, cost estimate,
held-out independent grading, and hostile claim review. Do not call live
verification complete without a real configured key and an exercised live
session.

**Dependencies:** 10.1–10.3; manual baseline dated before the provider trial.

### Issue 10.5 — Place and temporal consistency quality gates

**Type:** Rendering quality and safety boundary

**Goal:** Prevent visually attractive but materially misleading previews from
  reaching the creator as if they were reliable place previs.

**Work:**

- Add deterministic and provider-independent checks for subject persistence,
  horizon/terrain/landmark retention, frame-to-frame flicker, sudden object
  invention or disappearance, exposure/color instability, profile adherence,
  and playable duration.
- Assign `pass`, `warn`, or `fail` with machine-readable reasons and show the
  result in the dashboard.
- Keep `warn` outputs visibly illustrative; do not treat an uncorrected output
  as presumed correct.
- Require manual review for spatial claims and reject any output that could be
  read as an obstacle-aware or flight-certified path.
- Ensure all three concepts use the frozen source observation for one job and
  retain the exact profile labels: descending reveal, lateral parallax, and
  restrained pull-away.

**Acceptance criteria:** Failed previews cannot be presented as ready. A job
  cannot become `ready` unless it has exactly three validated previews or
  reaches an explicit failed state. Quality reasons are safe text, not HTML.

**Verification:** Synthetic repeatability tests, fixture corruption tests,
  temporal-stability tests, place-drift review, profile-adherence review, and
  independent scoring of false-pass and false-fail cases.

**Dependencies:** 10.3–10.4.

### Issue 10.6 — Optional spatial previs from multi-view capture

**Type:** Deferred capability

**Goal:** Add a more spatially consistent reference only after
  `place_consistent_previs` demonstrates enough value and reliability.

**Work:**

- Define a bounded multi-view capture protocol and reject insufficient overlap,
  excessive motion blur, and ambiguous scale.
- Evaluate a depth or scene-representation pipeline with explicit uncertainty,
  versioned reconstruction inputs, and reproducible output artifacts.
- Render the same three creative profiles against the representation while
  preserving story context and recommendation linkage.
- Present geometric confidence and limitations as advisory context; never
  expose a flight path, obstacle map, drone command, or safety certification.

**Acceptance criteria:** The feature is opt-in, unavailable when the source
  contract is not met, and clearly labeled spatial reference rather than
  navigation truth. It can be disabled without affecting the existing
  creative-reference flow.

**Verification:** Multi-view fixture tests, reconstruction repeatability,
  held-out landmark/geometry review, failure-case review, and a separate
  evidence decision. No spatial-quality claim is made from synthetic fixtures
  alone.

**Dependencies:** 10.1–10.5 and an approved evidence-frame amendment.

### Issue 10.7 — Production dashboard workflow and manual capture brief

**Type:** Frontend and creator workflow

**Goal:** Make the production path useful inside the existing story-first
dashboard without turning it into a gallery or automation console.

**Work:**

- Keep the current story, beat, shot contribution, missing coverage, and
  critique panel visible as the primary context.
- Add source selection/status, mode, provenance, 10-second duration, three
  playable previews, story purpose, visual objective, why now, manual
  execution guidance, safety notes, quality result, and linked capture brief.
- Keep Select and Dismiss on the existing recommendation decision endpoint;
  make retries idempotent and never mark coverage, capture, or recommendation
  completion automatically.
- Add loading, empty, validation-error, failed-job, stale-SSE,
  disconnected-source, unavailable-provider, and retry states.
- Render every model/provider string with `textContent` or an equivalent safe
  text API. Do not expose raw prompts, internal IDs, or untrusted markup.

**Acceptance criteria:** A creator can request, watch progress, play all three
  concepts, select or dismiss one, and read the manual brief without leaving
  the story-first dashboard. The critique panel remains functional as a
  secondary surface. The safety disclaimer is visible beside every preview.

**Verification:** Dashboard JavaScript parse check, browser interaction and
  screenshot verification, keyboard/focus review, XSS fixture test, stale-SSE
  recovery test, and end-to-end selection/dismissal tests.

**Dependencies:** 10.1–10.5; existing dashboard and recommendation APIs.

### Issue 10.8 — Pilot readiness, evaluation, and release gate

**Type:** Evidence and release

**Goal:** Decide whether the real-place workflow is ready for a limited pilot
  based on creator decisions and independent usefulness, not visual novelty.

**Work:**

- Define the held-out set before the pilot and keep it disjoint from prompt
  examples and provider-tuning fixtures.
- Run the scheduled manual baseline before CinePilot on the same cases.
- Have an independent reviewer score story advancement, specificity,
  technical plausibility as a manual concept, place fidelity, profile
  adherence, and usefulness; keep deterministic, synthetic, live-provider,
  and real-drone evidence in separate rows.
- Record selection time, valid-job rate, preview pass/warn/fail counts,
  selected/dismissed decisions, manual-brief completeness, failures, and
  provenance with numerators, denominators, and `n`.
- Run a hostile review for claims that accidentally imply improved shots,
  fewer retakes, faster production, expert replacement, obstacle awareness,
  or safe flight.

**Acceptance criteria:** A limited pilot is approved only when the evidence
  frame’s baseline, independent review, and claim review are complete. The
  release report states what was measured and what was not. If the gate fails,
  the product falls back to deterministic creative reference or remains
  internal; it does not silently promote provider output.

**Verification:** Full repository checks, synthetic-server smoke test, browser
  verification, clean-worktree review, evidence-ledger audit, manual baseline,
  independent grading, and release sign-off.

**Dependencies:** 10.1–10.7; ratified `docs/evidence-frame.md`.

## Issue 10 execution order and cut line

Implement in this order:

`10.1 → 10.2 → 10.3 → 10.4 → 10.5 → 10.7 → 10.8`

Implement `10.6` only after the place-consistent mode clears its own evidence
gate. The first production cut line is complete when a creator can provide an
eligible real-place source, request exactly three 10-second concepts, receive
three quality-gated previews linked to the current recommendation, choose one
or dismiss it, and read a manual capture brief with provenance and safety
boundaries visible. Provider absence must degrade to the deterministic
creative-reference flow rather than block the dashboard.

## Issue 10 non-goals

- No autonomous drone behavior, flight-plan generation, waypoint output,
  obstacle avoidance, geofencing, or safety certification.
- No claim that a preview predicts the captured shot, improves the shot, reduces
  retakes, accelerates production, or replaces a cinematographer.
- No live-video generation, unrestricted long-form generation, 3D gallery,
  persistence, accounts, collaboration, or asset marketplace in this cut.
- No provider lock-in before the qualification gate and no raw provider output
  bypassing the strict server contract.

## Issue 10 risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A provider changes the real place or invents objects | Freeze one observation, run place/temporal gates, expose pass/warn/fail, and fail closed for material drift |
| A creator mistakes cinematic plausibility for physical feasibility | Keep the disclaimer beside every preview and manual safety notes in the capture brief; never emit flight commands |
| Real-place uploads expose private or licensed material | Session-local bounded retention, explicit provenance, deletion/TTL, provider retention review, and no account sharing in this cut |
| Three outputs are technically valid but creatively repetitive | Keep fixed but distinct profiles, score profile adherence, and allow independent reviewers to mark repetition |
| Provider latency or cost makes the workflow unusable | Asynchronous jobs, budgets, bounded retries, visible progress, and deterministic fallback |
| Quality metrics become unsupported product claims | Treat them as supporting diagnostics; require the dated baseline and independent held-out review before outcome language |
| Spatial reconstruction creates false confidence | Defer 10.6, display uncertainty, and prohibit navigation/safety interpretations |
