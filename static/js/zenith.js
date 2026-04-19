// ── zenith.js ─────────────────────────────────────────────────────────────────
//
// Manages the Zenith college-counselling section of the dashboard.
//
// There are TWO kinds of Zenith items:
//
//   1. Manual action items  (state.zenith[])
//      Items the user types in themselves via the "Add Action Item" card.
//      Stored in dashboard-data.json and rendered by renderZenith().
//
//   2. Google Doc items  (zenithMeetings[])
//      Items parsed live from the Zenith Google Doc (one tab per meeting).
//      Fetched from the server via /api/zenith and rendered by loadMeetingItems().
//      Completions (tick marks) are stored in state.zenithDocCompletions so they
//      survive page reloads, but the text comes from the Doc each time.

// ══════════════════════════════════════════════════════════════════════════════
// MANUAL ACTION ITEMS
// ══════════════════════════════════════════════════════════════════════════════

// ── addZenithItem ─────────────────────────────────────────────────────────────
// Reads the title and optional link from the "Add Action Item" input fields,
// creates a new item object, adds it to state.zenith, saves, and re-renders.
// Date.now() gives a unique number (milliseconds since 1970) used as the ID.
function addZenithItem() {
  const title = document.getElementById('zenith-title-input').value.trim();
  const link  = document.getElementById('zenith-link-input').value.trim();
  if (!title) return;   // do nothing if the title is blank
  state.zenith.push({ id: Date.now(), title, link, done: false });
  document.getElementById('zenith-title-input').value = '';
  document.getElementById('zenith-link-input').value  = '';
  saveState(); renderZenith();
}

// ── toggleZenith ──────────────────────────────────────────────────────────────
// Flips the done/not-done state of an item when the user clicks its checkbox.
// Array.find() locates the object with the matching id.
function toggleZenith(id) {
  const item = state.zenith.find(z => z.id === id);
  if (item) item.done = !item.done;   // ! flips true→false and false→true
  saveState(); renderZenith();
}

// ── deleteZenith ──────────────────────────────────────────────────────────────
// Removes an item permanently.
// Array.filter() keeps every item EXCEPT the one with the matching id.
function deleteZenith(id) {
  state.zenith = state.zenith.filter(z => z.id !== id);
  saveState(); renderZenith();
}

// ── editZenith ────────────────────────────────────────────────────────────────
// Shows a browser prompt so the user can rename an action item in place.
// prompt() returns null if the user clicks Cancel — we check for that.
function editZenith(id) {
  const item = state.zenith.find(z => z.id === id);
  if (!item) return;
  const newTitle = prompt('Edit action item:', item.title);
  if (newTitle !== null && newTitle.trim()) {
    item.title = newTitle.trim();
    saveState(); renderZenith();
  }
}

// ── renderZenithItem ──────────────────────────────────────────────────────────
// Returns the HTML string for a single manual action item.
// Template literals (backtick strings with ${...}) let us embed variables
// directly in HTML text.
function renderZenithItem(item) {
  return `
    <div class="action-item">
      <div class="todo-check ${item.done ? 'checked' : ''}" onclick="toggleZenith(${item.id})"></div>
      <div class="action-body">
        <div class="action-title ${item.done ? 'todo-text done' : ''}">${item.title}</div>
        ${item.link ? `<a class="action-link" href="${item.link}" target="_blank">Open link →</a>` : ''}
      </div>
      <button class="btn-edit" onclick="editZenith(${item.id})">edit</button>
      <button class="btn btn-danger" onclick="deleteZenith(${item.id})">Remove</button>
    </div>
  `;
}

// ── renderZenith ──────────────────────────────────────────────────────────────
// Rebuilds the entire manual action items list from state.zenith.
// Active items are shown at the top; done items are collapsed in a <details>.
function renderZenith() {
  const list = document.getElementById('zenith-list');
  if (!list) return;
  if (!state.zenith.length) { list.innerHTML = '<div class="empty">No action items yet</div>'; return; }

  const active = state.zenith.filter(i => !i.done);
  const done   = state.zenith.filter(i =>  i.done);

  list.innerHTML = `
    ${active.map(renderZenithItem).join('')}
    ${done.length ? `
      <details style="margin-top:0.75rem">
        <summary style="cursor:pointer; font-size:0.8rem; color:var(--muted); padding:0.4rem 0; list-style:none; display:flex; align-items:center; gap:0.5rem;">
          <span>▶</span> Done (${done.length})
        </summary>
        <div style="margin-top:0.5rem">${done.map(renderZenithItem).join('')}</div>
      </details>
    ` : ''}
  `;
}

// ══════════════════════════════════════════════════════════════════════════════
// GOOGLE DOC ITEMS  (live from the Zenith meeting notes document)
// ══════════════════════════════════════════════════════════════════════════════

// Holds the parsed meetings array returned by /api/zenith.
// Each element: { title: "Meeting #12", actionItems: [{id, text, links}, ...] }
let zenithMeetings = [];

// ── fetchZenithDoc ────────────────────────────────────────────────────────────
// Calls the server to re-parse the Google Doc, then populates the meeting
// dropdown and shows the latest meeting's items.
// Called on page load (auth.js → showApp) and when the user clicks "Refresh".
async function fetchZenithDoc() {
  const listEl   = document.getElementById('zenith-doc-list');
  const selectEl = document.getElementById('meeting-select');
  listEl.innerHTML = '<div class="loading">Pulling from Google Doc...</div>';
  try {
    const res  = await fetch(`${SERVER}/api/zenith`);
    const data = await res.json();
    if (data.error) { listEl.innerHTML = `<div class="empty">Error: ${data.error}</div>`; return; }
    zenithMeetings = data.meetings;
    // Build dropdown options: one per meeting, value = index in the array
    selectEl.innerHTML = zenithMeetings.map((m, i) => `<option value="${i}">${m.title}</option>`).join('');
    loadMeetingItems();   // render the first (most recent) meeting
  } catch(e) {
    listEl.innerHTML = '<div class="empty">Could not reach server</div>';
  }
}

// ── loadMeetingItems ──────────────────────────────────────────────────────────
// Called when the user picks a different meeting from the dropdown.
// Reads the selected meeting from zenithMeetings[] and renders its items,
// splitting them into "active" and "done" (completed) groups.
function loadMeetingItems() {
  const selectEl = document.getElementById('meeting-select');
  const listEl   = document.getElementById('zenith-doc-list');
  const idx      = parseInt(selectEl.value) || 0;
  const meeting  = zenithMeetings[idx];
  if (!meeting) { listEl.innerHTML = '<div class="empty">No items found</div>'; return; }

  // zenithDocCompletions maps item-id → true for items the user has ticked off
  if (!state.zenithDocCompletions) state.zenithDocCompletions = {};
  const active = meeting.actionItems.filter(item => !state.zenithDocCompletions[item.id]);
  const done   = meeting.actionItems.filter(item => !!state.zenithDocCompletions[item.id]);

  // Build HTML for one Google Doc action item (may have embedded links)
  const renderDocItem = (item) => {
    const isDone      = !!state.zenithDocCompletions[item.id];
    // item.links is an array of {text, url} objects embedded in the bullet text
    const linkButtons = item.links.map(l =>
      `<a class="action-link" href="${l.url}" target="_blank">${l.text} →</a>`
    ).join(' ');
    return `
      <div class="action-item">
        <div class="todo-check ${isDone ? 'checked' : ''}" onclick="toggleDocItem('${item.id}', this)"></div>
        <div class="action-body">
          <div class="action-title ${isDone ? 'todo-text done' : ''}">${item.text}</div>
          ${linkButtons ? `<div style="margin-top:0.25rem; display:flex; flex-wrap:wrap; gap:0.5rem">${linkButtons}</div>` : ''}
        </div>
      </div>
    `;
  };

  listEl.innerHTML = `
    ${active.map(renderDocItem).join('')}
    ${done.length ? `
      <details style="margin-top:0.75rem">
        <summary style="cursor:pointer; font-size:0.8rem; color:var(--muted); padding:0.4rem 0; list-style:none; display:flex; align-items:center; gap:0.5rem;">
          <span>▶</span> Done (${done.length})
        </summary>
        <div style="margin-top:0.5rem">${done.map(renderDocItem).join('')}</div>
      </details>
    ` : ''}
  `;
}

// ── toggleDocItem ─────────────────────────────────────────────────────────────
// Marks a Google Doc item as done/not-done when its checkbox is clicked.
// el = the checkbox div that was clicked (we walk up to .action-item to update
//      the sibling title element too).
function toggleDocItem(id, el) {
  if (!state.zenithDocCompletions) state.zenithDocCompletions = {};
  // Toggle: if it was done, mark undone; if undone, mark done
  state.zenithDocCompletions[id] = !state.zenithDocCompletions[id];
  const done = state.zenithDocCompletions[id];
  // Update the visual state without a full re-render (faster, no flicker)
  const item = el.closest('.action-item');
  item.querySelector('.todo-check').classList.toggle('checked', done);
  item.querySelector('.action-title').classList.toggle('done', done);
  saveState();   // persist the completion to the server
}
