# Saylient AI API (Phase 0–2)

FastAPI service: rule-based politeness baseline (`prototype-0.1`, ported
from the live repo `arsalanahmedk/saylient-ai`) + an LLM provider adapter
(Gemini primary, Groq fallback) that always degrades gracefully to the
rule engine. Stateless in this phase — no database, no auth; those come
from the live repo's design in a later phase.

## Endpoints

| Route | What it does |
|---|---|
| `GET /health` | Liveness + whether an LLM is configured (never the key). |
| `POST /v1/analyze` | Rule-engine-only analysis: spec fields (`scenario`, `face_threat`, `detected_strategy`, `issues`) + engine detail. Request: `{"text": "...", "goal": "...?"}`. |
| `POST /v1/suggest` | LLM-first suggestion (`source: llm`); on any LLM failure — no key, 429, timeout, invalid JSON, blocked injection — the rule engine answers instead (`source: rule_based`, `llm_status` says why). Request field is `text` (max 4,000), `goal` a free string; replies are `{tone, text}` objects + `suggestion_id` + integer `score` (see `docs/openapi.yaml`). Auth/history/settings/feedback/export/account are planned for a later phase, not implemented. |

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../../.env.example ../../.env   # optional: set AI_PROVIDER / AI_API_KEY
uvicorn app.main:app --reload --port 8000
```

Without `AI_API_KEY` the API still runs and every suggestion is
rule-based. With a key, set `AI_PROVIDER=gemini` (Google AI Studio,
free tier) or `AI_PROVIDER=groq`. See `../../docs/LLM_CHOICE.md`.

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/v1/suggest \
  -H 'Content-Type: application/json' \
  -d '{"text": "The invoice #1048 is two weeks overdue. When will I be paid?", "goal": "ask for my payment"}'
```

## Tests

```bash
pip install -e .[dev]   # or: pip install pytest httpx
pytest -v
```

Tests cover the golden set (12/12 intent + strategy, ported from the
live repo's `eval/golden.json`), the LLM fallback paths (no key, 429,
invalid JSON retry, injection guardrail) and the HTTP endpoints.
