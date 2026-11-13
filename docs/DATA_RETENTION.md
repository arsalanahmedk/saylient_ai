# Data Retention

| Data | Retention | Deletion |
|---|---|---|
| Account (email, hash) | Until account deletion | User-initiated, complete within 24 h |
| Message history (encrypted) | Opt-in; default 30 days | Automatic job + user delete |
| Suggestions not saved | Not stored | Discarded after response |
| Feedback | Until account deletion | Cascade delete |
| Audit log (hashed IP/UA, no content) | 90 days | Automatic job |
| Refresh tokens | Until expiry/revocation | Automatic purge |
| Server logs (content-free) | 14 days | Automatic rotation |
| Backups | 30 days | Rolling expiry |
| Training data from users | Only with explicit opt-in | Removable on request before next training run |

## Rules
- Deletion cascades from `users`.
- Export returns all user-linked data as JSON.
- Retention job runs daily and is covered by tests.
- Changes to this policy are recorded in `CHANGELOG.md`.
