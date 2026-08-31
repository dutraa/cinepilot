# CinePilot Demo Script

This script has two layers. The story-aware path is the product narrative; the current critique path is the implemented fallback until Issue 8 is complete.

## Story-aware mock demo (next slice)

### Seeded story

**The place worth coming back to:** a remote mountain lodge reopens after a storm. The audience should move from isolation, to discovery, to warmth, and finally to confidence that the lodge is alive again.

Beats:

1. **Isolation** — high wide shot; lodge small in a large landscape.
2. **Discovery** — descending or forward reveal; lodge grows in frame.
3. **Invitation** — smooth approach or lateral move toward the entrance.
4. **Renewal** — orbit or rise revealing people, lights, or movement.
5. **Confidence** — pull-away or elevated closing image.

### Intended walkthrough

1. Load the seeded story and show the five ordered beats.
2. Set the active beat to Isolation.
3. Show the live drone feed or synthetic aerial scene.
4. Ask CinePilot what the current shot proves and what story coverage is missing.
5. Show two or three recommendations with story purpose, visual objective, why now, and manual execution guidance.
6. Select “Descending reveal” and explain that selection is a creator decision, not an automated flight command.
7. Capture or simulate the next take and mark it completed.
8. Show Discovery moving to covered and the next missing beat becoming active.

The demo is complete only when the audience can see the causal loop: story intent changes the recommendation, the current shot changes the missing coverage, and creator action changes the state.

## Current critique demo setup

```text
python main.py --source synthetic
```

Open `http://127.0.0.1:8000` and enable browser audio after the first user interaction.

## Current critique demonstration path

1. Enter the intent: “Make the main building feel imposing with a slow, deliberate reveal. Keep it on the right third.”
2. Submit the intent and show the active intent version.
3. Let Gemini watch the clean synthetic feed.
4. Show the critique summary and the one to three ranked tweaks.
5. Read the diagnosis, recommendation, and rationale aloud.
6. Mark one tweak accepted, then acted after the simulated camera adjustment.
7. Show that the next critique is associated with the updated workflow.
8. Show the source badge and explain that synthetic footage is the fallback, not a live drone claim.

## Evidence to capture

- elapsed time from intent submission to first useful critique;
- critique count and valid/invalid attempt counts;
- independent actionability score;
- creator action decisions;
- any duplicate suppression or reconnect event.

Do not claim reduced retakes or improved production outcomes from this demo alone.
