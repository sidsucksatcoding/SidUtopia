"""
routes/drive.py  —  Google Drive route
══════════════════════════════════════════════════════════════════════════════

Route in this file:
  GET /api/drive  — Return the 10 most recently modified Drive files

What is Google Drive?
  Google Drive is Google's cloud storage — like a hard drive that lives on
  the internet.  The Dashboard shows your most recently touched files in the
  "Google Data" tab so you can quickly jump back to whatever you were working
  on (a Doc, Sheet, PDF, etc.) without opening Drive separately.

Fields we request:
  id           — unique identifier (used to build the webViewLink)
  name         — file name shown in the UI
  mimeType     — file type (Google Doc, Sheet, PDF …)
  webViewLink  — the URL to open the file in the browser
  modifiedTime — when the file was last changed (shown as "Apr 18")

orderBy="modifiedTime desc" — most recently modified file appears first.
══════════════════════════════════════════════════════════════════════════════
"""
import logging

from flask import Blueprint, jsonify
from googleapiclient.discovery import build

from routes import require_auth

bp = Blueprint("drive", __name__)
logger = logging.getLogger(__name__)


@bp.route("/api/drive")
@require_auth
def api_drive(creds):
    """Return the 10 most recently modified Google Drive files.

    build("drive", "v3", creds) creates a Drive API client.
    files().list() queries the Drive API — think of it like a database
    SELECT statement filtered to your files.

    Returns:
        {"files": [{"id": "...", "name": "...", "mimeType": "...",
                    "webViewLink": "...", "modifiedTime": "..."}, ...]}
    """
    drive = build("drive", "v3", credentials=creds)
    result = drive.files().list(
        pageSize=10,
        # "fields" tells the API which properties to include in the response.
        # Requesting only what we need keeps the response small and fast.
        fields="files(id, name, mimeType, webViewLink, modifiedTime)",
        orderBy="modifiedTime desc",   # newest first
    ).execute()
    return jsonify({"files": result.get("files", [])})
