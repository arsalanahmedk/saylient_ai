# Deployment and DevOps

## 1. Environments
| Env | Purpose | Notes |
|---|---|---|
| dev | local | `docker-compose` (PostgreSQL, Redis, API, mock LLM) |
| staging | pre-release testing | auto-deploy from `main`, synthetic data only |
| prod | live demo/evaluation | deploy on version tag, manual approval |

## 2. Hosting plan
- **Web app:** Vercel.
- **API:** Docker container on Render / Railway / VPS.
- **Inference service:** GPU host (vLLM) or CPU VPS (llama.cpp + GGUF). Private network or firewall allowing only the API.
- **Database:** managed PostgreSQL (encrypted at rest, daily backups). **Redis:** managed or container.

## 3. CI (GitHub Actions)
On every PR: lint (ruff, eslint), type check (mypy, tsc), unit + integration tests, `pip-audit`, `npm audit`, CodeQL, secret scan.

## 4. CD
1. Merge to `main` -> build images -> deploy staging -> smoke tests.
2. Tag `vX.Y.Z` -> manual approval -> deploy prod -> post-deploy health check.
3. Rollback: redeploy previous image tag; DB migrations must be backward compatible.

## 5. Configuration and secrets
- Config via environment variables; see `.env.example`.
- Secrets in the host's secret manager (never in git, never in images).
- Rotate `APP_SECRET_KEY`, `DATA_ENCRYPTION_KEY` and service tokens on a schedule and after any incident.

## 6. Observability
- `/health` endpoint, uptime monitor.
- Structured JSON logs without message content.
- Sentry with data scrubbing; metrics for latency, error rate, token usage, rate-limit hits.

## 7. Backups and recovery
Daily encrypted DB backups, 30-day retention, restore drill monthly. RPO 24 h, RTO 4 h.

## 8. Release checklist
- [ ] Security checklist (`SECURITY.md`) complete
- [ ] Migrations tested on staging copy
- [ ] Model version recorded and smoke-tested
- [ ] `CHANGELOG.md` updated
- [ ] Rollback plan confirmed

## 9. Extension release
Build with `npm run build`, zip `dist/`, load unpacked for evaluation; unlisted Chrome Web Store listing for wider testing.
