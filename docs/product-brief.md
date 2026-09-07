# CinePilot Product Brief

## In one sentence

CinePilot is an advisory second set of eyes for a small production team: it
watches a live drone feed between takes, compares the current shot with the
story, and helps the director or DP decide what coverage to capture next.

## Who it is for

The first user is the director or director of photography on a small crew.
They may not have a dedicated cinematographer, continuity person, or story
editor available to evaluate every take immediately. The pilot remains the
person responsible for flight safety and every movement of the drone.

## The production problem

Small crews often know that a shot is not working, but the useful next action
is unclear. Feedback such as “make it more cinematic” does not tell the crew:

- what the current shot actually establishes;
- which story beat or visual proof is still missing;
- which shot should be captured next;
- why that shot is the best next choice; or
- whether the next take addressed the original gap.

When this decision is made from memory or vague taste, a crew can capture
several attractive shots and still discover later that the scene lacks a
necessary transition, reveal, entrance, human moment, or closing image.

## What we are building

CinePilot turns the live drone feed into a deliberate coverage decision. The
director provides a short structured brief: the scene goal, emotional arc,
active beat, must-show elements, and constraints. Between takes, the director
presses **Analyze current take**.

CinePilot then:

1. captures a short, fresh evidence burst from the live feed;
2. compares it with the story brief and current shot intent;
3. explains what the take establishes and what it does not establish;
4. identifies the strongest missing coverage;
5. recommends one ranked next shot plus two alternatives;
6. explains why the recommendation is useful now;
7. provides a manual capture brief and safety notes;
8. lets the crew select or dismiss the recommendation; and
9. evaluates a fresh live evidence burst after the next take.

The creator makes the decision. CinePilot does not fly the drone.

## Why a director or DP would use it

### To make the next decision concrete

The product translates a vague concern into a specific coverage choice:
“Discovery is still missing; use a restrained descending reveal so the lodge
becomes readable inside the landscape.”

### To keep story and cinematography connected

The recommendation is tied to a beat and a visual purpose. It is not a generic
list of camera movements detached from the scene.

### To protect the crew from attractive but incomplete coverage

The system keeps a visible record of what has been established, what remains
missing, what the crew selected, and what the next take appears to address.

### To preserve creative control

The output is advice, not an order. The director or DP can choose an
alternative, dismiss the recommendation, record why, or decide that the shot
is not safe or appropriate.

## What CinePilot is not

CinePilot is not:

- an autonomous drone pilot;
- a flight-plan or waypoint generator;
- an obstacle-avoidance or flight-safety system;
- an editor or asset-management platform;
- a replacement for a director or cinematographer;
- a guarantee that a shot will look good after capture; or
- proof that production outcomes improved.

## Why the first product is live and between takes

The crew already has a live source available while shooting, and the useful
decision happens after a take, not while the pilot is maneuvering. Explicitly
triggered analysis gives the crew control over when a take is ready for review,
avoids distracting the pilot during flight, and creates a clear evidence point
for each recommendation.

## Product boundary for the first pilot

The first pilot focuses on:

- one small production team;
- one live RTMP or RTSP drone source;
- one structured story brief per scene;
- one active story beat at a time;
- one explicit analysis request between takes;
- one ranked recommendation and two alternatives;
- manual capture by the crew; and
- a fresh live observation used for follow-up evaluation.

Synthetic footage remains available for repeatable demos and tests. It must be
labeled synthetic and cannot be used as evidence of live-drone performance.

## Current status and honesty

The deterministic story-aware demo and source-status behavior are implemented
and testable. Live Gemini reasoning, a real drone run, creator usefulness, and
faster decision-making remain unverified until the actual external systems and
held-out creator evaluation are exercised.

The honest product promise is therefore:

> CinePilot helps a small production team reason about missing story coverage
> from a live drone shot and choose a concrete next shot to attempt.

The stronger promise — that it helps creators choose better shots or improves
production outcomes — requires a manual comparator and independent review.
