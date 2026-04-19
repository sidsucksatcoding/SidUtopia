"""
routes/gmail.py  —  Gmail routes
══════════════════════════════════════════════════════════════════════════════

Routes in this file:
  GET  /api/gmail            — Fetch the latest unread emails
  POST /api/gmail/mark-read  — Mark all unread emails as read in one go

What is the Gmail API?
  Google provides a programming interface (API) that lets you read and manage
  your Gmail inbox using code instead of opening gmail.com.  We use it here
  to show unread messages in the dashboard and to add a "Mark All Read" button.
══════════════════════════════════════════════════════════════════════════════
"""
import logging

from flask import Blueprint, jsonify
from googleapiclient.discovery import build

from routes import require_auth

bp = Blueprint("gmail", __name__)
logger = logging.getLogger(__name__)


@bp.route("/api/gmail")
@require_auth
def api_gmail(creds):
    """Fetch up to 10 unread Gmail messages and return their subject + sender.

    How it works:
      1. build("gmail", "v1", creds) creates a Gmail API client.
      2. messages().list() gives us a list of message IDs that match "is:unread".
         It does NOT return the message content — just IDs.
      3. For each ID we call messages().get() to fetch the Subject and From headers.
         We ask for format="metadata" so Google only sends headers, not the full
         email body — much faster when we only need the subject line.

    Returns:
        {"messages": [{"id": "...", "subject": "...", "from": "..."}, ...]}
    """
    gmail = build("gmail", "v1", credentials=creds)

    # List matching message IDs (q= is the same search syntax as in Gmail's search bar)
    result = gmail.users().messages().list(
        userId="me",     # "me" = the authenticated user
        maxResults=10,   # no more than 10 messages
        q="is:unread",   # only unread messages
    ).execute()

    message_ids = result.get("messages", [])
    if not message_ids:
        return jsonify({"messages": []})  # inbox is clean — nothing to show

    messages = []
    for msg in message_ids:
        # Fetch metadata (headers only) for this specific message
        detail = gmail.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["Subject", "From"],   # only these two headers
        ).execute()

        # Convert the list of {name, value} header objects into a simple dict
        # so we can look up headers by name: headers["Subject"]
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}

        messages.append({
            "id":      msg["id"],
            "subject": headers.get("Subject", "(no subject)"),
            "from":    headers.get("From", ""),
        })

    return jsonify({"messages": messages})


@bp.route("/api/gmail/mark-read", methods=["POST"])
@require_auth
def gmail_mark_read(creds):
    """Mark every unread email as read using a single batch API call.

    Why batchModify instead of one call per message?
      batchModify can update up to 500 messages in a single HTTP request.
      Calling the API 500 times individually would be ~500x slower.

    How it works:
      1. List all unread message IDs (up to 500).
      2. Call batchModify with removeLabelIds: ["UNREAD"] — removing the UNREAD
         label is exactly what marking an email as read does in Gmail.

    Returns:
        {"success": True, "marked": N}   on success
        {"error": "...", "hint": "..."}  on failure
    """
    try:
        gmail = build("gmail", "v1", credentials=creds)

        # Get ALL unread IDs (up to 500 — Gmail's batchModify limit)
        result = gmail.users().messages().list(
            userId="me", q="is:unread", maxResults=500
        ).execute()

        ids = [m["id"] for m in result.get("messages", [])]
        if ids:
            gmail.users().messages().batchModify(
                userId="me",
                body={
                    "ids":            ids,
                    "removeLabelIds": ["UNREAD"],  # removing UNREAD = marking as read
                },
            ).execute()

        return jsonify({"success": True, "marked": len(ids)})

    except Exception as e:
        msg = str(e)
        # A 403 / insufficientPermissions error usually means the user logged in
        # before we added the gmail.modify scope — they need to sign out & back in.
        hint = (
            "Sign out and sign back in to grant the new permissions."
            if "insufficientPermissions" in msg or "403" in msg
            else ""
        )
        logger.warning("mark-read failed: %s", msg)
        return jsonify({"error": msg, "hint": hint}), 500
