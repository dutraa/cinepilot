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
