"""Rule-based politeness score (0-100) for a reply text.

Used in three places, so it lives here and not inside one endpoint:
- ``POST /v1/suggest`` scores the reply it returns (``score`` field), so
  LLM and rule-based replies are comparable on the same scale;
- ``ml/evaluation/metrics.py`` scores seed / model replies (its copy is
  self-contained; this module is the API-side canonical version);
- the FYP evaluation (``docs/EVALUATION_PLAN.md``) uses it as the
  automatic politeness metric next to strategy F1 and JSON validity.

Method: count politeness markers from Brown & Levinson (1987) —
hedges (``could you``, ``would it be possible``, ``perhaps``), gratitude
(``thank``, ``appreciate``), indirectness (questions, conditionals),
apologies and softeners — and subtract directness markers (bare
imperatives, ``must``, ``now``, ``ASAP``, ``immediately``). The result is
clamped to 0-100 and rounded to one decimal. It is a *lexical* score:
honest, reproducible, and deliberately not a judgement of the reply's
real-world appropriateness (see the limitations the API returns).
"""

from __future__ import annotations

import re

HEDGES = (
    "could you",
    "would you",
    "would it be possible",
    "could we",
    "would it be ok",
    "is it possible",
    "perhaps",
    "maybe",
    "just",
    "a little",
    "a bit",
    "whenever you have a moment",
    "if you don't mind",
    "i was wondering",
    "i wanted to check",
    "happy to",
)

GRATITUDE = ("thank", "thanks", "appreciate", "grateful")

INDIRECTNESS = (
    "?",
    "could",
    "would",
    "might",
    "may i",
    "let me know",
    "please let me know",
)

APOLOGY_SOFTENERS = (
    "sorry",
    "apolog",
    "i understand",
    "no worries",
    "of course",
    "absolutely",
)

DIRECTNESS_MARKERS = (
    "must",
    "need to",
    "you have to",
    "asap",
    "immediately",
    "right now",
    "do it now",
    "urgent",
    "!!!",
)

_WEIGHTS = {"hedge": 6.0, "gratitude": 8.0, "indirect": 3.0, "softener": 5.0}
_DIRECT_PENALTY = 7.0
_BASE = 45.0  # a plain, neutral sentence starts in the middle of the scale.


def _count(text: str, phrases: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for phrase in phrases if phrase in lowered)


def politeness_score(reply: str) -> float:
    """Score *reply* from 0 (blunt) to 100 (very hedged / polite)."""
    if not reply or not reply.strip():
        return 0.0
    text = reply.strip()
    score = _BASE
    score += _count(text, HEDGES) * _WEIGHTS["hedge"]
    score += _count(text, GRATITUDE) * _WEIGHTS["gratitude"]
    score += _count(text, INDIRECTNESS) * _WEIGHTS["indirect"]
    score += _count(text, APOLOGY_SOFTENERS) * _WEIGHTS["softener"]
    score -= _count(text, DIRECTNESS_MARKERS) * _DIRECT_PENALTY
    # Longer, well-formed replies with a greeting + close read as more
    # polite; very short blunt replies read as less. Small effect only.
    words = len(re.findall(r"\b\w+\b", text))
    if words >= 25:
        score += 3.0
    elif words <= 6:
        score -= 5.0
    return round(max(0.0, min(100.0, score)), 1)
