"""
routes/auth.py  —  Google "Sign in with Google" (OAuth 2.0) routes
══════════════════════════════════════════════════════════════════════════════

What does this file do?
  Handles the 4-step Google login flow:

  1. /auth/url       — Browser asks "where do I go to log in?"
                       We build a Google login URL and send it back.
  2. /auth/callback  — After the user approves on Google's page, Google
                       redirects the browser here with a one-time "code".
                       We exchange that code for real access tokens.
  3. /auth/status    — Browser checks "am I still logged in?"
  4. /auth/signout   — Delete the saved tokens (log out).

What is OAuth 2.0?
  OAuth is an industry-standard way for users to let third-party apps
  (like this dashboard) access their Google data WITHOUT sharing their password.
  Instead, Google issues a temporary "access token" — like a visitor badge.
══════════════════════════════════════════════════════════════════════════════
"""
import logging

from flask import Blueprint, request, redirect, jsonify
from requests_oauthlib import OAuth2Session
from google.oauth2.credentials import Credentials

from config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, REDIRECT_URI,
    GOOGLE_AUTH_URI, GOOGLE_TOKEN_URI, SCOPES, TOKEN_FILE,
)
from services.auth_service import save_tokens, load_tokens

# Blueprint groups related routes under the "auth" name
bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


@bp.route("/auth/url")
def auth_url():
    """Build and return the Google login URL.

    The frontend calls this first.  We return a URL like:
        https://accounts.google.com/o/oauth2/auth?client_id=...&scope=...

    The browser then redirects the user to that URL (Google's own login page).

    access_type="offline"  → ask Google for a refresh token so we can stay
                              logged in even after the access token expires (~1h).
    prompt="consent"       → always show the permissions screen so Google
                              always issues a fresh refresh token.
    """
    oauth = OAuth2Session(GOOGLE_CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPES)
    url, _ = oauth.authorization_url(
        GOOGLE_AUTH_URI,
        access_type="offline",
        prompt="consent",
    )
    return jsonify({"url": url})


@bp.route("/auth/callback")
def auth_callback():
    """Exchange the one-time Google authorization code for real access tokens.

    After the user approves permissions on Google's page, Google sends
    the browser back to this URL with a ?code=... query parameter.
    That code is useless by itself — we must exchange it for real tokens.

    Steps:
      1. Read the ?code= from the URL query string.
      2. Send it to Google's token endpoint along with our client credentials.
      3. Google returns an access_token and refresh_token.
      4. Wrap them in a Credentials object and save to tokens.json.
      5. Redirect the browser back to the dashboard (?auth=success).
    """
    code = request.args.get("code")   # the one-time code Google sent back
    oauth = OAuth2Session(GOOGLE_CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPES)
    # fetch_token() is the step that actually exchanges the code for tokens
    token = oauth.fetch_token(
        GOOGLE_TOKEN_URI,
        code=code,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    # Wrap the raw token dict in a Google Credentials object
    creds = Credentials(
        token=token["access_token"],
        refresh_token=token.get("refresh_token"),
        token_uri=GOOGLE_TOKEN_URI,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    save_tokens(creds)              # persist to disk
    return redirect("/?auth=success")  # send user back to the dashboard


@bp.route("/auth/status")
def auth_status():
    """Report whether valid Google credentials are currently stored.

    The frontend calls this on page load to decide whether to show the
    login screen or the main app.

    Returns:
        {"loggedIn": true}  if credentials exist and are (still) valid
        {"loggedIn": false} otherwise
    """
    creds = load_tokens()
    return jsonify({"loggedIn": creds is not None and creds.valid})


@bp.route("/auth/refresh-token")
def auth_refresh_token():
    """Return the current refresh token so it can be saved as a Render env var.

    This is a one-time setup route.  After logging in:
      1. Visit  /auth/refresh-token  in your browser.
      2. Copy the token value shown.
      3. Go to Render → your service → Environment → add:
           GOOGLE_REFRESH_TOKEN = <paste the value>
      4. Redeploy.  From now on the server re-authenticates itself on every
         restart without you having to log in again.

    The refresh token is like a long-lived master key — keep it secret.
    """
    creds = load_tokens()
    if not creds or not creds.refresh_token:
        return jsonify({"error": "Not logged in — connect Google first"}), 401
    return jsonify({
        "refresh_token": creds.refresh_token,
        "instructions": (
            "Copy 'refresh_token' above. In Render: your service → "
            "Environment → add variable GOOGLE_REFRESH_TOKEN = <paste value> → Save & Deploy."
        ),
    })


@bp.route("/auth/signout")
def auth_signout():
    """Delete tokens.json, effectively logging the user out.

    TOKEN_FILE.exists()  — check before deleting so we don't crash on double sign-out
    TOKEN_FILE.unlink()  — delete the file (like pressing Delete in the file explorer)
    """
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    return jsonify({"success": True})
