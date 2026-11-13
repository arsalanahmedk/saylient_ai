"""Evaluation metrics for Saylient AI (Phase 2).

Runnable against the seed set with the rule-based engine — no GPU, no
LLM key, no training needed:

    python -m ml.evaluation.metrics                 # report on ml/data/seed.jsonl
    python -m ml.evaluation.metrics --split --seed 42   # write ml/data/splits/

Metrics (plan §10.3, docs/EVALUATION_PLAN.md):

- **JSON validity rate** — share of model outputs that parse as JSON
  and match the contract (scenario / strategy / replies / explanation /
  score). The rule engine scores 1.0 by construction; the LLM path is
  measured the same way in the API tests.
- **Strategy F1** — macro-F1 of the predicted strategy vs the seed
  labels (per-strategy precision/recall/F1, then the mean). The
  rule-based engine has no learned strategy classifier, so this measures
  how well the *engine's* strategy rules agree with the seed labels —
  the baseline the fine-tuned model must beat.
- **Rule-based politeness score** — mean score of the replies on the
  same 0-100 lexical scale the API returns (hedges, gratitude,
  indirectness minus directness markers). Self-contained copy of the
  scorer in ``apps/api/app/services/politeness.py`` so this module runs
  without the API on ``sys.path``.
- **Latency** — mean / p95 seconds per example for the system under
  test (here: the rule engine, which is sub-millisecond; the number is
  reported so the fine-tuned / LLM numbers are comparable later).

A ``--predictions`` JSONL file (one ``{"scenario": ..., "strategy": ...,
"replies": [...], "explanation": ..., "score": ...}`` per line, in the
same order as the seed file) can be passed to score *any* system —
fine-tuned model, prompted LLM, or a new engine — on the same metrics.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys
import time
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "ml" / "data" / "seed.jsonl"
SPLITS_DIR = ROOT / "ml" / "data" / "splits"

STRATEGIES = (
    "bald_on_record",
    "positive_politeness",
    "negative_politeness",
    "off_record",
    "avoidance",
)

# --- rule-based politeness score (mirror of apps/api/app/services/politeness.py)
_HEDGES = (
    "could you", "would you", "would it be possible", "could we",
    "would it be ok", "is it possible", "perhaps", "maybe", "just",
    "a little", "a bit", "whenever you have a moment",
    "if you don't mind", "i was wondering", "i wanted to check", "happy to",
)
_GRATITUDE = ("thank", "thanks", "appreciate", "grateful")
_INDIRECTNESS = ("?", "could", "would", "might", "may i", "let me know", "please let me know")
_SOFTENERS = ("sorry", "apolog", "i understand", "no worries", "of course", "absolutely")
_DIRECTNESS = ("must", "need to", "you have to", "asap", "immediately", "right now", "do it now", "urgent", "!!!")


def politeness_score(reply: str) -> float:
    """Lexical politeness score, 0-100 (see apps/api/.../politeness.py)."""
    if not reply or not reply.strip():
        return 0.0
    text = reply.strip()
    lowered = text.lower()

    def count(phrases: tuple[str, ...]) -> int:
        return sum(1 for phrase in phrases if phrase in lowered)

    score = 45.0
    score += count(_HEDGES) * 6.0
    score += count(_GRATITUDE) * 8.0
    score += count(_INDIRECTNESS) * 3.0
    score += count(_SOFTENERS) * 5.0
    score -= count(_DIRECTNESS) * 7.0
    words = len(re.findall(r"\b\w+\b", text))
    if words >= 25:
        score += 3.0
    elif words <= 6:
        score -= 5.0
    return round(max(0.0, min(100.0, score)), 1)


# --- loading -------------------------------------------------------------
def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def _reply_text(reply) -> str | None:
    """Extract the text of one reply — a plain string or a spec
    ``{tone, text}`` object (openapi.yaml, Option A)."""
    if isinstance(reply, str):
        return reply
    if isinstance(reply, dict) and isinstance(reply.get("text"), str):
        return reply["text"]
    return None


def validate_predictions(rows: list[dict]) -> tuple[list[dict], list[int]]:
    """Return (valid_rows, invalid_row_indices) against the LLM contract."""
    valid, invalid = [], []
    for index, row in enumerate(rows):
        replies = row.get("replies")
        reply_texts = (
            [_reply_text(r) for r in replies]
            if isinstance(replies, list)
            else []
        )
        ok = (
            isinstance(row, dict)
            and row.get("scenario") in {
                "late_payment", "deadline_extension", "scope_creep",
                "revision_limit", "low-budget_offer", "ghosting_follow_up",
                "rude_client", "refund_demand", "boundary_setting",
                "compliment_negotiation",
            }
            and row.get("strategy") in STRATEGIES
            and isinstance(replies, list)
            and 1 <= len(replies) <= 3
            and all(t is not None and t.strip() for t in reply_texts)
            and isinstance(row.get("explanation"), str)
            and row.get("explanation", "").strip()
            and isinstance(row.get("score"), (int, float))
            and 0 <= row["score"] <= 100
        )
        (valid if ok else invalid).append(row if ok else index)
    return valid, invalid


def strategy_f1(expected: list[str], predicted: list[str]) -> dict:
    """Macro-F1 + per-strategy precision/recall/F1."""
    labels = sorted(set(expected) | set(predicted))
    per_label: dict[str, dict[str, float]] = {}
    f1s = []
    for label in labels:
        tp = sum(1 for e, p in zip(expected, predicted) if e == p == label)
        fp = sum(1 for e, p in zip(expected, predicted) if e != label and p == label)
        fn = sum(1 for e, p in zip(expected, predicted) if e == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": sum(1 for e in expected if e == label),
        }
        f1s.append(f1)
    return {
        "macro_f1": round(sum(f1s) / len(f1s), 3) if f1s else 0.0,
        "per_strategy": per_label,
    }


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(pct / 100 * len(ordered)) - 1))
    return round(ordered[index], 3)


# --- the rule-engine baseline -------------------------------------------
def rule_engine_predictions(seed_rows: list[dict]) -> tuple[list[dict], list[float]]:
    """Run the ported rule engine over the seed rows (imported from the API)."""
    sys.path.insert(0, str(ROOT / "apps" / "api"))
    from app.services import analysis_engine  # noqa: E402
    from app.services.politeness import politeness_score as api_score  # noqa: E402

    goal_map = {
        "late_payment": "request_payment",
        "deadline_extension": "negotiate_deadline",
        "scope_creep": "set_boundary",
        "revision_limit": "set_boundary",
        "low-budget_offer": "negotiate_budget",
        "ghosting_follow_up": "request_payment",
        "rude_client": "respond_to_criticism",
        "refund_demand": "negotiate_budget",
        "boundary_setting": "set_boundary",
        "compliment_negotiation": "resolve_disagreement",
    }
    predictions, latencies = [], []
    for row in seed_rows:
        started = time.perf_counter()
        result = analysis_engine.analyze(
            row["input"],
            goal_map[row["scenario"]],
            {
                "power": "unknown",
                "social_distance": (
                    "low" if row["context"]["relationship"] == "long_term_client"
                    else "medium"
                ),
                "imposition": row["context"]["imposition"],
            },
        )
        latencies.append(time.perf_counter() - started)
        predictions.append(
            {
                "scenario": row["scenario"],
                "strategy": result["strategy"]["label"],
                "replies": [result["draft"]],
                "explanation": result["strategy"]["rationale"],
                "score": api_score(result["draft"]),
            }
        )
    return predictions, latencies


def evaluate(seed_rows: list[dict], predictions: list[dict], latencies: list[float]) -> dict:
    valid, invalid_idx = validate_predictions(predictions)
    json_validity = len(valid) / len(predictions) if predictions else 0.0
    # Strategy F1 is computed on the valid rows only; invalid rows count
    # as wrong (they produced no usable strategy).
    expected = [row["strategy"] for row in seed_rows]
    predicted = [
        predictions[i]["strategy"] if i not in set(invalid_idx) else "__invalid__"
        for i in range(len(seed_rows))
    ]
    f1 = strategy_f1(expected, predicted)
    reply_scores = [
        politeness_score(_reply_text(pred["replies"][0]) or "") for pred in valid
    ]
    return {
        "n": len(seed_rows),
        "json_validity_rate": round(json_validity, 3),
        "invalid_rows": invalid_idx,
        "strategy_macro_f1": f1["macro_f1"],
        "strategy_per_label": f1["per_strategy"],
        "mean_politeness_score": (
            round(sum(reply_scores) / len(reply_scores), 1) if reply_scores else 0.0
        ),
        "mean_latency_s": round(sum(latencies) / len(latencies), 4) if latencies else 0.0,
        "p95_latency_s": percentile(latencies, 95),
    }


def split_seed(seed_rows: list[dict], seed: int = 42) -> dict[str, list[dict]]:
    """Stratified 80/10/10 split by scenario, deterministic on *seed*."""
    import random

    rng = random.Random(seed)
    by_scenario: dict[str, list[dict]] = defaultdict(list)
    for row in seed_rows:
        by_scenario[row["scenario"]].append(row)
    splits: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    for scenario, rows in sorted(by_scenario.items()):
        shuffled = rows[:]
        rng.shuffle(shuffled)
        n = len(shuffled)
        n_test = max(1, round(n * 0.10))
        n_val = max(1, round(n * 0.10))
        splits["test"].extend(shuffled[:n_test])
        splits["val"].extend(shuffled[n_test:n_test + n_val])
        splits["train"].extend(shuffled[n_test + n_val:])
    for name in splits:
        rng.shuffle(splits[name])
    return splits


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a system on the seed set.")
    parser.add_argument("--seed-file", type=pathlib.Path, default=SEED_PATH,
                        help="Seed JSONL file (default: ml/data/seed.jsonl).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for the stratified split.")
    parser.add_argument("--predictions", type=pathlib.Path, default=None,
                        help="JSONL of system outputs (default: run the rule engine).")
    parser.add_argument("--split", action="store_true",
                        help="Write stratified 80/10/10 splits to ml/data/splits/.")
    args = parser.parse_args()

    seed_rows = load_jsonl(args.seed_file)
    if args.split:
        splits = split_seed(seed_rows, seed=args.seed)
        SPLITS_DIR.mkdir(parents=True, exist_ok=True)
        for name, rows in splits.items():
            with (SPLITS_DIR / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"splits written to {SPLITS_DIR}: " +
              ", ".join(f"{name}={len(rows)}" for name, rows in splits.items()))

    if args.predictions:
        predictions = load_jsonl(args.predictions)
        latencies = [0.0] * len(predictions)
        source = f"predictions file {args.predictions}"
    else:
        predictions, latencies = rule_engine_predictions(seed_rows)
        source = "rule-based engine (prototype-0.1)"

    report = evaluate(seed_rows, predictions, latencies)
    print(f"\nEvaluation on {len(seed_rows)} seed examples — {source}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
