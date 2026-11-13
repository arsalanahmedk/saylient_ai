# ML Plan

## 1. Objective
Fine-tune a small open-weights LLM to produce polite, context-appropriate freelancer replies with a Politeness Theory strategy label and short explanation, outperforming a generic prompted baseline.

## 2. Model
- Candidates: Qwen2.5-3B-Instruct (preferred), Qwen2.5-1.5B-Instruct (low GPU), Llama 3.2 3B, Gemma 2B.
- No training from scratch.

## 3. Training
- Method: QLoRA (4-bit), r=16, alpha=32, dropout 0.05.
- Epochs 3, lr 2e-4, cosine schedule, max sequence 1024, batch via gradient accumulation.
- Libraries: transformers, peft, trl, bitsandbytes, datasets.
- Hardware: Colab/Kaggle T4 (free) for 1.5B-3B.
- Tracking: Weights & Biases or MLflow. Seeds fixed and logged.
- Output: LoRA adapter, merged model, GGUF quantized (Q4_K_M) for CPU serving.

## 4. Output contract
Model must return strict JSON:
```json
{"scenario": "...", "strategy": "...", "replies": [{"tone": "...", "text": "..."}], "explanation": "..."}
```
Invalid JSON is retried once, then returns a safe fallback error.

## 5. Experiments
| ID | System |
|---|---|
| B1 | Generic prompted open LLM |
| B2 | Prompted LLM + rule-based politeness engine |
| M1 | Fine-tuned model (ours) |
| M2 | Fine-tuned + rules engine scoring (final system) |

## 6. Evaluation
See `EVALUATION_PLAN.md`. Test split is never used in training or prompt tuning.

## 7. Serving
- vLLM (GPU) or llama.cpp server (CPU).
- Private network only, service token auth, max tokens 400, timeout 20 s, concurrency limit.

## 8. Versioning
`saylient-v0.1`, `v0.2`, ... Dataset version recorded with each model. API returns `model_version`.

## 9. Risks
Small dataset (mitigate with quality review), hallucinated facts (never invent amounts/dates), tone drift (guardrails + evaluation).
