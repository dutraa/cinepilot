# CinePilot Creator Workflow

This document describes how a director or DP uses CinePilot on set. It is
written for the between-takes workflow, where the drone feed is the primary
source and the pilot remains responsible for every flight decision.

## Before the first take

The director enters a short scene brief:

- What is the scene trying to make the audience feel?
- What must the audience understand or see?
- What are the story beats in order?
- What constraints matter on this shoot?
- What is the current shot intended to accomplish?

CinePilot must show the active source and its provenance before analysis. The
crew must be able to tell whether the feed is a real RTMP/RTSP source, a file,
webcam, synthetic demo, or an explicitly enabled synthetic fallback.

## Between takes

### 1. Confirm the source is ready

The source must be live and fresh. If it is connecting, stale, disconnected, or
reconnecting, CinePilot must show that status clearly and disable analysis.

The crew must never see a disconnected real source presented as current footage.

### 2. Finish the take

The pilot completes the maneuver manually. CinePilot does not issue flight
commands and does not continuously interrupt the pilot with AI advice.

### 3. Press “Analyze current take”

The director or DP explicitly starts analysis after the take. CinePilot captures
a short server-controlled evidence burst from the live feed. Only fresh frames
are eligible.

The analysis request records:

- observation ID;
- source and provenance;
- frame timestamps and freshness;
- story version;
- active beat;
- intent version; and
- provider/model status.

Raw frames are processed under the approved retention policy and are not
written permanently into the event log.

### 4. Read the diagnosis

The result is separated into three questions:

**What does this take establish?**

Only observations grounded in the evidence burst belong here.

**What does it not establish?**

This explains the limits of the evidence. A model must not treat an absent or
ambiguous detail as proven.

**What coverage is missing?**

This connects the current evidence to the active story beat and the remaining
visual proof.

### 5. Choose the next shot

CinePilot presents:

- one ranked primary recommendation;
- two lower-emphasis alternatives;
- the story purpose;
- the concrete visual objective;
- why the shot is useful now;
- manual capture guidance; and
- safety notes for the pilot to verify.

The director or DP can select one, select an alternative, or dismiss the
recommendations. Selection means only that the crew accepted a direction to
attempt. It does not mean the shot was captured or that the story beat is now
covered.

### 6. Capture manually

The pilot decides whether the recommendation is safe and appropriate. The crew
captures the shot manually, outside CinePilot's control boundary.

The director then marks the take as captured. This is a creator action, not a
model action and not an automated inference.

### 7. Evaluate the next take

The director presses **Evaluate captured take**. CinePilot captures a new fresh
evidence burst from the live feed and compares it with:

- the selected recommendation;
- the intended story beat;
- the earlier missing coverage; and
- the new evidence.

The result is one of:

- addressed;
- not addressed;
- unclear; or
- not evaluated because evidence was insufficient.

The creator's capture confirmation, the model's evaluation, and an
independent reviewer's usefulness score remain separate records.

## State vocabulary

| State | Meaning |
| --- | --- |
| Observed | Grounded in the current live evidence burst |
| Not established | Important context that the evidence does not prove |
| Recommended | Proposed by CinePilot; not yet accepted |
| Selected | Chosen by the director/DP for the next attempt |
| Captured | Creator confirms the crew captured the take |
| Evaluated | A follow-up evidence burst was reviewed |
| Addressed | Follow-up evidence appears to address the intended gap |
| Unclear | Evidence is insufficient for a reliable conclusion |
| Dismissed | Creator rejected the recommendation |

These states must not be collapsed. A selected recommendation is not a
captured shot. A captured shot is not proof of improvement. An evaluated shot
is not automatically a successful shot.

## Recovery behavior

The workflow must remain understandable when:

- no story or intent has been entered;
- the drone feed is unavailable;
- the frame is stale;
- the provider is unavailable;
- analysis is loading or times out;
- the model returns malformed or generic output;
- a request is duplicated;
- the browser disconnects; or
- the crew retries after an error.

In every case, CinePilot should preserve the last trusted state, explain what
cannot be concluded, and give the creator a safe next action.
