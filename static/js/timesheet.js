// ── timesheet.js ──────────────────────────────────────────────────────────────
//
// Manages the Timesheet tab — a view into a Google Sheets spreadsheet where
// you record hours worked on different activities each day.
//
// How it's structured:
//   • The spreadsheet has one tab per month: "April 2026", "May 2026", etc.
//   • Each tab has a header row of dates and rows of activities with hour values.
//   • The dashboard loads all months from the server and renders them as
//     collapsible <details> sections.
//   • Long months (>7 days shown at once) are split into weekly sub-tabs.
//   • Each cell is editable directly — clicking it, typing a value, and
//     clicking away saves the change back to Google Sheets.

let _timesheetLoaded = false;
let _nextMonth       = null;   // {year, month} — computed after load, used by "Add Month" button


// ── formatTimeDisplay ─────────────────────────────────────────────────────────
// Normalises a raw cell value into a consistent time format for display.
// Examples:
//   "2"   → "2:00"    (bare number = hours)
//   "30m" → "0:30"    (30 minutes)
//   "1:30"→ "1:30"    (already correct, left unchanged)
//   ""    → ""        (empty cell, left empty)
function formatTimeDisplay(val) {
  if (!val) return '';
  // Already in "H:MM" format — return as-is
  if (/^\d+:\d{2}$/.test(String(val).trim())) return String(val).trim();
  // Strip trailing "h" or "m" suffix, parse as a number
  const n = parseFloat(String(val).replace(/[hm]$/i, '').trim());
  if (isNaN(n)) return String(val);   // not a recognisable number — return raw
  if (n >= 0  && n <= 9)  return n + ':00';           // whole hours 0–9
  if (n >= 10 && n <= 59) return '0:' + String(n).padStart(2, '0');  // minutes
  return String(val);
}


// ── formatDateShort ───────────────────────────────────────────────────────────
// Converts a date string like "4/18/25" into a short label like "Apr 18"
// for use in the table column headers.
function formatDateShort(dateStr) {
  try {
    const parts  = dateStr.split('/');
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${months[parseInt(parts[0])-1]} ${parseInt(parts[1])}`;
  } catch { return dateStr; }
}


// ── loadTimesheet ─────────────────────────────────────────────────────────────
// Fetches all month data from the server (/api/timesheet) and renders it.
// Shows a loading message while waiting, or an error if the fetch fails.
async function loadTimesheet() {
  const container = document.getElementById('timesheet-container');
  container.innerHTML = '<div class="loading">Loading timesheet...</div>';
  try {
    const res  = await fetch(`${SERVER}/api/timesheet`);
    const data = await res.json();
    if (data.error) { container.innerHTML = `<div class="empty">Error: ${data.error}</div>`; return; }
    renderTimesheet(data);
    updateAddMonthBtn(data.months);
    _timesheetLoaded = true;
  } catch(e) {
    container.innerHTML = '<div class="empty">Could not load timesheet — make sure Google is connected.</div>';
  }
}


// ── renderTimesheet ───────────────────────────────────────────────────────────
// Builds and injects the full timesheet HTML from the server data.
// Each month becomes a <details> element (click the header to expand/collapse).
// Wide months are split into weekly sub-tabs so the table doesn't scroll horizontally.
function renderTimesheet(data) {
  const container = document.getElementById('timesheet-container');
  if (!data.months || !data.months.length) {
    container.innerHTML = '<div class="empty">No timesheet data found.</div>';
    return;
  }

  // ── makeWeekTable ──────────────────────────────────────────────────────────
  // Returns the HTML for one week's worth of data as a <table>.
  // weekDates  — the date strings for this week (column headers)
  // startIdx   — which cell index to start reading from in each row's cells[]
  function makeWeekTable(month, weekDates, startIdx) {
    return `
      <table class="timesheet-table">
        <thead><tr>
          <th class="ts-act-header">Activity</th>
          ${weekDates.map(d => `<th>${formatDateShort(d)}</th>`).join('')}
        </tr></thead>
        <tbody>
          ${month.rows.map(row => `
            <tr>
              <td class="ts-act-cell">${row.activity}</td>
              ${row.cells.slice(startIdx, startIdx + weekDates.length).map(cell => `
                <td><span
                  class="ts-cell"
                  contenteditable="true"
                  data-row="${cell.sheet_row}"
                  data-col="${cell.sheet_col}"
                  data-sheet="${month.sheet_name}"
                  data-original="${formatTimeDisplay(cell.value)}"
                  onblur="onTsCellBlur(this)"
                  onkeydown="if(event.key==='Enter'){event.preventDefault();this.blur();return false}"
                >${formatTimeDisplay(cell.value)}</span></td>
              `).join('')}
            </tr>
          `).join('')}
        </tbody>
      </table>`;
  }

  let html = '';
  data.months.forEach((month, mi) => {
    // First month is open by default; the rest start collapsed
    const isOpen  = mi === 0 ? 'open' : '';
    // A "Delete" button appears only on completely empty months (safety guard)
    const isEmpty = month.rows.every(r => r.cells.every(c => !c.value));
    const deleteBtn = isEmpty
      ? `<button onclick="event.preventDefault();deleteTimesheetMonth('${month.sheet_name}','${month.label}')"
           style="margin-left:auto;background:rgba(247,106,106,0.12);color:var(--accent4);border:1px solid rgba(247,106,106,0.3);border-radius:0.3rem;padding:0.15rem 0.6rem;font-size:0.73rem;cursor:pointer">Delete</button>`
      : '';

    // Split dates into chunks of 7 (one chunk per week tab)
    const weeks = [];
    for (let i = 0; i < month.dates.length; i += 7) {
      weeks.push({ dates: month.dates.slice(i, i + 7), startIdx: i });
    }

    // mKey = safe CSS id using underscores instead of hyphens
    const mKey   = month.key.replace(/-/g, '_');
    // Tab bar only appears if the month has more than one week of data
    const tabBar = weeks.length > 1 ? `
      <div class="ts-week-tabs">
        ${weeks.map((w, wi) => {
          const first = parseInt(w.dates[0].split('/')[1]);
          const last  = parseInt(w.dates[w.dates.length - 1].split('/')[1]);
          return `<button class="ts-week-tab ${wi === 0 ? 'active' : ''}" onclick="switchTsWeek('${mKey}',${wi})">${first}–${last}</button>`;
        }).join('')}
      </div>` : '';

    const panes = weeks.map((w, wi) => `
      <div class="ts-week-pane ${wi === 0 ? 'active' : ''}">
        ${makeWeekTable(month, w.dates, w.startIdx)}
      </div>`).join('');

    html += `<details class="timesheet-month card" ${isOpen}>
      <summary><span class="ts-arrow">▶</span>${month.label} <span style="color:var(--muted);font-size:0.78rem;font-weight:400;margin-left:0.4rem">${month.dates.length} days</span>${deleteBtn}</summary>
      <div class="timesheet-table-wrap" id="ts-month-${mKey}">
        ${tabBar}
        ${panes}
      </div>
    </details>`;
  });

  container.innerHTML = html;

  // ── Smooth close animation ─────────────────────────────────────────────────
  // By default <details> closes instantly.  We intercept the click, play a
  // slide-up animation, THEN remove the "open" attribute.
  container.querySelectorAll('details.timesheet-month').forEach(details => {
    details.querySelector('summary').addEventListener('click', e => {
      if (!details.open) return;   // already closed — let it open normally
      e.preventDefault();          // stop the default instant-close
      const content = details.querySelector('.timesheet-table-wrap');
      if (!content) { details.removeAttribute('open'); return; }
      content.style.animation = 'tsClose 0.32s cubic-bezier(0.4,0,0.2,1) forwards';
      content.addEventListener('animationend', () => {
        details.removeAttribute('open');
        content.style.animation = '';
      }, { once: true });   // { once: true } removes the listener after it fires
    });
  });
}


// ── switchTsWeek ──────────────────────────────────────────────────────────────
// Shows a specific week pane and highlights its tab button.
// Called by the week tab buttons rendered inside each month section.
function switchTsWeek(mKey, weekIdx) {
  const wrap = document.getElementById('ts-month-' + mKey);
  if (!wrap) return;
  // Toggle the "active" class on tab buttons and panes
  wrap.querySelectorAll('.ts-week-tab').forEach((t, i)  => t.classList.toggle('active', i === weekIdx));
  wrap.querySelectorAll('.ts-week-pane').forEach((p, i) => p.classList.toggle('active', i === weekIdx));
}


// ── _tsSaveCell ───────────────────────────────────────────────────────────────
// Makes one attempt to POST a cell value to the server.
// Returns true on success, false on any failure (HTTP error or network error).
async function _tsSaveCell(sheetRow, sheetCol, sheetName, value) {
  try {
    const res = await fetch(`${SERVER}/api/timesheet/update`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ row: sheetRow, col: sheetCol, value, sheet_name: sheetName }),
    });
    if (!res.ok) {
      console.warn('Timesheet save HTTP', res.status, { sheetRow, sheetCol, sheetName });
      return false;
    }
    const json = await res.json();
    if (!json.success) {
      console.warn('Timesheet save server error:', json.error, { sheetRow, sheetCol, sheetName });
      return false;
    }
    return true;
  } catch(e) {
    console.warn('Timesheet save network error:', e);
    return false;
  }
}


// ── onTsCellBlur ──────────────────────────────────────────────────────────────
// Called when the user clicks away from an editable timesheet cell (onblur).
// Formats the value, compares it to the original, and saves if it changed.
// Retries once after 4 seconds if the first attempt fails (handles transient 502s).
async function onTsCellBlur(el) {
  const raw      = el.textContent.trim();
  const stripped = /^\d+:\d{2}$/.test(raw) ? raw : raw.replace(/[hm]$/i, '').trim();
  const formatted = formatTimeDisplay(stripped);

  if (el.textContent.trim() !== formatted) el.textContent = formatted;

  const original = el.dataset.original || '';
  if (formatted === original) return;

  const sheetRow  = parseInt(el.dataset.row);
  const sheetCol  = parseInt(el.dataset.col);
  const sheetName = el.dataset.sheet;

  el.classList.add('saving');
  el.classList.remove('save-error');

  let ok = await _tsSaveCell(sheetRow, sheetCol, sheetName, formatted);

  if (!ok) {
    // First attempt failed — wait 4 s then retry once
    await new Promise(r => setTimeout(r, 4000));
    ok = await _tsSaveCell(sheetRow, sheetCol, sheetName, formatted);
  }

  if (ok) {
    el.dataset.original = formatted;
  } else {
    el.classList.add('save-error');
    console.error('Timesheet save failed after retry', { sheetRow, sheetCol, sheetName, formatted });
  }
  el.classList.remove('saving');
}


// ── updateAddMonthBtn ─────────────────────────────────────────────────────────
// Sets the "Add Next Month" button label after loading the timesheet.
// Looks at the most recent existing month and computes the one after it.
// e.g. if the newest tab is "April 2026", the button says "Add May 2026".
function updateAddMonthBtn(months) {
  if (!months || !months.length) return;
  const [y, m] = months[0].key.split('-').map(Number);
  let ny = y, nm = m + 1;
  if (nm > 12) { nm = 1; ny++; }
  const labels = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  _nextMonth = { year: ny, month: nm };
  const btn  = document.getElementById('ts-add-btn');
  if (btn) btn.textContent = `Add ${labels[nm-1]} ${ny}`;
}


// ── addTimesheetMonth ─────────────────────────────────────────────────────────
// Sends a request to the server to create the next month's tab in Google Sheets.
// The server copies activity names from the most recent tab and builds the header row.
async function addTimesheetMonth() {
  const status = document.getElementById('ts-add-status');
  if (!_nextMonth) { status.textContent = 'Load timesheet first.'; return; }
  status.textContent = 'Adding…';
  try {
    const res  = await fetch(`${SERVER}/api/timesheet/add-month`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(_nextMonth),
    });
    const json = await res.json();
    if (json.error) { status.textContent = 'Error: ' + json.error; return; }
    status.textContent = `✓ Added ${json.days_added} days`;
    setTimeout(() => { status.textContent = ''; }, 3000);
    loadTimesheet();   // reload to show the new month
  } catch(e) {
    status.textContent = 'Failed to add month.';
  }
}


// ── deleteTimesheetMonth ──────────────────────────────────────────────────────
// Asks the user for confirmation then permanently deletes the month's tab.
// The server only allows this on empty months (checked in renderTimesheet).
async function deleteTimesheetMonth(monthKey, label) {
  if (!confirm(`Delete all ${label} columns from the sheet? This cannot be undone.`)) return;
  try {
    const res  = await fetch(`${SERVER}/api/timesheet/delete-month`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ month_key: monthKey }),
    });
    const json = await res.json();
    if (json.error) { alert('Error: ' + json.error); return; }
    loadTimesheet();
  } catch(e) { alert('Failed to delete month.'); }
}
