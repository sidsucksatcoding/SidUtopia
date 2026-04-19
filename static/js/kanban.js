// ── kanban.js ─────────────────────────────────────────────────────────────────
//
// Manages the Kanban board in the Coding tab.
//
// What is a Kanban board?
//   A visual task board with columns representing stages of work.
//   Cards move from left to right as work progresses:
//     "To Do"  →  "In Progress"  →  "Done"
//
// Each card is stored as an object in state.kanban[column]:
//   {
//     id:          1713456789000,         unique number
//     text:        "SidUtopia refactor",  project name
//     repoUrl:     "https://github.com/…", optional GitHub link
//     description: "Personal dashboard",  auto-filled from GitHub API
//     language:    "Python",              auto-filled from GitHub API
//     stars:       3,                     auto-filled from GitHub API
//   }

// ── addKanban ─────────────────────────────────────────────────────────────────
// Creates a new card in the specified column.
// If a GitHub URL was entered, fetches repo info from the GitHub API and
// attaches the description, language, and star count to the card.
async function addKanban(col) {
  const input     = document.getElementById('kanban-' + col + '-input');
  const repoInput = document.getElementById('kanban-' + col + '-repo');
  const text      = input.value.trim();
  if (!text) return;

  const repoUrl = repoInput ? repoInput.value.trim() : '';
  // Start with a basic card; GitHub details will be filled in below if a URL was given
  const card = { id: Date.now(), text, repoUrl: '', description: '', language: '', stars: 0 };

  if (repoUrl) {
    card.repoUrl = repoUrl;
    // fetchRepoInfo (github.js) calls the GitHub API and returns repo details
    const info = await fetchRepoInfo(repoUrl);
    if (info) {
      card.description = info.description        || '';
      card.language    = info.language           || '';
      card.stars       = info.stargazers_count   || 0;
    }
  }

  state.kanban[col].push(card);
  input.value = '';
  if (repoInput) repoInput.value = '';
  saveState(); renderKanban();
}

// ── moveKanban ────────────────────────────────────────────────────────────────
// Moves a card from one column to another (e.g. "todo" → "inprogress").
// Array.find locates the card, Array.filter removes it from the old column,
// then .push() adds it to the new column.
function moveKanban(id, fromCol, toCol) {
  const item = state.kanban[fromCol].find(k => k.id === id);
  if (!item) return;
  state.kanban[fromCol] = state.kanban[fromCol].filter(k => k.id !== id);
  state.kanban[toCol].push(item);
  saveState(); renderKanban();
}

// ── deleteKanban ──────────────────────────────────────────────────────────────
// Permanently removes a card from a column.
function deleteKanban(id, col) {
  state.kanban[col] = state.kanban[col].filter(k => k.id !== id);
  saveState(); renderKanban();
}

// ── kanbanMoveButtons ─────────────────────────────────────────────────────────
// Returns HTML for the "→ To Do / → In Progress / → Done" move buttons shown
// at the bottom of each card.  The current column is excluded (no point moving
// a card to the column it's already in).
function kanbanMoveButtons(id, col) {
  const cols = { todo: 'To Do', inprogress: 'In Progress', done: 'Done' };
  return Object.keys(cols)
    .filter(c => c !== col)   // exclude the card's current column
    .map(c =>
      `<button onclick="moveKanban(${id},'${col}','${c}')"
        style="background:none;border:1px solid var(--border);color:var(--muted);border-radius:4px;padding:2px 6px;font-size:0.72rem;cursor:pointer;margin-right:4px;font-family:'DM Sans',sans-serif"
        onmouseover="this.style.color='var(--accent)'"
        onmouseout="this.style.color='var(--muted)'">→ ${cols[c]}</button>`
    ).join('');
}

// ── editKanban ────────────────────────────────────────────────────────────────
// Opens two consecutive prompts: one to rename the card, one to update its URL.
// If a new URL is provided, re-fetches GitHub info to refresh description/language.
async function editKanban(id, col) {
  const item = state.kanban[col].find(k => k.id === id);
  if (!item) return;

  const newText = prompt('Edit project name:', item.text);
  if (newText === null) return;   // user clicked Cancel
  if (newText.trim()) item.text = newText.trim();

  const newUrl = prompt('GitHub URL (leave blank to remove):', item.repoUrl || '');
  if (newUrl !== null) {
    item.repoUrl = newUrl.trim();
    if (newUrl.trim()) {
      // Re-fetch GitHub data with the new URL
      const info = await fetchRepoInfo(newUrl.trim());
      if (info) {
        item.description = info.description      || '';
        item.language    = info.language         || '';
        item.stars       = info.stargazers_count || 0;
      }
    } else {
      // URL was cleared — wipe the GitHub-sourced details too
      item.description = ''; item.language = ''; item.stars = 0;
    }
  }
  saveState(); renderKanban();
}

// ── renderKanban ──────────────────────────────────────────────────────────────
// Rebuilds all three Kanban columns from state.kanban.
// Each card shows: name, description, language chip, star count, GitHub link,
// move buttons, and an edit button.
function renderKanban() {
  ['todo', 'inprogress', 'done'].forEach(col => {
    const el = document.getElementById('kanban-' + col);
    if (!el) return;
    if (!state.kanban[col].length) {
      el.innerHTML = '<div class="empty" style="padding:1rem 0">Empty</div>';
      return;
    }
    el.innerHTML = state.kanban[col].map(item => `
      <div class="kanban-card">
        <button class="delete-card" onclick="deleteKanban(${item.id},'${col}')">×</button>
        <div style="font-weight:500; margin-bottom:0.25rem; padding-right:1.2rem">${item.text}</div>
        ${item.description ? `<div class="kanban-card-desc">${item.description}</div>` : ''}
        <div class="kanban-card-meta">
          ${item.language ? `<span class="kanban-lang-chip">${item.language}</span>` : ''}
          ${item.stars    ? `<span style="font-size:0.72rem; color:var(--accent3); font-family:'DM Mono',monospace">★ ${item.stars}</span>` : ''}
          ${item.repoUrl  ? `<a class="kanban-gh-link" href="${item.repoUrl}" target="_blank">↗ GitHub</a>` : ''}
        </div>
        <div style="display:flex; align-items:center; gap:0.3rem; flex-wrap:wrap;">
          ${kanbanMoveButtons(item.id, col)}
          <button class="btn-edit" style="opacity:0" onclick="editKanban(${item.id},'${col}')">edit</button>
        </div>
      </div>
    `).join('');
  });
}
