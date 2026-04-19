// ── exams.js ──────────────────────────────────────────────────────────────────
//
// Manages the custom Exam tracker in the "Exams & Events" tab.
// (Google Calendar events are handled separately in calendar.js.)
//
// Each exam is stored as an object in state.exams:
//   {
//     id:        1713456789000,   unique ID
//     name:      "AP Calc BC",    exam name
//     date:      "2025-05-10",    date string (ISO format: YYYY-MM-DD)
//     prepLinks: [               optional study links
//       { id: ..., label: "Khan Academy", url: "https://..." },
//     ]
//   }
//
// Exams are sorted by date so the soonest one always appears at the top.
// A countdown badge shows: "5d" (5 days away), "Today!", or "Past".

// ── addExam ───────────────────────────────────────────────────────────────────
// Reads the exam name and date from the input fields, creates a new exam object,
// adds it to state.exams, saves to server, and re-renders.
function addExam() {
  const name = document.getElementById('exam-name').value.trim();
  const date = document.getElementById('exam-date').value;
  if (!name || !date) return;   // both fields required
  state.exams.push({ id: Date.now(), name, date, prepLinks: [] });
  document.getElementById('exam-name').value = '';
  document.getElementById('exam-date').value = '';
  saveState(); renderExams();
}

// ── addPrepLink ───────────────────────────────────────────────────────────────
// Adds a study/prep link to a specific exam (identified by examId).
// Each exam has its own pair of inputs (prep-label-{id} and prep-url-{id})
// so multiple exams can each have their own links.
function addPrepLink(examId) {
  const labelEl = document.getElementById('prep-label-' + examId);
  const urlEl   = document.getElementById('prep-url-'   + examId);
  const label   = labelEl.value.trim();
  const url     = urlEl.value.trim();
  if (!label || !url) return;

  const exam = state.exams.find(e => e.id === examId);
  if (!exam) return;
  if (!exam.prepLinks) exam.prepLinks = [];   // guard for older saved data

  exam.prepLinks.push({
    id:    Date.now(),
    label,
    url:   url.startsWith('http') ? url : 'https://' + url,
  });
  labelEl.value = ''; urlEl.value = '';
  saveState(); renderExams();
}

// ── removePrepLink ────────────────────────────────────────────────────────────
// Removes one prep link from a specific exam.
function removePrepLink(examId, linkId) {
  const exam = state.exams.find(e => e.id === examId);
  if (!exam) return;
  exam.prepLinks = (exam.prepLinks || []).filter(l => l.id !== linkId);
  saveState(); renderExams();
}

// ── deleteExam ────────────────────────────────────────────────────────────────
// Permanently removes an exam and all its prep links.
function deleteExam(id) {
  state.exams = state.exams.filter(e => e.id !== id);
  saveState(); renderExams();
}

// ── daysUntil ─────────────────────────────────────────────────────────────────
// Calculates how many days from today until the exam date.
// Returns a negative number if the exam is in the past.
//
// setHours(0,0,0,0) resets today to midnight so we compare whole days,
// not partial days (otherwise "today at 11pm" would show as 0.04 days away).
// 86400000 = the number of milliseconds in one day (24 × 60 × 60 × 1000).
function daysUntil(dateStr) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  return Math.round((new Date(dateStr + 'T00:00:00') - today) / 86400000);
}

// ── renderExams ───────────────────────────────────────────────────────────────
// Rebuilds the exam list sorted by date (soonest first).
// Each exam card shows a countdown badge, the exam name, date, prep links,
// and an "Add Prep Link" form.
function renderExams() {
  const list = document.getElementById('exam-list');
  if (!list) return;   // guard: tab may not be visible yet
  if (!state.exams.length) { list.innerHTML = '<div class="empty">No exams added yet</div>'; return; }

  // Sort a copy (spread operator [...] avoids mutating the original array)
  const sorted = [...state.exams].sort((a, b) => new Date(a.date) - new Date(b.date));

  list.innerHTML = sorted.map(exam => {
    const days = daysUntil(exam.date);

    // Choose the countdown badge colour based on urgency
    const cls = days <= 7 ? 'days-soon' : days <= 21 ? 'days-medium' : 'days-far';
    // Choose the countdown text
    const txt = days < 0 ? 'Past' : days === 0 ? 'Today!' : `${days}d`;

    // Format the date for display: "May 10, 2025"
    const display = new Date(exam.date + 'T00:00:00').toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric'
    });

    const prepLinks = exam.prepLinks || [];
    // Render each prep link as a small chip with a remove button
    const prepChips = prepLinks.map(l => `
      <span class="prep-link-chip">
        <a href="${l.url}" target="_blank">${l.label}</a>
        <button onclick="removePrepLink(${exam.id}, ${l.id})" title="Remove">×</button>
      </span>
    `).join('');

    return `
      <div class="exam-item" style="flex-direction:column; align-items:stretch; gap:0.5rem;">
        <div style="display:flex; align-items:center; gap:1rem;">
          <span class="exam-countdown ${cls}">${txt}</span>
          <div class="exam-info" style="flex:1">
            <div class="exam-name">${exam.name}</div>
          </div>
          <div class="exam-date">${display}</div>
          <button class="btn btn-danger" onclick="deleteExam(${exam.id})">Remove</button>
        </div>
        <div class="prep-links-section">
          <div style="font-size:0.75rem; color:var(--muted); margin-bottom:0.3rem; font-weight:600; text-transform:uppercase; letter-spacing:0.06em;">Prep Links</div>
          <div>${prepChips || '<span style="font-size:0.78rem; color:var(--muted)">No prep links yet</span>'}</div>
          <div class="prep-link-add-row">
            <input class="kanban-input" id="prep-label-${exam.id}" placeholder="Link name..." style="flex:1; min-width:100px" onkeydown="if(event.key==='Enter') addPrepLink(${exam.id})" />
            <input class="kanban-input" id="prep-url-${exam.id}"   placeholder="https://..."  style="flex:2; min-width:140px" onkeydown="if(event.key==='Enter') addPrepLink(${exam.id})" />
            <button class="btn-small" onclick="addPrepLink(${exam.id})">+</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}
