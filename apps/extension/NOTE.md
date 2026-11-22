# Browser extension — built (Phase 5)

See `README.md` in this folder. The extension (Chrome Manifest V3,
side panel, shortcut, listener-only content script, client-side PII
redaction) is built here; it calls `POST /v1/analyze` then
`POST /v1/suggest` and never sends or inserts messages on its own.
It works without sign-in. Load it unpacked from this folder, or use
`dist/saylient-extension.zip` (built by `tools/package.py`).
