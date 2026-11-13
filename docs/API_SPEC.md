# API Specification (v1)

Base URL: `/v1` | Format: JSON | Auth: `Authorization: Bearer <access_token>` unless noted.
Machine-readable version: `openapi.yaml`.

## Conventions
- Errors: `{"error": {"code": "string", "message": "string"}}`
- Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`
- Max body size: 16 KB. Max text length: 4,000 chars.

## Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | `{email, password}` -> 201, sends verification email |
| POST | `/auth/verify-email` | `{token}` -> 200 |
| POST | `/auth/login` | `{email, password}` -> access token + refresh cookie |
| POST | `/auth/refresh` | rotates refresh token (httpOnly cookie) |
| POST | `/auth/logout` | revokes refresh token |
| POST | `/auth/reset-password` | request/confirm password reset |
| POST | `/auth/extension-token` | short-lived token for the extension |

## Core
**Auto-analyze (2026-11-13):** the extension calls `/analyze` then `/suggest` automatically as soon as its side panel opens, and again (debounced) when a new message appears — no Analyze click needed. The panel being open is the trigger; nothing is called when the panel is closed. There is no auto-send endpoint: no API call ever sends a message on the user's behalf; sending/inserting always needs the user's click.

### POST `/analyze`
Request: `{"text": "string", "goal": "string?"}`
Response:
```json
{"scenario": "late_payment", "face_threat": "high", "detected_strategy": "bald_on_record", "issues": ["too direct"]}
```

### POST `/suggest`
Request:
```json
{"text": "Client hasn't paid for 12 days", "tone": "polite", "goal": "ask for payment", "context": {"relationship": "regular_client"}}
```
Response:
```json
{
  "scenario": "late_payment",
  "strategy": "negative_politeness",
  "replies": [{"tone": "polite", "text": "..."}, {"tone": "friendly", "text": "..."}, {"tone": "firm", "text": "..."}],
  "explanation": "Hedged request reduces imposition while keeping the deadline clear.",
  "score": 91,
  "model_version": "saylient-v0.1",
  "suggestion_id": "uuid"
}
```

## Phased endpoints (not in Phase 0–2)

The endpoints below are part of the v1 spec and are **planned, not
implemented** in this phase. The Phase 0–2 API is deliberately
stateless: no database, no auth — the baseline (rule engine + LLM
adapter) comes first so it can be evaluated on its own. Auth +
PostgreSQL + these endpoints come in the next phase; the live repo
already owns a working auth design to port from. There are **no stub
endpoints** returning fake success — calling one of these paths today
returns 404.

| Method | Path | Status |
|---|---|---|
| POST | `/auth/register`, `/auth/verify-email`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/reset-password`, `/auth/extension-token` | Planned |
| GET | `/history` | Planned (only if history enabled) |
| DELETE | `/history/{id}`, `/history` | Planned |
| GET/PUT | `/settings` (`save_history`, `default_tone`, `language`) | Planned |
| POST | `/feedback` (`{suggestion_id, rating, reason?}`) | Planned |
| GET | `/export` | Planned |
| DELETE | `/account` | Planned |

## User data
*(Planned — see "Phased endpoints" above. Shapes, for the next phase:)*

| Method | Path | Description |
|---|---|---|
| GET | `/history` | list (only if history enabled) |
| DELETE | `/history/{id}` | delete one item |
| DELETE | `/history` | delete all |
| GET/PUT | `/settings` | `save_history`, `default_tone`, `language` |
| POST | `/feedback` | `{suggestion_id, rating, reason?}` |
| GET | `/export` | download all user data |
| DELETE | `/account` | delete account and data |

## System
`GET /health` returns `{"status": "ok"}` (no auth).

## Status codes
200 OK, 201 Created, 400 validation error, 401 unauthenticated, 403 forbidden, 404 not found, 413 payload too large, 429 rate limited, 503 model unavailable.
