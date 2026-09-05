# Implementation Plan: Visualize cinematic concepts

## Overview

Add an advisory “visualize” workflow to CinePilot. From the current story beat,
current footage observation, and cinematic intent, a creator can request exactly
three illustrative cinematography concepts targeted at a 10-second shot. The
creator can preview the concepts in the existing story-first dashboard, select
one, and receive a manual capture brief. The actual drone flight and the quality
of the captured shot remain outside the system and are evaluated separately.

The first release is an explicit deterministic demo path. It must produce a
repeatable, browser-playable 10-second concept animation from a server-captured
latest JPEG observation (or the seeded synthetic scene) without Gemini, a drone,
RTMP, or Grafana. This is a motion concept over a source frame, not a
geographically faithful reconstruction or a new AI-generated video. A
separately labeled live video-generation provider may be added behind the same
contracts later.

## Evidence Frame

The existing working frame in `docs/evidence-frame.md` is the governing frame
for this slice. Its decision-maker is the CinePilot founder/team deciding
whether the product deserves continued pilot work and demo investment. The
external creator scoreboard is still unverified, so no visualization metric is
a headline KPI yet.

| Decision-maker measure | Supporting visualize measure | Measurement | Baseline | Headline? |
| --- | --- | --- | --- | --- |
| To be discovered | Time to first useful concept | Request to first preview a creator can understand | Timed manual concept-selection workflow before the demo on 5–10 held-out cases | No |
| To be discovered | Useful concept rate | Independent reviewer marks story advancement, specificity, technical plausibility, and usefulness | Manual baseline on the same held-out cases | No |
| To be discovered | Preview-to-shot fidelity | Independent comparison of selected concept against manually captured result | Same-case manual comparison; failures remain in the denominator | No |

The baseline gate is scheduled as follows: freeze and run the manual baseline
on 2026-09-06, complete independent scoring by 2026-09-07, and permit the first
outcome presentation on 2026-09-08 or later only when both are complete. If the
dates slip, show deterministic behavior only and make no outcome claim. Keep
fixture, synthetic, live Gemini/video-generation, and real-drone evidence as
separate strata. Every rate must include numerator, denominator, and `n`;
generated preview selection is creator behavior, not proof that the resulting
shot improved.

## Product and architecture decisions

- Keep visualization in the existing story-first dashboard as a focused panel
  or drawer. A separate gallery/history page is deferred until asset browsing
  becomes a real workflow.
- Treat a visualization as a creative reference. It is not a flight plan,
  obstacle map, camera-path guarantee, or evidence that a shot was captured.
- Request generation asynchronously. The creator can continue monitoring the
  source while a job is pending, but the UI should recommend requesting during
  a safe hover or after a short evidence burst rather than continuously during
  maneuvering.
- At request time, the server freezes the latest available frame into a
  session-local observation snapshot. In deterministic mode, the seeded
  synthetic scene is the fallback snapshot. The snapshot is referenced by a
  server-owned observation ID and is never supplied by the browser.
- Use one in-process worker with at most one rendering job per session. A
  repeated request fingerprint returns the existing job; a different request
  while one is rendering returns `409`. Jobs are session-local and temporary
  preview snapshots are cleaned up when the job is evicted or the process ends.
- The server derives story version, active beat, current observation, intent
  version, IDs, timestamps, provenance, and status. Browser/provider input must
  not invent those fields.
- The deterministic provider renders a fixed 10-second browser animation over
  the frozen source frame for three named archetypes. Their screen-space
  recipes are fixed: `descending_reveal` scales from 1.00 to 1.25 while
  revealing downward; `lateral_parallax` pans across a 1.08 scale while holding
  the subject on the right third; `restrained_pull_away` scales from 1.18 to
  1.00 with a slight upward drift. These are illustrative 2D transforms, not
  physical camera paths. The animation profile is a server-owned enum, not
  executable flight instructions.
- A future live provider can use image/video-conditioned generation, but it is
  optional and must use the same job, provenance, validation, and selection
  boundaries. It must not block the deterministic release cut line.
- Each visualization preview is attached to exactly one canonical
  `ShotRecommendation`. The existing recommendation lifecycle is the only
  selection/completion/dismissal lifecycle; no second preview decision state is
  introduced. Selecting a visualization selects its linked recommendation.
- Selecting a recommendation creates or exposes a manual next-shot brief; it
  does not mark coverage complete. Only the creator’s later completion action
  can advance story coverage, and the captured result must be evaluated
  separately.

## Contract outline

The exact Pydantic fields are to be finalized in the first implementation
issue, with tests written before the implementation:

```text
VisualizationRequestInput
  duration_seconds: exactly 10
  variation_count: exactly 3

VisualizationJob
  job_id, request_fingerprint, story_version, beat_id, observation_id
  intent_version, requested_at, started_at, completed_at
  status: requested | rendering | ready | failed
  provenance, previews[], error

VisualizationPreview
  preview_id, job_id, recommendation_id, title
  cinematography_summary, story_purpose, visual_objective, why_now
  manual_execution_guidance, safety_notes, duration_seconds
  animation_profile, source_frame_available, provenance, created_at

Existing ShotRecommendation
  remains the canonical selected/completed/dismissed decision record
```

The request shape contains no server-owned IDs, timestamps, statuses, asset
references, prompt versions, intent versions, or provenance. The server creates
the observation snapshot, job ID, preview IDs, linked recommendation IDs,
timestamps, and provenance. The dashboard retrieves the frozen source frame
with `GET /api/visualizations/{job_id}/source-frame`; the browser animates only
the validated `animation_profile` over that image.

## Task List

Tasks are tracked in the canonical local issue tracker, `docs/issues.md`.

### Phase 1: Boundary and contracts

- [ ] Issue 9.1: Freeze visualization semantics, provenance, fixture, and rubric
- [ ] Issue 9.2: Add strict visualization job and preview contracts

### Checkpoint: Contract boundary

- [ ] Evidence frame amendment and claim boundary are documented.
- [ ] Fixture and prompt/evaluation assets are mechanically separate.
- [ ] Unknown fields, invalid enum/status values, and server-owned field
      injection fail before state mutation.

### Phase 2: Deterministic end-to-end path

- [ ] Issue 9.3: Request and render deterministic 10-second concept previews
- [ ] Issue 9.4: Select a concept and hand it off to manual capture
- [ ] Issue 9.5: Expose visualization jobs through API and SSE

### Checkpoint: Synthetic story flow

- [ ] `python main.py --source synthetic --demo-mode` exposes the visualization
      workflow without external services.
- [ ] A creator can request previews, view exactly three results, select one, and
      see a manual next-shot brief without coverage being falsely completed.
- [ ] Repeated requests/decisions are idempotent; failures and invalid
      transitions leave canonical state unchanged and are logged.

### Phase 3: Dashboard and deferred live provider

- [ ] Issue 9.6: Add the visualization panel to the story-first dashboard
- [ ] Issue 9.7: Specify and, only if justified, add the optional live provider

### Checkpoint: Provider and UI parity

- [ ] The deterministic provider uses the canonical recommendation lifecycle,
      API, SSE, and provenance labels.
- [ ] Model-generated text is rendered safely; loading, empty, error, stale,
      and disconnected states are visible.
- [ ] Live provider tests do not require a real API key; live verification is
      reported only when a real key and service are exercised.

### Phase 4: Verification and evidence

- [ ] Issue 9.8: Verify the flow, update docs, and run the evidence gate

### Checkpoint: Release cut line

- [ ] Full tests, lint, AST parse, dashboard JavaScript parse, synthetic server
      smoke, browser interaction, secret scan, and diff checks pass.
- [ ] Held-out baseline and independent review are complete before any outcome
      claim.
- [ ] Results identify the provenance stratum and report denominators.
- [ ] The baseline and independent review dates are recorded in
      `docs/evidence-frame.md`; no outcome presentation precedes them.

## Dependency graph

```text
9.1 boundary/fixture/rubric
  -> 9.2 contracts and invariants
      -> 9.3 observation snapshot and deterministic render
          -> 9.4 recommendation linkage and selection
              -> 9.5 API/SSE integration
                  -> 9.6 dashboard
                      -> 9.8 verification/evidence
      -> 9.7 deferred live provider -> 9.8 only if approved
```

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Generated motion invents geography or obstacles | High | Label previews as creative references; require manual safety notes; never expose a flight-control API |
| “10 seconds” is mistaken for real-time generation | Medium | Make the job asynchronous and show requested duration, generation status, and provenance |
| Preview selection is mistaken for shot improvement | High | Keep preview selection, capture completion, and result evaluation as separate events and metrics |
| Feature expands into an asset-management product | Medium | Keep jobs and assets session-local; defer gallery, persistence, accounts, and collaboration |
| Live video generation blocks the demo | Medium | Defer it; ship the deterministic renderer first and do not make the provider a release dependency |
| Concepts are visually impressive but story-generic | High | Include active beat, missing coverage, why-now, and independent story/usefulness grading in the contract and rubric |

## Decisions intentionally deferred

The deterministic cut line has no unresolved product decision: it uses a
server-frozen source frame, a browser-playable 10-second animation, exactly
three fixed archetypes, and the existing recommendation lifecycle.

Live video generation remains deferred until a provider is selected and its
latency, cost, exact-duration behavior, spatial drift, content failures, and
asset handling are measured. No live-provider implementation or evidence is
required for the deterministic release.
