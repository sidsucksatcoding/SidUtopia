// ── config.js ─────────────────────────────────────────────────────────────────
//
// This file must be loaded FIRST (before any other JS file) because every
// other file uses the SERVER variable defined here.
//
// What is SERVER?
//   When JavaScript calls the backend (Flask server), it needs to know the URL.
//   In production on Render, the HTML page and the server are at the SAME address,
//   so relative URLs like "/api/gmail" work fine — SERVER is just an empty string.
//
//   In development, you might open the HTML via VS Code Live Server (port 5500)
//   while Flask runs separately on port 3000.  In that case, relative URLs would
//   hit port 5500 (where there is no API) instead of 3000.  We detect this by
//   checking window.location.port and point SERVER at the correct address.
//
// Example usage in other files:
//   fetch(`${SERVER}/api/gmail`)   →  in prod:  /api/gmail
//                                  →  in dev:   http://localhost:3000/api/gmail

const SERVER = window.location.port === '5500' ? 'http://localhost:3000' : '';
