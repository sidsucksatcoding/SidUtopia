"""
routes/timesheet.py  —  Timesheet routes (Google Sheets backend)
══════════════════════════════════════════════════════════════════════════════

Routes in this file:
  GET  /api/timesheet               — Load all months of timesheet data
  POST /api/timesheet/update        — Save one cell after the user edits it
  POST /api/timesheet/add-month     — Create a new monthly tab in the Sheet
  POST /api/timesheet/delete-month  — Delete an empty monthly tab

How the timesheet is structured in Google Sheets:
  • One Google Sheet file contains all your timesheet data.
  • Each MONTH gets its own tab (called a "sheet") named "April 2026", "May 2026", etc.
  • Row 1 (the header row) has: "Activity" | "4/1/26" | "4/2/26" | … (one column per day)
  • Each subsequent row is one activity (e.g. "Tutoring", "Research") with hours per day.

  Visual example:
      Activity    | 4/1/26 | 4/2/26 | 4/3/26 | …
      Tutoring    |  2:00  |  3:00  |        | …
      Research    |  1:30  |        |  2:00  | …

A1 notation:
  Google Sheets cells are addressed like "B5" = column B, row 5.
  For columns beyond Z we use "AA", "AB", etc.  _col_letter() converts a
  1-based number into that letter string.
══════════════════════════════════════════════════════════════════════════════
"""
import logging
import calendar as cal_module
from datetime import datetime as dt

from flask import Blueprint, request, jsonify
from googleapiclient.discovery import build

from config import TIMESHEET_ID
from routes import require_auth

bp = Blueprint("timesheet", __name__)
logger = logging.getLogger(__name__)

# Month names indexed 0–11 (used to build tab titles like "April 2026")
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _col_letter(col: int) -> str:
    """Convert a 1-based column number into the A1-notation letter(s).

    Examples:
      1  → "A"
      26 → "Z"
      27 → "AA"
      28 → "AB"

    How it works:
      Each iteration peels off one letter from the right using divmod (division
      with remainder), then prepends it to the result string.
      This is similar to converting a decimal number to base-26.

    Args:
        col: 1-based column index (column A = 1, column B = 2, …)
    """
    result = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)   # rem = 0–25 → maps to A–Z
        result = chr(65 + rem) + result  # chr(65) = 'A', chr(66) = 'B', …
    return result


@bp.route("/api/timesheet")
@require_auth
def api_timesheet(creds):
    """Load every month tab from the timesheet Google Sheet.

    Steps:
      1. Fetch the spreadsheet metadata to discover all tab names.
      2. Filter to only tabs named "Month YYYY" (e.g. "April 2026").
      3. For each month tab, read all rows and parse them into a structured format.
      4. Return the months sorted newest-first.

    Returns:
        {"months": [{"key": "2026-04", "label": "April 2026",
                     "dates": [...], "rows": [...]}, ...]}
    """
    try:
        sheets_svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

        # Get spreadsheet metadata — this tells us what tabs exist
        meta = sheets_svc.spreadsheets().get(spreadsheetId=TIMESHEET_ID).execute()

        months = []
        for sheet in meta["sheets"]:
            # sheet["properties"]["title"] is the tab name, e.g. "April 2026"
            title = sheet["properties"]["title"].strip()
            parts = title.split()

            # Skip tabs that aren't in "Month YYYY" format
            if len(parts) != 2 or parts[0] not in MONTH_NAMES:
                continue
            try:
                year      = int(parts[1])
                month_num = MONTH_NAMES.index(parts[0]) + 1  # "April" → 4
            except ValueError:
                continue

            # "2026-04" — used to sort months chronologically
            month_key = f"{year}-{month_num:02d}"

            # Read all cell values from this tab
            result = sheets_svc.spreadsheets().values().get(
                spreadsheetId=TIMESHEET_ID,
                range=f"'{title}'",   # single quotes wrap the tab name in A1 notation
            ).execute()
            values = result.get("values", [])   # 2D list: values[row][col]

            if not values or len(values) < 2:
                continue   # tab has no data rows — skip

            headers = values[0]   # first row = ["Activity", "4/1/26", "4/2/26", …]

            # Parse each header column that looks like a date
            date_cols = []
            for col_i, h in enumerate(headers[1:], start=1):  # skip "Activity" col
                try:
                    raw = h.strip()
                    # Dates can be "4/1/26" (2-digit year) or "4/1/2026" (4-digit year)
                    date_obj = (
                        dt.strptime(raw, "%m/%d/%y")
                        if len(raw.split("/")[-1]) == 2
                        else dt.strptime(raw, "%m/%d/%Y")
                    )
                    date_cols.append({
                        "col_index": col_i,      # 0-based index in the row list
                        "sheet_col": col_i + 1,  # 1-based col number for A1 notation
                        "date_str":  raw,         # the raw string as it appears in the sheet
                        "date_obj":  date_obj,    # Python datetime for sorting
                    })
                except ValueError:
                    pass  # not a date header — skip it

            # Build one "row" object per activity (each row after the header)
            rows = []
            for row_i, row in enumerate(values[1:], start=1):
                activity = row[0] if row else ""
                if not activity:
                    continue  # blank rows in the sheet are skipped

                # Build a "cell" for each date column
                cells = []
                for dc in date_cols:
                    ci  = dc["col_index"]
                    val = row[ci] if ci < len(row) else ""  # empty if row is short
                    cells.append({
                        "value":     val,
                        "sheet_row": row_i + 1,    # +1 because header is row 1
                        "sheet_col": dc["sheet_col"],
                        "date":      dc["date_str"],
                    })
                rows.append({"activity": activity, "cells": cells})

            months.append({
                "key":        month_key,
                "label":      title,
                "sheet_name": title,
                "dates":      [dc["date_str"] for dc in date_cols],
                "rows":       rows,
            })

        # Sort months newest-first using the "YYYY-MM" key string
        months.sort(key=lambda m: m["key"], reverse=True)
        return jsonify({"months": months})

    except Exception as e:
        logger.exception("Timesheet load error")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/timesheet/update", methods=["POST"])
@require_auth
def api_timesheet_update(creds):
    """Write a single edited cell value back to Google Sheets.

    This is called every time the user clicks away (blur event) after editing
    a time cell in the timesheet table.

    Expected JSON body:
        {"row": 3, "col": 5, "value": "2:30", "sheet_name": "April 2026"}

    A1 notation example:
        row=3, col=5 → "E3" (E is the 5th letter)
        With sheet name: "'April 2026'!E3"
    """
    try:
        body       = request.get_json()
        sheet_row  = int(body["row"])
        sheet_col  = int(body["col"])
        value      = body.get("value", "")
        sheet_name = body.get("sheet_name", "Sheet1")

        # Build the A1 cell reference, e.g. "'April 2026'!E3"
        cell_ref   = f"'{sheet_name}'!{_col_letter(sheet_col)}{sheet_row}"

        sheets_svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        sheets_svc.spreadsheets().values().update(
            spreadsheetId=TIMESHEET_ID,
            range=cell_ref,
            valueInputOption="USER_ENTERED",  # interprets "2:30" as a time value
            body={"values": [[value]]},       # 2D array: [[single cell value]]
        ).execute()
        logger.info("Saved %s → %s = %r", sheet_name, cell_ref, value)
        return jsonify({"success": True})

    except Exception as e:
        logger.warning("Timesheet update error: %s", e)
        return jsonify({"error": str(e)}), 500


@bp.route("/api/timesheet/add-month", methods=["POST"])
@require_auth
def api_timesheet_add_month(creds):
    """Create a new monthly tab in the Google Sheet.

    Steps:
      1. Figure out the tab title ("May 2026").
      2. Check the tab doesn't already exist.
      3. Copy the activity names (column A) from the most recent existing tab.
      4. Create the new tab (addSheet API call).
      5. Write the header row (Activity + one column per day) and activity rows.

    Expected JSON body:
        {"year": 2026, "month": 5}

    Returns:
        {"days_added": 31}  (the number of day columns created)
    """
    try:
        body      = request.get_json()
        year      = int(body["year"])
        month     = int(body["month"])
        tab_title = f"{MONTH_NAMES[month - 1]} {year}"   # e.g. "May 2026"

        sheets_svc      = build("sheets", "v4", credentials=creds, cache_discovery=False)
        meta            = sheets_svc.spreadsheets().get(spreadsheetId=TIMESHEET_ID).execute()
        existing_titles = [s["properties"]["title"] for s in meta["sheets"]]

        # Don't create a duplicate tab
        if tab_title in existing_titles:
            return jsonify({"days_added": 0, "message": "Tab already exists"})

        # ── Find activities from the most recent existing month tab ───────────
        month_tabs = []
        for s in meta["sheets"]:
            parts = s["properties"]["title"].strip().split()
            if len(parts) == 2 and parts[0] in MONTH_NAMES:
                try:
                    mn = MONTH_NAMES.index(parts[0]) + 1
                    yr = int(parts[1])
                    month_tabs.append((yr, mn, s["properties"]["title"]))
                except ValueError:
                    pass

        activity_list = []
        if month_tabs:
            month_tabs.sort(reverse=True)  # newest first
            source_tab = month_tabs[0][2]  # use the most recent tab as the template
            res        = sheets_svc.spreadsheets().values().get(
                spreadsheetId=TIMESHEET_ID,
                range=f"'{source_tab}'!A:A",  # column A only = activity names
            ).execute()
            col_a         = res.get("values", [])
            activity_list = [r[0].strip() for r in col_a[1:] if r and r[0].strip()]

        # ── Create the new empty tab ──────────────────────────────────────────
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=TIMESHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": tab_title}}}]},
        ).execute()

        # ── Build and write the header + data rows ────────────────────────────
        # cal_module.monthrange(year, month)[1] returns the number of days in the month
        days_in_month = cal_module.monthrange(year, month)[1]

        # Date headers: "5/1/26", "5/2/26", … (2-digit year to match existing format)
        dates = [f"{month}/{day}/{str(year)[2:]}" for day in range(1, days_in_month + 1)]

        # First row: ["Activity", "5/1/26", "5/2/26", ...]
        # Each activity row:  ["Tutoring", "", "", ...]  (empty cells for all days)
        rows_to_write = [["Activity"] + dates]
        for act in activity_list:
            rows_to_write.append([act] + [""] * days_in_month)

        sheets_svc.spreadsheets().values().update(
            spreadsheetId=TIMESHEET_ID,
            range=f"'{tab_title}'!A1",
            valueInputOption="RAW",          # write strings as-is, no parsing
            body={"values": rows_to_write},
        ).execute()

        return jsonify({"days_added": days_in_month})

    except Exception as e:
        logger.exception("add-month error")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/timesheet/delete-month", methods=["POST"])
@require_auth
def api_timesheet_delete_month(creds):
    """Delete an entire monthly tab from the Google Sheet.

    The UI only shows the Delete button on months where ALL cells are empty,
    so this is safe — you can't accidentally delete filled-in data via the UI.

    Expected JSON body:
        {"month_key": "April 2026"}   ← the tab's display name

    Steps:
      1. Find the tab's internal numeric sheetId (different from its title).
      2. Call deleteSheet with that ID.
    """
    try:
        body      = request.get_json()
        tab_title = body["month_key"]   # the tab display name, e.g. "April 2026"

        sheets_svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        meta       = sheets_svc.spreadsheets().get(spreadsheetId=TIMESHEET_ID).execute()

        # Find the internal sheetId for the tab with this title
        sheet_id = next(
            (s["properties"]["sheetId"] for s in meta["sheets"]
             if s["properties"]["title"] == tab_title),
            None,
        )
        if sheet_id is None:
            return jsonify({"error": "Tab not found"}), 404

        # Delete the tab — this is permanent!
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=TIMESHEET_ID,
            body={"requests": [{"deleteSheet": {"sheetId": sheet_id}}]},
        ).execute()
        return jsonify({"success": True})

    except Exception as e:
        logger.exception("delete-month error")
        return jsonify({"error": str(e)}), 500
