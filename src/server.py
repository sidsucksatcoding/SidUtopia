"""
server.py  —  The main entry point for the web server
══════════════════════════════════════════════════════════════════════════════

What does this file do?
  This is the "front door" of the whole application.  When you run the server,
  Python starts here.  This file:
    1. Creates the Flask app (the web server object)
    2. Tells Flask where to find HTML templates and CSS/JS files
    3. Registers all the route "blueprints" (each blueprint handles one topic)
    4. Starts listening for browser requests

What is Flask?
  Flask is a Python library that makes it easy to build websites and APIs.
  An "API" is just a set of URLs that a program can call to get or send data.
  For example, when the browser visits /api/gmail, Flask runs a Python function
  that fetches your unread emails and returns them as JSON.

What is a Blueprint?
  A Blueprint is like a sub-folder of routes.  Instead of putting ALL 30+ routes
  in this one file (messy!), each topic gets its own file in src/routes/:
    routes/gmail.py     → /api/gmail, /api/gmail/mark-read
    routes/calendar.py  → /api/calendar, /api/calendar/add, /api/calendar/delete
    ... and so on.
  This file just collects and registers them all.

How to run locally:
  python src/server.py

How to deploy on Render:
  gunicorn --chdir src --bind 0.0.0.0:$PORT server:app
══════════════════════════════════════════════════════════════════════════════
"""
import os

from flask import Flask, render_template
from flask_cors import CORS

from config import BASE_DIR, PORT

# ── Allow HTTP (not just HTTPS) during local development ──────────────────────
# OAuth normally requires HTTPS for security.  This environment variable tells
# the oauthlib library to relax that rule on localhost.
# In production on Render this setting has no effect (Render always uses HTTPS).
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# ── Create the Flask application ──────────────────────────────────────────────
# Flask(__name__, ...) creates a web server object called `app`.
#   template_folder  — where Flask looks for .html files (render_template)
#   static_folder    — where Flask serves CSS, JS, images from
#   static_url_path  — the URL prefix for those files (/static/css/main.css)
#
# We use BASE_DIR (the project root) so these paths are correct whether the
# server is started from the project root or from inside src/.
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),   # project_root/templates/
    static_folder=str(BASE_DIR / "static"),         # project_root/static/
    static_url_path="/static",
)

# ── Enable CORS ───────────────────────────────────────────────────────────────
# CORS (Cross-Origin Resource Sharing) is a browser security rule.
# By default browsers block a web page from calling an API on a different domain.
# CORS(app) tells Flask to add the right headers so the browser allows it.
# This is needed in development when the HTML is served from port 5500
# (VS Code Live Server) but the API is on port 3000.
CORS(app)


# ── Index route ───────────────────────────────────────────────────────────────
# When a browser visits the root URL ( http://localhost:3000/ ),
# Flask runs this function and returns the HTML page.
# render_template("index.html") reads templates/index.html and sends it.
@app.route("/")
def serve_index():
    """Serve the single-page dashboard HTML."""
    return render_template("index.html")


# ── Register Blueprints ───────────────────────────────────────────────────────
# Import each blueprint (group of routes) and register it with the app.
# After this, Flask knows about ALL routes across ALL files.
#
# Import is done here (not at the top) because the blueprints themselves import
# from config.py, which must finish loading first.
from routes.auth      import bp as auth_bp       # /auth/url, /auth/callback …
from routes.gmail     import bp as gmail_bp       # /api/gmail …
from routes.calendar  import bp as calendar_bp    # /api/calendar …
from routes.drive     import bp as drive_bp       # /api/drive
from routes.zenith    import bp as zenith_bp      # /api/zenith
from routes.dashboard import bp as dashboard_bp   # /api/data
from routes.chat      import bp as chat_bp        # /api/chat
from routes.timesheet import bp as timesheet_bp   # /api/timesheet …
from routes.sms       import bp as sms_bp         # /api/send-summary

for blueprint in [
    auth_bp, gmail_bp, calendar_bp, drive_bp, zenith_bp,
    dashboard_bp, chat_bp, timesheet_bp, sms_bp,
]:
    app.register_blueprint(blueprint)


# ── Start the server (development only) ───────────────────────────────────────
# This block only runs when you execute  `python src/server.py`  directly.
# When gunicorn (production) imports this file, __name__ is "server", not
# "__main__", so this block is skipped — gunicorn manages the server itself.
if __name__ == "__main__":
    print(f"Dashboard running at http://localhost:{PORT}")
    print("Open your dashboard and click 'Connect Google Account'")
    # debug=False keeps the server stable; set to True only for troubleshooting
    app.run(host="0.0.0.0", port=PORT, debug=False)
