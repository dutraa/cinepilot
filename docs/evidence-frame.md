# CinePilot Evidence Frame

Status: working frame ratified by the founder's explicit end-to-end execution instruction on 2026-08-31. External scoreboard details remain an open discovery item; no external outcome claim is permitted until they are confirmed.

## Decision-maker map

The immediate decision-maker is the CinePilot founder/team deciding whether this product deserves continued pilot work and a public demo. The likely external judge is a hackathon evaluator, but that role and rubric are not yet verified.

If the product fails, the team loses demo credibility and engineering time. The evaluator loses confidence that the system solves a creator problem rather than only demonstrating an API integration.

## Existing scoreboard

No verified external scoreboard has been supplied. Until it is discovered, the following remain supporting metrics only:

- critique latency;
- valid structured critique rate;
- duplicate critique rate;
- creator decision time;
- independently judged actionability;
- acted-tweak rate.

The team must obtain the evaluator rubric or a creator's existing review workflow before presenting any of these as headline KPIs.

## KPI cross-map

| Decision-maker measure | CinePilot measure | Current measurement | Baseline | Headline? |
| --- | --- | --- | --- | --- |
| To be discovered | Creator decision time | Intent submission to first accepted/acted tweak | Manual timed baseline on 5–10 held-out clips before demo | No, pending mapping |
| To be discovered | Actionable recommendation rate | Independent reviewer marks each eligible tweak actionable or not | Manual critique baseline on the same clip set | No, pending mapping |
| To be discovered | Retake or iteration count | Number of attempts before creator accepts a take | Manual workflow baseline | No, pending mapping |

Engineering metrics such as latency, frame rate, and schema validity are supporting rows and cannot substitute for the missing scoreboard.

## Provenance strata

Evidence is recorded in separate, never-pooled strata, carried on every
event-log record and source snapshot:

- `synthetic` — the generated demo scene;
- `synthetic-fallback` — generated frames explicitly enabled after a real-source failure;
- `prerecorded-file` — local fixture or held-out clips;
- `live-rtmp` / `live-rtsp` / `live-webcam` — real observation streams;
- `gemini` — model outputs (valid, invalid, and malformed attempts);
- creator actions (`actor="creator"`) — selections, dismissals, and manual completion marks.

A run's claims may only cite the stratum it actually used. Live-drone
observation (CinePilot watched a real stream) is a weaker claim than
creator-performed flight execution (the creator acted on a recommendation
and captured the shot); the two must be reported separately. Engineering
diagnostics — latency, FPS, frame validity, reconnect counts, schema
validity — remain supporting metrics and never become headline outcomes
without a verified decision-maker scoreboard.

## Baseline plan

Before the first demo, run 5–10 representative clips through:

1. a timed manual creator/director critique workflow;
2. CinePilot with the same intent format;
3. an independent reviewer scoring whether each recommendation is specific and actionable.

The clip set must be held out from prompt examples. Every eligible attempt, including malformed or failed model calls, remains in the denominator.

## Eval integrity contract

- Evaluation clips and prompt examples are stored in separate manifests.
- A mechanical hash check verifies that no evaluation asset appears in prompt examples.
- The prompt author cannot be the sole actionability grader.
- Invalid extraction or schema validation counts as an incorrect critique attempt.
- Every percentage is reported with its numerator, denominator, and sample size.
- “Uncorrected means correct” is not an accepted evaluation rule.

## Claim boundaries

The first release can support: “CinePilot produces a structured cinematic critique in a live multimodal workflow and warrants a pilot evaluation.”

It cannot support: “CinePilot improves production outcomes,” “reduces retakes,” or “replaces a cinematographer” without a measured comparator and a real creator baseline.
