/* Saylient AI — web app configuration (Phase 4).
   Edit this file to point the page at your API. No build step. */

window.SAYLIENT_CONFIG = {
  // Base URL of the Saylient API (apps/api, FastAPI).
  // Default: the local dev server. Set to "" to disable API calls
  // entirely and always use the built-in demo.
  //
  // CORS note: the API only accepts the origins in ALLOWED_ORIGINS
  // (default http://localhost:5173 and http://127.0.0.1:5173).
  // Either serve this page from one of those origins, or start the API
  // with e.g. ALLOWED_ORIGINS=http://localhost:8000 (or wherever you
  // serve this page from). If the API is unreachable or rejects the
  // origin, the page falls back to the built-in demo — never an error.
  apiBaseUrl: "http://localhost:8000",

  // How long to wait for the API before falling back to the demo (ms).
  apiTimeoutMs: 5000,
};
