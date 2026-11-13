# Risk Register

Scale: Likelihood (L) and Impact (I): 1 low to 5 high. Score = L x I.

| ID | Risk | L | I | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|
| R1 | Not enough GPU/compute for fine-tuning | 3 | 4 | 12 | Use 1.5B-3B model, QLoRA, free Colab/Kaggle, GGUF for CPU serving | [ML lead] |
| R2 | Dataset too small or low quality | 3 | 5 | 15 | Linguist review, kappa checks, synthetic + human mix, iterate on errors | [Data lead] |
| R3 | Latency too high for a smooth extension | 3 | 3 | 9 | Quantization, max token limit, caching, skeleton UI | [Backend lead] |
| R4 | Privacy complaint or leak of client messages | 2 | 5 | 10 | Opt-in history, redaction, encryption, content-free logs | [Security lead] |
| R5 | Prompt injection via page text | 3 | 4 | 12 | Data/instruction separation, schema validation, test suite | [Security lead] |
| R6 | Scope creep (vision, mobile, more languages) | 4 | 3 | 12 | MVP freeze, v2 backlog | [Team lead] |
| R7 | Offensive or wrong model output | 3 | 4 | 12 | Guardrails, user review before send, feedback loop | [ML lead] |
| R8 | Extension breaks on site layout changes | 4 | 2 | 8 | Fallback to selection/visible text, per-site extractors with tests | [Extension lead] |
| R9 | Team member unavailable / workload | 3 | 3 | 9 | Clear ownership, weekly sync, documentation | [Team lead] |
| R10 | Linguistics collaboration delays | 3 | 3 | 9 | Fixed review dates, shared taxonomy early | [Team lead] |
| R11 | Hosting cost overruns | 2 | 3 | 6 | Free tiers, CPU demo, usage quotas | [DevOps lead] |
| R12 | Evaluation participants hard to recruit | 3 | 3 | 9 | Start recruiting early, use freelancer communities | [Team lead] |

## Process
Review weekly; update status, add new risks, close mitigated ones.
