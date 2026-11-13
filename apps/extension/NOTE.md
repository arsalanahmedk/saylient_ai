# Browser extension — placeholder (Phase 5)

This folder is intentionally empty in Phase 0–2.

The extension (Chrome Manifest V3, side panel, shortcut, on-demand
content script, client-side PII redaction) is built in **Phase 5** of the
plan (`docs/ROADMAP.md`), after the API and the web app exist. It calls
`POST /v1/suggest` and shows the reply in the side panel — it never
sends messages on its own and never scans pages in the background.

Design and behaviour follow `docs/EXTENSION_SPEC.md` and
`docs/SECURITY.md` (minimal permissions, no broad `<all_urls>` host
permission, tokens in `chrome.storage.session` only). The panel UI will
follow the web app's design language once that exists in Phase 4 — no
generic placeholder UI here.
