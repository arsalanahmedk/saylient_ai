# Data Model (PostgreSQL)

## Tables
### users
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| email | citext unique | |
| password_hash | text | Argon2id |
| email_verified | boolean | default false |
| created_at | timestamptz | |

### refresh_tokens
id, user_id FK, token_hash, device_info, expires_at, revoked_at.

### settings
user_id PK/FK, save_history (default false), default_tone, language, updated_at.

### conversations
id, user_id FK, scenario, created_at.

### suggestions
id, conversation_id FK, input_ciphertext, output_ciphertext, strategy, score, model_version, created_at.
Message text is encrypted at application level with `DATA_ENCRYPTION_KEY`.

### feedback
id, suggestion_id FK, rating (-1/0/1), reason, created_at.

### audit_log
id, user_id, action, ip_hash, user_agent_hash, created_at. No message content.

## Relationships
users 1-N conversations 1-N suggestions 1-N feedback. users 1-1 settings. users 1-N refresh_tokens.

## Rules
- Every query filters by `user_id` (prevents IDOR).
- `ON DELETE CASCADE` from users so account deletion removes all data.
- Retention job deletes history older than the configured period (default 30 days).
- Migrations via Alembic; no manual schema changes in production.
