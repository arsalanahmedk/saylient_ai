# Architecture

## 1. Overview
```
[Chrome Extension]          [Web App]
 content script              dashboard, history,
 side panel (React)          settings, templates
        \                        /
         \--- HTTPS + JWT -------/
                   |
           [FastAPI API Gateway]
   auth | rate limit | validation | PII redaction | guardrails
                   |
     +-------------+--------------+
     |             |              |
 [PostgreSQL]    [Redis]   [Inference Service]
 users, history  rate      fine-tuned LLM + politeness
 feedback        limits    rules engine (private network)
```

## 2. Components
- **Web app** (`apps/web`): React/Next.js + TypeScript. Landing, auth, compose, history, settings, templates.
- **Extension** (`apps/extension`): Manifest V3. Service worker (shortcut handling), on-demand content script (text extraction), side panel UI.
- **API** (`apps/api`): FastAPI. Auth, validation, rate limiting, orchestration, persistence.
- **Inference service** (`ml/serving`): hosts the fine-tuned model (vLLM or llama.cpp) and the politeness rules engine. Reachable only from the API.
- **PostgreSQL:** users, sessions, conversations, suggestions (encrypted), feedback, audit log.
- **Redis:** rate limits, short-lived caches.

## 3. Request flow (extension)
1. User presses shortcut; service worker opens side panel.
2. Content script extracts selected/visible text on that tab only.
3. Panel redacts PII locally, then `POST /v1/suggest` with bearer token.
4. API verifies token, rate limits, validates schema, applies input guardrails.
5. API calls inference service (internal token).
6. Model returns structured JSON (scenario, strategy, replies, explanation).
7. Politeness engine computes score; API validates output schema and filters unsafe content.
8. Panel renders results; history saved only if user opted in (encrypted).

## 4. Theory-guided pipeline
Scenario + FTA analysis (distance, power, imposition) -> strategy selection (bald on-record, positive, negative, off-record) -> generation -> explanation -> scoring.

## 5. Key decisions
| Decision | Rationale |
|---|---|
| Fine-tune small open model (QLoRA) | Feasible on free GPUs, owns the dataset contribution |
| DOM text instead of screenshots in MVP | Faster, cheaper, more private |
| Chrome Side Panel API | Same-tab experience, no new tab |
| Model server on private network | Reduces attack surface |
| History opt-in + encryption | Privacy by design |

## 6. Deployment topology
Web on Vercel; API container on Render/Railway/VPS; inference service on a GPU host or CPU VPS with GGUF; managed PostgreSQL and Redis. See `DEPLOYMENT.md`.

## 7. Observability
Health endpoints, structured logs (no content), error tracking with scrubbing, latency and token metrics.
