// ── calendar.js ───────────────────────────────────────────────────────────────
//
// Renders the Google Calendar mini-grid in the "Exams & Events" tab.
//
// How the mini calendar works:
//   • calYear / calMonth track which month is currently displayed.
//   • loadCalendarEvents() fetches events from the server for that month.
//   • renderCalendarGrid() builds the grid HTML and places event "chips"
//     on the correct day cells.
//   • calPrev() / calNext() change the month and reload.
//
// calEvents holds all events from ALL of the user's Google Calendars,
// merged into one array: [{id, title, start, color, calendarId}, ...]

let calEvents = [];
let calYear   = new Date().getFullYear();
let calMonth  = new Date().getMonth();   // 0-indexed (0=January … 11=December)


// ── loadCalendarEvents ────────────────────────────────────────────────────────
// Fetches events for the current calYear/calMonth from the server.
// Called on page load, when switching to the Exams tab, and when navigating months.
async function loadCalendarEvents() {
  const el = document.getElementById('cal-container');
  el.innerHTML = '<div class="cal-loading">Loading calendar...</div>';
  try {
    // calMonth + 1 because the URL expects 1-indexed months (January = 1)
    const res  = await fetch(`${SERVER}/api/calendar?year=${calYear}&month=${calMonth + 1}`);
    const data = await res.json();
    if (data.error) { el.innerHTML = `<div class="cal-loading">Error: ${data.error}</div>`; return; }
    calEvents = data.events || [];
    renderCalendarGrid();
  } catch(e) {
    el.innerHTML = '<div class="cal-loading">Could not load — make sure Google is connected</div>';
  }
}

// ── calPrev / calNext ─────────────────────────────────────────────────────────
// Navigate backward or forward one month, then reload events.
// JavaScript months are 0-indexed so we handle wrapping:
//   month 0 - 1 → month 11 of the previous year
//   month 11 + 1 → month 0 of the next year
function calPrev() { calMonth--; if (calMonth < 0)  { calMonth = 11; calYear--; } loadCalendarEvents(); }
function calNext() { calMonth++; if (calMonth > 11) { calMonth = 0;  calYear++; } loadCalendarEvents(); }


// ── calParseDate ──────────────────────────────────────────────────────────────
// Converts a Google Calendar event start string into a JavaScript Date object.
//
// Why not just  new Date(start) ?
//   "2025-05-10" parsed by new Date() is treated as UTC midnight.
//   In timezones behind UTC (e.g. US Eastern = UTC-5) that becomes the *previous*
//   evening local time, so the event would appear on the wrong day.
//   Parsing manually with new Date(y, m-1, d) uses local time instead.
function calParseDate(start) {
  if (!start) return null;
  if (!start.includes('T')) {
    // All-day event: "2025-05-10" → parse as local date
    const [y, m, d] = start.split('-').map(Number);
    return new Date(y, m - 1, d);
  }
  return new Date(start);   // timed event (has hour/minute) — safe to parse directly
}


// ── renderCalendarGrid ────────────────────────────────────────────────────────
// Builds the full month grid HTML and injects it into #cal-container.
//
// Grid layout:
//   Row 1:  Sun Mon Tue Wed Thu Fri Sat  (day-of-week labels)
//   Rows 2+: day number cells, starting after blank spacers for the offset
//
// Each day cell can contain up to 3 event chips; extras show "+N more".
function renderCalendarGrid() {
  const months   = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const today    = new Date();
  // "YYYY-MM-DD" string for today to highlight the correct cell
  const todayKey = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;

  // Group events by date key for O(1) lookup when building each cell
  const byDay = {};
  for (const ev of calEvents) {
    const d = calParseDate(ev.start);
    if (!d) continue;
    const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    (byDay[key] = byDay[key] || []).push(ev);
  }

  // Day-of-week index of the 1st of the month (0=Sunday … 6=Saturday)
  const firstDow  = new Date(calYear, calMonth, 1).getDay();
  // Total days in the month (handles leap years automatically)
  const totalDays = new Date(calYear, calMonth + 1, 0).getDate();

  let cells = '';
  // Blank spacer cells before day 1 (e.g. month starts on Wednesday → 3 blanks)
  for (let i = 0; i < firstDow; i++) cells += '<div class="cal-day cal-empty"></div>';

  for (let d = 1; d <= totalDays; d++) {
    const key     = `${calYear}-${String(calMonth+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    const isToday = key === todayKey;
    const evs     = byDay[key] || [];

    // Build chips for up to 3 events; truncate title to keep chip small
    const chips = evs.slice(0, 3).map(ev => {
      const t   = ev.title.length > 17 ? ev.title.slice(0, 15) + '…' : ev.title;
      const c   = ev.color || '#7c6af7';
      const idx = calEvents.indexOf(ev);
      // The × button stops the click from bubbling then deletes the event
      return `<span class="cal-event-chip" style="background:${c}33; color:${c}" title="${ev.title}"><span>${t}</span><button class="cal-chip-del" onclick="event.stopPropagation(); deleteCalEvent(${idx})">×</button></span>`;
    }).join('');
    const more  = evs.length > 3 ? `<span class="cal-more">+${evs.length - 3} more</span>` : '';

    cells += `<div class="cal-day${isToday ? ' cal-today' : ''}"><span class="cal-day-num">${d}</span>${chips}${more}</div>`;
  }

  document.getElementById('cal-container').innerHTML = `
    <div class="cal-nav">
      <button class="cal-nav-btn" onclick="calPrev()">‹</button>
      <span class="cal-month-label">${months[calMonth]} ${calYear}</span>
      <button class="cal-nav-btn" onclick="calNext()">›</button>
    </div>
    <div class="cal-grid">
      <div class="cal-dow">Su</div><div class="cal-dow">Mo</div><div class="cal-dow">Tu</div>
      <div class="cal-dow">We</div><div class="cal-dow">Th</div><div class="cal-dow">Fr</div><div class="cal-dow">Sa</div>
      ${cells}
    </div>
  `;
}


// ── addCalendarEvent ──────────────────────────────────────────────────────────
// Reads the "Add Event" form and POSTs to /api/calendar/add.
// On success, clears the form and refreshes the grid.
async function addCalendarEvent() {
  const name   = document.getElementById('ev-name').value.trim();
  const start  = document.getElementById('ev-start').value;
  const end    = document.getElementById('ev-end').value;
  const status = document.getElementById('ev-status');
  if (!name || !start) { status.textContent = 'Please fill in a name and start date.'; return; }
  status.style.color  = 'var(--muted)';
  status.textContent  = 'Adding event…';
  try {
    const res  = await fetch(`${SERVER}/api/calendar/add`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ name, start, end }),
    });
    const data = await res.json();
    if (data.success) {
      status.style.color = 'var(--accent2)';
      status.textContent = '✓ Event added to Google Calendar!';
      document.getElementById('ev-name').value  = '';
      document.getElementById('ev-start').value = '';
      document.getElementById('ev-end').value   = '';
      setTimeout(() => { status.textContent = ''; loadCalendarEvents(); }, 1800);
    } else if (data.hint === 'REAUTH') {
      // User logged in before calendar.events write scope was added — needs re-auth
      status.style.color = 'var(--accent4)';
      status.innerHTML   = '⚠ New permissions needed. <a href="#" onclick="signOut();return false;" style="color:var(--accent5)">Sign out</a> and sign back in.';
    } else {
      status.style.color = 'var(--accent4)';
      status.textContent = 'Error: ' + (data.error || 'Could not add event');
    }
  } catch(e) {
    status.style.color = 'var(--accent4)';
    status.textContent = 'Network error. Is the server running?';
  }
}


// ── deleteCalEvent ────────────────────────────────────────────────────────────
// Removes an event from Google Calendar when the user clicks the × on a chip.
// idx is the event's index in calEvents[] — set when the chip HTML was built above.
async function deleteCalEvent(idx) {
  const ev = calEvents[idx];
  if (!ev) return;
  if (!confirm(`Remove "${ev.title}" from Google Calendar?`)) return;
  try {
    const res  = await fetch(`${SERVER}/api/calendar/delete`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ eventId: ev.id, calendarId: ev.calendarId }),
    });
    const data = await res.json();
    if (data.success) { loadCalendarEvents(); }
    else { alert(data.error || 'Could not delete event.'); }
  } catch(e) {
    alert('Network error. Is the server running?');
  }
}
