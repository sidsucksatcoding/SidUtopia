// ── state.js ──────────────────────────────────────────────────────────────────
//
// The "state" is the single source of truth for all the data displayed on the
// dashboard.  Think of it as one big box that holds everything:
//   • College-counselling action items (zenith)
//   • Math to-do tasks (mathTodos)
//   • Coding project cards in 3 columns (kanban)
//   • Upcoming exams (exams)
//   • Quick links for each section (links)
//
// Why store it in one place?
//   Every render function reads from `state`.  When the AI chat adds a new
//   task, it updates `state`, then calls renderAll() — and every widget on the
//   page refreshes automatically.  There is no confusion about which copy of
//   the data is "real".
//
// Why save it to the server?
//   JavaScript variables live only in the browser tab.  If you close the page
//   and come back, all your tasks would be gone.  By saving to the server
//   (dashboard-data.json via /api/data), the data persists across page loads
//   and is accessible from any device.

// ── The state object ──────────────────────────────────────────────────────────
// This is the starting shape.  loadStateFromServer() replaces these empty arrays
// with real data as soon as the page loads.
let state = {
  zenith:    [],                                     // college-counselling items
  mathTodos: [],                                     // math study tasks
  kanban:    { todo: [], inprogress: [], done: [] }, // coding project board
  exams:     [],                                     // upcoming exams
  links:     { zenith: [], math: [] },               // quick links per tab
};

// ── loadStateFromServer ───────────────────────────────────────────────────────
// Fetches the saved dashboard data from the server and replaces `state`.
// Called once on startup (from auth.js → showApp) and after chat actions.
async function loadStateFromServer() {
  try {
    const res  = await fetch(`${SERVER}/api/data`);
    const data = await res.json();
    state = data;
    // Guard: older saves may not have a `links` field — add it if missing
    if (!state.links) state.links = { zenith: [], math: [] };
    renderAll();   // redraw every section with the freshly loaded data
  } catch(e) {
    console.error('Could not load data from server:', e);
  }
}

// ── saveState ─────────────────────────────────────────────────────────────────
// Sends the current `state` to the server so it is saved to dashboard-data.json.
// Called after every change (adding a task, ticking a checkbox, etc.).
//
// JSON.stringify(state) converts the JavaScript object to a JSON string so it
// can be sent in the HTTP request body.
async function saveState() {
  try {
    await fetch(`${SERVER}/api/data`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(state),
    });
  } catch(e) {
    console.error('Could not save:', e);
  }
}
