# CinePilot Evidence Frame

Status: working frame ratified by the founder's explicit end-to-end execution instruction on 2026-08-31. The Visualize amendment was ratified by the founder's instruction to fix the reviewed plan on 2026-09-05. External scoreboard details remain an open discovery item; no external outcome claim is permitted until they are confirmed.

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
- time to first understandable visualization;
- independently judged visualization usefulness;
- preview-to-captured-shot fidelity.

The team must obtain the evaluator rubric or a creator's existing review workflow before presenting any of these as headline KPIs.

## KPI cross-map

| Decision-maker measure | CinePilot measure | Current measurement | Baseline | Headline? |
| --- | --- | --- | --- | --- |
| To be discovered | Creator decision time | Intent submission to first accepted/acted tweak | Manual timed baseline on 5–10 held-out clips; execute 2026-09-06 | No, pending mapping |
| To be discovered | Actionable recommendation rate | Independent reviewer marks each eligible tweak actionable or not | Manual critique baseline on the same clip set; execute 2026-09-06 | No, pending mapping |
| To be discovered | Visualization time to first understandable concept | Request timestamp to first ready concept that the creator can identify and describe | Timed manual concept-selection baseline on the same 5–10 held-out cases; execute 2026-09-06 | No, pending mapping |
| To be discovered | Visualization usefulness rate | Independent reviewer marks story advancement, specificity, technical plausibility, and usefulness | Manual baseline scored by 2026-09-07 before any presentation on or after 2026-09-08 | No, pending mapping |
| To be discovered | Preview-to-shot fidelity | Independent reviewer compares selected concept with the manually captured result | Same held-out cases; failures remain in the denominator; score by 2026-09-07 | No, pending mapping |
| To be discovered | Retake or iteration count | Number of attempts before creator accepts a take | Manual workflow baseline | No, pending mapping |

Engineering metrics such as latency, frame rate, and schema validity are supporting rows and cannot substitute for the missing scoreboard.

## Baseline plan

The baseline schedule is fixed for this feature:

- **2026-09-06:** freeze 5–10 held-out cases in `fixtures/eval-manifest.json`,
  record asset hashes, and run the timed manual baseline before any CinePilot
  run on those cases.
- **2026-09-07:** have an independent reviewer score the manual and CinePilot
  records using the preregistered rubric.
- **2026-09-08 or later:** presentation is permitted only if the prior two
  steps are complete. If they are not complete, show deterministic behavior
  only and make no outcome claim.

Run the same cases through:

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

The deterministic Visualize slice can support only: “CinePilot renders three
clearly labeled, story-linked 10-second concept animations over a captured
source frame and hands the selected concept to a manual capture workflow.”

After the scheduled baseline and independent review, the evidence may support a
stronger pilot recommendation if the measured result warrants it.

It cannot support: “CinePilot helps creators choose better shots,” “improves
production outcomes,” “reduces retakes,” or “replaces a cinematographer” until
the measured comparator, creator baseline, and independent review are complete.

## Story-aware demo extension

The next decision is whether the story-aware mock demo is worth advancing to a creator pilot. Its decision question is:

> Given a story brief and current footage, can a creator select a technically plausible next shot that advances missing story coverage?

The demo may show a seeded story and synthetic footage for repeatability. It may not present synthetic recommendations as proof of live-drone performance. The minimum comparator is a timed manual next-shot workflow on the same held-out cases, completed before the demo date. Supporting rows are time to first recommendation, valid recommendation rate, independent usefulness, creator selection rate, and completion rate; each must carry numerator, denominator, and `n`.

For Visualize, the provisional internal go/no-go rule is: do not add a live
video-generation provider unless the independent reviewer scores at least 4 of
5 held-out cases as useful and no case produces safety-critical flight advice.
This is an internal sequencing gate, not a verified external KPI or an outcome
claim.
