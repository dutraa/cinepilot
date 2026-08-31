# CinePilot Evaluation Protocol

## Objective

Determine whether CinePilot provides more specific and useful cinematic direction than a manual baseline for the same shot intent, and whether the planned story-aware mode helps a creator choose a useful next shot for missing coverage.

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

## Story-aware grading rubric

An eligible next-shot recommendation is useful only when an independent reviewer can identify:

1. the story beat or missing coverage it advances;
2. a concrete visual objective;
3. a technically plausible manual capture approach;
4. a reason the recommendation is useful now rather than generic advice.

Selection or completion is evidence of creator behavior, not proof of recommendation quality. Report it alongside independent grading and include all eligible recommendations in the denominator.

## Integrity rules

- Prompt examples and evaluation clips must be disjoint.
- The prompt author cannot be the only grader.
- Failed, malformed, and rejected attempts stay in denominators.
- Every reported percentage includes numerator, denominator, and `n`.
- Results from synthetic footage are labeled synthetic.
