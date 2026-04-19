// ── links.js ──────────────────────────────────────────────────────────────────
//
// Manages the "Quick Links" grids that appear in the Zenith and Math tabs.
//
// Each tab has its own set of links stored in state.links:
//   state.links.zenith  — links shown in the Zenith section
//   state.links.math    — links shown in the Math / Resources section
//
// Each link is an object: { id: 1713456789000, label: "Khan Academy", url: "https://..." }
//
// The `tab` parameter used throughout this file is a string like "zenith" or "math"
// that tells the function which section to operate on.

// Colour for the dot next to each link (matches the section's accent colour)
const linkColors = { zenith: 'var(--accent)', math: 'var(--accent2)' };

// ── addLink ───────────────────────────────────────────────────────────────────
// Reads the label and URL inputs for the given tab, adds a new link to state,
// saves, and re-renders that tab's link grid.
//
// If the URL doesn't start with "http", we add "https://" automatically so
// the link works when clicked (bare URLs like "google.com" would otherwise
// be treated as relative paths).
function addLink(tab) {
  const label  = document.getElementById(tab + '-link-label').value.trim();
  const url    = document.getElementById(tab + '-link-url').value.trim();
  if (!label || !url) return;   // both fields are required
  const fullUrl = url.startsWith('http') ? url : 'https://' + url;
  state.links[tab].push({ id: Date.now(), label, url: fullUrl });
  document.getElementById(tab + '-link-label').value = '';
  document.getElementById(tab + '-link-url').value   = '';
  saveState(); renderLinks(tab);
}

// ── removeLink ────────────────────────────────────────────────────────────────
// Removes a single link from the given tab's list by ID.
function removeLink(tab, id) {
  state.links[tab] = state.links[tab].filter(l => l.id !== id);
  saveState(); renderLinks(tab);
}

// ── renderLinks ───────────────────────────────────────────────────────────────
// Rebuilds the link grid for a specific tab.
// If no tab argument is given (e.g. called from renderAll), it renders both.
//
// Each link becomes a clickable <a> tag that opens in a new browser tab.
// The × button calls event.preventDefault() to stop the click from also
// following the link before removing it.
function renderLinks(tab) {
  // If called without arguments (from renderAll), render all tabs
  if (!tab) { ['zenith', 'math'].forEach(renderLinks); return; }

  const grid  = document.getElementById(tab + '-links');
  if (!grid) return;
  const color = linkColors[tab] || 'var(--accent)';

  if (!state.links[tab] || !state.links[tab].length) {
    grid.innerHTML = `<div class="empty" style="text-align:left;padding:0.5rem 0">No links yet — add one above</div>`;
    return;
  }

  grid.innerHTML = state.links[tab].map(link => `
    <a class="link-item" href="${link.url}" target="_blank">
      <span class="link-dot" style="background:${color}"></span>
      ${link.label}
      <button class="link-remove-btn" onclick="event.preventDefault(); removeLink('${tab}', ${link.id})">×</button>
    </a>
  `).join('');
}
