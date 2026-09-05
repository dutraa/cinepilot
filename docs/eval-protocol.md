# CinePilot Evaluation Protocol

## Objective

Determine whether CinePilot provides more specific and useful cinematic direction than a manual baseline for the same shot intent, and whether the story-aware mode helps a creator choose a useful next shot for missing coverage.

## Required artifacts

- `fixtures/eval-manifest.json`: held-out clips and metadata;
- prompt-example manifest kept separate from evaluation assets;
- one manual baseline record per clip;
- one CinePilot run record per clip;
- independent actionability scores;
- story-advancement and technical-plausibility scores for next-shot recommendations;
- creator selection and completion records;
- event log with all eligible attempts.

## Unit of evaluation

The primary unit is a published tweak, not a frame and not a Gemini request. A critique with three tweaks contributes three eligible tweak records.

## Actionability rubric

A tweak is actionable only when an independent reviewer can identify:

1. the visible problem;
2. a concrete camera, framing, lighting, pacing, or continuity change;
3. a plausible connection between that change and the stated shot intent.

Vague statements such as “make it more cinematic” fail.

## Metrics

```text
actionable_rate = actionable_tweaks / eligible_tweaks
valid_critique_rate = valid_critiques / critique_tool_attempts
creator_decision_time = first_decision_timestamp - intent_timestamp
acted_rate = acted_tweaks / eligible_tweaks
next_shot_selection_rate = selected_recommendations / eligible_recommendations
next_shot_completion_rate = completed_recommendations / selected_recommendations
coverage_usefulness_rate = useful_recommendations / eligible_recommendations
```

Only metrics mapped to a verified decision-maker scoreboard may become headline KPIs. Latency and validity remain supporting metrics.

For the story-aware slice, the eligible unit is a published next-shot
recommendation. A batch of three contributes three eligible recommendation
records. Deterministic fixture recommendations, synthetic footage, live Gemini,
and real drone footage are separate evidence strata and must not be pooled.

## Story-aware grading rubric

An eligible next-shot recommendation is useful only when an independent reviewer can identify:

1. the story beat or missing coverage it advances;
2. a concrete visual objective;
3. a technically plausible manual capture approach;
4. a reason the recommendation is useful now rather than generic advice.

Selection or completion is evidence of creator behavior, not proof of recommendation quality. Report it alongside independent grading and include all eligible recommendations in the denominator.

For Visualize, the eligible unit is a ready preview and its linked
recommendation. A job must contain exactly three previews, use one server-
decoded frozen observation, and remain in a separately labeled deterministic,
synthetic, file, webcam, RTSP, RTMP, or live evidence stratum. Report renderer
validity, source provenance, profile adherence, temporal stability, and place
fidelity as separate supporting dimensions; a contract pass is not a spatial-
accuracy pass. The animation profile illustrates screen-space motion over the
JPEG and cannot be graded as obstacle awareness or a flight route. Preview
selection is creator behavior and manual handoff, not evidence that the
captured shot improved. Failed, malformed, retried, and rejected attempts stay
in denominators. The scheduled manual baseline and independent review in
`docs/evidence-frame.md` must be complete before any outcome claim.

## Integrity rules

- Prompt examples and evaluation clips must be disjoint.
- The prompt author cannot be the only grader.
- Failed, malformed, and rejected attempts stay in denominators.
- Every reported percentage includes numerator, denominator, and `n`.
- Results from synthetic footage are labeled synthetic.
- Provenance strata (synthetic, synthetic-fallback, prerecorded-file,
  live-rtmp/rtsp/webcam) are never pooled in a single denominator.
- Recommendation publication, selection, and completion are separate events;
  completion is not evidence that the resulting shot improved.

## Future real-drone evaluation

Any evaluation on real drone footage must additionally:

- use held-out footage that never appears in prompt examples;
- remain separate from synthetic and fixture evidence;
- include failed and malformed model attempts in denominators;
- use an independent reviewer (not the prompt author alone);
- report numerator, denominator, and sample size for every figure;
- distinguish live-drone observation (CinePilot watched a real stream) from
  creator-performed flight execution (the creator acted on a recommendation
  and captured the shot);
- make no claims about improved shots, fewer retakes, safer flight, or
  cinematographer replacement without a measured comparator.

Until that evaluation exists, real-source metrics (frame age, FPS,
reconnect counts, schema validity) are engineering diagnostics only.
