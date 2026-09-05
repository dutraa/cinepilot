# CinePilot Demo Script

## Synthetic demo (no hardware)

```text
python main.py --source synthetic
```

Open `http://127.0.0.1:8000` and enable browser audio after the first user
interaction. The source strip must read `SYNTHETIC / GENERATED` — say so out
loud; this demo makes no live-drone claim.

### Demonstration path

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
