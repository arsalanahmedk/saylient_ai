"""CPU smoke test for the Saylient v2 training pipeline (no GPU needed).

Proves the pipeline is not broken before anyone spends Colab GPU time:

1. loads ``ml/data/splits_v2/train.jsonl`` and validates the v2 schema;
2. renders training texts with ``ml/training/train_qlora_v2.to_chat_text``
   and tokenizes a batch with the **Qwen/Qwen2.5-1.5B-Instruct** tokenizer;
3. loads the 1.5B base model on CPU (bfloat16) and runs one forward pass;
4. optionally runs a few LoRA training steps on a tiny subset
   (``--steps N``, default 1) to prove the optimizer path works.

Run::

    python ml/training/smoke_test_cpu.py [--steps 3] [--max_len 256]

Expected on this VM (1.5 shared CPUs, 6 GB RAM): tokenizer + data
validation in seconds; model download ~3 GB once (cached in
``~/.cache/huggingface``); one forward pass (batch 1, seq <= 256) in
~1-3 minutes; each LoRA training step a few minutes. If the 1.5B
forward pass is too slow or OOMs here, that does NOT block Colab
training (T4 GPU) — it only limits what this CPU box can prove.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REQUIRED_FIELDS = (
    "input", "intent", "tone", "strategy", "sentiment", "formality",
    "face_threat_level", "relationship", "polite_rewrite", "explanation",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="CPU smoke test (Qwen2.5-1.5B, v2 data).")
    parser.add_argument("--train", type=pathlib.Path,
                        default=ROOT / "ml" / "data" / "splits_v2" / "train.jsonl")
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--max_len", type=int, default=256)
    parser.add_argument("--steps", type=int, default=1,
                        help="LoRA training steps on a tiny subset (0 = forward pass only)")
    parser.add_argument("--batch", type=int, default=1)
    args = parser.parse_args()

    t0 = time.perf_counter()
    rows = [json.loads(line) for line in args.train.open(encoding="utf-8") if line.strip()]
    bad = [i for i, r in enumerate(rows) if any(k not in r for k in REQUIRED_FIELDS)]
    assert not bad, f"rows missing required fields: {bad[:5]}"
    print(f"[1] Loaded {len(rows)} train rows from {args.train} "
          f"({time.perf_counter() - t0:.1f}s); schema OK, 0 bad rows")

    from ml.training.train_qlora_v2 import to_chat_text  # noqa: E402

    import torch  # noqa: E402
    from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

    t0 = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    texts = [to_chat_text(r, tokenizer) for r in rows[:args.batch]]
    enc = tokenizer(texts, return_tensors="pt", padding=True,
                    truncation=True, max_length=args.max_len)
    print(f"[2] Tokenizer {args.model}: batch of {args.batch} -> "
          f"input_ids {tuple(enc['input_ids'].shape)} "
          f"({time.perf_counter() - t0:.1f}s)")
    print(f"    Example (first 300 chars):\n{texts[0][:300]}")

    t0 = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16)
    model.eval()
    print(f"[3] Model loaded on CPU, bf16 ({time.perf_counter() - t0:.1f}s); "
          f"params: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B")

    labels = enc["input_ids"].clone()
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model(input_ids=enc["input_ids"],
                    attention_mask=enc["attention_mask"], labels=labels)
    print(f"[4] Forward pass: loss={out.loss.item():.4f} "
          f"({time.perf_counter() - t0:.1f}s)")

    if args.steps > 0:
        from peft import LoraConfig, get_peft_model  # noqa: E402
        peft_config = LoraConfig(
            r=8, lora_alpha=16, lora_dropout=0.0, bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
        )
        model = get_peft_model(model, peft_config)
        model.train()
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"[5] LoRA attached (r=8): trainable params {trainable / 1e6:.1f}M")
        opt = torch.optim.AdamW(
            (p for p in model.parameters() if p.requires_grad), lr=2e-4)
        subset = rows[:4]
        subset_texts = [to_chat_text(r, tokenizer) for r in subset]
        for step in range(args.steps):
            t0 = time.perf_counter()
            batch = tokenizer(subset_texts, return_tensors="pt", padding=True,
                              truncation=True, max_length=args.max_len)
            batch_labels = batch["input_ids"].clone()
            out = model(input_ids=batch["input_ids"],
                        attention_mask=batch["attention_mask"],
                        labels=batch_labels)
            out.loss.backward()
            opt.step()
            opt.zero_grad()
            print(f"    step {step + 1}/{args.steps}: loss={out.loss.item():.4f} "
                  f"({time.perf_counter() - t0:.1f}s)")
        print("[6] Training-step path works (loss computed, optimizer stepped).")
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
