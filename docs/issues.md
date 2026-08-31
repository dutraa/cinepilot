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
