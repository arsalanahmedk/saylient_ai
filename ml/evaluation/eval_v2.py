"""Evaluate a system on the Saylient v2 test split.

    python -m ml.evaluation.eval_v2 --test ml/data/splits_v2/test.jsonl
    python -m ml.evaluation.eval_v2 --test ml/data/splits_v2/test.jsonl \\
        --predictions predictions.jsonl [--limit 500]

Without ``--predictions`` it scores a small keyword baseline, so the
script always produces a number to beat (the fine-tuned model must
beat it clearly).

Metrics:

- **JSON validity rate** — share of outputs that parse as JSON and
  match the v2 contract (intent / tone / strategy / sentiment /
  formality / face_threat_level / polite_rewrite / explanation, with
  values in the allowed sets). Invalid rows count as wrong on every
  label metric.
- **Intent accuracy** — overall + per-intent.
- **Strategy accuracy** — overall + per-strategy.
- **Formality MAE** — mean absolute error of the predicted formality
  score vs the gold score (valid rows only).
- **Sample rewrites** — 5 test examples printed with the gold rewrite
  and the predicted rewrite, so a human can judge quality at a glance.

A ``--predictions`` JSONL file has one JSON object per line, in the
same order as the test file, each with the v2 assistant fields
(intent, tone, strategy, sentiment, formality, face_threat_level,
polite_rewrite, explanation). A line that is not valid JSON, or a
prediction file shorter than the test file, is reported, not hidden.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEST_PATH = ROOT / "ml" / "data" / "splits_v2" / "test.jsonl"

INTENTS = (
    "payment_request", "deadline_negotiation", "scope_boundary",
    "revision_request", "late_delivery_apology", "rate_discussion",
    "follow_up", "feedback_handling", "question_how_to_ask", "greeting",
    "other",
)
TONES = ("polite", "firm_polite", "warm", "formal", "casual",
         "apologetic", "assertive")
STRATEGIES = ("positive_politeness", "negative_politeness",
              "bald_on_record", "off_record")
SENTIMENTS = ("positive", "neutral", "negative", "frustrated")
FACE_LEVELS = ("low", "medium", "high")


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


def validate_prediction(pred) -> bool:
    """True if *pred* matches the v2 assistant contract."""
    if not isinstance(pred, dict):
        return False
    return bool(
        pred.get("intent") in INTENTS
        and pred.get("tone") in TONES
        and pred.get("strategy") in STRATEGIES
        and pred.get("sentiment") in SENTIMENTS
        and isinstance(pred.get("formality"), (int, float))
        and 0 <= pred["formality"] <= 1
        and pred.get("face_threat_level") in FACE_LEVELS
        and isinstance(pred.get("polite_rewrite"), str)
        and pred["polite_rewrite"].strip()
        and isinstance(pred.get("explanation"), str)
        and pred["explanation"].strip()
    )


# --- keyword baseline (intent only; strategy = majority class) ------------
_KEYWORDS = [
    (r"\b(pay|payment|invoice|paid|overdue|deposit|refund)\b", "payment_request"),
    (r"\b(deadline|extend|extension|delay|late|deliver by|due date)\b", "deadline_negotiation"),
    (r"\b(out of scope|extra work|not in the|beyond the scope|boundary)\b", "scope_boundary"),
    (r"\b(revision|revise|change the|feedback|draft|version)\b", "revision_request"),
    (r"\b(sorry|apolog|late delivery|missed the deadline)\b", "late_delivery_apology"),
    (r"\b(rate|price|budget|discount|charge|fee|cost)\b", "rate_discussion"),
    (r"\b(follow up|following up|checking in|heard nothing|ghosted|reminder)\b", "follow_up"),
    (r"\b(feedback|review|criticis|unhappy|terrible|love the work)\b", "feedback_handling"),
    (r"^how do i\b", "question_how_to_ask"),
    (r"\b(hello|hi there|introduce myself|welcome|congratulations|happy new year)\b", "greeting"),
]


def keyword_baseline(rows: list[dict]) -> list[dict]:
    preds = []
    for row in rows:
        text = row["input"].lower()
        intent = "other"
        for pattern, label in _KEYWORDS:
            if re.search(pattern, text):
                intent = label
                break
        preds.append({
            "intent": intent,
            "tone": "polite",
            "strategy": "negative_politeness",
            "sentiment": "neutral",
            "formality": 0.6,
            "face_threat_level": "medium",
            "polite_rewrite": "(baseline: no rewrite generated)",
            "explanation": "Keyword baseline prediction.",
        })
    return preds


def per_label_accuracy(gold: list[str], pred: list[str]) -> dict:
    labels = sorted(set(gold))
    out: dict[str, dict] = {}
    for label in labels:
        idx = [i for i, g in enumerate(gold) if g == label]
        acc = sum(1 for i in idx if pred[i] == gold[i]) / len(idx) if idx else 0.0
        out[label] = {"accuracy": round(acc, 3), "support": len(idx)}
    return out


def evaluate(gold_rows: list[dict], predictions: list[dict]) -> dict:
    n = len(gold_rows)
    valid = [validate_prediction(p) for p in predictions]
    json_validity = sum(valid) / n if n else 0.0
    gold_intent = [r["intent"] for r in gold_rows]
    pred_intent = [p.get("intent") if v else "__invalid__"
                   for p, v in zip(predictions, valid)]
    gold_strategy = [r["strategy"] for r in gold_rows]
    pred_strategy = [p.get("strategy") if v else "__invalid__"
                     for p, v in zip(predictions, valid)]
    intent_acc = sum(g == p for g, p in zip(gold_intent, pred_intent)) / n if n else 0.0
    strat_acc = sum(g == p for g, p in zip(gold_strategy, pred_strategy)) / n if n else 0.0
    form_errors = [abs(p["formality"] - r["formality"])
                   for p, r, v in zip(predictions, gold_rows, valid) if v]
    return {
        "n": n,
        "json_validity_rate": round(json_validity, 3),
        "invalid_rows": sum(1 for v in valid if not v),
        "intent_accuracy": round(intent_acc, 3),
        "intent_per_label": per_label_accuracy(gold_intent, pred_intent),
        "strategy_accuracy": round(strat_acc, 3),
        "strategy_per_label": per_label_accuracy(gold_strategy, pred_strategy),
        "formality_mae": (
            round(sum(form_errors) / len(form_errors), 3) if form_errors else None
        ),
        "majority_intent_baseline": round(
            max(Counter(gold_intent).values()) / n, 3) if n else 0.0,
        "majority_strategy_baseline": round(
            max(Counter(gold_strategy).values()) / n, 3) if n else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a system on the v2 test split.")
    parser.add_argument("--test", type=pathlib.Path, default=TEST_PATH)
    parser.add_argument("--predictions", type=pathlib.Path, default=None,
                        help="JSONL of model outputs, same order as --test. "
                             "If omitted, a keyword baseline is scored.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Score only the first N test rows.")
    parser.add_argument("--samples", type=int, default=5,
                        help="Sample rewrites to print.")
    args = parser.parse_args()

    gold_rows = load_jsonl(args.test)
    if args.limit:
        gold_rows = gold_rows[:args.limit]
    if args.predictions:
        predictions = load_jsonl(args.predictions)[:len(gold_rows)]
        source = f"predictions file {args.predictions}"
        if len(predictions) < len(gold_rows):
            print(f"WARNING: predictions file has {len(predictions)} rows "
                  f"for {len(gold_rows)} test rows; missing rows count as invalid.")
            predictions += [{}] * (len(gold_rows) - len(predictions))
    else:
        predictions = keyword_baseline(gold_rows)
        source = "keyword baseline (no model)"

    report = evaluate(gold_rows, predictions)
    print(f"\nEvaluation on {len(gold_rows)} v2 test examples — {source}")
    print(json.dumps(report, indent=2))

    print(f"\n--- {args.samples} sample rewrites ---")
    step = max(1, len(gold_rows) // args.samples)
    for i in range(0, len(gold_rows), step)[:args.samples]:
        gold = gold_rows[i]
        pred = predictions[i]
        print(f"\n[{i}] gold intent={gold['intent']} strategy={gold['strategy']} | "
              f"pred intent={pred.get('intent')} strategy={pred.get('strategy')}")
        print(f"INPUT: {gold['input']}")
        print(f"GOLD REWRITE: {gold['polite_rewrite']}")
        print(f"PRED REWRITE: {pred.get('polite_rewrite')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
