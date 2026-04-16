# ─────────────────────────────────────────────────────────────
#  Dashboard Server — Python / Flask version
#  Replaces server.js. Run with:  python server.py
# ─────────────────────────────────────────────────────────────
#
#  What this file teaches you (Python concepts):
#  - Importing libraries (import / from … import)
#  - Functions (def)
#  - Dictionaries & lists (the main data structures)
#  - Reading / writing files (open, json.load, json.dump)
#  - HTTP routes with Flask (@app.route)
#  - Environment variables (os.environ / python-dotenv)
#  - Google OAuth2 flow with the google-auth library
# ─────────────────────────────────────────────────────────────

import os           # built-in: access environment variables & file paths
import json         # built-in: read/write JSON files
from pathlib import Path  # built-in: cleaner file path handling

from dotenv import load_dotenv   # pip: reads your .env file
from flask import Flask, request, redirect, jsonify, send_file  # pip: web framework
from flask_cors import CORS      # pip: allows browser to talk to this server

# Google API libraries
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleRequest
from requests_oauthlib import OAuth2Session

# ─── Load .env file ───────────────────────────────────────────
# This reads your GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET etc.
# from the .env file so we don't hardcode secrets in code.
load_dotenv(override=True)   # override=True ensures a freshly edited .env is always picked up

# ─── File paths ───────────────────────────────────────────────
# Path(__file__).parent = src/
# Path(__file__).parent.parent = project root (where .env, tokens.json, etc. live)
BASE_DIR   = Path(__file__).parent.parent
TOKEN_FILE = BASE_DIR / "tokens.json"
TIMESHEET_ID = "1lg7AQ6z2GaSHIRU4qVHfUPTJNkIUyQjtP5k5T8yKlcI"
DATA_FILE  = BASE_DIR / "dashboard-data.json"

# ─── Google OAuth config ──────────────────────────────────────
CLIENT_ID     = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
REDIRECT_URI  = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback")
PORT          = int(os.environ.get("PORT", 3000))

# The Zenith Google Doc ID (same as before)
ZENITH_DOC_ID = "1DCWSwpSohO_8eIe5Lsb1X7qlpgeE67L70JyohXO1BUc"

# Permissions we ask Google for.
# generative-language is the new one — lets us call Gemini AI
# using the same Google login, no separate API key needed.
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/gmail.modify",          # mark emails as read
    "https://www.googleapis.com/auth/calendar.readonly",     # read all calendars/events
    "https://www.googleapis.com/auth/calendar.events",       # create/edit events
    "https://www.googleapis.com/auth/spreadsheets",          # read/write timesheet
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# ─── Flask app setup ──────────────────────────────────────────
# Flask is the web framework. Think of it like Express in Node.
app = Flask(__name__)
CORS(app)  # allows the HTML page to call our API

@app.route("/")
def serve_index():
    return send_file(BASE_DIR / "index.html")

# Allow OAuth over plain http during local dev
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


# ─────────────────────────────────────────────────────────────
#  HELPER: Token storage
#  We save your Google tokens to tokens.json so you stay
#  logged in between server restarts — same idea as before.
# ─────────────────────────────────────────────────────────────

def save_tokens(creds: Credentials):
    """Write Google credentials to tokens.json."""
    data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes or []),
        "expiry":        creds.expiry.isoformat() if creds.expiry else None,
    }
    TOKEN_FILE.write_text(json.dumps(data))


def load_tokens() -> Credentials | None:
    """
    Read tokens.json and return a Credentials object.
    If the access token is expired, it automatically refreshes it
    using the refresh_token (so you never need to log in again).
    Returns None if no tokens are saved.
    """
    if not TOKEN_FILE.exists():
        return None

    data = json.loads(TOKEN_FILE.read_text())

    # The old Node.js server saved tokens with the key "access_token".
    # The Python server uses "token". If we find the old format, delete
    # the file so the user gets prompted to log in again cleanly.
    if "access_token" in data and "token" not in data:
        TOKEN_FILE.unlink()
        return None

    try:
        from datetime import datetime, timezone
        expiry_str = data.get("expiry")
        expiry = datetime.fromisoformat(expiry_str).replace(tzinfo=timezone.utc) if expiry_str else None
        creds = Credentials(
            token=data["token"],
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id", CLIENT_ID),
            client_secret=data.get("client_secret", CLIENT_SECRET),
            scopes=data.get("scopes", SCOPES),
            expiry=expiry,
        )
    except Exception:
        TOKEN_FILE.unlink()
        return None

    # If the access token has expired, refresh it automatically
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleRequest())
            save_tokens(creds)
        except Exception as e:
            print(f"Token refresh error: {e}")
            # Refresh failed but we still have the creds — let the caller handle it

    return creds


# ─────────────────────────────────────────────────────────────
#  HELPER: Dashboard data storage
#  All your tasks, links, exams live in dashboard-data.json.
#  This is shared across all your accounts.
# ─────────────────────────────────────────────────────────────

def load_data() -> dict:
    """Read dashboard-data.json, or return a fresh empty structure."""
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    # Default empty state — matches what the HTML expects
    return {
        "zenith":    [],
        "mathTodos": [],
        "kanban":    {"todo": [], "inprogress": [], "done": []},
        "exams":     [],
        "links":     {"zenith": [], "math": []},
    }


def save_data(data: dict):
    """Write dashboard data to dashboard-data.json."""
    DATA_FILE.write_text(json.dumps(data, indent=2))


# ─────────────────────────────────────────────────────────────
#  AUTH ROUTES
#  Same two-step OAuth flow as the Node version:
#   1. /auth/url  → generate a Google login URL, send to browser
#   2. /auth/callback → Google sends back a code, swap for tokens
# ─────────────────────────────────────────────────────────────

GOOGLE_AUTH_URI  = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


@app.route("/auth/url")
def auth_url():
    """
    The HTML calls this to get the Google login URL.
    We use requests_oauthlib directly so we have full control —
    no automatic PKCE, no state lost between requests.
    """
    # OAuth2Session manages the login URL generation.
    # Think of it as a helper that knows the OAuth protocol.
    oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPES)
    url, _ = oauth.authorization_url(
        GOOGLE_AUTH_URI,
        access_type="offline",   # get a refresh token so we stay logged in
        prompt="consent",        # always show the consent screen so we get refresh_token
    )
    return jsonify({"url": url})


@app.route("/auth/callback")
def auth_callback():
    """
    Google redirects here after the user logs in.
    We swap the one-time 'code' for real tokens and save them.
    """
    code = request.args.get("code")
    oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPES)
    # Exchange the code for an access token + refresh token
    token = oauth.fetch_token(
        GOOGLE_TOKEN_URI,
        code=code,
        client_secret=CLIENT_SECRET,
    )
    # Build a standard Google Credentials object and save it
    creds = Credentials(
        token=token["access_token"],
        refresh_token=token.get("refresh_token"),
        token_uri=GOOGLE_TOKEN_URI,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES,
    )
    save_tokens(creds)
    return redirect("/?auth=success")


@app.route("/auth/status")
def auth_status():
    """Returns whether we have valid saved tokens."""
    creds = load_tokens()
    return jsonify({"loggedIn": creds is not None and creds.valid})


@app.route("/auth/signout")
def auth_signout():
    """Delete saved tokens — effectively signs out."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()  # unlink = delete the file
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────
#  GOOGLE DATA ROUTES
#  Each route calls a different Google API and returns the data
#  as JSON to the browser. Same endpoints as the Node version.
# ─────────────────────────────────────────────────────────────

@app.route("/api/gmail")
def api_gmail():
    """Fetch up to 10 unread Gmail messages."""
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "Not authenticated"}), 401

    # build() creates a Google API client for a specific service.
    # "gmail" is the service name, "v1" is the API version.
    gmail = build("gmail", "v1", credentials=creds)

    result = gmail.users().messages().list(
        userId="me", maxResults=10, q="is:unread"
    ).execute()

    message_ids = result.get("messages", [])
    if not message_ids:
        return jsonify({"messages": []})

    messages = []
    for msg in message_ids:
        detail = gmail.users().messages().get(
            userId="me", id=msg["id"],
            format="metadata",
            metadataHeaders=["Subject", "From"]
        ).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        messages.append({
            "id":      msg["id"],
            "subject": headers.get("Subject", "(no subject)"),
            "from":    headers.get("From", ""),
        })

    return jsonify({"messages": messages})


@app.route("/api/gmail/mark-read", methods=["POST"])
def gmail_mark_read():
    """Mark all unread emails as read."""
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        gmail = build("gmail", "v1", credentials=creds)

        result = gmail.users().messages().list(
            userId="me", q="is:unread", maxResults=500
        ).execute()

        ids = [m["id"] for m in result.get("messages", [])]
        if ids:
            gmail.users().messages().batchModify(
                userId="me",
                body={"ids": ids, "removeLabelIds": ["UNREAD"]},
            ).execute()

        return jsonify({"success": True, "marked": len(ids)})
    except Exception as e:
        # If it's a scope error, tell the user to sign out and back in
        msg = str(e)
        hint = "Sign out of the dashboard and sign back in to grant the new permissions." if "insufficientPermissions" in msg or "403" in msg else ""
        return jsonify({"error": msg, "hint": hint}), 500


@app.route("/api/calendar")
def api_calendar():
    """
    Fetch events from ALL the user's calendars (personal, holidays, birthdays, etc.)
    Optional ?year=YYYY&month=M for a specific month.
    """
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "Not authenticated"}), 401

    from datetime import datetime, timezone, timedelta
    cal_service = build("calendar", "v3", credentials=creds)

    year  = request.args.get("year",  type=int)
    month = request.args.get("month", type=int)

    if year and month:
        time_min = datetime(year, month, 1, tzinfo=timezone.utc).isoformat()
        time_max = (
            datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12
            else datetime(year, month + 1, 1, tzinfo=timezone.utc)
        ).isoformat()
    else:
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=60)).isoformat()

    # Get the list of all calendars this user has (includes holidays, birthdays, etc.)
    try:
        cal_list_result = cal_service.calendarList().list().execute()
        calendars = cal_list_result.get("items", [])
    except Exception:
        calendars = [{"id": "primary", "summary": "My Calendar", "backgroundColor": "#7c6af7"}]

    all_events = []
    for cal in calendars[:20]:   # cap at 20 calendars to stay fast
        # Skip calendars the user has hidden in Google Calendar
        if not cal.get("selected", True):
            continue
        try:
            result = cal_service.events().list(
                calendarId=cal["id"],
                timeMin=time_min,
                timeMax=time_max,
                maxResults=50,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            color = cal.get("backgroundColor", "#7c6af7")
            for e in result.get("items", []):
                all_events.append({
                    "id":         e["id"],
                    "calendarId": cal["id"],           # needed so frontend can delete
                    "title":      e.get("summary", "(no title)"),
                    "start":      e["start"].get("dateTime") or e["start"].get("date"),
                    "end":        e["end"].get("dateTime")   or e["end"].get("date"),
                    "calendar":   cal.get("summary", ""),
                    "color":      color,
                })
        except Exception:
            pass  # skip any calendar we can't read (shared/limited access)

    # Sort all collected events by start time
    all_events.sort(key=lambda x: x.get("start", ""))
    return jsonify({"events": all_events})


@app.route("/api/calendar/add", methods=["POST"])
def calendar_add_event():
    """
    Create a new all-day (or multi-day) event in the primary calendar.
    Body: { "name": "...", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" (optional) }
    """
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "Not authenticated"}), 401

    body  = request.get_json()
    name  = body.get("name",  "").strip()
    start = body.get("start", "").strip()
    end   = body.get("end",   "").strip()

    if not name or not start:
        return jsonify({"error": "Name and start date are required"}), 400

    from datetime import date, timedelta
    cal_service = build("calendar", "v3", credentials=creds)

    # Google Calendar's all-day end date is exclusive (day AFTER the last visible day)
    if end and end != start:
        end_excl = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
    else:
        end_excl = (date.fromisoformat(start) + timedelta(days=1)).isoformat()

    event_body = {
        "summary": name,
        "start":   {"date": start},
        "end":     {"date": end_excl},
    }

    try:
        created = cal_service.events().insert(calendarId="primary", body=event_body).execute()
        return jsonify({"success": True, "id": created.get("id")})
    except Exception as e:
        msg = str(e)
        if "insufficientPermissions" in msg or "403" in msg:
            return jsonify({
                "error": "Missing calendar write permission.",
                "hint": "REAUTH"   # frontend will show the sign-out prompt
            }), 403
        return jsonify({"error": msg}), 500


@app.route("/api/calendar/delete", methods=["POST"])
def calendar_delete_event():
    """
    Delete a calendar event.
    Body: { "eventId": "...", "calendarId": "..." }
    """
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "Not authenticated"}), 401

    body        = request.get_json()
    event_id    = body.get("eventId", "")
    calendar_id = body.get("calendarId", "primary")

    if not event_id:
        return jsonify({"error": "eventId is required"}), 400

    try:
        cal_service = build("calendar", "v3", credentials=creds)
        cal_service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        msg = str(e)
        if "403" in msg or "insufficientPermissions" in msg:
            return jsonify({"error": "This calendar is read-only (e.g. US Holidays). You can only delete events you created."}), 403
        if "410" in msg or "404" in msg:
            # Already deleted
            return jsonify({"success": True})
        return jsonify({"error": msg}), 500


@app.route("/api/drive")
def api_drive():
    """Fetch the 10 most recently modified Drive files."""
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "Not authenticated"}), 401

    drive = build("drive", "v3", credentials=creds)
    result = drive.files().list(
        pageSize=10,
        fields="files(id, name, mimeType, webViewLink, modifiedTime)",
        orderBy="modifiedTime desc",
    ).execute()

    return jsonify({"files": result.get("files", [])})


# ─────────────────────────────────────────────────────────────
#  ZENITH DOC PARSER
#  Same logic as server.js — reads your Google Doc and extracts
#  action items from each meeting tab.
# ─────────────────────────────────────────────────────────────

@app.route("/api/zenith")
def api_zenith():
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "Not authenticated"}), 401

    docs = build("docs", "v1", credentials=creds)
    doc = docs.documents().get(
        documentId=ZENITH_DOC_ID,
        includeTabsContent=True,
    ).execute()

    meetings = []
    tabs = doc.get("tabs", [])

    for tab in tabs:
        tab_title = tab.get("tabProperties", {}).get("title", "Untitled")

        # Skip template / root tabs
        if "template" in tab_title.lower() or tab_title.lower() == "root":
            continue

        content = (
            tab.get("documentTab", {})
               .get("body", {})
               .get("content", [])
        )

        in_action_items = False
        item_index = 0
        action_items = []

        for block in content:
            if "paragraph" not in block:
                continue

            para = block["paragraph"]
            text = "".join(
                e.get("textRun", {}).get("content", "")
                for e in para.get("elements", [])
            ).strip()

            if not text:
                continue

            style = para.get("paragraphStyle", {}).get("namedStyleType", "")

            # Detect "Action Items #N" heading (not "Previous Action Items")
            import re
            if (
                style == "HEADING_2"
                and "action items" in text.lower()
                and "previous" not in text.lower()
                and re.search(r"#+\d+", text)
            ):
                in_action_items = True
                continue

            if in_action_items and style in ("HEADING_1", "HEADING_2"):
                in_action_items = False

            if in_action_items and para.get("bullet") and len(text) > 2:
                links = []
                for element in para.get("elements", []):
                    url  = element.get("textRun", {}).get("textStyle", {}).get("link", {}).get("url")
                    link_text = element.get("textRun", {}).get("content", "").strip()
                    if url and link_text:
                        links.append({"text": link_text, "url": url})

                item_index += 1
                # Stable ID based on text content (not position)
                stable_id = f"{tab_title.replace(' ', '_')}-{re.sub(r'[^a-z0-9]+', '_', text[:50].lower())}"
                action_items.append({"id": stable_id, "text": text, "links": links})

        if action_items:
            meetings.append({"title": tab_title, "actionItems": action_items})

    # Sort by meeting number descending (newest first)
    def meeting_num(m):
        match = re.search(r"\d+", m["title"])
        return int(match.group()) if match else 0

    meetings.sort(key=meeting_num, reverse=True)
    return jsonify({"meetings": meetings})


# ─────────────────────────────────────────────────────────────
#  DASHBOARD DATA ROUTES
#  GET  /api/data  → return all dashboard data as JSON
#  POST /api/data  → save new dashboard data (body = full state)
# ─────────────────────────────────────────────────────────────

@app.route("/api/data", methods=["GET"])
def get_data():
    return jsonify(load_data())


@app.route("/api/data", methods=["POST"])
def post_data():
    save_data(request.get_json())
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────
#  AI CHATBOT — Groq AI
#
#  Uses the same Google login token you already have.
#  No separate API key needed.
#
#  How it works:
#  1. Frontend sends the user's message + full chat history
#  2. We load the current dashboard data (tasks, exams, etc.)
#  3. We build a prompt that includes all that data as context
#  4. We call the Gemini API using your Google OAuth token
#  5. We parse the response for any ACTION commands (add items)
#  6. We return the AI reply + execute any actions
# ─────────────────────────────────────────────────────────────

import requests as http_requests  # for calling Gemini REST API
from datetime import date


def _pid(val) -> str:
    """Return the ID value as a string for embedding in context."""
    return str(val)


def build_dashboard_context(data: dict) -> str:
    """
    Turns the dashboard data dictionary into a readable text summary.
    Each item includes its [id:…] so the AI can reference it in actions.
    """
    lines = []
    today = date.today()

    zenith = [z for z in data.get("zenith", []) if not z.get("done")]
    if zenith:
        lines.append("ZENITH ACTION ITEMS (manually added):")
        for z in zenith:
            lines.append(f"  • [id:{_pid(z['id'])}] {z.get('title', '')}")

    math = [m for m in data.get("mathTodos", []) if not m.get("done")]
    if math:
        lines.append("\nMATH TO-DOs:")
        for m in math:
            lines.append(f"  • [id:{_pid(m['id'])}] {m.get('text', '')}")

    kanban = data.get("kanban", {})
    has_kanban = any(kanban.get(c) for c in ["todo", "inprogress", "done"])
    if has_kanban:
        lines.append("\nCODING PROJECTS (kanban):")
        for col, label in {"todo": "To Do", "inprogress": "In Progress", "done": "Done"}.items():
            items = kanban.get(col, [])
            if items:
                lines.append(f"  {label}:")
                for item in items:
                    lines.append(f"    - [id:{_pid(item['id'])}|col:{col}] {item.get('text', '')}")

    return "\n".join(lines) if lines else "No items in the dashboard yet."


def parse_zenith_doc(creds: Credentials) -> list:
    """
    Re-uses the same parsing logic as api_zenith() but returns
    the meeting list directly so other code can call it.
    """
    import re
    try:
        docs = build("docs", "v1", credentials=creds)
        doc = docs.documents().get(
            documentId=ZENITH_DOC_ID,
            includeTabsContent=True,
        ).execute()
    except Exception:
        return []

    meetings = []
    for tab in doc.get("tabs", []):
        tab_title = tab.get("tabProperties", {}).get("title", "Untitled")
        if "template" in tab_title.lower() or tab_title.lower() == "root":
            continue

        content = (
            tab.get("documentTab", {})
               .get("body", {})
               .get("content", [])
        )
        in_action_items = False
        action_items = []

        for block in content:
            if "paragraph" not in block:
                continue
            para = block["paragraph"]
            text = "".join(
                e.get("textRun", {}).get("content", "")
                for e in para.get("elements", [])
            ).strip()
            if not text:
                continue
            style = para.get("paragraphStyle", {}).get("namedStyleType", "")
            if (
                style == "HEADING_2"
                and "action items" in text.lower()
                and "previous" not in text.lower()
                and re.search(r"#+\d+", text)
            ):
                in_action_items = True
                continue
            if in_action_items and style in ("HEADING_1", "HEADING_2"):
                in_action_items = False
            if in_action_items and para.get("bullet") and len(text) > 2:
                stable_id = f"{tab_title.replace(' ', '_')}-{re.sub(r'[^a-z0-9]+', '_', text[:50].lower())}"
                action_items.append({"id": stable_id, "text": text})

        if action_items:
            meetings.append({"title": tab_title, "actionItems": action_items})

    def meeting_num(m):
        match = re.search(r"\d+", m["title"])
        return int(match.group()) if match else 0
    meetings.sort(key=meeting_num, reverse=True)
    return meetings


def _coerce_id(s: str):
    """Convert a string ID to int if it looks like one, otherwise keep as str."""
    try:
        return int(s)
    except (ValueError, TypeError):
        return s


def process_chat_action(action: str, dashboard: dict, index: int = 0):
    """
    Parses a single ACTION string and mutates `dashboard` accordingly.

    ADD actions:
      ADD_ZENITH:title
      ADD_MATH_TODO:text
      ADD_KANBAN_TODO:text
      ADD_KANBAN_INPROGRESS:text
      ADD_EXAM:name|subject|YYYY-MM-DD

    DONE actions (mark complete):
      DONE_ZENITH:<id>          — manually-added zenith item
      DONE_ZENITH_DOC:<id>      — Zenith Google Doc item (stable string id)
      DONE_MATH_TODO:<id>

    REMOVE actions:
      REMOVE_ZENITH:<id>
      REMOVE_MATH_TODO:<id>
      REMOVE_KANBAN:<id>        — searches all columns

    EDIT actions:
      EDIT_ZENITH:<id>|<new title>
      EDIT_MATH_TODO:<id>|<new text>

    MOVE kanban between columns:
      MOVE_KANBAN:<id>|<to_column>   (to_column: todo / inprogress / done)
    """
    import time
    new_id = int(time.time() * 1000) + index

    try:
        # ── ADD ────────────────────────────────────────────────
        if action.startswith("ADD_ZENITH:"):
            dashboard.setdefault("zenith", []).append({
                "id": new_id, "title": action[11:].strip(), "link": "", "done": False
            })
        elif action.startswith("ADD_MATH_TODO:"):
            dashboard.setdefault("mathTodos", []).append({
                "id": new_id, "text": action[14:].strip(), "done": False
            })
        elif action.startswith("ADD_KANBAN_TODO:"):
            dashboard.setdefault("kanban", {}).setdefault("todo", []).append(
                {"id": new_id, "text": action[16:].strip()}
            )
        elif action.startswith("ADD_KANBAN_INPROGRESS:"):
            dashboard.setdefault("kanban", {}).setdefault("inprogress", []).append(
                {"id": new_id, "text": action[22:].strip()}
            )
        # ── DONE ───────────────────────────────────────────────
        elif action.startswith("DONE_ZENITH_DOC:"):
            sid = action[16:].strip()
            # Frontend stores completions as {id: true}, NOT an array — match that format
            completions = dashboard.setdefault("zenithDocCompletions", {})
            completions[sid] = True

        elif action.startswith("DONE_ZENITH:"):
            tid = _coerce_id(action[12:].strip())
            for z in dashboard.get("zenith", []):
                if z.get("id") == tid:
                    z["done"] = True
                    break

        elif action.startswith("DONE_MATH_TODO:"):
            tid = _coerce_id(action[15:].strip())
            for m in dashboard.get("mathTodos", []):
                if m.get("id") == tid:
                    m["done"] = True
                    break

        # ── REMOVE ─────────────────────────────────────────────
        elif action.startswith("REMOVE_ZENITH:"):
            tid = _coerce_id(action[14:].strip())
            dashboard["zenith"] = [z for z in dashboard.get("zenith", []) if z.get("id") != tid]

        elif action.startswith("REMOVE_MATH_TODO:"):
            tid = _coerce_id(action[17:].strip())
            dashboard["mathTodos"] = [m for m in dashboard.get("mathTodos", []) if m.get("id") != tid]

        elif action.startswith("REMOVE_KANBAN:"):
            tid = _coerce_id(action[14:].strip())
            kanban = dashboard.get("kanban", {})
            for col in ["todo", "inprogress", "done"]:
                kanban[col] = [k for k in kanban.get(col, []) if k.get("id") != tid]

        # ── EDIT ───────────────────────────────────────────────
        elif action.startswith("EDIT_ZENITH:"):
            parts = action[12:].split("|", 1)
            if len(parts) == 2:
                tid = _coerce_id(parts[0].strip())
                for z in dashboard.get("zenith", []):
                    if z.get("id") == tid:
                        z["title"] = parts[1].strip()
                        break

        elif action.startswith("EDIT_MATH_TODO:"):
            parts = action[15:].split("|", 1)
            if len(parts) == 2:
                tid = _coerce_id(parts[0].strip())
                for m in dashboard.get("mathTodos", []):
                    if m.get("id") == tid:
                        m["text"] = parts[1].strip()
                        break

        # ── MOVE KANBAN ────────────────────────────────────────
        elif action.startswith("MOVE_KANBAN:"):
            parts = action[12:].split("|")
            if len(parts) >= 2:
                tid   = _coerce_id(parts[0].strip())
                to_col = parts[-1].strip()
                kanban = dashboard.get("kanban", {})
                moved  = None
                for col in ["todo", "inprogress", "done"]:
                    for k in kanban.get(col, []):
                        if k.get("id") == tid:
                            moved = k
                            break
                    if moved:
                        kanban[col] = [k for k in kanban[col] if k.get("id") != tid]
                        break
                if moved and to_col in ["todo", "inprogress", "done"]:
                    kanban.setdefault(to_col, []).append(moved)


    except Exception as e:
        print(f"Action error ({action}): {e}")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "not_authenticated"}), 401

    body         = request.get_json()
    user_message = body.get("message", "").strip()
    # history is a list of {role: "user"|"model", text: "..."}
    history      = body.get("history", [])

    if not user_message:
        return jsonify({"error": "empty message"}), 400

    # Build the system context prompt with current dashboard data
    data = load_data()
    dashboard_context = build_dashboard_context(data)

    # Also fetch live Zenith Google Doc action items (with IDs + done status)
    zenith_doc_context = ""
    zenith_meetings = parse_zenith_doc(creds)
    if zenith_meetings:
        completions = data.get("zenithDocCompletions", {})
        lines = ["\nZENITH GOOGLE DOC LIVE ACTION ITEMS (from Google Doc):"]
        for meeting in zenith_meetings[:5]:
            lines.append(f"  {meeting['title']}:")
            for item in meeting["actionItems"]:
                done_tag = " ✓ done" if item["id"] in completions else ""
                lines.append(f"    • [id:{item['id']}] {item['text']}{done_tag}")
        zenith_doc_context = "\n".join(lines)

    # Fetch unread Gmail messages for context
    gmail_context = ""
    try:
        gmail_svc = build("gmail", "v1", credentials=creds)
        gmail_result = gmail_svc.users().messages().list(
            userId="me", maxResults=10, q="is:unread"
        ).execute()
        gmail_ids = gmail_result.get("messages", [])
        if gmail_ids:
            lines = ["\nUNREAD GMAIL (up to 10):"]
            for msg in gmail_ids:
                detail = gmail_svc.users().messages().get(
                    userId="me", id=msg["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From"]
                ).execute()
                headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
                lines.append(f"  • [emailId:{msg['id']}] From: {headers.get('From', '')} — {headers.get('Subject', '(no subject)')}")
            gmail_context = "\n".join(lines)
        else:
            gmail_context = "\nUNREAD GMAIL: No unread emails."
    except Exception as e:
        import traceback
        print(f"Gmail context error: {e}")
        traceback.print_exc()
        gmail_context = "\nUNREAD GMAIL: (could not fetch)"

    print(f"[DEBUG] gmail_context length: {len(gmail_context)}, preview: {gmail_context[:100]}")

    # Fetch upcoming Google Calendar events for context
    calendar_context = ""
    try:
        from datetime import datetime, timezone
        cal_service = build("calendar", "v3", credentials=creds)
        now_iso = datetime.now(timezone.utc).isoformat()
        cal_result = cal_service.events().list(
            calendarId="primary",
            timeMin=now_iso,
            maxResults=15,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        cal_events = cal_result.get("items", [])
        if cal_events:
            lines = ["\nGOOGLE CALENDAR EVENTS (upcoming, primary calendar):"]
            for ev in cal_events:
                start = ev.get("start", {}).get("date") or ev.get("start", {}).get("dateTime", "")[:10]
                lines.append(f"  • [eventId:{ev['id']}|calId:primary] {ev.get('summary', '(no title)')} — {start}")
            calendar_context = "\n".join(lines)
    except Exception:
        pass

    system_prompt = f"""You are a helpful personal assistant inside Sid's Utopia — Siddhant's personal dashboard.

Today's date: {date.today().strftime("%B %d, %Y")}

The "Exams & Events" tab is Google Calendar only. When the user says "add to calendar", "schedule", or "add an event/exam", always use ADD_CALENDAR_EVENT.

Current dashboard data:
{dashboard_context}{zenith_doc_context}{calendar_context}{gmail_context}

Your job:
1. Answer questions about the dashboard (tasks, exams, calendar events, projects)
2. Give summaries and reports when asked
3. Add, remove, mark done, or edit items when asked

Put ACTION lines at the very end of your reply (after your text). Use the exact [id:…] values shown above.

CALENDAR EVENTS:
  ACTION:ADD_CALENDAR_EVENT:title|YYYY-MM-DD
  ACTION:REMOVE_CALENDAR_EVENT:eventId|calendarId

ZENITH / TASKS:
  ACTION:ADD_ZENITH:title
  ACTION:ADD_MATH_TODO:text
  ACTION:ADD_KANBAN_TODO:text
  ACTION:ADD_KANBAN_INPROGRESS:text

MARK DONE (check off):
  ACTION:DONE_ZENITH_DOC:<id>     ← for Google Doc meeting items
  ACTION:DONE_ZENITH:<id>         ← for manually-added zenith items
  ACTION:DONE_MATH_TODO:<id>

REMOVE:
  ACTION:REMOVE_ZENITH:<id>
  ACTION:REMOVE_MATH_TODO:<id>
  ACTION:REMOVE_KANBAN:<id>

EDIT:
  ACTION:EDIT_ZENITH:<id>|<new title>
  ACTION:EDIT_MATH_TODO:<id>|<new text>

MOVE kanban column:
  ACTION:MOVE_KANBAN:<id>|<to_column>   (to_column: todo / inprogress / done)

Rules:
- NEVER add a new item to describe that something is done — use DONE_* instead
- NEVER add a new item when asked to edit — use EDIT_* instead
- Only output ACTION lines when explicitly asked to change something
- Be concise and friendly; use bullet points for lists"""

    # Use Groq (free, fast, no age/quota restrictions).
    # Convert chat history to OpenAI-compatible format (Groq uses the same format).
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        return jsonify({"error": "GROQ_API_KEY not set in .env"}), 500

    groq_messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = "assistant" if msg["role"] == "model" else "user"
        groq_messages.append({"role": role, "content": msg["text"]})
    groq_messages.append({"role": "user", "content": user_message})

    response = http_requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": groq_messages,
            "temperature": 0.7,
            "max_tokens": 1024,
        },
        timeout=30,
    )

    if response.status_code != 200:
        return jsonify({"error": f"Groq error {response.status_code}: {response.text}"}), 500

    ai_text = response.json()["choices"][0]["message"]["content"]

    # Separate ACTION lines from the readable response
    actions     = []
    reply_lines = []
    for line in ai_text.splitlines():
        if line.startswith("ACTION:"):
            actions.append(line[7:])
        else:
            reply_lines.append(line)

    clean_reply = "\n".join(reply_lines).strip()

    # Execute any actions and save the updated dashboard
    if actions:
        dashboard = load_data()
        cal_service = None
        for i, action in enumerate(actions):
            if action.startswith("ADD_CALENDAR_EVENT:"):
                parts = action[19:].split("|")
                if len(parts) >= 2:
                    try:
                        if cal_service is None:
                            cal_service = build("calendar", "v3", credentials=creds)
                        cal_service.events().insert(calendarId="primary", body={
                            "summary": parts[0].strip(),
                            "start": {"date": parts[1].strip()},
                            "end":   {"date": parts[1].strip()},
                        }).execute()
                    except Exception as e:
                        print(f"Calendar add error: {e}")
            elif action.startswith("REMOVE_CALENDAR_EVENT:"):
                parts = action[22:].split("|")
                if len(parts) >= 2:
                    try:
                        if cal_service is None:
                            cal_service = build("calendar", "v3", credentials=creds)
                        cal_service.events().delete(
                            calendarId=parts[1].strip(),
                            eventId=parts[0].strip(),
                        ).execute()
                    except Exception as e:
                        print(f"Calendar delete error: {e}")
            else:
                process_chat_action(action, dashboard, index=i)
        save_data(dashboard)

    return jsonify({"response": clean_reply, "actions": actions})


# ─────────────────────────────────────────────────────────────
#  TIMESHEET ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/api/timesheet")
def api_timesheet():
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "not_authenticated"}), 401
    try:
        from datetime import datetime as dt
        MONTH_NAMES = ['January','February','March','April','May','June',
                       'July','August','September','October','November','December']
        sheets_svc = build("sheets", "v4", credentials=creds)
        meta = sheets_svc.spreadsheets().get(spreadsheetId=TIMESHEET_ID).execute()

        months = []
        for sheet in meta["sheets"]:
            title = sheet["properties"]["title"].strip()
            # Expect tab names like "March 2026"
            parts = title.split()
            if len(parts) != 2 or parts[0] not in MONTH_NAMES:
                continue
            try:
                year = int(parts[1])
                month_num = MONTH_NAMES.index(parts[0]) + 1
            except Exception:
                continue

            month_key = f"{year}-{month_num:02d}"

            result = sheets_svc.spreadsheets().values().get(
                spreadsheetId=TIMESHEET_ID,
                range=f"'{title}'"
            ).execute()
            values = result.get("values", [])
            if not values or len(values) < 2:
                continue

            headers = values[0]
            date_cols = []
            for col_i, h in enumerate(headers[1:], start=1):
                try:
                    raw = h.strip()
                    date_obj = dt.strptime(raw, "%m/%d/%y") if len(raw.split('/')[-1]) == 2 else dt.strptime(raw, "%m/%d/%Y")
                    date_cols.append({
                        "col_index": col_i,
                        "sheet_col": col_i + 1,
                        "date_str": raw,
                        "date_obj": date_obj,
                    })
                except Exception:
                    pass

            rows = []
            for row_i, row in enumerate(values[1:], start=1):
                activity = row[0] if row else ""
                if not activity:
                    continue
                cells = []
                for dc in date_cols:
                    ci = dc["col_index"]
                    val = row[ci] if ci < len(row) else ""
                    cells.append({
                        "value": val,
                        "sheet_row": row_i + 1,
                        "sheet_col": dc["sheet_col"],
                        "date": dc["date_str"],
                    })
                rows.append({"activity": activity, "cells": cells})

            months.append({
                "key": month_key,
                "label": title,
                "sheet_name": title,
                "dates": [dc["date_str"] for dc in date_cols],
                "rows": rows,
            })

        months.sort(key=lambda m: m["key"], reverse=True)
        return jsonify({"months": months})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/timesheet/update", methods=["POST"])
def api_timesheet_update():
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "not_authenticated"}), 401
    try:
        body = request.get_json()
        sheet_row = int(body["row"])
        sheet_col = int(body["col"])
        value = body.get("value", "")
        sheet_name = body.get("sheet_name", "Sheet1")

        col_letter = ""
        c = sheet_col
        while c > 0:
            c, rem = divmod(c - 1, 26)
            col_letter = chr(65 + rem) + col_letter

        cell_ref = f"'{sheet_name}'!{col_letter}{sheet_row}"
        sheets_svc = build("sheets", "v4", credentials=creds)
        sheets_svc.spreadsheets().values().update(
            spreadsheetId=TIMESHEET_ID,
            range=cell_ref,
            valueInputOption="USER_ENTERED",
            body={"values": [[value]]},
        ).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/timesheet/add-month", methods=["POST"])
def api_timesheet_add_month():
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "not_authenticated"}), 401
    try:
        import calendar
        MONTH_NAMES = ['January','February','March','April','May','June',
                       'July','August','September','October','November','December']
        body = request.get_json()
        year = int(body["year"])
        month = int(body["month"])
        tab_title = f"{MONTH_NAMES[month - 1]} {year}"

        sheets_svc = build("sheets", "v4", credentials=creds)
        meta = sheets_svc.spreadsheets().get(spreadsheetId=TIMESHEET_ID).execute()
        existing_titles = [s["properties"]["title"] for s in meta["sheets"]]

        if tab_title in existing_titles:
            return jsonify({"days_added": 0, "message": "Tab already exists"})

        # Find the most recent existing month tab by date, then copy its activity list
        month_tabs = []
        for s in meta["sheets"]:
            t = s["properties"]["title"].strip().split()
            if len(t) == 2 and t[0] in MONTH_NAMES:
                try:
                    mn = MONTH_NAMES.index(t[0]) + 1
                    yr = int(t[1])
                    month_tabs.append((yr, mn, s["properties"]["title"]))
                except Exception:
                    pass

        activity_list = []
        if month_tabs:
            month_tabs.sort(reverse=True)   # newest first by (year, month)
            source_tab = month_tabs[0][2]
            res = sheets_svc.spreadsheets().values().get(
                spreadsheetId=TIMESHEET_ID,
                range=f"'{source_tab}'!A:A"
            ).execute()
            col_a = res.get("values", [])
            # Skip the header row ("Activity") and collect all non-empty names
            activity_list = [r[0].strip() for r in col_a[1:] if r and r[0].strip()]

        # Create the new tab
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=TIMESHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": tab_title}}}]}
        ).execute()

        # Build header + activity rows
        days_in_month = calendar.monthrange(year, month)[1]
        dates = [f"{month}/{day}/{str(year)[2:]}" for day in range(1, days_in_month + 1)]
        rows_to_write = [["Activity"] + dates]
        for act in activity_list:
            rows_to_write.append([act] + [""] * days_in_month)

        sheets_svc.spreadsheets().values().update(
            spreadsheetId=TIMESHEET_ID,
            range=f"'{tab_title}'!A1",
            valueInputOption="RAW",
            body={"values": rows_to_write},
        ).execute()

        return jsonify({"days_added": days_in_month})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/timesheet/delete-month", methods=["POST"])
def api_timesheet_delete_month():
    creds = load_tokens()
    if not creds:
        return jsonify({"error": "not_authenticated"}), 401
    try:
        body = request.get_json()
        tab_title = body["month_key"]  # now the tab title e.g. "April 2026"

        sheets_svc = build("sheets", "v4", credentials=creds)
        meta = sheets_svc.spreadsheets().get(spreadsheetId=TIMESHEET_ID).execute()

        sheet_id = None
        for s in meta["sheets"]:
            if s["properties"]["title"] == tab_title:
                sheet_id = s["properties"]["sheetId"]
                break

        if sheet_id is None:
            return jsonify({"error": "Tab not found"}), 404

        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=TIMESHEET_ID,
            body={"requests": [{"deleteSheet": {"sheetId": sheet_id}}]}
        ).execute()
        return jsonify({"success": True})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  START SERVER
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Dashboard server running at http://localhost:{PORT}")
    print("Open your dashboard and click 'Connect Google Account'")
    app.run(host="0.0.0.0", port=PORT, debug=False)
