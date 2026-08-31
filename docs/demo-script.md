# CinePilot Demo Script

## Setup

```text
python main.py --source synthetic
```

Open `http://127.0.0.1:8000` and enable browser audio after the first user interaction.

## Demonstration path

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
