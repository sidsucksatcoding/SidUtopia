"""
services/data_service.py  —  Save and load dashboard data
══════════════════════════════════════════════════════════════════════════════

What does this file do?
  The dashboard lets you manage tasks, kanban cards, exams, and links.
  All of that data needs to survive page refreshes and server restarts, so
  we store it in a JSON file called dashboard-data.json at the project root.

  This file provides two simple functions:
    load_data()      — Read the file and return the data as a Python dictionary.
    save_data(data)  — Write a Python dictionary back to the file.

What is JSON?
  JSON (JavaScript Object Notation) is a text format for storing structured data.
  It looks like Python dictionaries/lists but is understood by almost every
  programming language.  Example:
      {"name": "Sid", "tasks": ["Study", "Code"]}

What is a dictionary?
  In Python, a dictionary is a collection of key-value pairs:
      {"zenith": [], "mathTodos": [], "kanban": {"todo": [], ...}}
  You look up a value by its key, e.g.  data["zenith"]
══════════════════════════════════════════════════════════════════════════════
"""
import json
import logging
from config import DATA_FILE

logger = logging.getLogger(__name__)

# ── Default (empty) state ──────────────────────────────────────────────────────
# This is what the data looks like before the user has added anything.
# Keys match the JavaScript `state` object in static/js/state.js exactly,
# so the frontend can consume the JSON without any transformation.
_DEFAULT_STATE: dict = {
    "zenith":    [],                                   # College counselling action items
    "mathTodos": [],                                   # Math to-do list
    "kanban":    {"todo": [], "inprogress": [], "done": []},  # Kanban board columns
    "exams":     [],                                   # Upcoming exams
    "links":     {"zenith": [], "math": []},           # Quick links per section
}


def load_data() -> dict:
    """Read dashboard-data.json and return its contents as a dictionary.

    If the file does not exist yet (first run), or if it is corrupt,
    return a fresh copy of the default empty state instead.

    Why copy() instead of returning _DEFAULT_STATE directly?
      If we returned the _DEFAULT_STATE object itself, callers could
      accidentally modify it (e.g. data["zenith"].append(...)) which would
      silently corrupt the default for every future call.  dict() creates a
      new independent copy.
    """
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception as e:
            # The file exists but is not valid JSON — log a warning and fall back
            logger.warning("Could not parse dashboard-data.json: %s", e)
    # File missing or corrupt — return a fresh default state
    return dict(_DEFAULT_STATE)


def save_data(data: dict) -> None:
    """Write the full dashboard state dictionary to dashboard-data.json.

    Args:
        data: The complete state dictionary (must match the structure above).

    indent=2 makes the file human-readable with nice indentation, so you
    can open dashboard-data.json in a text editor and understand its contents.
    """
    DATA_FILE.write_text(json.dumps(data, indent=2))
