// ── chat.js ───────────────────────────────────────────────────────────────────
//
// Controls the AI chat panel (the ✦ button fixed to the bottom-right corner).
//
// How it works:
//   1. The user clicks ✦ → toggleChat() opens/closes the panel.
//   2. The user types a message and presses Enter or clicks ➤.
//   3. sendChat() POSTs the message + conversation history to /api/chat.
//   4. The server calls the Groq AI, then returns a reply + optional ACTION lines.
//   5. We show the reply and render coloured "chips" for each action taken.
//   6. If there were actions, we reload the dashboard state so all widgets refresh.
//
// chatHistory keeps the last 10 exchanges so the AI remembers context.
// chatBusy prevents double-sending if the user clicks the button twice quickly.

let chatOpen    = false;
let chatHistory = [];    // [{role:"user"|"model", text:"..."}]
let chatBusy    = false;


// ── toggleChat ────────────────────────────────────────────────────────────────
// Opens or closes the chat panel by toggling the "open" CSS class.
// Automatically focuses the input field when opened so the user can type immediately.
function toggleChat() {
  chatOpen = !chatOpen;
  document.getElementById('chat-panel').classList.toggle('open', chatOpen);
  if (chatOpen) document.getElementById('chat-input').focus();
}


// ── sendChat ──────────────────────────────────────────────────────────────────
// Reads the input field, sends the message to the server, and handles the response.
// Shows a "...thinking" placeholder while waiting for the AI reply.
async function sendChat() {
  if (chatBusy) return;   // prevent double-send
  const input = document.getElementById('chat-input');
  const msg   = input.value.trim();
  if (!msg) return;

  input.value = '';        // clear the input immediately (feels responsive)
  chatBusy    = true;
  document.getElementById('chat-send').disabled = true;

  // Add the user's message to the chat window
  appendChatMsg('user', msg);
  // Add a placeholder "thinking" bubble while we wait for the server
  const thinkEl = appendChatMsg('ai', '...thinking', true);

  try {
    const res  = await fetch(`${SERVER}/api/chat`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      // Send the message AND the recent conversation history so the AI has context
      body:    JSON.stringify({ message: msg, history: chatHistory }),
    });
    const data = await res.json();

    if (data.error) {
      thinkEl.textContent = `Error: ${data.error}`;
      thinkEl.classList.remove('thinking');
    } else {
      // Replace "...thinking" with the real reply
      thinkEl.classList.remove('thinking');
      thinkEl.textContent = data.response;

      // Render action chips below the AI's message
      // Each action is a coloured badge showing what the AI did
      if (data.actions && data.actions.length) {
        data.actions.forEach(a => {
          const chip     = document.createElement('div');
          chip.className = 'chat-action-chip';
          // Choose a verb prefix based on the action type
          const verb     = a.startsWith('DONE_')   ? '✓ Checked off: '
                         : a.startsWith('REMOVE_') ? '✕ Removed: '
                         : a.startsWith('EDIT_')   ? '✎ Edited: '
                         : a.startsWith('MOVE_')   ? '↕ Moved: '
                         : '✓ Added: ';
          chip.textContent = verb + formatAction(a);
          thinkEl.after(chip);   // insert chip directly after the AI's message bubble
        });
        // Reload all dashboard data so widgets reflect the changes the AI made
        loadStateFromServer().then(() => { renderAll(); fetchZenithDoc(); });
      }

      // Save to history so the next message has conversational context
      chatHistory.push({ role: 'user',  text: msg });
      chatHistory.push({ role: 'model', text: data.response });
      // Keep only the last 20 entries (10 exchanges) to avoid a huge prompt
      if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
    }
  } catch(e) {
    thinkEl.textContent = 'Could not reach server.';
    thinkEl.classList.remove('thinking');
  }

  chatBusy = false;
  document.getElementById('chat-send').disabled = false;
  input.focus();   // put the cursor back in the input for the next message
}


// ── appendChatMsg ─────────────────────────────────────────────────────────────
// Creates a new message bubble div and appends it to #chat-messages.
// role     — "user" (right-aligned blue) or "ai" (left-aligned dark)
// text     — the initial text content
// thinking — if true, adds a "thinking" style (grey, italic) for the placeholder
// Returns the created element so the caller can update it later (sendChat does this).
function appendChatMsg(role, text, thinking = false) {
  const el  = document.createElement('div');
  el.className = `chat-msg ${role}${thinking ? ' thinking' : ''}`;
  el.textContent = text;
  const box = document.getElementById('chat-messages');
  box.appendChild(el);
  // Auto-scroll to the bottom so the latest message is always visible
  box.scrollTop = box.scrollHeight;
  return el;
}


// ── formatAction ──────────────────────────────────────────────────────────────
// Converts a raw ACTION string into a short human-readable label for the chip.
// Example:  "ADD_MATH_TODO:Study chapter 5"  →  "Math to-do: Study chapter 5"
function formatAction(action) {
  const map = {
    'ADD_ZENITH':            'Zenith item',
    'ADD_MATH_TODO':         'Math to-do',
    'ADD_KANBAN_TODO':       'Coding project',
    'ADD_KANBAN_INPROGRESS': 'Coding project (in progress)',
    'ADD_EXAM':              'Exam',
  };
  const [key, ...rest] = action.split(':');
  const label          = map[key] || key;
  // Only show the part before the first "|" (hides the ID for cleaner display)
  const value          = rest.join(':').split('|')[0];
  return `${label}: ${value}`;
}
