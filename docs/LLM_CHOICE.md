# LLM choice (Phase 2 baseline)

**Decision (2026-11-13, for the FYP baseline — not the final model):**
live inference uses a hosted free-tier LLM behind one OpenAI-compatible
adapter (`apps/api/app/services/llm_client.py`); the fine-tuned model is
a separate, later research step. Nothing in this choice is permanent:
if a free tier changes, only the provider config changes, not the API.

## The choice

| Role | Model | Why |
|---|---|---|
| **Primary (live inference)** | Google **Gemini Flash family** — default `gemini-2.5-flash` via Google AI Studio | Most generous free tier of the options considered; **no card required**; speaks the OpenAI-compatible chat-completions API, so the same client code works for every provider. |
| **Fallback** | **Groq** free plan — default `openai/gpt-oss-120b` | Fast inference, OpenAI-compatible endpoint, generous enough as a second free tier when Gemini is unavailable or rate-limited. |
| **Fine-tune (FYP research contribution, later — Phase 3)** | **Qwen2.5-3B-Instruct** with **QLoRA** (4-bit, r=16) on free Colab T4 via Unsloth | Small open model that fits a free T4, instruction-tuned base, permissive licence; fine-tuning it on our own dataset is the actual research contribution. It is **not** used for live inference yet. |

Why not the alternatives: OpenAI/Anthropic free tiers need a card or
paid credits and are much smaller; running a local model for live
inference needs a GPU the project does not have yet; training from
scratch is out of scope for an FYP (plan §2, decision 1).

## Endpoints (OpenAI-compatible chat completions)

- Gemini: `https://generativelanguage.googleapis.com/v1beta/openai/` —
  key from [Google AI Studio](https://aistudio.google.com) (free, no card).
- Groq: `https://api.groq.com/openai/v1` — key from the Groq console
  (free plan).

The adapter sends `response_format: {"type": "json_object"}` and parses
the answer as strict JSON (`scenario`, `strategy`, `replies[]` as
`{tone, text}` objects — exactly 3, distinct tones — `explanation`,
`score`), matching `docs/openapi.yaml` (Option A, 2026-11-13). One
repair retry on invalid JSON, then the rule-based engine answers
instead. HTTP 429 is never retried — the rule engine answers
immediately. Strategies are the spec enum only: the LLM must never
return the engine's internal `avoidance` (validation rejects it);
the API boundary maps engine `avoidance` to `off_record`.

## Free-tier limits (verify before relying on them)

**Free-tier limits change often.** The numbers below are the ones this
decision was made on (Nov 2026); check the provider's own rate-limit
page before a demo, a deadline, or any claim in the FYP report.

- **Gemini (AI Studio free tier):** high request/minute and token/minute
  allowances for the Flash models relative to other free tiers; exact
  RPM/TPM/RPD depend on the model — see
  <https://ai.google.dev/gemini-api/docs/rate-limits>. No card is needed.
- **Groq (free plan, `gpt-oss-120b`):** 30 requests/minute,
  1,000 requests/day, 200,000 tokens/day (as supplied Nov 2026) — see
  <https://console.groq.com/docs/rate-limits>. That is enough for
  development and a demo, not for production traffic.

Design consequences: the API never depends on the LLM being up. Every
`/v1/suggest` response carries `source` (`llm` | `rule_based`) and
`llm_status` (`ok` | `disabled` | `rate_limited` | `invalid_response` |
`blocked_injection` | `error`), so a quota hit is visible, not silent.

## Caveats (read before any real use)

1. **Free-tier data use.** Content sent to a free tier **may be used by
   the provider to improve its products** (Google's AI Studio free-tier
   terms say so explicitly). **Never send real client data, real names,
   real invoices, or anything confidential through the free tier in
   production.** For the FYP, use synthetic / anonymised examples only;
   for production, move to a paid tier with a no-training data policy
   or to the self-hosted fine-tuned model.
2. **Limits change often.** A limit that is true today can halve
   tomorrow. The adapter's fallback exists for exactly this reason.
3. **The hosted LLM is a baseline, not the contribution.** The FYP's
   research claim is the fine-tuned Qwen2.5-3B + politeness-theory
   pipeline beating the prompted baseline (plan §10.3) — not "we called
   an API". Keep the baseline honest: same prompts, same test set.

## Environment variables

```bash
AI_PROVIDER=gemini        # gemini | groq | none (default: none = rule engine only)
AI_API_KEY=               # Google AI Studio key (gemini) or Groq key (groq); never commit
AI_MODEL=gemini-2.5-flash # optional override; defaults: gemini-2.5-flash / openai/gpt-oss-120b
AI_TIMEOUT_SECONDS=20     # per-request timeout; the adapter never blocks longer
```

Without `AI_API_KEY` the API still runs — every suggestion is answered
by the rule-based engine (`prototype-0.1`). See `.env.example`.

## Fine-tuning (later, Phase 3 — not run yet)

- Base: `Qwen/Qwen2.5-3B-Instruct`, QLoRA 4-bit, r=16, alpha=32,
  3 epochs, lr 2e-4, max length 1024 (see `ml/training/train_qlora.py`).
- Runs on a free Colab T4 via Unsloth; the adapter is saved to Drive
  (configurable path) and merged/quantised later (`ml/serving/`).
- Dataset: `ml/data/seed.jsonl` (60 seed examples, 6 per scenario) grows
  to the plan's 1,500–4,000 reviewed examples before any training run
  is claimed as an evaluation result.
