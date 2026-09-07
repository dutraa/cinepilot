# CinePilot Demo Script

This script has three layers. The story-aware path is the primary deterministic
demo surface; the current critique path remains available for live Gemini
critique behavior; the real-drone observation path (below) requires hardware.

## Story-aware mock demo

### Seeded story

**The place worth coming back to:** a remote mountain lodge reopens after a storm. The audience should move from isolation, to discovery, to warmth, and finally to confidence that the lodge is alive again.

Beats:

1. **Isolation** — high wide shot; lodge small in a large landscape.
2. **Discovery** — descending or forward reveal; lodge grows in frame.
3. **Invitation** — smooth approach or lateral move toward the entrance.
4. **Renewal** — orbit or rise revealing people, lights, or movement.
5. **Confidence** — pull-away or elevated closing image.

### Intended walkthrough

1. Start `python main.py --source synthetic --demo-mode` and open the monitor.
2. Show the seeded story and five ordered beats; explain that this seed is an
   explicitly labeled demo source, not the primary live story workflow.
3. Show the source badge and wait for a current frame.
4. Give explicit cloud consent, then press **Analyze current take** once
   between takes. No continuous advice is expected while maneuvering.
5. Show the fresh burst progress, then the separate observed, not established,
   and missing coverage sections.
6. Show exactly one ranked primary recommendation and two alternatives with
   story purpose, diagnosis, visual objective, why now, technical plausibility,
   manual guidance, safety notes, and model uncertainty.
7. Select one option and explain that selection is a creator decision, not an
   automated flight command. Show the manual capture brief.
8. Manually capture or simulate the take, press **Mark take captured**, then
   press **Evaluate captured take**.
9. Show that evaluation uses a new burst and returns addressed,
   not-addressed, unclear, or insufficient-evidence. It does not prove quality
   improvement or automatically mark a beat covered.
10. Open the secondary **Visual Reference** tab and request concepts only after
    the current recommendation result exists. Keep it labeled “AI visualization
    — illustrative creative reference, not flight truth.”

### Real-place source variant

Run with a real prerecorded or camera source, for example
`python main.py --source file --video-path .\footage\place.mp4` or a configured
`webcam`, `rtsp`, or `rtmp` source. Wait until the monitor shows a current frame,
then request Visualize. Confirm that the panel identifies the source kind and
label, the frozen-frame dimensions, the deterministic renderer version, and
the same three fixed screen-space profiles. A real source makes the reference
visually grounded in that place; it does not turn the 2D motion into a physical
camera path, a reconstruction, or a safety assessment.

If the source is disconnected or stale, **Analyze current take** and evaluation
must remain unavailable and show `NO LIVE SIGNAL`.
If rendering fails, show the failure and retry without changing story
coverage. Do not present a provider-backed or spatial-previs claim from this
deterministic source variant.

The demo is complete only when the audience can see the causal loop: story intent changes the recommendation, the current shot changes the missing coverage, and creator action changes the state.

## Current critique demo setup (no hardware)

```text
python main.py --source synthetic
```

Open `http://127.0.0.1:8000` and enable browser audio after the first user
interaction. The source strip must read `SYNTHETIC / GENERATED` — say so out
loud; this demo makes no live-drone claim.

## Current critique demonstration path

1. Enter the intent: “Make the main building feel imposing with a slow, deliberate reveal. Keep it on the right third.”
2. Submit the intent and show the active intent version.
3. Let Gemini watch the clean synthetic feed.
4. Show the critique summary and the one to three ranked tweaks.
5. Read the diagnosis, recommendation, and rationale aloud.
6. Mark one tweak accepted, then acted after the simulated camera adjustment.
7. Show that the next critique is associated with the updated workflow.
8. Show the source badge and explain that synthetic footage is generated demo
   material, not a live drone claim.

## Real-drone observation demo (requires hardware)

Prerequisites: a drone publishing RTMP (e.g. DJI Fly → MediaMTX); see
`docs/real-drone-setup.md`. Do not enable synthetic fallback.

```text
python main.py --source rtmp --stream-url rtmp://127.0.0.1:1935/live/drone
```

1. Show `/health` and the dashboard source strip: `REAL SOURCE`, status
   `live`, frame age under ~2 s.
2. Enter and submit a shot intent for the scene the drone actually sees.
3. Show a validated critique arriving against live footage.
4. Accept a recommendation; read the manual execution guidance and safety
   note aloud, and state that the pilot decides whether and how to fly it.
5. The pilot manually flies the adjustment and captures the shot.
6. Mark the tweak acted, then mark the shot captured & completed (creator
   button) — show the coverage update.
7. Stop the drone stream; show the `disconnected`/`reconnecting` state, the
   "NO LIVE SIGNAL" card, and that no synthetic footage appears.
8. Restart the stream; show automatic recovery to `live`.

State explicitly during the demo: CinePilot is advisory only; it never
controls the drone, and the pilot is responsible for flight safety.

## Evidence to capture

- elapsed time from intent submission to first useful critique;
- critique count and valid/invalid/malformed attempt counts;
- independent actionability score;
- creator action decisions and manual completion marks;
- source transitions, reconnect counts, and provenance strata
  (synthetic vs. live evidence stays separate);
- any duplicate suppression or reconnect event.

Do not claim reduced retakes or improved production outcomes from these
demos alone, and do not claim “real-drone support verified” until the
hardware checklist in `docs/real-drone-setup.md` has been performed.
