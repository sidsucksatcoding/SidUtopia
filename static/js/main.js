// ── main.js ──────────────────────────────────────────────────────────────────
//
// This file is the "conductor" of the whole dashboard.
// When we want to update everything on screen at once (for example after loading
// data from the server, or after the AI chat adds a new task), we just call
// renderAll() and it delegates to each section's own rendering function.
//
// Think of renderAll() like refreshing every widget on a phone home screen
// at the same time — each widget knows how to draw itself, we just tell
// them all to go at once.

// ── renderAll ────────────────────────────────────────────────────────────────
// Calls every "render" function across the app so the whole page reflects
// the latest data stored in the `state` variable (defined in state.js).
//
// When to call this:
//   • After loading data from the server (loadStateFromServer)
//   • After the AI chat processes an action (addTask, removeTodo, etc.)
//   • Basically any time `state` changes and you want the screen to catch up.

function renderAll() {
  // Redraw the Zenith college-counseling action items list
  renderZenith();

  // Redraw the Math to-do list
  renderMathTodos();

  // Redraw all three Kanban columns (To Do / In Progress / Done)
  renderKanban();

  // Redraw the Exams & Events section
  renderExams();

  // Redraw all Quick Link sections (zenith links, math links, etc.)
  renderLinks();
}
