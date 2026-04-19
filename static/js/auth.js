// ── auth.js ───────────────────────────────────────────────────────────────────
//
// This file controls who can see the dashboard.
// It handles:
//   1. Starting the Google login flow (connectGoogle)
//   2. Signing out (signOut)
//   3. Showing the main app once login is confirmed (showApp)
//   4. Keeping the "Google connected" status dot up to date (updateStatusIndicator)
//   5. Sending the SMS summary (sendSummary)
//   6. Booting the whole app when the page first loads (window "load" event)

// ── connectGoogle ─────────────────────────────────────────────────────────────
// Called when the user clicks "Connect Google Account" on the login screen.
// Asks the server for a Google login URL, then sends the browser there.
// Google shows a permissions screen; after approval, it redirects back to
// /auth/callback on our server, which saves the tokens and redirects to /?auth=success.
function connectGoogle() {
  fetch(`${SERVER}/auth/url`)
    .then(r => r.json())
    .then(data => { window.location.href = data.url; })
    .catch(() => alert('Cannot reach server. Make sure it is running!'));
}

// ── checkAuthStatus ───────────────────────────────────────────────────────────
// Asks the server whether there are valid Google credentials saved.
// Returns true (logged in) or false (not logged in).
// Used on page load and by updateStatusIndicator.
async function checkAuthStatus() {
  try {
    const res  = await fetch(`${SERVER}/auth/status`);
    const data = await res.json();
    return data.loggedIn;
  } catch(e) { return false; }
}

// ── signOut ───────────────────────────────────────────────────────────────────
// Tells the server to delete the saved Google tokens, then hides the app and
// shows the login screen again.
// localStorage.removeItem removes the saved user name so the next visitor
// gets a clean login experience.
async function signOut() {
  await fetch(`${SERVER}/auth/signout`);
  localStorage.removeItem('dashboard-user');
  document.getElementById('login-screen').style.display = 'flex';
  document.getElementById('app').style.display          = 'none';
}

// ── showApp ───────────────────────────────────────────────────────────────────
// Called once we know the user is logged in.
// Hides the login screen, shows the main app, sets the avatar and name,
// then kicks off all the data loads (state, Google data, Zenith doc, Calendar).
function showApp(userName) {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app').style.display          = 'flex';
  document.getElementById('app').style.flexDirection    = 'column';

  // Build initials from the user's name — e.g. "Sid Shende" → "SS"
  const initials = userName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
  document.getElementById('user-avatar').textContent = initials;
  document.getElementById('user-name').textContent   = userName;

  // Load all data sources in parallel — each function handles its own errors
  loadStateFromServer();   // tasks, kanban, exams, links (state.js)
  updateStatusIndicator(); // green/red dot in the header
  loadGoogleData();        // Gmail + Drive (google_data.js)
  fetchZenithDoc();        // Zenith Google Doc action items (zenith.js)
  loadCalendarEvents();    // Google Calendar grid (calendar.js)

  // Restore GitHub credentials the user previously typed, so they don't
  // have to re-enter them every time the page loads.
  const savedUser = localStorage.getItem('gh_username');
  const savedPat  = localStorage.getItem('gh_pat');
  if (savedUser) document.getElementById('gh-username').value = savedUser;
  if (savedPat)  document.getElementById('gh-pat').value      = savedPat;
  if (savedUser) loadGitHub();  // auto-load their repos if we have a username
}

// ── updateStatusIndicator ─────────────────────────────────────────────────────
// Checks auth status and updates the coloured dot + text in the top header.
// A green dot means Google is connected; grey/red means not connected.
async function updateStatusIndicator() {
  const connected = await checkAuthStatus();
  // classList.toggle(cls, condition) adds the class if condition is true, removes it otherwise
  document.getElementById('status-dot').classList.toggle('connected', connected);
  document.getElementById('status-text').textContent = connected ? 'Google connected' : 'Google not connected';
}

// ── sendSummary ───────────────────────────────────────────────────────────────
// Triggered by the "📱 Send Summary" button in the header.
// POSTs to /api/send-summary — the server gathers data and fires an SMS via Twilio.
// The button shows live progress: "Sending…" → "✓ Sent to N" → back to normal.
async function sendSummary() {
  const btn = document.getElementById('sms-btn');
  btn.textContent = '⏳ Sending...';
  btn.disabled    = true;
  try {
    const res  = await fetch(`${SERVER}/api/send-summary`, { method: 'POST' });
    const json = await res.json();
    if (json.success) {
      btn.textContent = `✓ Sent to ${json.sent_to}`;
      btn.style.color = 'var(--accent2)';
      // Reset button back to normal after 4 seconds
      setTimeout(() => {
        btn.textContent = '📱 Send Summary';
        btn.disabled    = false;
        btn.style.color = '';
      }, 4000);
    } else {
      const msg       = json.error || 'unknown error';
      btn.textContent = '✗ Failed';
      btn.style.color = 'var(--accent4)';
      btn.title       = msg;   // hovering the button shows the full error
      console.error('Send Summary error:', msg);
      alert(`Send Summary failed:\n${msg}`);
      setTimeout(() => {
        btn.textContent = '📱 Send Summary';
        btn.disabled    = false;
        btn.style.color = '';
        btn.title       = '';
      }, 4000);
    }
  } catch(e) {
    btn.textContent = '✗ Error';
    setTimeout(() => { btn.textContent = '📱 Send Summary'; btn.disabled = false; }, 3000);
  }
}

// ── Boot: runs when the page finishes loading ─────────────────────────────────
// window "load" fires after ALL resources (HTML, CSS, JS, fonts) have loaded.
// This is the very first thing that runs when the user opens the dashboard.
//
// Two cases:
//   Case 1: Google just redirected back here with ?auth=success
//           → clean the URL, ask for the user's name (first time only), show app.
//   Case 2: User is returning to the page (already logged in before)
//           → silently check auth status, show app if still connected.
window.addEventListener('load', async () => {
  // URLSearchParams parses the ?key=value portion of the current URL
  const params = new URLSearchParams(window.location.search);

  if (params.get('auth') === 'success') {
    // Remove ?auth=success from the URL bar so it looks clean (no page reload)
    window.history.replaceState({}, '', window.location.pathname);

    let userName = localStorage.getItem('dashboard-user');
    if (!userName) {
      // First login — ask for the user's name
      userName = prompt("Welcome! What's your name?") || 'User';
      localStorage.setItem('dashboard-user', userName);
    }
    showApp(userName);
    return;
  }

  // Normal page load — check if the user is already authenticated
  const savedUser   = localStorage.getItem('dashboard-user');
  const isConnected = await checkAuthStatus();
  if (savedUser && isConnected) showApp(savedUser);
  // Otherwise: login screen stays visible (it's the default)
});
