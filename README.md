![Saylient AI — Say It Right. Every Time.](.github/assets/banner.png)

<p align="center">
  <a href="https://github.com/arsalanahmedk/saylient_ai/actions/workflows/ci.yml"><img src="https://github.com/arsalanahmedk/saylient_ai/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11-blue?logo=python&logoColor=white" alt="Python 3.11">
  <img src="https://img.shields.io/badge/FastAPI-0.1xx-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/dataset-99%2C990%20rows-8B5CF6" alt="Dataset: 99,990 rows">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT">
</p>

<h3 align="center">Say It Right. Every Time.</h3>

<p align="center">
Saylient AI is an AI assistant for freelancers that rewrites difficult client
messages — late payments, deadline talks, scope creep, disputes — into polite,
clear and professional replies, and explains <i>why</i> the rewrite works,
using Brown &amp; Levinson's Politeness Theory (1987).
</p>

---

## ✨ See it in action

**You write:**

> "You still haven't paid invoice #1048. Pay now."

**Saylient suggests** (scenario: `late_payment`, strategy: `negative_politeness`, score: 80/100):

| Tone | Reply |
|---|---|
| 😊 Polite | "Hi! Just a friendly reminder that invoice #1048 is still pending. Could you please let me know when it will be processed? Thank you!" |
| 🤝 Friendly | "Hey! Hope you're doing well — quick nudge on invoice #1048. Whenever you get a chance to send the payment, I'd really appreciate it." |
| 💼 Firm | "Hi, following up on invoice #1048, which is now overdue. Please arrange payment at your earliest convenience so we can keep the project on track." |

Every suggestion also explains the strategy it used — so you learn the skill, not just copy the text.

## 🚀 What it does

- **3 tones, 1 click** — polite, friendly and firm rewrites for any tricky message
- **Knows the situation** — detects the scenario (late payment, scope creep, rude client…) and the face-threat level
- **Explains itself** — every reply comes with the politeness strategy behind it
- **Auto-analyze (planned)** — the extension will read the conversation and suggest replies by itself. It **never** sends anything without your click
- **Works offline too** — a rule-based engine answers instantly when no LLM is available

## 🧠 How it works

```mermaid
flowchart LR
    A["Your message"] --> B["POST /v1/suggest"]
    B --> C{"LLM available?"}
    C -->|"Yes: Gemini Flash / Groq"| D["LLM adapter"]
    C -->|"No / quota hit"| E["Rule-based engine"]
    D --> F["3 replies + score + explanation"]
    E --> F
```

- **Live inference:** Google Gemini Flash (primary, free tier) with Groq `gpt-oss-120b` as fallback — one OpenAI-compatible adapter, no vendor lock-in. See [`docs/LLM_CHOICE.md`](docs/LLM_CHOICE.md).
- **Fine-tuned model (the research):** Qwen2.5-3B-Instruct + QLoRA, trained on our own politeness dataset — the FYP contribution. See [`ml/training/train_qlora.py`](ml/training/train_qlora.py).
- **Always honest fallback:** if the LLM is down or rate-limited, the rule engine answers and the response says so (`source: rule_based`, `llm_status`).

## 🗃️ The dataset — 99,990 rows

| Split | Rows | Per intent |
|---|---:|---:|
| Train | 84,986 | 7,727 |
| Validation | 7,502 | 682 |
| Test | 7,502 | 682 |
| **Total** | **99,990** | **9,090** |

10 scenarios × 11 intents, built from 700 hand-written seeds + 165 templates.
Keyword baseline on the full test set (the bar the fine-tuned model must beat):
intent F1 **0.392**, strategy F1 **0.447**. See [`ml/data/README.md`](ml/data/README.md).

## ⚡ Quick start

```bash
cp .env.example .env          # fill in values, never commit .env
# LLM (optional): set AI_PROVIDER=gemini + AI_API_KEY from Google AI Studio (free, no card)
# Without a key the API still runs — rule-based only.
cd apps/api && pip install -r requirements.txt && uvicorn app.main:app --reload
# API at http://127.0.0.1:8000 — GET /health, POST /v1/suggest, POST /v1/analyze
```

```bash
cd apps/api && pip install -e .[dev] && pytest -q   # 60 tests, incl. golden set 12/12
```

```bash
# Try it
curl -X POST http://127.0.0.1:8000/v1/suggest \
  -H "Content-Type: application/json" \
  -d '{"text": "You still haven'"'"'t paid invoice #1048. Pay now."}'
```

**API contract:** request field `text` (max 4,000 chars), optional free-text `goal`;
replies are `{tone, text}` objects + `suggestion_id` + integer `score`; 16 KB body
cap. Auth, history, settings, feedback, export and account deletion are
**planned for a later phase, not implemented** — the API is stateless for now.
Full spec: [`docs/API_SPEC.md`](docs/API_SPEC.md) and [`docs/openapi.yaml`](docs/openapi.yaml).

## 📁 Project structure

```
saylient_ai/
├── apps/
│   ├── api/            # FastAPI backend — rule engine, LLM adapter, tests (CI ✅)
│   ├── web/            # Web app — placeholder until Phase 4
│   └── extension/      # Chrome extension (side panel) — placeholder until Phase 5
├── docs/               # PRD, SRS, architecture, security, API spec, roadmap
├── ml/
│   ├── data/           # Dataset v3 — 99,990 rows + generator + splits
│   ├── evaluation/     # Metrics + baselines
│   └── training/       # QLoRA training script + Colab notebook
└── packages/shared/    # Shared types (later)
```

## 🗺️ Roadmap

- [x] **Phase 0–2** — API baseline, rule engine, LLM adapter, seed dataset, CI
- [x] **Dataset v3** — 99,990 rows, baselines measured
- [ ] **Phase 3** — Fine-tune Qwen2.5-3B (QLoRA) on Colab T4 — *waiting on GPU*
- [ ] **Phase 4** — Web app (React + Tailwind)
- [ ] **Phase 5** — Chrome extension with auto-analyze + auto-suggest (never auto-send)

## 📚 Documentation

Start with [`docs/PRD.md`](docs/PRD.md), then
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/SECURITY.md`](docs/SECURITY.md),
[`docs/LLM_CHOICE.md`](docs/LLM_CHOICE.md) and
[`docs/ROADMAP.md`](docs/ROADMAP.md).

## 👥 Team

[Team member names, registration numbers] | Supervisor: [Name] | Collaborating department: English Linguistics

## 📄 License

MIT, see [`LICENSE`](LICENSE).
