"""
routes/zenith.py  —  Zenith Google Doc route
══════════════════════════════════════════════════════════════════════════════

Route in this file:
  GET /api/zenith  — Parse the Zenith Google Doc and return meetings + action items

What is Zenith?
  Zenith is Sid's college counselling program.  Their shared Google Doc has one
  tab per meeting, and each tab contains an "Action Items" section with bullet
  points of things to do before the next session.

  This route fetches that document and returns all the action items so the
  dashboard can show them under the "Zenith" tab.

Why is the parsing logic in services/zenith_parser.py?
  Three routes need the same parsed data:
    • This route  (/api/zenith)      — displays items on the Zenith tab
    • /api/chat                      — lets the AI answer questions about them
    • /api/send-summary              — includes them in the SMS

  Rather than copy the same code three times, it lives in one place and is
  imported here.  That's the DRY principle ("Don't Repeat Yourself").
══════════════════════════════════════════════════════════════════════════════
"""
import logging

from flask import Blueprint, jsonify

from routes import require_auth
from services.zenith_parser import parse_zenith_doc

bp = Blueprint("zenith", __name__)
logger = logging.getLogger(__name__)


@bp.route("/api/zenith")
@require_auth
def api_zenith(creds):
    """Parse the Zenith Google Doc and return all meetings with their action items.

    Delegates entirely to parse_zenith_doc() in services/zenith_parser.py.
    See that file for the full explanation of how the document is parsed.

    Returns:
        {"meetings": [{"title": "Meeting #12", "actionItems": [...]}, ...]}
        Meetings are sorted newest-first (Meeting #12 before Meeting #11).
    """
    meetings = parse_zenith_doc(creds)
    return jsonify({"meetings": meetings})
