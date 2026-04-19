"""
services/auth_service.py  —  Save and load Google login credentials
══════════════════════════════════════════════════════════════════════════════

What does this file do?
  After the user logs in with Google, we receive an "access token" — a
  temporary password that lets us call Google's APIs (Gmail, Calendar, etc.)
  on the user's behalf.

  This file has two jobs:
    save_tokens(creds)  —  Write the token to disk so it survives server restarts.
    load_tokens()       —  Read the token from disk; refresh it if it has expired.

What is a token?
  A token is like a concert wristband:
    • You show your ID once (Google login screen) and get a wristband.
    • From then on you just show the wristband at the door (each API call).
    • The wristband expires after ~1 hour — but we have a "refresh token" that
      automatically gets a new wristband without asking you to log in again.

Where is the token stored?
  In tokens.json at the project root.  This file is listed in .gitignore
  so it never gets committed to GitHub — it is personal data.
══════════════════════════════════════════════════════════════════════════════
"""
import json
import logging
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest

from config import TOKEN_FILE, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SCOPES

# Each module gets its own named logger so log messages show where they came from
logger = logging.getLogger(__name__)


def save_tokens(creds: Credentials) -> None:
    """Write Google credentials to tokens.json on disk.

    Why save to a file?
      Web servers handle many requests and can restart at any time.
      Variables in memory disappear on restart.  By writing to a file we
      make sure the user does not have to log in again every time the server
      restarts.

    Args:
        creds: A Google Credentials object returned after OAuth login.
    """
    # Convert the Credentials object to a plain dictionary (JSON-serialisable)
    data = {
        "token":         creds.token,           # short-lived access token (~1 hour)
        "refresh_token": creds.refresh_token,   # long-lived token used to get new access tokens
        "token_uri":     creds.token_uri,       # Google's URL to exchange the refresh token
        "client_id":     creds.client_id,       # your app's Google client ID
        "client_secret": creds.client_secret,   # your app's Google client secret
        "scopes":        list(creds.scopes or []),  # what permissions are granted
        # .isoformat() converts a datetime object to a string like "2025-04-18T14:30:00"
        "expiry":        creds.expiry.isoformat() if creds.expiry else None,
    }
    # json.dumps(data) converts the dictionary to a JSON string
    # .write_text() saves that string into the file
    TOKEN_FILE.write_text(json.dumps(data))


def load_tokens() -> Credentials | None:
    """Read tokens.json and return valid Google credentials.

    Steps:
      1. If the file doesn't exist → return None (not logged in).
      2. Read and parse the JSON.
      3. If it looks like an old Node.js token format → delete it, return None.
      4. Reconstruct a Credentials object from the data.
      5. If the access token has expired → use the refresh token to get a new one.
      6. Return the (possibly refreshed) credentials.

    Returns:
        A valid Credentials object, or None if not logged in / token is broken.
    """
    # If the file doesn't exist, the user has never logged in (or signed out)
    if not TOKEN_FILE.exists():
        return None

    # Read the file contents and parse the JSON into a Python dictionary
    data = json.loads(TOKEN_FILE.read_text())

    # ── Migration: handle old Node.js token format ────────────────────────────
    # The original version of this project used a Node.js server that saved
    # tokens differently (using "access_token" instead of "token").
    # If we see that format, delete the old file so the user logs in again.
    if "access_token" in data and "token" not in data:
        TOKEN_FILE.unlink()   # unlink = delete the file
        return None

    try:
        # Parse the expiry time string back into a proper datetime object
        # timezone.utc ensures the expiry is compared correctly
        expiry_str = data.get("expiry")
        expiry = (
            datetime.fromisoformat(expiry_str).replace(tzinfo=timezone.utc)
            if expiry_str else None
        )

        # Reconstruct the Credentials object from the saved data
        creds = Credentials(
            token=data["token"],
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id", GOOGLE_CLIENT_ID),
            client_secret=data.get("client_secret", GOOGLE_CLIENT_SECRET),
            scopes=data.get("scopes", SCOPES),
            expiry=expiry,
        )
    except Exception:
        # If anything goes wrong reading the file, delete it and start fresh
        TOKEN_FILE.unlink()
        return None

    # ── Auto-refresh if expired ───────────────────────────────────────────────
    # The access token lasts ~1 hour.  If it has expired we can get a new one
    # silently using the refresh_token (no user interaction required).
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleRequest())   # asks Google for a new access token
            save_tokens(creds)               # save the new token to disk
        except Exception as e:
            logger.warning("Token refresh failed: %s", e)

    return creds
