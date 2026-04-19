"""
services/zenith_parser.py  —  Parse action items from the Zenith Google Doc
══════════════════════════════════════════════════════════════════════════════

What does this file do?
  The Zenith college counselling Google Doc is structured like this:
    • Each meeting has its own "tab" (like a sheet in a spreadsheet).
    • Within each tab there is a HEADING_2 section called "Action Items #N".
    • Below that heading are bullet-point action items, some with links.

  This file reads the raw Google Docs API response and extracts all those
  action items into a clean Python list that the rest of the app can use.

Why is this in services/ instead of routes/?
  Three different routes need the same data:
    • /api/zenith        — shows action items on the dashboard
    • /api/chat          — lets the AI answer questions about them
    • /api/send-summary  — includes them in the SMS text message
  Rather than copy-pasting the same parsing logic three times, we write it
  once here and import it where needed.  This is the DRY principle:
  "Don't Repeat Yourself."

Return value:
  A list of meeting dictionaries, sorted newest meeting first:
  [
    {
      "title": "Meeting #12",
      "actionItems": [
        {"id": "Meeting_12-...", "text": "Research common app essay topics", "links": [...]},
        ...
      ]
    },
    ...
  ]
══════════════════════════════════════════════════════════════════════════════
"""
import re
import logging

from googleapiclient.discovery import build
from config import ZENITH_DOC_ID

logger = logging.getLogger(__name__)


def parse_zenith_doc(creds) -> list[dict]:
    """Fetch the Zenith Google Doc and extract all action items from every meeting.

    Args:
        creds: Valid Google OAuth credentials (from load_tokens()).

    Returns:
        List of meeting dictionaries sorted newest-first (by meeting number).
        Returns an empty list [] if the document can't be fetched.
    """
    # ── Step 1: Call the Google Docs API ─────────────────────────────────────
    # build("docs", "v1", credentials=creds) creates a client object that knows
    # how to talk to the Google Docs API (version 1).
    # includeTabsContent=True tells Google to send us the content of ALL tabs,
    # not just the first one.
    try:
        docs = build("docs", "v1", credentials=creds)
        doc = docs.documents().get(
            documentId=ZENITH_DOC_ID,
            includeTabsContent=True,
        ).execute()
    except Exception as e:
        logger.warning("Could not fetch Zenith doc: %s", e)
        return []

    # ── Step 2: Loop through each tab (= each meeting) ───────────────────────
    meetings = []
    for tab in doc.get("tabs", []):
        # Get the tab's display name (e.g. "Meeting #12")
        tab_title = tab.get("tabProperties", {}).get("title", "Untitled")

        # Skip the template tab and any root-level tab — they're not real meetings
        if "template" in tab_title.lower() or tab_title.lower() == "root":
            continue

        # Navigate into the document body content — this is the list of paragraphs
        content = (
            tab.get("documentTab", {})
               .get("body", {})
               .get("content", [])
        )

        # ── Step 3: Find the "Action Items" heading and collect bullets ───────
        # We scan each paragraph looking for a HEADING_2 that says "Action Items #N".
        # Once we find it, we collect every bullet point below it until we hit
        # the next major heading (which signals a new section like "Notes").

        in_action_items = False   # Are we currently inside the Action Items section?
        action_items    = []      # Collected action items for this meeting tab

        for block in content:
            # Skip anything that isn't a paragraph (e.g. tables, images)
            if "paragraph" not in block:
                continue

            para = block["paragraph"]

            # Combine all text runs into one string — a "text run" is a chunk of
            # text with consistent formatting (bold, italic, link, etc.)
            text = "".join(
                e.get("textRun", {}).get("content", "")
                for e in para.get("elements", [])
            ).strip()   # .strip() removes leading/trailing spaces and newlines

            if not text:
                continue   # skip blank lines

            # Get the paragraph's heading style (HEADING_1, HEADING_2, NORMAL_TEXT …)
            style = para.get("paragraphStyle", {}).get("namedStyleType", "")

            # ── Detect the "Action Items" section heading ──────────────────────
            # We look for a HEADING_2 that:
            #   • Contains "action items" (case-insensitive)
            #   • Does NOT contain "previous" (to skip "Previous Action Items" recaps)
            #   • Contains a meeting number like "#12" or "##12"
            if (
                style == "HEADING_2"
                and "action items" in text.lower()
                and "previous" not in text.lower()
                and re.search(r"#+\d+", text)   # regex: one or more # followed by digits
            ):
                in_action_items = True
                continue   # don't add the heading itself as an action item

            # If we hit any other major heading while inside Action Items, stop
            if in_action_items and style in ("HEADING_1", "HEADING_2"):
                in_action_items = False

            # ── Collect bullet points as action items ─────────────────────────
            # para.get("bullet") is truthy when the paragraph is a bullet/list item
            # len(text) > 2 ignores single-character bullets like "•" or "-"
            if in_action_items and para.get("bullet") and len(text) > 2:
                # Collect any hyperlinks embedded in this bullet's text runs
                links = []
                for element in para.get("elements", []):
                    url = (
                        element.get("textRun", {})
                               .get("textStyle", {})
                               .get("link", {})
                               .get("url")
                    )
                    link_text = element.get("textRun", {}).get("content", "").strip()
                    if url and link_text:
                        links.append({"text": link_text, "url": url})

                # Build a stable ID for this action item so checkboxes are
                # remembered correctly even if other items are added/removed.
                # Example ID: "Meeting_12-research_common_app_essay_topics"
                stable_id = (
                    f"{tab_title.replace(' ', '_')}-"
                    f"{re.sub(r'[^a-z0-9]+', '_', text[:50].lower())}"
                )
                action_items.append({"id": stable_id, "text": text, "links": links})

        # Only include this tab if it had at least one action item
        if action_items:
            meetings.append({"title": tab_title, "actionItems": action_items})

    # ── Step 4: Sort newest meeting first ─────────────────────────────────────
    # Extract the number from the tab title ("Meeting #12" → 12) and sort
    # in descending order so Meeting #12 appears before Meeting #11.
    def _meeting_num(m: dict) -> int:
        match = re.search(r"\d+", m["title"])   # find the first number in the title
        return int(match.group()) if match else 0

    meetings.sort(key=_meeting_num, reverse=True)
    return meetings
