// ── github.js ─────────────────────────────────────────────────────────────────
//
// Loads GitHub repository and issue data for the Coding tab.
//
// The GitHub API is public — you can call it without logging in to see
// basic repo info.  However, to see issues and pull requests you need a
// Personal Access Token (PAT), because those require authentication.
//
// What is a PAT?
//   A Personal Access Token is like a password you generate on GitHub that
//   lets code act on your behalf.  Generate one at:
//   GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens
//
// Data flow:
//   1. User types username (and optionally PAT) in the Coding tab.
//   2. loadGitHub() is called.
//   3. We hit https://api.github.com/users/{username}/repos for the repo grid.
//   4. If a PAT is available, we also hit https://api.github.com/issues for PRs/issues.
//   5. fetchRepoInfo() is also called by kanban.js when a user adds a card with a URL.

// ── ghHeaders ─────────────────────────────────────────────────────────────────
// Returns the HTTP headers to include with every GitHub API request.
// If a PAT is available (from the input field or localStorage), it's included
// as an Authorization header — this raises the rate limit and unlocks private data.
function ghHeaders() {
  const pat = (document.getElementById('gh-pat') || {}).value?.trim()
           || localStorage.getItem('gh_pat')
           || '';
  const h = { 'Accept': 'application/vnd.github+json' };
  if (pat) h['Authorization'] = `Bearer ${pat}`;
  return h;
}

// ── fetchRepoInfo ─────────────────────────────────────────────────────────────
// Given a GitHub repo URL like "https://github.com/user/project", fetches
// the repo's description, language, and star count from the GitHub API.
// Returns the API response object, or null if the URL is invalid or the request fails.
// Used by kanban.js when adding/editing a card with a GitHub URL.
async function fetchRepoInfo(url) {
  // Regex to extract "owner" and "repo" from any github.com URL
  const match = url.match(/github\.com\/([^/]+)\/([^/?#]+)/);
  if (!match) return null;   // not a GitHub URL
  try {
    const res = await fetch(`https://api.github.com/repos/${match[1]}/${match[2]}`, { headers: ghHeaders() });
    return res.ok ? res.json() : null;
  } catch { return null; }
}

// ── loadGitHub ────────────────────────────────────────────────────────────────
// Main function: called when the user clicks "Load" or switches to the Coding tab.
// Saves the username and PAT to localStorage so they persist across page reloads.
// Makes two separate API calls:
//   1. Public repos list (no PAT needed)
//   2. Open issues + PRs (PAT required)
async function loadGitHub() {
  const usernameEl = document.getElementById('gh-username');
  const patEl      = document.getElementById('gh-pat');
  const username   = usernameEl.value.trim() || localStorage.getItem('gh_username') || '';
  const pat        = patEl.value.trim();
  if (!username) {
    document.getElementById('gh-status').textContent = 'Enter a GitHub username.';
    return;
  }

  // Persist to localStorage so they survive page refreshes
  localStorage.setItem('gh_username', username);
  if (pat) localStorage.setItem('gh_pat', pat);

  document.getElementById('gh-status').textContent  = 'Loading...';
  document.getElementById('gh-repos').innerHTML     = '<div class="loading">Fetching repos...</div>';
  document.getElementById('gh-issues').innerHTML    = '<div class="loading">Fetching issues...</div>';

  // ── Section 1: Repositories ───────────────────────────────────────────────
  // Fetches up to 12 repos sorted by most recently updated.
  // Renders them as a responsive card grid.
  try {
    const res   = await fetch(
      `https://api.github.com/users/${username}/repos?sort=updated&per_page=12`,
      { headers: ghHeaders() }
    );
    if (!res.ok) throw new Error(res.status);
    const repos = await res.json();

    document.getElementById('gh-repo-count').textContent = `${repos.length} repos`;
    document.getElementById('gh-repos').innerHTML = repos.length ? `
      <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(260px,1fr)); gap:0.75rem">
        ${repos.map(r => `
          <a href="${r.html_url}" target="_blank" style="text-decoration:none; color:inherit">
            <div style="background:var(--surface2); border:1px solid var(--border); border-radius:10px; padding:0.95rem 1rem; transition:border-color 0.2s, transform 0.2s, box-shadow 0.2s; cursor:pointer"
                 onmouseover="this.style.borderColor='var(--accent)';this.style.transform='translateY(-2px)';this.style.boxShadow='0 4px 16px rgba(124,106,247,0.2)'"
                 onmouseout="this.style.borderColor='';this.style.transform='';this.style.boxShadow=''">
              <div style="font-weight:600; font-size:0.93rem; margin-bottom:0.25rem; color:var(--accent)">${r.name}</div>
              ${r.description ? `<div style="font-size:0.8rem; color:var(--muted); margin-bottom:0.5rem; line-height:1.4">${r.description}</div>` : ''}
              <div style="display:flex; gap:0.5rem; flex-wrap:wrap; align-items:center">
                ${r.language ? `<span style="font-size:0.72rem; background:rgba(124,106,247,0.15); color:var(--accent); border-radius:4px; padding:1px 7px; font-family:'DM Mono',monospace">${r.language}</span>` : ''}
                ${r.stargazers_count ? `<span style="font-size:0.72rem; color:var(--accent3); font-family:'DM Mono',monospace">★ ${r.stargazers_count}</span>` : ''}
                <span style="font-size:0.72rem; color:var(--muted); font-family:'DM Mono',monospace; margin-left:auto">${new Date(r.updated_at).toLocaleDateString()}</span>
              </div>
            </div>
          </a>
        `).join('')}
      </div>
    ` : '<div class="empty">No public repos found</div>';
    document.getElementById('gh-status').textContent = `Loaded ${repos.length} repos`;
  } catch(e) {
    document.getElementById('gh-repos').innerHTML    = '<div class="empty">Failed to load repos — check username or rate limit</div>';
    document.getElementById('gh-status').textContent = 'Error loading repos';
  }

  // ── Section 2: Issues & Pull Requests ────────────────────────────────────
  // This endpoint requires a PAT — it returns issues assigned to the user.
  // PRs are detected by checking if issue.pull_request exists.
  const savedPat = localStorage.getItem('gh_pat') || '';
  if (!savedPat) {
    document.getElementById('gh-issues').innerHTML = '<div class="empty">Enter a Personal Access Token to load issues &amp; PRs</div>';
    return;
  }
  try {
    const res    = await fetch(
      `https://api.github.com/issues?filter=created&state=open&per_page=20`,
      { headers: ghHeaders() }
    );
    if (!res.ok) throw new Error(res.status);
    const issues = await res.json();

    document.getElementById('gh-issues').innerHTML = issues.length ? issues.map(i => {
      const isPR = !!i.pull_request;   // issues have no pull_request property; PRs do
      const repo = i.repository_url.replace('https://api.github.com/repos/', '');
      return `
        <div style="display:flex; align-items:flex-start; gap:0.75rem; padding:0.75rem 0.9rem; border:1px solid var(--border); border-radius:10px; background:var(--surface2); margin-bottom:0.55rem;
                    transition:border-color 0.2s, transform 0.2s"
             onmouseover="this.style.borderColor='${isPR ? 'var(--accent2)' : 'var(--accent5)'}';this.style.transform='translateX(3px)'"
             onmouseout="this.style.borderColor='';this.style.transform=''">
          <span style="font-size:0.82rem; padding:1px 7px; border-radius:4px; background:${isPR ? 'rgba(78,205,196,0.15)' : 'rgba(74,158,255,0.15)'}; color:${isPR ? 'var(--accent2)' : 'var(--accent5)'}; font-family:'DM Mono',monospace; flex-shrink:0; margin-top:1px">${isPR ? 'PR' : '#' + i.number}</span>
          <div style="flex:1; min-width:0">
            <a href="${i.html_url}" target="_blank" style="font-weight:500; font-size:0.93rem; color:var(--text); text-decoration:none" onmouseover="this.style.color='var(--accent)'" onmouseout="this.style.color='var(--text)'">${i.title}</a>
            <div style="font-size:0.78rem; color:var(--muted); margin-top:0.15rem; font-family:'DM Mono',monospace">${repo}</div>
          </div>
          <span style="font-size:0.75rem; color:var(--muted); font-family:'DM Mono',monospace; flex-shrink:0">${new Date(i.updated_at).toLocaleDateString()}</span>
        </div>`;
    }).join('') : '<div class="empty">No open issues or PRs</div>';
  } catch(e) {
    document.getElementById('gh-issues').innerHTML = '<div class="empty">Failed to load issues — check your PAT permissions</div>';
  }
}
