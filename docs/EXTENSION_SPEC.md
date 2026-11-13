# Extension Specification (Chrome, Manifest V3)

## 1. Purpose
Let freelancers get reply suggestions from any conversation page with one shortcut, in a side panel, without opening a new tab.

## 2. Manifest essentials
```json
{
  "manifest_version": 3,
  "name": "SaylientAI",
  "version": "0.1.0",
  "permissions": ["activeTab", "scripting", "sidePanel", "storage", "identity"],
  "host_permissions": ["https://api.saylient.example/*"],
  "background": {"service_worker": "background.js", "type": "module"},
  "side_panel": {"default_path": "sidepanel.html"},
  "commands": {
    "open-saylient": {
      "suggested_key": {"default": "Ctrl+Shift+S", "mac": "Command+Shift+S"},
      "description": "Open SaylientAI side panel"
    }
  },
  "action": {"default_title": "SaylientAI"},
  "content_security_policy": {"extension_pages": "script-src 'self'; object-src 'self'"}
}
```
No `<all_urls>`. Backend domain only.

## 3. Behavior
1. Shortcut (or toolbar click) -> service worker calls `chrome.sidePanel.open()` (requires user gesture).
2. **Auto-analyze (requirement, 2026-11-13 — "aik AI ho jo khud analyze kara or suggest kara"):** as soon as the side panel opens, the panel automatically asks the service worker to inject the extractor into the active tab via `chrome.scripting.executeScript` — no click on Analyze is needed to start. The extractor returns, in priority order: user text selection, else the last N messages in known chat containers (Gmail, LinkedIn, Upwork, Fiverr, WhatsApp Web), else visible text.
3. The panel decides the condition/intent itself from the extracted text (via `POST /v1/analyze`: scenario + face-threat + strategy) and immediately calls `POST /v1/suggest` — suggestions appear automatically.
4. **Auto re-analyze while the panel is open:** when a new message appears in the conversation, the panel re-analyzes automatically (debounced, only if the text changed, at most one call per few seconds). Auto-analysis runs ONLY while the side panel is open on that tab — never in the background, never on page load, never when the panel is closed.
5. Panel shows the extracted text (editable) with a "Clear" button, a "Pause auto-analyze" toggle, and a note: "This text was sent to SaylientAI automatically".
6. Redactor masks emails, phones, card/IBAN, CNIC patterns locally before anything is sent.
7. Panel renders tone chips, 3 reply cards, explanation, score.
8. Actions: Copy, Insert into compose box (confirm first), Regenerate, Feedback. **Auto-suggest only — never auto-send, never auto-insert:** no reply is ever sent or inserted without the user's click (see §5).

## 4. Authentication
`chrome.identity.launchWebAuthFlow` against the web app login; short-lived access token stored in `chrome.storage.session`. Refresh via the web session; no long-lived secrets in the extension.

## 5. Rules
- Auto-analysis runs only while the side panel is open. Never read page text in the background, on page load, or when the panel is closed. (Changed 2026-11-13: previously "only after an explicit user trigger" — the panel being open is now the trigger; no Analyze click is needed.)
- Skip `input[type=password]`, payment fields and hidden elements.
- Render extracted text with `textContent`.
- No remote code, no eval.
- **Never auto-send, never auto-insert.** Copy needs a click; Insert needs a click + confirmation. There is no endpoint or code path that sends a message on the user's behalf.
- Handle failures: offline, 401 (re-login), 429 (cool-down message + auto-pause), 503 (model unavailable).

## 6. Performance
Side panel opens < 1 s; extraction < 300 ms; show skeleton while generating.

## 7. Publishing
Developer-mode package for evaluation; unlisted Chrome Web Store listing later. Provide a privacy disclosure and single-purpose description.
