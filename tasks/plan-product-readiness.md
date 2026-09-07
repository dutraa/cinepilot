# CinePilot Product-Readiness Implementation Plan

## Overview

This plan converts the repository and browser audit into an ordered set of
implementation slices. The objective is to move CinePilot from a deterministic
story-aware demonstration to a trustworthy pilot foundation for a narrowly
defined filmmaking user. It covers the findings in the audit: product wedge,
truthful state semantics, provenance, UX completion, async failure handling,
agent reliability, evidence integrity, evaluation, packaging, and deployment.

This plan does not authorize autonomous drone control, editing automation,
multi-agent orchestration, or claims that CinePilot improves production
outcomes. Those remain explicitly out of scope until separate evidence and
safety decisions exist.

The existing visualization-specific plan in `tasks/plan.md` is preserved. Its
completed or pending work should be reconciled with CP-05 and CP-06 below
before implementation begins.

Implementation items remain tracked in the project’s designated issue ledger,
`docs/issues.md`, per `AGENTS.md`; this document is the cross-cutting execution
plan and dependency index. New issue entries should be created there only
after CP-00 is ratified.

## Execution update — 2026-09-08

The product direction is now fixed for a local, session-scoped director/DP
pilot: creator-entered story context, live RTMP/RTSP source truth, explicit
between-takes analysis, one bounded Gemini multimodal request, one ranked next
shot plus two alternatives, manual capture confirmation, and fresh follow-up
evaluation. Issues 11–20 in `docs/issues.md` are the implementation ledger.

The initial implementation establishes the contracts and dashboard foundation.
Live Gemini, real RTMP/RTSP, independent usefulness, and production outcome
claims remain unverified until the external systems and evidence protocol are
actually exercised.

## Current baseline

- The deterministic synthetic story loop runs in a browser and the repository
  checks currently pass: 46 tests, Ruff, Python AST parsing, dashboard
  JavaScript parsing, and synthetic smoke checks.
- The core demo is not yet a production pilot. The live path was not exercised
  with a real Gemini key or real camera/drone source.
- The browser journey is understandable but still demo-shaped: no visible
  guidance banner, no beat activation control, weak distinction between
  observed and inferred state, and incomplete async/error affordances.
- The repository has no license file, hosted URL, CI/deployment artifact, or
  verified public-runtime integration evidence. Public-repository status is
  **Unverified**.
- The evaluation manifest is a template with no evaluation assets, and the
  manual baseline/independent review required by the evidence frame are not
  complete. Outcome claims are therefore not available.

## Readiness target

The first honest target is:

> A single creator or small production team can give CinePilot a story brief,
> current beat, shot intent, and a live, prerecorded, or synthetic source;
> receive a bounded, explainable next-shot or current-shot recommendation;
> understand its provenance and confidence; accept or reject it; mark what was
> actually captured; and recover safely from provider, source, and connection
> failures.

The implementation must prove this in a synthetic path first, then in a
held-out manual comparator and a clearly labeled live-source pilot. It must not
use selection, completion, or model schema validity as a proxy for improved
footage.

## Architecture decisions and invariants

These are safe defaults because they preserve the existing mission and
technical boundaries. The open questions below must be answered before work
that depends on them.

1. `AppState` remains the canonical state owner. Grafana and browser state are
   observers, not sources of truth.
2. Every state transition carries a server-owned session ID, event ID,
   correlation ID, intent version, story version, observation ID where
   applicable, actor/source, timestamp, and provenance.
3. Model output is untrusted input. Pydantic validation, semantic validation,
   bounded tool policy, and safe text rendering happen before mutation or
   display.
4. The product exposes recommendations, never flight commands. Safety notes
   and manual capture briefs remain advisory and creator-approved.
5. Synthetic, prerecorded, live-camera, live-Gemini, and real-drone evidence
   are separate strata. A result from one stratum cannot be generalized to
   another.
6. A recommendation lifecycle is explicit and monotonic:
   `recommended -> selected -> acted -> completed`, with `dismissed` as a
   terminal alternative. Selection never implies action or coverage.
7. “Observed contribution” is only populated by a frame/clip observation;
   story inference and recommendation rationale use distinct fields and labels.
8. All asynchronous operations expose loading, empty, error, stale,
   disconnected, duplicate, and unavailable-provider states.

## Open questions requiring your answer

The plan can be implemented in dependency order up to the first decision gate,
but these choices materially change scope and acceptance criteria.

1. **Initial customer:** Should the first pilot target (a) a solo creator or
   drone pilot, (b) a small production team with director/DP roles, or (c) a
   filmmaking company with producer-level project oversight? My recommended
   default is **(b)** because it matches the current story/coverage workflow
   without requiring enterprise permissions immediately.
2. **Near-term objective:** Is the immediate release primarily (a) Agentic
   Cinema submission compliance by the Sep 9 deadline, (b) a credible private
   pilot, or (c) both with compliance as a thin parallel track? My recommended
   default is **(c)**; it prevents hackathon requirements from distorting the
   product architecture.
3. **Runtime constraint:** Do you have a real Gemini/Google Cloud key and a
   selected Partner integration to exercise in a hosted deployment? If yes,
   which Partner track should be treated as mandatory? If no, the plan will
   label live AI and hosted compliance as blocked/unverified rather than fake
   them.
4. **Data boundary:** For the first pilot, should projects remain local and
   session-scoped, or do you want shared persistent projects, accounts, and
   roles in this release? My recommended default is **local pilot first**;
   persistence should follow creator evidence, not precede it.
5. **Evidence access:** Can you provide at least 5–10 held-out clips/story
   cases and one independent reviewer who did not author the prompt examples?
   Without them, the plan can build the measurement harness but cannot claim
   usefulness or outcome improvement.

## Dependency graph

```text
Decision gate (customer / objective / runtime / data)
  -> CP-01 product and evidence contract
      -> CP-02 canonical state and provenance
          -> CP-03 event/evidence instrumentation
              -> CP-04 source and live-loop reliability
                  -> CP-05 recommendation lifecycle and cinematic semantics
                      -> CP-06 browser decision surface
                          -> CP-07 visualization/previs truthfulness
                              -> CP-08 failure-path and browser verification
                                  -> CP-09 held-out evaluation and pilot evidence
                                      -> CP-10 packaging, hosting, and release

CP-10 hackathon compliance can run in parallel after the runtime decision.
CP-11 persistence/collaboration depends on the data-boundary decision.
CP-12 broader inputs/providers depends on pilot evidence from CP-09.
```

## Ordered task list

The CP identifiers below are planning identifiers. Before implementation, map
each approved item to one or more issue-ledger entries in `docs/issues.md` and
keep acceptance criteria and verification steps there in sync.

### Phase 0: Decisions and release boundaries

## Task CP-00: Ratify the first customer, release objective, and evidence frame

**Description:** Resolve the five open questions above and update the existing
evidence frame with the chosen decision-maker, scoreboard mapping, baseline
date, comparator, claim boundaries, and evidence strata. Do not invent a KPI
or percentage while the external scoreboard remains unknown.

**Acceptance criteria:**

- [ ] The first user and highest-value decision are named in plain language.
- [ ] Every headline measure has a decision-maker scoreboard mapping or is
      explicitly marked supporting-only.
- [ ] Baseline, independent reviewer, held-out cases, and disjointness checks
      have owners and dates before any outcome presentation.
- [ ] Hackathon compliance and pilot product work have separate release gates.

**Verification:** Review `docs/evidence-frame.md`, `docs/eval-protocol.md`, and
`docs/issues.md` against the answers; confirm all proposed claims have an
explicit numerator, denominator, provenance stratum, and comparator.

**Dependencies:** None; requires your answers.

**Files likely touched:** `docs/evidence-frame.md`, `docs/eval-protocol.md`,
`docs/issues.md`, `README.md`

**Estimated scope:** Medium

### Phase 1: Contracts and canonical truth

## Task CP-01: Freeze the product vocabulary and decision contract

**Description:** Define the server-owned schemas and state transitions for
intent, observation, story beat, coverage, critique, recommendation, preview,
creator decision, and source provenance. Separate observed facts from story
inference, recommendations, creator actions, and completed coverage. Reject
unknown fields and invalid enums before state mutation.

**Acceptance criteria:**

- [ ] Every recommendation has diagnosis, concrete change, rationale,
      priority, why-now, technical plausibility, safety notes, and evidence
      references where available.
- [ ] Lifecycle transitions are monotonic and idempotent; completion cannot
      mark a recommendation or unrelated beat complete by inference alone.
- [ ] Intent/story/observation versions are server-owned and stale writes are
      rejected or safely no-op.

**Verification:** Add failing-first unit tests for unknown fields, stale
versions, duplicate requests, illegal transitions, cross-beat completion, and
missing observation provenance; run focused state/schema tests.

**Dependencies:** CP-00

**Files likely touched:** `schemas.py`, `domain.py`, `state.py`,
`tests/test_state.py`, `tests/test_schemas.py`

**Estimated scope:** Large; split into schema and transition subtasks before
implementation if it exceeds one focused session.

## Task CP-02: Make source and session provenance truthful

**Description:** Establish one provenance object used by video manager,
`AppState`, API snapshots, SSE, health, visualizations, and the dashboard.
Correct the RTMP-to-synthetic fallback mismatch, expose configured versus
active source, frame availability, freshness, and provider status, and make
story/session identity explicit when no demo story is loaded.

**Acceptance criteria:**

- [ ] When RTMP/RTSP/file/webcam fails, UI/API/event log agree that the active
      source is synthetic fallback and retain the configured source separately.
- [ ] `frames_sent`, frame freshness, and feed availability describe the actual
      stream rather than deterministic-demo defaults.
- [ ] Health distinguishes process health, source health, provider health, and
      story/session readiness.

**Verification:** Add source-failure tests and run a browser check for valid
synthetic, unavailable RTMP, disconnected SSE, and no-story states.

**Dependencies:** CP-01

**Files likely touched:** `video_stream.py`, `state.py`, `server.py`,
`schemas.py`, `tests/test_video_stream.py`

**Estimated scope:** Medium

## Task CP-03: Instrument canonical evidence and audit history

**Description:** Expand the append-only local event log so every material
decision is reconstructable: intent versions, observations/frame metrics,
recommendation attempts including rejected/malformed attempts, tool calls,
creator decisions, guidance, source/provider transitions, visualization jobs,
and errors. Add correlation/session IDs, safe redaction, retention/rotation,
and explicit event schemas. Grafana remains optional and non-canonical.

**Acceptance criteria:**

- [ ] A single run can be replayed from events to explain what the agent saw,
      recommended, what the creator selected/acted/completed, and why.
- [ ] Failed and malformed attempts remain in denominators and are not silently
      dropped.
- [ ] Secrets, raw sensitive media, and unbounded model text are not written
      to the event log.

**Verification:** Event replay test; malformed-tool and provider-failure tests;
redaction test; inspect a complete synthetic JSONL run and compare it with the
API/SSE timeline.

**Dependencies:** CP-01

**Files likely touched:** `event_log.py`, `state.py`, `tools.py`,
`director_agent.py`, `tests/test_event_log.py`

**Estimated scope:** Large; split event schema/replay from retention/redaction.

### Phase 2: Reliable cinematic decision loop

## Task CP-04: Harden the agent boundary and tool execution

**Description:** Make malformed Gemini Live events, malformed function-call
arguments, disconnects, duplicate calls, semantic-invalid recommendations, and
provider unavailability recoverable. Move parsing inside per-call protection,
validate all tool payloads with strict schemas, bound speech/guidance to a
server-owned policy, and add prompt-injection boundaries for story and visual
text.

**Acceptance criteria:**

- [ ] A malformed function call cannot kill the receiver or corrupt canonical
      state.
- [ ] Unknown tools, arbitrary speech instructions, invalid recommendation
      semantics, and unsafe values are rejected with a logged reason.
- [ ] Reconnect/backoff and provider-unavailable behavior preserves the last
      trusted state and presents a recoverable status to the creator.

**Verification:** Fault-injection tests for malformed args, unknown tools,
duplicate calls, disconnect/reconnect, timeout, and prompt-injection strings;
live verification is reported only if a real key/session is exercised.

**Dependencies:** CP-01, CP-03

**Files likely touched:** `director_agent.py`, `tools.py`, `director_prompt.py`,
`schemas.py`, `tests/test_director_agent.py`

**Estimated scope:** Large; split parser/reconnect and tool-policy work.

## Task CP-05: Correct story coverage and recommendation semantics

**Description:** Fix the domain behavior that can mark the wrong beat covered,
allow future-beat recommendations without an explicit reason, and present
“current shot contribution” as a grounded observation rather than a
recommendation-derived assertion. Add active-beat selection only if the chosen
customer workflow requires it; otherwise make the current-beat rule explicit.

**Acceptance criteria:**

- [ ] Only an explicitly completed, selected/acted recommendation can add
      coverage, and it can only advance the intended beat.
- [ ] Current contribution, missing coverage, inferred story purpose, and
      recommendation rationale render in separate fields with provenance.
- [ ] Recommendation invalidation is defined for a new intent, new observation,
      source change, and beat transition.

**Verification:** State-machine tests for all beat transitions and retries;
fixture tests for current/future beat recommendations; browser verification
that completion advances only the selected intended coverage.

**Dependencies:** CP-01, CP-02

**Files likely touched:** `state.py`, `domain.py`, `server.py`,
`tests/test_story_flow.py`, `tests/test_recommendations.py`

**Estimated scope:** Large; split transition correctness from invalidation.

## Task CP-06: Rebuild the decision-first browser journey

**Description:** Make the dashboard answer the creator’s questions in order:
story, beat, current contribution, missing coverage, best next shot, and exact
advisory action. Add visible guidance, provenance labels, intent versioning,
clear selection versus action versus completion, beat controls where approved,
and usable empty states. Remove misleading telemetry emphasis from the primary
decision surface.

**Acceptance criteria:**

- [ ] The screen clearly distinguishes observed, recommended, selected, acted,
      and completed states.
- [ ] Guidance is visible and, when enabled, browser speech is invoked only
      for bounded advisory cues; it never implies flight control.
- [ ] Every async control has loading, success, error, retry, disabled, and
      stale/disconnected behavior; failed actions re-enable safely.
- [ ] Keyboard focus, labels, contrast, reduced motion, and screen-reader
      status updates meet the applicable WCAG 2.1 AA checks for this surface.

**Verification:** Browser interaction matrix, keyboard-only pass, accessibility
tree review, visual review at the supported viewport, and dashboard JS parse.

**Dependencies:** CP-02, CP-05

**Files likely touched:** `templates/index.html`, `server.py`, `state.py`,
`tests/test_server.py`

**Estimated scope:** Large; split markup/state rendering from accessibility and
failure states.

## Task CP-07: Make visualization and previs claims technically honest

**Description:** Reconcile the existing visualization plan with the product
contract. Label deterministic previews as 2D creative references over a frozen
source frame, distinguish them from generated video and physical camera paths,
preserve provenance, and ensure selecting a preview does not complete coverage.
Decide whether the deferred live provider is in scope only after runtime,
latency, cost, failure, and spatial-drift evidence exists.

**Acceptance criteria:**

- [ ] UI and README never describe the deterministic animation as generated
      footage, a flight plan, or proof of shot quality.
- [ ] Preview selection, capture/action, completion, and post-capture evaluation
      are separate events and metrics.
- [ ] Request deduplication, in-flight conflicts, eviction, malformed profiles,
      and source-frame absence are tested and visible.

**Verification:** Visualization API/state tests; browser select/complete flow;
claim-boundary review against `tasks/plan.md`, `README.md`, and
`docs/evidence-frame.md`.

**Dependencies:** CP-03, CP-05, CP-06

**Files likely touched:** `visualization.py`, `state.py`, `server.py`,
`templates/index.html`, `tests/test_visualization.py`

**Estimated scope:** Medium

### Phase 3: Evidence and pilot foundation

## Task CP-08: Build the held-out evaluation and comparator harness

**Description:** Populate the evaluation protocol with mechanically disjoint
held-out cases and prompt examples. Implement a repeatable manual baseline and
CinePilot scoring workflow for actionability, story advancement, specificity,
technical plausibility, safety, selection time, flyability, and independent
usefulness. Keep synthetic, live, and real-drone results separate.

**Acceptance criteria:**

- [ ] Evaluation assets have hashes and a passing disjointness check.
- [ ] Manual and CinePilot arms use the same cases and rubric, with failures in
      the denominator.
- [ ] Reports include numerator, denominator, `n`, provenance stratum, and
      reviewer independence; no internal metric is promoted to headline.

**Verification:** Run the manifest validator, baseline run, independent scoring,
and evidence-ledger review; record the dates before any demo claim.

**Dependencies:** CP-00, CP-03, CP-05

**Files likely touched:** `fixtures/eval-manifest.json`, `docs/eval-protocol.md`,
`docs/evidence-frame.md`, `tests/test_eval_manifest.py`

**Estimated scope:** Medium

## Task CP-09: Add pilot-grade project boundary only for the chosen customer

**Description:** Based on the answer to the data-boundary question, either
formalize the local session model as an explicit pilot boundary or add the
minimum project persistence, account, role, and audit model required by the
chosen user. Do not add a database merely because it is conventional.

**Acceptance criteria:**

- [ ] A creator understands what is saved, where it is saved, and who can see
      it.
- [ ] Restart, duplicate browser request, and concurrent-session behavior are
      defined and tested for the selected boundary.
- [ ] If shared projects are in scope, actor permissions and immutable audit
      history cover intent changes, recommendations, decisions, and media
      references.

**Verification:** Fresh-process/restart test, two-session isolation test, and
role/audit tests if persistence is approved; otherwise documentation review
that confirms local-only claims.

**Dependencies:** CP-00, CP-03, CP-06

**Files likely touched:** `server.py`, `state.py`, `event_log.py`,
`docs/architecture.md`, plus persistence files only if approved

**Estimated scope:** Medium for local boundary; Large for shared persistence.

## Task CP-10: Package, secure, and host a repeatable release

**Description:** Make installation and operation credible: pin or constrain
dependencies, resolve the observed `google-genai`/`google-auth` environment
conflict, add configuration validation, secret handling, request limits,
basic auth or network boundary appropriate to the pilot, structured logs,
health/readiness probes, CI, startup/shutdown cleanup, and a documented hosted
deployment. Add the missing license file and replace placeholder repository
instructions.

**Acceptance criteria:**

- [ ] A clean environment installs from documented files and starts with one
      documented command.
- [ ] Secrets are supplied through environment/configuration and never logged;
      the app fails clearly when live provider configuration is absent.
- [ ] Hosted URL, source provenance, dependency versions, health checks, and
      rollback/recovery instructions are documented.
- [ ] A top-level license file exists and the public repository/runtime status
      is verified rather than asserted.

**Verification:** Clean-environment install, CI checks, secret scan, dependency
check, hosted smoke test, restart test, and `git diff --check`/clean-worktree
review.

**Dependencies:** CP-02, CP-04, CP-08; runtime choice from CP-00

**Files likely touched:** `requirements.txt`, `requirements-dev.txt`,
`.env.example`, `README.md`, `server.py`, deployment/CI files

**Estimated scope:** Large; split packaging, security, and hosting.

### Phase 4: Agentic Cinema compliance (parallel release track)

## Task CP-11: Satisfy and verify the competition/runtime requirements

**Description:** If the submission objective is confirmed, select one allowed
Partner track and make the Google Cloud plus Partner service visible in the
actual runtime path. Produce the hosted project URL, public open-source repo
with detectable license, reproducible setup, and a three-minute English
demo/subtitles. Keep the demo behavior faithful to the hosted build.

**Acceptance criteria:**

- [ ] The selected Google Cloud and Partner services are imported and actually
      called at runtime, with logs/evidence proving the call.
- [ ] No prohibited non-Google AI model, framework, or API is used.
- [ ] Hosted URL, public repository, license, demo video, and source/runtime
      evidence are available before submission.
- [ ] The demo states deterministic versus live behavior and does not claim
      unverified outcomes.

**Verification:** Fresh-machine or clean-container run; inspect runtime logs;
record hosted browser journey; run the three-minute demo against the same
build; final rule-by-rule checklist.

**Dependencies:** CP-00, CP-04, CP-10

**Files likely touched:** `README.md`, `docs/demo-script.md`, `main.py`,
`director_agent.py`, deployment/CI files

**Estimated scope:** Large and externally blocked until runtime credentials and
Partner choice are confirmed.

### Phase 5: Post-pilot expansion

## Task CP-12: Improve cinematic intelligence using creator evidence

**Description:** Use independent review and creator corrections to improve
recommendation specificity, story advancement, why-now reasoning, and
technical plausibility. Add only the smallest model/prompt or deterministic
heuristic changes that address measured failure modes; do not optimize generic
“cinematic” language.

**Acceptance criteria:**

- [ ] Each quality change names the failure mode, comparator, metric, and
      provenance stratum it is intended to move.
- [ ] Recommendations remain bounded to one to three high-impact actions and
      include an actionable verification cue.
- [ ] Regression fixtures cover previous failures and malformed outputs.

**Verification:** Re-run held-out comparator, independent review, regression
suite, and claim-boundary review.

**Dependencies:** CP-08, CP-09

**Files likely touched:** `director_prompt.py`, `director_agent.py`,
`demo_provider.py`, `tests/test_director_agent.py`, `docs/eval-protocol.md`

**Estimated scope:** Medium per measured failure mode

## Task CP-13: Add broader inputs and integrations only after the wedge works

**Description:** Extend beyond the initial source only when the same decision
engine has evidence on the first wedge. Add uploaded footage, phones,
webcams, other camera sources, editing integrations, or autonomous controls as
separate contracts with their own provenance, safety, and evaluation strata.

**Acceptance criteria:**

- [ ] Each new input has explicit support status, failure behavior, and a
      separate evaluation set.
- [ ] No README or demo claim generalizes from drone/synthetic evidence to all
      footage until the new path is implemented and evaluated.
- [ ] Autonomous control remains absent unless a separate safety review and
      authorization boundary are approved.

**Verification:** Per-input contract tests, source-failure browser checks,
security review, and evidence-frame amendment before public claims.

**Dependencies:** CP-09, CP-12

**Files likely touched:** `video_stream.py`, `server.py`, `schemas.py`,
`docs/architecture.md`, source-specific tests

**Estimated scope:** Large per input/integration

## Checkpoints

### Checkpoint A: Before implementation

- [ ] CP-00 questions answered and evidence frame ratified.
- [ ] Existing visualization plan reconciled; no duplicate contracts are
      introduced.
- [ ] Scope is split into S/M implementation sessions; no XL task is started
      as one change.

### Checkpoint B: After CP-01 through CP-04

- [ ] State transitions, provenance, event replay, malformed model calls, and
      source fallback are covered by tests.
- [ ] A synthetic run can explain every material state change from the event
      log.

### Checkpoint C: After CP-05 through CP-07

- [ ] Browser flow correctly distinguishes observed/recommended/selected/
      acted/completed.
- [ ] Story completion and visualization selection cannot falsely advance
      coverage.
- [ ] Keyboard/accessibility and all async state variants are verified.

### Checkpoint D: After CP-08 through CP-11

- [ ] Held-out baseline and independent review are complete before outcome
      claims.
- [ ] Clean install, hosted smoke, live-provider status, and public packaging
      are verified or explicitly marked Unverified/Blocked.
- [ ] Competition checklist passes if that release objective is selected.

### Checkpoint E: Pilot release

- [ ] All required repository checks pass.
- [ ] The chosen customer can complete the core loop without operator-only
      knowledge.
- [ ] The evidence package includes denominators, strata, comparator, and
      known failure modes.

## Readiness labels to use throughout

| Capability | Current label | Exit condition |
| --- | --- | --- |
| Deterministic synthetic story loop | Demo | CP-05 through CP-08 pass |
| Current-shot critique with real Gemini | Not yet / Unverified | Real key/session plus fault tests and evidence |
| Live RTMP/RTSP/webcam use | Not yet | Correct provenance, reconnect behavior, source test |
| Visualization/previs | Demo | Honest 2D-reference labeling and lifecycle tests |
| Creator usefulness | Not yet | Held-out comparator and independent review |
| Local single-session pilot | Pilot candidate | CP-01 through CP-10 pass |
| Shared production-team product | Not yet | CP-09 persistence/roles plus pilot evidence |
| Hosted hackathon submission | Not yet | CP-10 and CP-11 rule-by-rule verification |
| Production deployment | Not yet | Security, reliability, support, retention, and repeated pilot evidence |

## Major risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Customer is not selected before implementation | High | Stop at CP-00; keep current local advisory wedge as the recommended default |
| Hackathon integration consumes product scope | High | Separate CP-11; do not make Partner plumbing the core domain contract |
| Demo telemetry implies false health or AI activity | High | CP-02 provenance contract and browser labels; zero ambiguous status copy |
| Model output kills the live receiver or corrupts state | High | CP-04 strict boundary and fault injection before live claims |
| Recommendation selection is mistaken for usefulness | High | CP-08 comparator and independent review; selection/completion remain supporting signals |
| Persistence creates security/support obligations prematurely | Medium | CP-09 is gated by customer/data decision |
| “Cinematic” output remains generic | High | CP-12 optimizes measured failure modes tied to story advancement and concrete changes |
| Competition deadline leaves no time for evidence | High | Run CP-10/CP-11 in parallel only after CP-00; publish no outcome claims without the baseline gate |

## Required implementation verification for every slice

Run the focused tests first, then the repository baseline:

```text
python -m pytest -p no:cacheprovider -q
ruff check --no-cache .
Python AST parse for all project modules
Node parse for dashboard JavaScript
Synthetic server smoke: /, /health, /api/state, /api/intent, /video_feed
Browser screenshot and interaction check for dashboard changes
git diff --check
Secret scan
Clean-worktree check
```

Live Gemini, hosted, and real-drone verification must be reported separately
and only as complete when the real external system was exercised.

## Definition of done for this plan

The product is ready for the selected pilot only when CP-00 through CP-10 are
complete, their checkpoints pass, the evidence frame is current, and the final
claims are narrower than or equal to the evidence. CP-11 is additionally
required for a competition submission. CP-12 and CP-13 are expansion work, not
prerequisites for the first honest pilot wedge.
