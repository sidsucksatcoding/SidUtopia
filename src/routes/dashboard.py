"""
routes/dashboard.py  —  Save and load dashboard data
══════════════════════════════════════════════════════════════════════════════

Routes in this file:
  GET  /api/data  — Load the dashboard state (tasks, kanban, exams, links …)
  POST /api/data  — Save the dashboard state

Why is there no @require_auth here?
  The dashboard data (tasks, kanban cards, exams) is stored locally on the
  server and doesn't touch any Google API.  You don't need to be logged in
  to read or write it — authentication is only needed when calling Google.

How does the frontend use these routes?
  • On startup: loadStateFromServer() calls GET /api/data and stores the
    result in the `state` variable (state.js).
  • After any change: saveState() calls POST /api/data with the current state.
══════════════════════════════════════════════════════════════════════════════
"""
import logging

from flask import Blueprint, request, jsonify

from services.data_service import load_data, save_data

bp = Blueprint("dashboard", __name__)
logger = logging.getLogger(__name__)


@bp.route("/api/data", methods=["GET"])
def get_data():
    """Return the full dashboard state as JSON.

    The frontend calls this on page load to populate all the lists and cards.
    load_data() reads dashboard-data.json (or returns defaults if it doesn't exist).
    jsonify() converts the Python dictionary to a JSON HTTP response.
    """
    return jsonify(load_data())


@bp.route("/api/data", methods=["POST"])
def post_data():
    """Replace the entire dashboard state with the JSON body.

    The frontend sends the complete `state` object after any change
    (adding a task, moving a kanban card, deleting an exam, etc.).

    request.get_json() parses the JSON body of the POST request into
    a Python dictionary, which we then write to disk.
    """
    save_data(request.get_json())
    return jsonify({"success": True})
