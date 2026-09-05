# ADR-001: Keep the story-aware demo single-agent and advisory

## Status

Accepted

## Date

2026-09-01

## Context

CinePilot is evolving from a live drone director into a cinematic decision engine. The next demo needs to show more than isolated critique cards: it should connect a mock story, the current shot, missing coverage, and plausible next shots.

There is a temptation to introduce separate story, cinematography, safety, and flight agents immediately. That would create more orchestration, state synchronization, failure modes, and demo surface before the core user value is proven.

## Decision

Build the first story-aware demo with one explicit `DirectorAgent` context containing:

- the seeded story brief and ordered beats;
- current beat and covered/missing coverage;
- current frame observation;
- the current cinematic intent;
- prior accepted, acted, completed, and dismissed decisions.

The agent may recommend next shots, but the creator manually selects and executes them. The server validates all recommendations and owns IDs, statuses, timestamps, and provenance. No tool or API may control a drone.

## Alternatives considered

### Multiple specialized agents

Rejected for the first demo. It may improve separation of concerns later, but currently adds coordination cost without evidence that it improves recommendation usefulness.

### Autonomous flight planning

Rejected. Flight safety, hardware integration, and liability are separate problems from proving story-aware cinematic decision support.

### A static scripted presentation

Rejected as the product path. Seeded story fixtures are allowed for repeatability, but the live/synthetic frame must still pass through the same recommendation contract so the demo exercises the actual decision loop.

## Consequences

- The first demo is explainable: one context, one validated output, one creator decision.
- Synthetic mode can provide a deterministic shell and fixture path without implying Gemini quality.
- Story-aware contracts can later support specialist agents behind the same server-owned state boundary.
- Evidence can compare recommendation usefulness without confusing orchestration complexity with product value.

