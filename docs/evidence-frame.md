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

## Story-aware demo extension

The next decision is whether the story-aware mock demo is worth advancing to a creator pilot. Its decision question is:

> Given a story brief and current footage, can a creator select a technically plausible next shot that advances missing story coverage?

The demo may show a seeded story and synthetic footage for repeatability. It may not present synthetic recommendations as proof of live-drone performance. The minimum comparator is a timed manual next-shot workflow on the same held-out cases, completed before the demo date. Supporting rows are time to first recommendation, valid recommendation rate, independent usefulness, creator selection rate, and completion rate; each must carry numerator, denominator, and `n`.
