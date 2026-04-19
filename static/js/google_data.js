// ── google_data.js ────────────────────────────────────────────────────────────
//
// Loads Gmail and Google Drive data for the "Google Data" tab.
//
// loadGoogleData() is the entry point — it calls both loadGmail() and loadDrive()
// in parallel.  It's called from auth.js when the app first opens, and again
// each time the user switches to the Google Data tab (tabs.js).

// ── loadGoogleData ────────────────────────────────────────────────────────────
// Triggers both Gmail and Drive loads simultaneously.
// Since they are independent there's no need to wait for one before starting the other.
function loadGoogleData() { loadGmail(); loadDrive(); }


// ── loadGmail ─────────────────────────────────────────────────────────────────
// Fetches unread emails from the server (/api/gmail) and renders them as
// clickable rows.  Clicking a row opens the email in Gmail in a new tab.
async function loadGmail() {
  const el = document.getElementById('gmail-list');
  el.innerHTML = '<div class="loading">Loading Gmail...</div>';
  try {
    const res  = await fetch(`${SERVER}/api/gmail`);
    const data = await res.json();

    if (data.error) { el.innerHTML = `<div class="empty">Error: ${data.error}</div>`; return; }
    if (!data.messages.length) { el.innerHTML = '<div class="empty">No unread emails ✓</div>'; return; }

    el.innerHTML = data.messages.map(m => {
      // Build the direct link to this email in Gmail
      // "#inbox/{id}" opens exactly that message thread
      const gmailUrl = `https://mail.google.com/mail/u/0/#inbox/${m.id}`;
      // Strip the "<email@example.com>" part from the From header — show just the name
      const from     = m.from.replace(/<.*>/, '').trim() || m.from;
      return `
        <div class="google-item" style="cursor:pointer" onclick="window.open('${gmailUrl}','_blank')">
          <span class="google-item-icon">✉</span>
          <div class="google-item-body" style="flex:1; min-width:0">
            <div class="google-item-title" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis">${m.subject}</div>
            <div class="google-item-sub">${from}</div>
          </div>
          <span style="font-size:0.7rem; color:var(--muted); white-space:nowrap; margin-left:0.5rem">↗</span>
        </div>
      `;
    }).join('');
  } catch(e) {
    el.innerHTML = '<div class="empty">Could not load — make sure Google is connected</div>';
  }
}


// ── markAllRead ───────────────────────────────────────────────────────────────
// Sends a POST to /api/gmail/mark-read which calls Gmail's batchModify API
// to remove the UNREAD label from every unread message in one go.
// The button element is passed in (btn) so we can update its label during the request.
async function markAllRead(btn) {
  btn.textContent = 'Marking...';
  btn.disabled    = true;
  try {
    const res  = await fetch(`${SERVER}/api/gmail/mark-read`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      btn.textContent = `Marked ${data.marked}`;
      // After 1.8 seconds: reset button and refresh the inbox list
      setTimeout(() => { btn.textContent = 'Mark All Read'; btn.disabled = false; loadGmail(); }, 1800);
    } else {
      alert('Could not mark as read.\n\n' + (data.hint || data.error || 'Unknown error'));
      btn.textContent = 'Mark All Read'; btn.disabled = false;
    }
  } catch(e) {
    alert('Network error — is the server running?');
    btn.textContent = 'Mark All Read'; btn.disabled = false;
  }
}


// ── loadDrive ─────────────────────────────────────────────────────────────────
// Fetches the 10 most recently modified Drive files from the server (/api/drive)
// and renders them as clickable rows that open the file in a new tab.
async function loadDrive() {
  const el = document.getElementById('drive-list');
  el.innerHTML = '<div class="loading">Loading Drive...</div>';
  try {
    const res  = await fetch(`${SERVER}/api/drive`);
    const data = await res.json();

    if (data.error) { el.innerHTML = `<div class="empty">Error: ${data.error}</div>`; return; }
    if (!data.files.length) { el.innerHTML = '<div class="empty">No recent files</div>'; return; }

    // Human-readable labels for common Google Drive MIME types
    // (MIME type = a standard code that identifies a file type)
    const typeLabel = {
      'application/vnd.google-apps.document':     'Doc',
      'application/vnd.google-apps.spreadsheet':  'Sheet',
      'application/vnd.google-apps.presentation': 'Slides',
      'application/vnd.google-apps.folder':       'Folder',
      'application/pdf': 'PDF',
    };

    el.innerHTML = data.files.map(f => {
      const label    = typeLabel[f.mimeType] || 'File';
      // Format the modified date as "Apr 18"
      const modified = new Date(f.modifiedTime).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      return `
        <div class="google-item" onclick="window.open('${f.webViewLink}','_blank')">
          <span class="google-item-icon">📄</span>
          <div class="google-item-body">
            <div class="google-item-title">${f.name}</div>
            <div class="google-item-sub">${label}</div>
          </div>
          <span class="google-item-time">${modified}</span>
        </div>
      `;
    }).join('');
  } catch(e) {
    el.innerHTML = '<div class="empty">Could not load — make sure Google is connected</div>';
  }
}
