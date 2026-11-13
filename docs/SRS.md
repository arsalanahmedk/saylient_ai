# Software Requirements Specification (SRS)

Version 0.1

## 1. Purpose
Defines functional and non-functional requirements for SaylientAI (web app, extension, API, model service).

## 2. Functional requirements
| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Users can register, verify email, log in, log out, reset password. | Must |
| FR-02 | System accepts a message or situation text (max 4,000 chars). | Must |
| FR-03 | System detects scenario type and face-threat level. | Must |
| FR-04 | System returns 3 reply options with selected tone. | Must |
| FR-05 | Each response includes strategy label, explanation, politeness score. | Must |
| FR-06 | Users can copy, regenerate and rate suggestions. | Must |
| FR-07 | Extension opens side panel via keyboard shortcut. | Must |
| FR-08 | Extension auto-analyzes the screen/conversation itself: when the side panel opens it extracts selected/visible conversation text automatically (no Analyze click), decides scenario/intent itself, and auto-suggests replies; re-analyzes (debounced) when a new message appears, only while the panel is open. | Must |
| FR-09 | Extension redacts PII client-side before sending. | Must |
| FR-10 | Users can opt in to history, view and delete it. | Must |
| FR-11 | Users can export and delete all their data. | Must |
| FR-12 | Templates library for common scenarios. | Should |
| FR-13 | Insert suggested reply into compose box after confirmation. | Should |
| FR-15 | Auto-suggest only — never auto-send, never auto-insert: no reply is sent or inserted without the user's click. | Must |
| FR-14 | Usage dashboard. | Could |

> Change 2026-11-13 (user requirement, "aik AI ho jo khud analyze kara or suggest kara"): FR-08 changed from "extracts on user trigger" to auto-analyze + auto-suggest while the side panel is open; FR-15 added (never auto-send / never auto-insert). The old "read page text only after explicit user trigger" rule is superseded — the panel being open is now the trigger.

## 3. Non-functional requirements
**Performance:** p95 suggestion latency <= 3 s (GPU) or 5 s (CPU demo). Side panel opens in < 1 s.
**Availability:** 99% during evaluation period; graceful message if model is down.
**Security:** see `SECURITY.md` (auth, encryption, rate limiting, prompt-injection defence).
**Privacy:** see `PRIVACY_POLICY.md`; history opt-in; data deletion within 24 h of request.
**Usability:** WCAG 2.1 AA, responsive 360-1440+ px, keyboard navigable.
**Maintainability:** typed code, >= 70% unit test coverage on services, CI on every PR.
**Compatibility:** latest Chrome/Edge (Manifest V3), modern browsers for web app.
**Scalability:** stateless API, horizontal scaling, model server isolated.

## 4. Constraints
- FYP timeline (about 16 weeks), limited GPU budget.
- Model must be fine-tuned from an open-weights base, no training from scratch.
- No real client data in training sets.

## 5. External interfaces
- Web app <-> API: HTTPS JSON REST.
- Extension <-> API: HTTPS JSON with short-lived bearer token.
- API <-> Inference service: internal HTTP with service token.
- Email provider for verification/reset (SMTP).

## 6. Traceability
Each FR maps to test cases in `TEST_PLAN.md` (e.g. FR-05 -> API contract test `test_suggest_schema`).
