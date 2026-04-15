# Sid's Utopia

A personal dashboard for managing college counseling, studies, coding projects, and Google data — all in one place, with a cosmic purple theme and an AI assistant.

## Features

- **Zenith** — College counseling action items synced live from a shared Google Doc, plus manual items
- **Math** — To-do list and resource links
- **Coding** — Kanban board (To Do / In Progress / Done)
- **Exams & Events** — Full monthly Google Calendar view with event creation and deletion
- **Google Data** — Unread Gmail (with mark-all-read), recent Drive files
- **AI Chat** — Powered by Groq (Llama 3.3 70b); reads your dashboard and can add, remove, edit, check off, and move items by chat

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+ · Flask · Flask-CORS |
| Frontend | Vanilla HTML / CSS / JavaScript |
| Auth | Google OAuth 2.0 (`requests-oauthlib`) |
| Google APIs | Docs · Drive · Gmail · Calendar |
| AI | Groq API (`llama-3.3-70b-versatile`) |

## Project Structure

```
dashboard/
├── src/
│   └── server.py          # Flask backend — all API routes
├── index.html             # Single-page frontend dashboard
├── themes-preview.html    # Standalone theme palette preview
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable template
└── README.md
```

Files created at runtime (gitignored):
- `tokens.json` — Google OAuth tokens
- `dashboard-data.json` — your local tasks, kanban, and exam data

## Setup

### 1. Clone

```bash
git clone https://github.com/yourusername/sids-utopia.git
cd sids-utopia
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Google Cloud project

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a project
2. Enable these APIs:
   - Google Docs API
   - Google Drive API
   - Gmail API
   - Google Calendar API
3. Go to **APIs & Services → Credentials → Create OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Authorised redirect URI: `http://localhost:3000/auth/callback`
4. Copy the Client ID and Client Secret

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values (see `.env.example` for descriptions).

| Variable | Where to get it |
|---|---|
| `GOOGLE_CLIENT_ID` | Google Cloud Console → Credentials |
| `GOOGLE_CLIENT_SECRET` | Google Cloud Console → Credentials |
| `GOOGLE_REDIRECT_URI` | Must match the redirect URI you registered |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) — free tier |
| `PORT` | Default `3000` |

### 5. (Optional) Point to your own Zenith Google Doc

In `src/server.py`, update the `ZENITH_DOC_ID` constant to your own Google Doc ID:

```python
ZENITH_DOC_ID = "your-google-doc-id-here"
```

The doc ID is the long string in the URL: `docs.google.com/document/d/**<ID>**/edit`

### 6. Run

```bash
python src/server.py
```

Then open `index.html` using a local file server. The easiest way is the **Live Server** extension in VS Code — right-click `index.html` and choose *Open with Live Server*.

Visit `http://127.0.0.1:5500/index.html` and click **Connect Google Account**.

## AI Chat

The floating **✦** button opens the AI assistant. It has full read access to your dashboard and can:

| You say | AI does |
|---|---|
| "What do I have due soon?" | Summarises upcoming tasks and exams |
| "Add a math todo: finish problem set" | Adds it to the Math tab |
| "Check off the Zenith item about essays" | Marks it done |
| "Remove the kanban card for project X" | Deletes it |
| "Move project Y to In Progress" | Moves the kanban card |
| "Edit my math todo to say…" | Updates it in place |

## Notes

- Sign out and sign back in after any scope changes to refresh Google permissions
- The OAuth consent screen must be in **Testing** mode with your Google account added as a test user while the app is not verified
