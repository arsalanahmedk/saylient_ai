# SaylientAI

**Say It Right. Every Time.**

SaylientAI is an AI-based client communication assistant for freelancers. It helps them write polite, clear and professional replies in difficult situations (late payment, deadline negotiation, scope creep, disputes) and explains the linguistic strategy used, based on Brown and Levinson's Politeness Theory (1987).

## Components

| Component | Path | Stack |
|---|---|---|
| Web app | `apps/web` | React / Next.js, TypeScript, Tailwind, Framer Motion |
| Browser extension (side panel) | `apps/extension` | Chrome Manifest V3, React, TypeScript |
| API | `apps/api` | Python, FastAPI, PostgreSQL, Redis |
| LLM (fine-tuned) | `ml/` | PyTorch, Hugging Face, PEFT (QLoRA), vLLM / llama.cpp |
| Shared types | `packages/shared` | TypeScript |
| Docs | `docs/` | Markdown |

## Quick start (development)

**Phase 0–2 status (2026-11-13):** the API baseline and the ML seed work
are done and tested in staging; the web app and the extension are
placeholders (`apps/web/NOTE.md`, `apps/extension/NOTE.md`) until
Phases 4–5. Nothing here is pushed to GitHub yet.

**API contract (Option A, 2026-11-13):** the code follows
`docs/openapi.yaml` exactly — request field `text` (max 4,000 chars),
free-text `goal`, replies as `{tone, text}` objects + `suggestion_id` +
integer `score`, spec analyze shape (`scenario`, `face_threat`,
`detected_strategy`, `issues`), 16 KB body cap, spec strategy enum
(the engine's internal `avoidance` maps to `off_record` at the API
boundary). Auth, history, settings, feedback, export and account
deletion are **planned for a later phase, not implemented** — the API
is stateless in Phase 0–2 (see `docs/API_SPEC.md`, "Phased
endpoints").

```bash
cp .env.example .env          # fill in values, never commit .env
# LLM (optional): set AI_PROVIDER=gemini + AI_API_KEY from Google AI Studio
# (free, no card). Without a key the API still runs — rule-based only.
cd apps/api && pip install -r requirements.txt && uvicorn app.main:app --reload
# API at http://127.0.0.1:8000 — GET /health, POST /v1/suggest, POST /v1/analyze
```

```bash
cd apps/api && pip install -e .[dev] && pytest -v   # 60 tests, incl. golden set 12/12
python -m ml.evaluation.metrics --split --seed 42  # seed evaluation + 80/10/10 splits
```

**Fine-tuning (later, Phase 3):** `ml/training/train_qlora.py` is NOT RUN —
it needs a free Colab T4 and the full reviewed dataset (1,500–4,000
examples; the 60-row seed is a format sample only). See
`ml/training/train_qlora.py` header and `ml/data/README.md`.

**Measured baselines (2026-11-13, seed set, n=60):** rule-based engine —
JSON validity 1.0, strategy macro-F1 0.24 vs seed labels, mean politeness
score 67.0, mean latency 0.7 ms. The low strategy F1 is the honest
baseline the fine-tuned model must beat: the keyword rules default to
`negative_politeness` and rarely predict the other strategies.

## Documentation

Start with `docs/PRD.md`, then `docs/ARCHITECTURE.md`, `docs/SECURITY.md`,
`docs/LLM_CHOICE.md` and `docs/ROADMAP.md`.

## Team

[Team member names, registration numbers] | Supervisor: [Name] | Collaborating department: English Linguistics

## License

MIT, see `LICENSE`.
