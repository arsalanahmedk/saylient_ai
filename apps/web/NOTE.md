# Web app — Phase 4

Static frontend, no build step. Design: **Neumorphism** (approved
2026-11-21) — Polar White #F1F3F4 surfaces, raised/inset shadows,
Glacier Blue #9CBDE0 secondary layer, Safety Orange #FF5F00 accent in
small touches only (60/30/10 rule from the colour-combination reels,
approved 2026-11-21), no gradients; light + dark modes (manual toggle wins over
the system setting; the choice is in-memory and resets on reload).

Pages (hash routes, client-side): Home (`#/home`, animated hero +
live demo), Features (`#/features`), Politeness Theory (`#/theory` —
overview only), About (`#/about`), Extension (`#/extension`), Log in /
Create account (`#/login`).

- `index.html` — page structure and content (all six views)
- `styles.css` — all styling, including the light/dark theme tokens
- `app.js` — router, hero animation, rewrite demo, theme toggle,
  auth preview + password meter (ported from the approved Neumorphism
  preview, `saylient-ai-neumorphism-preview`)
- `config.js` — API base URL (default `http://localhost:8000`)

## Backend connection (the demo is wired to the real API)

The rewrite demo calls the FastAPI backend whenever it is reachable:

- `GET /health` on page load — the status line above the demo shows
  "Connected to the Saylient API · rule-based engine" (or "live LLM …"
  when an LLM key is configured). When the API is down it says
  "Demo mode — API not reachable, using the built-in demo."
- `POST /v1/suggest` on "Polish my reply" — the demo always uses the
  real response (3 replies, score, scenario, source) when the API
  answers; the meta line under the polished reply shows e.g.
  "Score 80/100 · scenario: late_payment · strategy:
  negative_politeness · via rule-based engine".
- `POST /v1/analyze` after a successful suggest — enriches the meta
  line with the detected strategy, face threat and issues. Fire and
  forget; the reply never waits on it.
- If the API stops responding mid-session, the demo falls back to the
  built-in rewrite — never an error state.

## Run it

```bash
# 1. Backend (from the repo root):
cd apps/api && uvicorn app.main:app --reload   # API on http://127.0.0.1:8000
#    (needs the API deps: pip install -r apps/api/requirements.txt)
#    Without an AI key the API still runs — rule-based only.

# 2. Frontend (the demo works standalone too):
python3 -m http.server 5173 --directory apps/web
# open http://localhost:5173

# The page calls the API configured in apps/web/config.js
# (default http://localhost:8000). Override for one session with
# ?api=http://127.0.0.1:8000. CORS: serve this page from
# http://localhost:5173 (an allowed origin), or start the API with
# ALLOWED_ORIGINS set to this page's origin.
```

## Extension tab

`#/extension` explains the browser extension (floating panel,
auto-analyze, never auto-sends) and how to install it. The extension
build (Phase 5) does not exist yet, so the download button is honestly
marked "Coming soon" and disabled — there is no download link until
Phase 5 ships. See `docs/ROADMAP.md`.

## Notes

- Sign-in / sign-up on `#/login` is a design preview only: the
  account endpoints are a later phase, so nothing is submitted.
  The password meter + passphrase generator run fully in the browser.
- No internal stats on the page (no dataset/intent counts) — the
  user asked for a professional landing page without them.
- The theme choice is in-memory only (as in the approved preview),
  and the hero/demo/auth logic is ported verbatim from the preview
  apart from the API wiring and the new Extension view.
