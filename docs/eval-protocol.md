# CinePilot Evaluation Protocol

## Objective

Determine whether CinePilot provides more specific and useful cinematic direction than a manual baseline for the same shot intent.

## Required artifacts

- `fixtures/eval-manifest.json`: held-out clips and metadata;
- prompt-example manifest kept separate from evaluation assets;
- one manual baseline record per clip;
- one CinePilot run record per clip;
- independent actionability scores;
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
```

Only metrics mapped to a verified decision-maker scoreboard may become headline KPIs. Latency and validity remain supporting metrics.

## Integrity rules

- Prompt examples and evaluation clips must be disjoint.
- The prompt author cannot be the only grader.
- Failed, malformed, and rejected attempts stay in denominators.
- Every reported percentage includes numerator, denominator, and `n`.
- Results from synthetic footage are labeled synthetic.
- Provenance strata (synthetic, synthetic-fallback, prerecorded-file,
  live-rtmp/rtsp/webcam) are never pooled in a single denominator.

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
