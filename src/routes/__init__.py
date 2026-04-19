"""
routes/__init__.py  —  Shared utilities used by every route file
══════════════════════════════════════════════════════════════════════════════

What is this file for?
  Python treats any folder with an __init__.py as a "package" — a group of
  related modules you can import from.

  This particular __init__.py also defines require_auth, a "decorator" that
  every protected route uses.  Instead of copy-pasting two lines of
  authentication checking into every single route function, we write it once
  here and attach it with @require_auth.

What is a decorator?
  A decorator is a function that wraps another function to add extra behaviour.
  Think of it like a security guard at a door:
    • Without @require_auth:  anyone who calls the route gets in.
    • With    @require_auth:  the guard first checks for Google credentials;
                              if they're missing, the guard turns the caller away.

  Usage example (in routes/gmail.py):
      @bp.route("/api/gmail")
      @require_auth
      def get_gmail(creds):      ← creds is injected automatically
          ...
══════════════════════════════════════════════════════════════════════════════
"""
from functools import wraps
from flask import jsonify
from services.auth_service import load_tokens


def require_auth(f):
    """Decorator that protects a route by checking Google credentials first.

    How it works:
      1. When the browser calls a protected URL, Flask runs this wrapper first.
      2. It calls load_tokens() to read the saved Google credentials from disk.
      3. If no credentials exist → return a 401 "not authenticated" error JSON.
         (401 is the HTTP status code meaning "you need to log in first")
      4. If credentials exist → call the original route function, passing the
         credentials in as a keyword argument called `creds`.

    Why inject `creds`?
      Every protected route needs the credentials to call Google APIs.
      By injecting them automatically, the route function gets them for free
      without having to call load_tokens() itself — less repetition.
    """
    @wraps(f)   # @wraps preserves the original function's name and docstring
    def wrapper(*args, **kwargs):
        # Try to load saved Google credentials from tokens.json
        creds = load_tokens()
        if not creds:
            # No credentials found — tell the browser to log in first
            return jsonify({"error": "not_authenticated"}), 401
        # Credentials OK — call the real route function with creds added
        return f(*args, creds=creds, **kwargs)
    return wrapper
