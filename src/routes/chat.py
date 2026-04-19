"""
routes/chat.py  —  AI chat route: POST /api/chat
══════════════════════════════════════════════════════════════════════════════

What does this file do?
  Powers the "Utopia AI" chat panel in the bottom-right corner.

  When the user sends a message, this route:
    1. Pulls the FULL current state of the dashboard (tasks, kanban, exams …)
    2. Fetches live data (Zenith Doc, Gmail, Calendar) to give the AI context
    3. Sends everything to Groq's AI API along with the user's message
    4. Parses the AI's reply for ACTION: lines (commands to change the dashboard)
    5. Executes those actions (add/remove/edit/move items, add calendar events)
    6. Returns the text reply + list of actions to the frontend

What is Groq?
  Groq is an AI service (like OpenAI) that runs large language models.
  We use "llama-3.3-70b-versatile" — a very capable open-source model.
  The API is compatible with OpenAI's format, so we send a list of messages
  and get a text response back.

What are ACTION: lines?
  The AI is told in its system prompt to append special command lines to its
  reply, like:
      ACTION:ADD_MATH_TODO:Review chapter 5
      ACTION:DONE_ZENITH:1714000000001
  process_chat_action() reads these and mutates the dashboard dictionary.
══════════════════════════════════════════════════════════════════════════════
"""
import logging
import time
from datetime import date

import requests as http_requests
from flask import Blueprint, request, jsonify
from googleapiclient.discovery import build

from config import GROQ_API_KEY
from routes import require_auth
from services.data_service import load_data, save_data
from services.zenith_parser import parse_zenith_doc

bp = Blueprint("chat", __name__)
logger = logging.getLogger(__name__)


# ── Helper: stringify any id ──────────────────────────────────────────────────

def _pid(val) -> str:
    """Convert any id value to a string (so IDs display consistently in prompts)."""
    return str(val)


# ── Context builder ───────────────────────────────────────────────────────────

def build_dashboard_context(data: dict) -> str:
    """Format the dashboard's tasks/kanban into a plain-text block for the AI.

    We include the item IDs in [id:...] tags so the AI can reference them
    in ACTION: commands (e.g. DONE_MATH_TODO:1714000000001).

    Args:
        data: The full dashboard state dictionary (from load_data()).

    Returns:
        A multi-line string describing all current non-done items.
    """
    lines = []

    # Zenith action items that haven't been checked off yet
    zenith = [z for z in data.get("zenith", []) if not z.get("done")]
    if zenith:
        lines.append("ZENITH ACTION ITEMS (manually added):")
        for z in zenith:
            lines.append(f"  • [id:{_pid(z['id'])}] {z.get('title', '')}")

    # Math to-dos that are still open
    math = [m for m in data.get("mathTodos", []) if not m.get("done")]
    if math:
        lines.append("\nMATH TO-DOs:")
        for m in math:
            lines.append(f"  • [id:{_pid(m['id'])}] {m.get('text', '')}")

    # Kanban board — all three columns
    kanban = data.get("kanban", {})
    if any(kanban.get(c) for c in ["todo", "inprogress", "done"]):
        lines.append("\nCODING PROJECTS (kanban):")
        for col, label in {"todo": "To Do", "inprogress": "In Progress", "done": "Done"}.items():
            items = kanban.get(col, [])
            if items:
                lines.append(f"  {label}:")
                for item in items:
                    # Include |col:... so the AI knows which column to move FROM
                    lines.append(f"    - [id:{_pid(item['id'])}|col:{col}] {item.get('text', '')}")

    return "\n".join(lines) if lines else "No items in the dashboard yet."


# ── Action processor ──────────────────────────────────────────────────────────

def _coerce_id(s: str):
    """Try to convert a string ID to an integer; return the string if it can't.

    IDs are stored as integers (timestamps) but the AI returns them as strings.
    This function handles both cases so lookups work either way.
    """
    try:
        return int(s)
    except (ValueError, TypeError):
        return s


def process_chat_action(action: str, dashboard: dict, index: int = 0) -> None:
    """Parse a single ACTION string and mutate the dashboard dictionary in-place.

    The AI returns lines like:
        ACTION:ADD_MATH_TODO:Review chapter 5
        ACTION:DONE_ZENITH:1714000000001
        ACTION:MOVE_KANBAN:1714000000002|inprogress

    This function strips the "ACTION:" prefix, figures out the verb, and
    makes the corresponding change to `dashboard`.

    Note: `dashboard` is mutated directly (no return value).
          The caller is responsible for calling save_data() afterwards.

    Supported verbs:
      ADD_ZENITH            — Add a new Zenith action item
      ADD_MATH_TODO         — Add a new Math to-do
      ADD_KANBAN_TODO       — Add a card to the "To Do" column
      ADD_KANBAN_INPROGRESS — Add a card to the "In Progress" column
      DONE_ZENITH_DOC       — Mark a Google Doc action item as done
      DONE_ZENITH           — Check off a manually-added Zenith item
      DONE_MATH_TODO        — Check off a Math to-do
      REMOVE_ZENITH         — Delete a Zenith item
      REMOVE_MATH_TODO      — Delete a Math to-do
      REMOVE_KANBAN         — Delete a Kanban card from any column
      EDIT_ZENITH           — Rename a Zenith item
      EDIT_MATH_TODO        — Rename a Math to-do
      MOVE_KANBAN           — Move a Kanban card to a different column

    Args:
        action: The action string WITHOUT the leading "ACTION:" prefix.
        dashboard: The current dashboard state dict (will be modified).
        index: Used to offset generated IDs when multiple actions fire at once.
    """
    # Generate a unique ID: current time in milliseconds + offset
    # Using time.time() * 1000 means IDs are roughly chronological
    new_id = int(time.time() * 1000) + index

    try:
        if action.startswith("ADD_ZENITH:"):
            # action[11:] strips the "ADD_ZENITH:" prefix, leaving just the title text
            dashboard.setdefault("zenith", []).append(
                {"id": new_id, "title": action[11:].strip(), "link": "", "done": False}
            )
        elif action.startswith("ADD_MATH_TODO:"):
            dashboard.setdefault("mathTodos", []).append(
                {"id": new_id, "text": action[14:].strip(), "done": False}
            )
        elif action.startswith("ADD_KANBAN_TODO:"):
            dashboard.setdefault("kanban", {}).setdefault("todo", []).append(
                {"id": new_id, "text": action[16:].strip()}
            )
        elif action.startswith("ADD_KANBAN_INPROGRESS:"):
            dashboard.setdefault("kanban", {}).setdefault("inprogress", []).append(
                {"id": new_id, "text": action[22:].strip()}
            )

        elif action.startswith("DONE_ZENITH_DOC:"):
            # Store the completion in a separate dict keyed by the stable ID string
            sid = action[16:].strip()
            dashboard.setdefault("zenithDocCompletions", {})[sid] = True

        elif action.startswith("DONE_ZENITH:"):
            tid = _coerce_id(action[12:].strip())
            for z in dashboard.get("zenith", []):
                if z.get("id") == tid:
                    z["done"] = True
                    break   # stop after finding the matching item

        elif action.startswith("DONE_MATH_TODO:"):
            tid = _coerce_id(action[15:].strip())
            for m in dashboard.get("mathTodos", []):
                if m.get("id") == tid:
                    m["done"] = True
                    break

        elif action.startswith("REMOVE_ZENITH:"):
            tid = _coerce_id(action[14:].strip())
            # List comprehension: keep every item EXCEPT the one with matching id
            dashboard["zenith"] = [z for z in dashboard.get("zenith", []) if z.get("id") != tid]

        elif action.startswith("REMOVE_MATH_TODO:"):
            tid = _coerce_id(action[17:].strip())
            dashboard["mathTodos"] = [m for m in dashboard.get("mathTodos", []) if m.get("id") != tid]

        elif action.startswith("REMOVE_KANBAN:"):
            tid = _coerce_id(action[14:].strip())
            kanban = dashboard.get("kanban", {})
            # Search all three columns and remove from whichever one contains it
            for col in ["todo", "inprogress", "done"]:
                kanban[col] = [k for k in kanban.get(col, []) if k.get("id") != tid]

        elif action.startswith("EDIT_ZENITH:"):
            # Format: "EDIT_ZENITH:<id>|<new title>"
            # split("|", 1) splits on the FIRST "|" only, leaving the title intact
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

        elif action.startswith("MOVE_KANBAN:"):
            # Format: "MOVE_KANBAN:<id>|<to_column>"
            parts  = action[12:].split("|")
            if len(parts) >= 2:
                tid    = _coerce_id(parts[0].strip())
                to_col = parts[-1].strip()   # last part = destination column name
                kanban = dashboard.get("kanban", {})
                moved  = None
                # Find the card in any column and remove it
                for col in ["todo", "inprogress", "done"]:
                    for k in kanban.get(col, []):
                        if k.get("id") == tid:
                            moved = k
                            break
                    if moved:
                        kanban[col] = [k for k in kanban[col] if k.get("id") != tid]
                        break
                # Add it to the destination column
                if moved and to_col in ["todo", "inprogress", "done"]:
                    kanban.setdefault(to_col, []).append(moved)

    except Exception as e:
        logger.warning("Action error (%s): %s", action, e)


# ── Route ─────────────────────────────────────────────────────────────────────

@bp.route("/api/chat", methods=["POST"])
@require_auth
def api_chat(creds):
    """Handle a chat message: build context, call Groq, execute actions.

    Expected JSON body:
        {
          "message": "What are my open math tasks?",
          "history": [{"role": "user", "text": "..."}, {"role": "model", "text": "..."}]
        }

    Returns:
        {"response": "Here are your open math tasks: ...", "actions": ["DONE_MATH_TODO:123"]}
    """
    body         = request.get_json()
    user_message = body.get("message", "").strip()
    history      = body.get("history", [])   # previous turns for conversation context

    if not user_message:
        return jsonify({"error": "empty message"}), 400

    if not GROQ_API_KEY:
        return jsonify({"error": "GROQ_API_KEY not set in .env"}), 500

    # ── Step 1: Build context from all data sources ───────────────────────────

    # Dashboard tasks/kanban
    data              = load_data()
    dashboard_context = build_dashboard_context(data)

    # Zenith Google Doc — live action items from the actual document
    zenith_doc_context = ""
    zenith_meetings    = parse_zenith_doc(creds)
    if zenith_meetings:
        completions = data.get("zenithDocCompletions", {})
        lines = ["\nZENITH GOOGLE DOC LIVE ACTION ITEMS:"]
        for meeting in zenith_meetings[:5]:   # show up to 5 most recent meetings
            lines.append(f"  {meeting['title']}:")
            for item in meeting["actionItems"]:
                # Mark items the user has already checked off
                done_tag = " ✓ done" if item["id"] in completions else ""
                lines.append(f"    • [id:{item['id']}] {item['text']}{done_tag}")
        zenith_doc_context = "\n".join(lines)

    # Gmail — unread emails so the AI can answer "what emails do I have?"
    gmail_context = ""
    try:
        from datetime import datetime, timezone as tz
        gmail_svc    = build("gmail", "v1", credentials=creds)
        gmail_result = gmail_svc.users().messages().list(
            userId="me", maxResults=10, q="is:unread"
        ).execute()
        gmail_ids = gmail_result.get("messages", [])
        if gmail_ids:
            lines = ["\nUNREAD GMAIL (up to 10):"]
            for msg in gmail_ids:
                detail  = gmail_svc.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["Subject", "From"],
                ).execute()
                headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
                lines.append(
                    f"  • [emailId:{msg['id']}] From: {headers.get('From', '')} "
                    f"— {headers.get('Subject', '(no subject)')}"
                )
            gmail_context = "\n".join(lines)
        else:
            gmail_context = "\nUNREAD GMAIL: No unread emails."
    except Exception as e:
        logger.warning("Gmail context error: %s", e)
        gmail_context = "\nUNREAD GMAIL: (could not fetch)"

    # Google Calendar — upcoming events
    calendar_context = ""
    try:
        from datetime import datetime, timezone as tz
        cal_service = build("calendar", "v3", credentials=creds)
        cal_result  = cal_service.events().list(
            calendarId="primary",
            timeMin=datetime.now(tz.utc).isoformat(),
            maxResults=15,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        cal_events = cal_result.get("items", [])
        if cal_events:
            lines = ["\nGOOGLE CALENDAR EVENTS (upcoming):"]
            for ev in cal_events:
                start = ev.get("start", {}).get("date") or ev.get("start", {}).get("dateTime", "")[:10]
                lines.append(
                    f"  • [eventId:{ev['id']}|calId:primary] "
                    f"{ev.get('summary', '(no title)')} — {start}"
                )
            calendar_context = "\n".join(lines)
    except Exception as e:
        logger.warning("Calendar context error: %s", e)

    # ── Step 2: Build the system prompt ──────────────────────────────────────
    # The "system prompt" is an invisible instruction we give the AI at the
    # start of every conversation.  It tells the AI who it is and what it can do.
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

MARK DONE:
  ACTION:DONE_ZENITH_DOC:<id>
  ACTION:DONE_ZENITH:<id>
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

    # ── Step 3: Build the message list for Groq ───────────────────────────────
    # Groq (like most AI APIs) takes a list of messages in alternating
    # user/assistant roles.  We include the conversation history so the AI
    # remembers what was said earlier in the same chat session.
    groq_messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        # Our history uses "model" for assistant messages — Groq uses "assistant"
        role = "assistant" if msg["role"] == "model" else "user"
        groq_messages.append({"role": role, "content": msg["text"]})
    groq_messages.append({"role": "user", "content": user_message})

    # ── Step 4: Call the Groq API ─────────────────────────────────────────────
    response = http_requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model":       "llama-3.3-70b-versatile",
            "messages":    groq_messages,
            "temperature": 0.7,    # 0 = deterministic, 1 = creative
            "max_tokens":  1024,   # maximum length of the AI's reply
        },
        timeout=30,   # give up after 30 seconds if Groq is slow
    )

    if response.status_code != 200:
        return jsonify({"error": f"Groq error {response.status_code}: {response.text}"}), 500

    # Extract the AI's text reply from the JSON response
    ai_text = response.json()["choices"][0]["message"]["content"]

    # ── Step 5: Split the reply into text and ACTION: lines ───────────────────
    actions     = []   # list of action strings (without the "ACTION:" prefix)
    reply_lines = []   # the human-readable part of the reply
    for line in ai_text.splitlines():
        if line.startswith("ACTION:"):
            actions.append(line[7:])   # strip "ACTION:" prefix
        else:
            reply_lines.append(line)

    clean_reply = "\n".join(reply_lines).strip()

    # ── Step 6: Execute any actions ───────────────────────────────────────────
    if actions:
        dashboard   = load_data()
        cal_service = None   # lazy-init the Calendar client only if needed

        for i, action in enumerate(actions):
            if action.startswith("ADD_CALENDAR_EVENT:"):
                # Format: "ADD_CALENDAR_EVENT:Title|YYYY-MM-DD"
                parts = action[19:].split("|")
                if len(parts) >= 2:
                    try:
                        if cal_service is None:
                            cal_service = build("calendar", "v3", credentials=creds)
                        cal_service.events().insert(
                            calendarId="primary",
                            body={
                                "summary": parts[0].strip(),
                                "start":   {"date": parts[1].strip()},
                                "end":     {"date": parts[1].strip()},
                            },
                        ).execute()
                    except Exception as e:
                        logger.warning("Calendar add error: %s", e)

            elif action.startswith("REMOVE_CALENDAR_EVENT:"):
                # Format: "REMOVE_CALENDAR_EVENT:eventId|calendarId"
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
                        logger.warning("Calendar delete error: %s", e)
            else:
                # All other actions modify dashboard-data.json
                process_chat_action(action, dashboard, index=i)

        save_data(dashboard)   # persist all changes at once

    return jsonify({"response": clean_reply, "actions": actions})
