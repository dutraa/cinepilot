# CinePilot Product Evidence and Claims

This document keeps the product story aligned with what has actually been
verified. It is not a marketing claims sheet. It is the boundary between a
useful product hypothesis, a working demo, and evidence strong enough for a
pilot or public outcome claim.

## Product question

The first evidence question is:

> Given a story brief and a current live drone take, can a director or DP
> choose a technically plausible next shot that advances missing story
> coverage?

The primary outcome is recommendation usefulness. Faster decision-making
between takes is a supporting outcome.

## What is currently supported

The repository currently supports and tests:

- a deterministic story-aware demo;
- structured story, beat, coverage, intent, and recommendation contracts;
- explicit source provenance and source failure states;
- stale-frame prevention in the live feed and Gemini frame sender;
- creator selection, dismissal, and completion paths;
- visualization references labeled as illustrative rather than flight truth;
- event records for several source, observation, tool, recommendation, and
  creator transitions; and
- repeatable synthetic browser behavior.

These are implementation capabilities. They are not evidence that creators
find the recommendations useful.

## What remains unverified

The following must remain labeled **Unverified** until directly exercised:

- live Gemini reasoning against a real configured session;
- real RTMP/RTSP drone operation;
- usefulness to a director or DP on held-out material;
- faster decision-making between takes;
- improved shot quality;
- fewer retakes;
- safer flight; and
- replacement of a cinematographer.

## Measurement plan

| Outcome | Measurement | Comparator | Status |
| --- | --- | --- | --- |
| Recommendation usefulness | Independent reviewer marks story advancement, specificity, technical plausibility, safety, and usefulness | Manual next-shot workflow on the same held-out cases | Not yet measured |
| Decision speed | Time from analysis-ready state to creator selection or dismissal | Timed manual workflow on the same cases | Not yet measured |
| Coverage advancement | Independent reviewer assesses whether the follow-up live evidence addresses the missing beat | Manual baseline and creator review | Not yet measured |

Every rate must include its numerator, denominator, and sample size. Failed,
malformed, rejected, retried, and unclear attempts remain in the denominator.
Selection and completion are behavior signals, not proof of recommendation
quality.

## Required evaluation design

Before presenting an outcome claim:

1. freeze 5–10 representative held-out cases or a larger justified sample;
2. verify mechanically that evaluation cases are disjoint from prompt examples
   and tuning fixtures;
3. run a timed manual baseline before the CinePilot comparison;
4. run the same cases through CinePilot;
5. use an independent reviewer who did not author the prompts or recommendations;
6. score the preregistered rubric;
7. report the provenance stratum for every result; and
8. perform a hostile review of the wording before publication.

## Provenance strata

Results must remain separate for:

- synthetic demo footage;
- explicitly enabled synthetic fallback;
- prerecorded files;
- live RTMP/RTSP/webcam observation;
- live Gemini model output; and
- creator-performed capture and evaluation.

Evidence from synthetic footage cannot be pooled with real-drone evidence. A
live-drone observation claim is also different from a claim that the creator
acted on the recommendation and captured a useful shot.

## Claim ladder

### Demo claim

“CinePilot demonstrates a story-aware workflow that uses source provenance,
missing coverage, and structured next-shot recommendations.”

### Pilot-foundation claim

“CinePilot provides an advisory workflow for a small production team to review
a live drone take between takes and choose a concrete next-shot attempt.”

This requires direct live-source and live-provider verification.

### Outcome claim

“CinePilot helps creators choose more useful next shots” or “reduces time
between decisions.”

These claims require the held-out manual comparator, independent scoring, valid
denominators, and a result that supports the wording.

### Claims not permitted without separate evidence

Do not claim that CinePilot:

- improves production outcomes;
- reduces retakes;
- makes flight safer;
- understands obstacles or navigation;
- guarantees cinematic quality; or
- replaces a cinematographer.

## Evidence ledger minimum

Each analysis should preserve enough metadata to reconstruct the decision:

- session and event IDs;
- observation ID and frame timestamps;
- source and provider provenance;
- story and intent versions;
- model/prompt version;
- all valid, invalid, malformed, rejected, and retried attempts;
- creator selection, dismissal, capture, and evaluation actions; and
- the final independent usefulness score where applicable.

Raw production media must follow the approved consent, retention, deletion,
and access policy and must not be treated as permanent event-log content.
