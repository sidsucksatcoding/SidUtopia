"""
routes/calendar.py  —  Google Calendar routes
══════════════════════════════════════════════════════════════════════════════

Routes in this file:
  GET  /api/calendar               — Fetch all events for the requested month
  POST /api/calendar/add           — Create a new all-day event
  POST /api/calendar/delete        — Delete an event by its ID

What is the Google Calendar API?
  It lets you read and manage Google Calendar events using code.
  Each user can have multiple calendars (personal, work, holidays …).
  We iterate over all of them and merge their events into one list so the
  mini-calendar grid shows everything in one view.
══════════════════════════════════════════════════════════════════════════════
"""
import logging
from datetime import datetime, timezone, timedelta, date as date_type

from flask import Blueprint, request, jsonify
from googleapiclient.discovery import build

from routes import require_auth

bp = Blueprint("calendar", __name__)
logger = logging.getLogger(__name__)


@bp.route("/api/calendar")
@require_auth
def api_calendar(creds):
    """Fetch events from all the user's calendars for the requested month.

    Query parameters:
      year  — 4-digit year  (e.g. 2025)
      month — 1-indexed month (1 = January … 12 = December)

    If no year/month is provided, defaults to the next 60 days.

    Returns:
        {"events": [{"id": "...", "title": "...", "start": "...", "color": "..."}, ...]}
    """
    cal_service = build("calendar", "v3", credentials=creds)

    # Read ?year= and ?month= from the URL query string
    year  = request.args.get("year",  type=int)
    month = request.args.get("month", type=int)

    if year and month:
        # First moment of the requested month (midnight UTC on the 1st)
        time_min = datetime(year, month, 1, tzinfo=timezone.utc).isoformat()
        # First moment of the NEXT month — used as the exclusive upper bound
        time_max = (
            datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12
            else datetime(year, month + 1, 1, tzinfo=timezone.utc)
        ).isoformat()
    else:
        # Fallback: show the next 60 days from now
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=60)).isoformat()

    # Fetch the list of all calendars in the user's account
    try:
        calendars = cal_service.calendarList().list().execute().get("items", [])
    except Exception:
        # If listing calendars fails, fall back to just the primary calendar
        calendars = [{"id": "primary", "summary": "My Calendar", "backgroundColor": "#7c6af7"}]

    # Loop through each calendar and collect its events
    all_events = []
    for cal in calendars[:20]:   # cap at 20 to avoid extremely long loops
        # Skip calendars the user has deselected in Google Calendar
        if not cal.get("selected", True):
            continue
        try:
            result = cal_service.events().list(
                calendarId=cal["id"],
                timeMin=time_min,
                timeMax=time_max,
                maxResults=50,       # at most 50 events per calendar
                singleEvents=True,   # expand repeating events into individual occurrences
                orderBy="startTime",
            ).execute()

            # Use the calendar's colour for the event chip in the UI
            color = cal.get("backgroundColor", "#7c6af7")

            for e in result.get("items", []):
                all_events.append({
                    "id":         e["id"],
                    "calendarId": cal["id"],
                    "title":      e.get("summary", "(no title)"),
                    # All-day events use "date"; timed events use "dateTime"
                    "start":      e["start"].get("dateTime") or e["start"].get("date"),
                    "end":        e["end"].get("dateTime")   or e["end"].get("date"),
                    "calendar":   cal.get("summary", ""),
                    "color":      color,
                })
        except Exception as e:
            # One calendar failing should not block the others
            logger.debug("Skipped calendar %s: %s", cal.get("id"), e)

    # Sort by start time so events appear in chronological order
    all_events.sort(key=lambda x: x.get("start", ""))
    return jsonify({"events": all_events})


@bp.route("/api/calendar/add", methods=["POST"])
@require_auth
def calendar_add_event(creds):
    """Create a new all-day event in the user's primary Google Calendar.

    Expected JSON body:
        {"name": "Exam", "start": "2025-05-10", "end": "2025-05-10"}
        ("end" is optional — defaults to the same day as start)

    Important: Google Calendar end dates are exclusive.
      If you want an event to appear on May 10, the API needs end = May 11.
      We add one day automatically to handle this.
    """
    body  = request.get_json()
    name  = body.get("name",  "").strip()
    start = body.get("start", "").strip()
    end   = body.get("end",   "").strip()

    if not name or not start:
        return jsonify({"error": "Name and start date are required"}), 400

    # Google Calendar end date is exclusive — we must send the day AFTER the last day
    end_excl = (
        (date_type.fromisoformat(end) + timedelta(days=1)).isoformat()
        if end and end != start
        else (date_type.fromisoformat(start) + timedelta(days=1)).isoformat()
    )

    try:
        cal_service = build("calendar", "v3", credentials=creds)
        created = cal_service.events().insert(
            calendarId="primary",
            body={
                "summary": name,
                "start":   {"date": start},
                "end":     {"date": end_excl},
            },
        ).execute()
        return jsonify({"success": True, "id": created.get("id")})
    except Exception as e:
        msg = str(e)
        if "insufficientPermissions" in msg or "403" in msg:
            # User logged in before we requested calendar.events write scope
            return jsonify({"error": "Missing calendar write permission.", "hint": "REAUTH"}), 403
        return jsonify({"error": msg}), 500


@bp.route("/api/calendar/delete", methods=["POST"])
@require_auth
def calendar_delete_event(creds):
    """Delete a Google Calendar event by its ID.

    Expected JSON body:
        {"eventId": "abc123", "calendarId": "primary"}

    Note: 404/410 responses from Google mean the event is already gone —
    we treat that as success so the UI doesn't show a confusing error.
    """
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
            return jsonify({"error": "This calendar is read-only."}), 403
        if "410" in msg or "404" in msg:
            return jsonify({"success": True})   # already deleted — not an error
        return jsonify({"error": msg}), 500
