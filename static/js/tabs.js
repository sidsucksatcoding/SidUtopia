// ── tabs.js ───────────────────────────────────────────────────────────────────
//
// Handles the tab bar at the top of the dashboard (Zenith / Math / Coding / …).
//
// How tabs work:
//   Each tab button in the HTML has  onclick="switchTab('zenith', this)".
//   There is a corresponding <div id="tab-zenith" class="tab-panel"> for the content.
//   Only one tab-panel has the CSS class "active" at a time — that's the visible one.
//   The rest are hidden by CSS.
//
// "Lazy loading":
//   Some tabs (Google Data, Timesheet, GitHub) make network requests.
//   We don't load them until the user actually clicks on them.
//   This makes the initial page load faster.

// ── switchTab ─────────────────────────────────────────────────────────────────
// name  — the tab identifier, e.g. 'zenith', 'math', 'coding', 'google', 'timesheet'
// btn   — the <button> element that was clicked (so we can highlight it)
function switchTab(name, btn) {
  // Remove "active" from ALL tab panels (hides them all)
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

  // Remove "active" from ALL tab buttons (un-highlights them all)
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));

  // Show only the selected panel and highlight only the clicked button
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');

  // ── Lazy loading: fetch data only when its tab is first opened ────────────
  // These are skipped on startup and triggered here so the page loads fast.

  // Exams tab also shows Google Calendar — reload it every visit so it's fresh
  if (name === 'exams') loadCalendarEvents();

  // Google Data tab: fetch unread Gmail + recent Drive files
  if (name === 'google') loadGoogleData();

  // Coding tab: load GitHub repos if the user has a saved username
  if (name === 'coding' && localStorage.getItem('gh_username')) loadGitHub();

  // Timesheet tab: reading a large spreadsheet takes time — do it on demand
  if (name === 'timesheet') loadTimesheet();
}
