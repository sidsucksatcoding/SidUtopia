"""
config.py  —  Central configuration for the whole application
══════════════════════════════════════════════════════════════════════════════

What does this file do?
  Every app needs secret keys, file paths, and settings.  Instead of
  scattering them across dozens of files (making them hard to find and
  easy to forget), we gather ALL of them here.

  Any other Python file that needs a setting just writes:
      from config import GROQ_API_KEY

  That's it — one import, one place to look.

What is an environment variable?
  A value stored OUTSIDE your code, in the operating system or a .env file.
  This is important because you should never put real passwords or API keys
  directly in code that gets uploaded to GitHub.  Instead, you put them in
  .env (which is hidden from Git), and Python reads them at startup.
══════════════════════════════════════════════════════════════════════════════
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── Find the project root folder ──────────────────────────────────────────────
# __file__  = the full path to THIS file (config.py)
# .parent   = the folder that contains this file  (src/)
# .parent   = one level up from that             (project root)
#
# So if config.py is at  /home/sid/SidUtopia/src/config.py
# then BASE_DIR will be  /home/sid/SidUtopia/
BASE_DIR = Path(__file__).parent.parent

# ── Load the .env file ────────────────────────────────────────────────────────
# dotenv reads the .env file and copies every line into Python's environment,
# so os.environ["GOOGLE_CLIENT_ID"] will work after this call.
#
# We pass the explicit path (BASE_DIR / ".env") so it always finds the file
# even when gunicorn starts the server from a different working directory.
# override=True means .env values win over anything already in the environment.
load_dotenv(BASE_DIR / ".env", override=True)

# ── Logging setup ─────────────────────────────────────────────────────────────
# Logging is like a diary for your server.  Instead of print(), use logging
# so messages include a timestamp, severity level, and the module name.
#
# Example output:
#   2025-04-18 14:32:01  INFO      routes.gmail — Fetching unread messages
#   2025-04-18 14:32:02  ERROR     routes.sms   — Twilio not configured
#
# logging.INFO means: show INFO messages and anything more serious (WARNING,
# ERROR, CRITICAL).  DEBUG messages (very detailed) are hidden.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

# ── File paths ────────────────────────────────────────────────────────────────
# These are the two JSON files that store data on disk.
#   tokens.json          — Google login credentials (refreshed automatically)
#   dashboard-data.json  — Your tasks, kanban cards, links, exams, etc.
TOKEN_FILE = BASE_DIR / "tokens.json"
DATA_FILE  = BASE_DIR / "dashboard-data.json"

# ── Google OAuth credentials ──────────────────────────────────────────────────
# OAuth is the "sign in with Google" system.  Your app sends Google these two
# values to prove it is allowed to ask for permissions on your behalf.
#
# os.environ["KEY"]        raises an error if the key is missing — good for
#                          required values (we cannot run without these).
# os.environ.get("KEY","") returns a default value instead of crashing —
#                          good for optional values like Twilio.
GOOGLE_CLIENT_ID     = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]

# The URL Google redirects to after the user grants/denies permission.
# Must exactly match what you registered in Google Cloud Console.
REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback")

# The port the server listens on.  Render sets this automatically in production.
PORT = int(os.environ.get("PORT", 3000))

# Fixed Google API URLs — these never change, they are part of Google's API.
GOOGLE_AUTH_URI  = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

# ── Google API Scopes ─────────────────────────────────────────────────────────
# Scopes = the exact list of permissions we ask the user to grant.
# Google shows each of these on the "Grant access" screen so the user knows
# what the app can and cannot do.
SCOPES = [
    # Read files from Google Drive (used for the Zenith Google Doc)
    "https://www.googleapis.com/auth/drive.readonly",

    # Read the content of Google Docs (used to parse the Zenith meeting notes)
    "https://www.googleapis.com/auth/documents.readonly",

    # Read AND modify Gmail (read unread emails, mark them as read)
    "https://www.googleapis.com/auth/gmail.modify",

    # Read calendar events (display them in the calendar grid)
    "https://www.googleapis.com/auth/calendar.readonly",

    # Create and delete calendar events (Add Event / delete button)
    "https://www.googleapis.com/auth/calendar.events",

    # Read AND write Google Sheets (the timesheet feature)
    "https://www.googleapis.com/auth/spreadsheets",

    # "openid" + profile + email = lets us get the user's name and email address
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# ── Google resource IDs ───────────────────────────────────────────────────────
# Each Google Doc / Sheet has a unique ID in its URL, e.g.:
#   docs.google.com/document/d/<<THIS_PART>>/edit
ZENITH_DOC_ID = "1DCWSwpSohO_8eIe5Lsb1X7qlpgeE67L70JyohXO1BUc"
TIMESHEET_ID  = "1lg7AQ6z2GaSHIRU4qVHfUPTJNkIUyQjtP5k5T8yKlcI"

# ── Twilio SMS ────────────────────────────────────────────────────────────────
# Twilio is a service that sends text messages (SMS) through code.
# TWILIO_SID   = your account identifier (starts with "AC")
# TWILIO_AUTH  = your account password / secret token
# TWILIO_FROM  = the Twilio phone number that sends the message
# TWILIO_TO    = list of real phone numbers to receive the message
#                (multiple numbers separated by commas in .env)
TWILIO_SID  = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM", "")
TWILIO_TO   = [n.strip() for n in os.environ.get("TWILIO_TO", "").split(",") if n.strip()]

# ── AI (Groq) ─────────────────────────────────────────────────────────────────
# Groq is the service that runs the AI chat.
# The API key is like a password that proves you are allowed to use the service.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
