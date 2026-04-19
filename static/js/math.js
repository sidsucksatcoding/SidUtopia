// ── math.js ───────────────────────────────────────────────────────────────────
//
// Manages the Math to-do list in the Math tab.
// Tasks are stored in state.mathTodos — each task is an object like:
//   { id: 1713456789000, text: "Complete chapter 5 exercises", done: false }
//
// id   — a unique number (milliseconds since 1970 = Date.now())
// text — the task description
// done — whether the checkbox has been ticked

// ── addMathTodo ───────────────────────────────────────────────────────────────
// Reads the input field, creates a new task, adds it to state, and redraws.
function addMathTodo() {
  const text = document.getElementById('math-todo-input').value.trim();
  if (!text) return;   // ignore empty submissions
  state.mathTodos.push({ id: Date.now(), text, done: false });
  document.getElementById('math-todo-input').value = '';   // clear the input
  saveState(); renderMathTodos();
}

// ── toggleMathTodo ────────────────────────────────────────────────────────────
// Flips the done state of a task when the user clicks its checkbox.
function toggleMathTodo(id) {
  const item = state.mathTodos.find(t => t.id === id);
  if (item) item.done = !item.done;
  saveState(); renderMathTodos();
}

// ── deleteMathTodo ────────────────────────────────────────────────────────────
// Removes a task permanently using Array.filter (keeps everything EXCEPT the match).
function deleteMathTodo(id) {
  state.mathTodos = state.mathTodos.filter(t => t.id !== id);
  saveState(); renderMathTodos();
}

// ── editMathTodo ──────────────────────────────────────────────────────────────
// Opens a browser prompt to rename a task.
// Returns without saving if the user clicks Cancel (prompt returns null).
function editMathTodo(id) {
  const item = state.mathTodos.find(t => t.id === id);
  if (!item) return;
  const newText = prompt('Edit task:', item.text);
  if (newText !== null && newText.trim()) {
    item.text = newText.trim();
    saveState(); renderMathTodos();
  }
}

// ── renderMathTodos ───────────────────────────────────────────────────────────
// Rebuilds the entire math to-do list from state.mathTodos.
//
// Active (undone) tasks are shown first.
// Completed tasks are hidden inside a collapsible <details> element so they
// don't clutter the view, but can still be seen if needed.
function renderMathTodos() {
  const list = document.getElementById('math-todo-list');
  if (!list) return;   // guard: element might not exist if tab hasn't rendered yet
  if (!state.mathTodos.length) { list.innerHTML = '<div class="empty">No tasks yet</div>'; return; }

  const active = state.mathTodos.filter(i => !i.done);
  const done   = state.mathTodos.filter(i =>  i.done);

  // A helper function that returns the HTML for one task row.
  // Written as a const so it can be used with .map() below.
  const renderTodoItem = (item) => `
    <div class="todo-item">
      <div class="todo-check ${item.done ? 'checked' : ''}" onclick="toggleMathTodo(${item.id})"></div>
      <span class="todo-text ${item.done ? 'done' : ''}">${item.text}</span>
      <button class="btn-edit" onclick="editMathTodo(${item.id})">edit</button>
      <button class="btn btn-danger" onclick="deleteMathTodo(${item.id})">×</button>
    </div>
  `;

  // .map() applies renderTodoItem to every task, .join('') combines the HTML strings
  list.innerHTML = `
    ${active.map(renderTodoItem).join('')}
    ${done.length ? `
      <details style="margin-top:0.75rem">
        <summary style="cursor:pointer; font-size:0.8rem; color:var(--muted); padding:0.4rem 0; list-style:none; display:flex; align-items:center; gap:0.5rem;">
          <span>▶</span> Done (${done.length})
        </summary>
        <div style="margin-top:0.5rem">${done.map(renderTodoItem).join('')}</div>
      </details>
    ` : ''}
  `;
}
