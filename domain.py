"""Small, dependency-free domain constants shared by the app layers."""

SHOT_DEFINITIONS = {
    "establishing_wide": "Establishing Wide",
    "topdown_property": "Top-Down Property",
    "orbit_pass": "Orbit Pass",
    "low_reveal": "Low Reveal",
    "pull_away": "Pull Away",
}

ALLOWED_SHOT_IDS = tuple(SHOT_DEFINITIONS)
ALLOWED_STATUSES = ("PENDING", "IN_PROGRESS", "COMPLETED", "REJECTED")
ALLOWED_PRIORITIES = ("INFO", "WARNING", "URGENT")
