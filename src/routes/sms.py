"""
routes/sms.py  —  POST /api/send-summary  (the "Send Summary" SMS button)
══════════════════════════════════════════════════════════════════════════════

What does this route do?
  When the user clicks "📱 Send Summary" in the dashboard header, the browser
  calls this endpoint.  It collects data from four sources, formats them into
  a single text message, and fires it to every phone number in TWILIO_TO.

  Sources gathered:
    1. Today's timesheet hours  (from Google Sheets)
    2. Upcoming events this week (from Google Calendar)
    3. Zenith action items from the latest meeting (from the Google Doc)
    4. In-progress kanban + open math to-dos  (from dashboard-data.json)

What is Twilio?
  Twilio is a service that sends SMS text messages via code.
  You sign up, buy a phone number, and call their API with the message text
  and destination number.  They handle the actual carrier delivery.

Error handling strategy:
  Each section (timesheet, calendar, zenith, kanban) is wrapped in its own
  try/except so that if one source fails (e.g. the timesheet tab for today
  doesn't exist yet), the other sections still make it into the SMS.
══════════════════════════════════════════════════════════════════════════════
"""
import logging
from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify
from googleapiclient.discovery import build

from config import TIMESHEET_ID, TWILIO_SID, TWILIO_AUTH, TWILIO_FROM, TWILIO_TO
from routes import require_auth
from services.data_service import load_data
from services.zenith_parser import parse_zenith_doc

bp = Blueprint("sms", __name__)
logger = logging.getLogger(__name__)

# Month names indexed 0–11 (matches Python's datetime.month - 1)
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@bp.route("/api/send-summary", methods=["POST"])
@require_auth
def api_send_summary(creds):
    """Build a daily summary message and send it as an SMS via Twilio.

    Requires:
        TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, TWILIO_TO
        to be set in .env (or Render environment).

    Returns:
        {"success": True, "sent_to": N, "preview": "...full message text..."}
        or {"error": "reason"} with an appropriate HTTP status code.
    """
    # Guard: do nothing if Twilio is not configured
    if not (TWILIO_SID and TWILIO_AUTH and TWILIO_FROM and TWILIO_TO):
        return jsonify({"error": "Twilio not configured"}), 500

    try:
        # Import inside the function so the rest of the app still works even if
        # the twilio package is not installed (it's optional in dev without SMS)
        from twilio.rest import Client

        # Current UTC date/time — used for the header and for date comparisons
        today    = datetime.now(timezone.utc)
        date_str = today.strftime("%b ") + str(today.day)   # e.g. "Apr 18"

        # `lines` is a list of strings that we join at the end with newlines
        lines = [f"SidUtopia Summary — {date_str}", ""]

        # ── Section 1: Today's timesheet ─────────────────────────────────────
        # Read the Google Sheet tab named "April 2025" (or current month/year),
        # find the column whose header matches today's date, and list the hours.
        try:
            tab_title = f"{MONTH_NAMES[today.month - 1]} {today.year}"

            # Dates in the header row can be formatted as "4/18/25" or "4/18/2025"
            today_variants = {
                f"{today.month}/{today.day}/{str(today.year)[2:]}",   # 4/18/25
                f"{today.month}/{today.day}/{today.year}",            # 4/18/2025
            }

            sheets_svc = build("sheets", "v4", credentials=creds)
            result     = sheets_svc.spreadsheets().values().get(
                spreadsheetId=TIMESHEET_ID, range=f"'{tab_title}'"
            ).execute()
            values = result.get("values", [])  # 2D list: values[row][col]

            if values and len(values) > 1:
                headers   = values[0]     # first row = column headers (dates)
                # Find the column index that matches today's date
                today_col = next(
                    (i for i, h in enumerate(headers) if h.strip() in today_variants),
                    None,
                )
                if today_col is not None:
                    # Collect non-empty "activity: hours" entries
                    entries = [
                        f"  {row[0]}: {row[today_col]}"
                        for row in values[1:]
                        if len(row) > today_col and row[0] and row[today_col]
                    ]
                    if entries:
                        lines.append("TODAY'S TIMESHEET")
                        lines.extend(entries)
                        lines.append("")  # blank line between sections
        except Exception as e:
            # Log the problem but continue — other sections may still work
            logger.warning("Timesheet section skipped: %s", e)

        # ── Section 2: Upcoming calendar events (next 7 days) ────────────────
        try:
            cal_svc = build("calendar", "v3", credentials=creds)
            result  = cal_svc.events().list(
                calendarId="primary",
                timeMin=today.isoformat(),                         # from now
                timeMax=(today + timedelta(days=7)).isoformat(),   # to 7 days from now
                maxResults=6,        # at most 6 events
                singleEvents=True,   # expand recurring events
                orderBy="startTime",
            ).execute()
            events = result.get("items", [])
            if events:
                lines.append("UPCOMING EVENTS")
                for e in events:
                    # All-day events use "date"; timed events use "dateTime"
                    start = e["start"].get("dateTime") or e["start"].get("date", "")
                    try:
                        # Parse the ISO datetime string into a Python datetime
                        d     = datetime.fromisoformat(start.replace("Z", "+00:00"))
                        label = d.strftime("%b ") + str(d.day)  # e.g. "Apr 22"
                    except Exception:
                        label = start[:10]  # fallback: first 10 chars of the string
                    lines.append(f"  {label} — {e.get('summary', '(no title)')}")
                lines.append("")
        except Exception as e:
            logger.warning("Calendar section skipped: %s", e)

        # ── Section 3: Latest Zenith meeting action items ─────────────────────
        try:
            import re
            meetings = parse_zenith_doc(creds)  # shared service function

            # Filter to only meetings with a number in their title, skip templates
            numbered = [
                (int(re.search(r"\d+", m["title"]).group()), m)
                for m in meetings
                if re.search(r"\d+", m["title"]) and "template" not in m["title"].lower()
            ]
            if numbered:
                numbered.sort(reverse=True)  # highest number = most recent meeting
                _, latest = numbered[0]
                # Show up to 5 action items from the latest meeting
                items = [f"  • {item['text']}" for item in latest["actionItems"][:5]]
                if items:
                    lines.append(f"ZENITH ({latest['title']})")
                    lines.extend(items)
                    lines.append("")
        except Exception as e:
            logger.warning("Zenith section skipped: %s", e)

        # ── Section 4: Kanban + Math to-dos from the dashboard ───────────────
        try:
            data        = load_data()
            in_progress = [k.get("text", "") for k in data.get("kanban", {}).get("inprogress", [])]
            # Only show math tasks that are NOT yet ticked off
            open_todos  = [t.get("text", "") for t in data.get("mathTodos", []) if not t.get("done")]
            if in_progress:
                lines.append("IN PROGRESS")
                lines.extend(f"  • {t}" for t in in_progress[:4])  # at most 4 items
                lines.append("")
            if open_todos:
                lines.append("OPEN TODOS")
                lines.extend(f"  • {t}" for t in open_todos[:4])
                lines.append("")
        except Exception as e:
            logger.warning("Dashboard section skipped: %s", e)

        # Sign-off line
        lines.append("— Sid's Utopia")
        message = "\n".join(lines)  # join all lines into one string

        # ── Send the SMS via Twilio ───────────────────────────────────────────
        # Client(sid, auth) authenticates with Twilio.
        # messages.create() sends one SMS per phone number in TWILIO_TO.
        client = Client(TWILIO_SID, TWILIO_AUTH)
        for number in TWILIO_TO:
            client.messages.create(body=message, from_=TWILIO_FROM, to=number)

        logger.info("SMS summary sent to %d numbers", len(TWILIO_TO))
        return jsonify({"success": True, "sent_to": len(TWILIO_TO), "preview": message})

    except Exception as e:
        logger.exception("send-summary error")
        return jsonify({"error": str(e)}), 500
