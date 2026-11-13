"""Rule-based analysis baseline (model_version ``prototype-0.1``).

Implements the pipeline and output contract of
05-ai-ml/AI_ML_ARCHITECTURE.md for the prototype:

    input validation -> normalisation -> intent classification
    -> tone classification -> FTA / face prediction
    -> assemble known P/D/R context -> strategy engine
    -> draft generation -> output validation -> response

This is a *baseline*, not a trained model: keyword scoring replaces the
TF-IDF + logistic-regression classifier the architecture describes for
later phases. The LLM drafting step is replaced by template-based drafting
that reuses only facts present in the user's own message (dates, invoice
numbers, amounts) and never invents facts.

Guardrails (from the architecture doc and the project brief):
- Never infer protected traits.
- Never claim to know the recipient's true intent or emotions.
- P/D/R values are taken ONLY from the request context. ``unknown`` is a
  real value and is never guessed from the message text.
- Always include at least one limitation.
- Confidence is honest: it comes from keyword-match strength and is low
  when the match is weak.

Strategy rules (Brown & Levinson 1987, operationalised; the numbers are
the rule order — first match wins):
    R1  intent is respond_to_criticism or resolve_disagreement:
            imposition high + social_distance high -> avoidance
            imposition high                         -> off_record
            otherwise                               -> positive_politeness
    R2  intent is request_payment or negotiate_deadline
            -> negative_politeness (deadline/payment pressure)
    R3  power is high (the recipient holds more power) and imposition
        is medium or high -> negative_politeness (deference)
    R4  imposition high + social_distance unknown/high
            -> negative_politeness
    R5  imposition low + social_distance low
            -> bald_on_record
    R6  intent is clarify_requirements + imposition unknown/low
            -> bald_on_record (seeking information is low-threat)
    R7  default -> negative_politeness (the safe, hedged default)
"""

from __future__ import annotations

import math
import re

MODEL_VERSION = "prototype-0.1"

INTENT_LABELS = [
    "set_boundary",
    "request_payment",
    "negotiate_deadline",
    "clarify_requirements",
    "respond_to_criticism",
    "negotiate_budget",
    "resolve_disagreement",
    "unknown",
]

TONE_LABELS = [
    "direct",
    "frustrated",
    "diplomatic",
    "neutral",
    "anxious",
    "appreciative",
]

STRATEGY_LABELS = [
    "bald_on_record",
    "positive_politeness",
    "negative_politeness",
    "off_record",
    "avoidance",
]

# Keyword phrases with weights. Longer, more specific phrases weigh more.
# Matching is case-insensitive with word boundaries; common inflections are
# listed explicitly so "delayed" does not need a stemmer.
INTENT_KEYWORDS: dict[str, list[tuple[str, float]]] = {
    "set_boundary": [
        ("outside the scope", 2.0),
        ("out of scope", 2.0),
        ("extra work", 2.0),
        ("extra revisions", 2.0),
        ("extra pages", 2.0),
        ("extra", 1.5),
        ("unpaid", 2.0),
        ("boundary", 2.0),
        ("scope", 1.0),
        ("can't", 1.0),
        ("cannot", 1.0),
        ("won't be able", 1.5),
        ("not able to", 1.0),
        ("separate task", 1.5),
        ("separate paid", 1.5),
    ],
    "request_payment": [
        ("invoice", 2.0),
        ("payment", 2.0),
        ("overdue", 2.0),
        ("paid", 1.0),
        ("pay", 1.0),
        ("owed", 1.5),
        ("billing", 1.5),
        ("balance due", 2.0),
        ("remit", 1.5),
        ("fee", 0.5),
    ],
    "negotiate_deadline": [
        ("deadline", 2.0),
        ("move the deadline", 2.0),
        ("delay", 1.0),
        ("delayed", 1.0),
        ("delays", 1.0),
        ("extend", 1.5),
        ("extension", 1.5),
        ("due date", 2.0),
        ("deliver", 1.0),
        ("delivery", 1.0),
        ("timeline", 1.0),
        ("postpone", 2.0),
        ("push back", 2.0),
        ("due", 0.5),
    ],
    "clarify_requirements": [
        ("clarify", 2.0),
        ("clarification", 2.0),
        ("unclear", 1.5),
        ("what do you mean", 2.0),
        ("requirements", 1.0),
        ("exactly what", 1.5),
        ("could you explain", 1.5),
        ("confirm", 0.5),
        ("spec", 1.0),
        ("details", 0.5),
    ],
    "respond_to_criticism": [
        ("poor", 2.0),
        ("bad", 1.0),
        ("wrong", 2.0),
        ("mistake", 1.5),
        ("terrible", 2.0),
        ("disappointed", 2.0),
        ("not good", 2.0),
        ("unhappy", 2.0),
        ("not happy", 2.0),
        ("quality", 1.0),
        ("redo", 1.5),
        ("rework", 1.5),
        ("didn't work", 1.5),
        ("doesn't work", 1.5),
    ],
    "negotiate_budget": [
        ("budget", 2.0),
        ("rate", 2.0),
        ("hourly", 1.5),
        ("price", 1.5),
        ("discount", 2.0),
        ("expensive", 1.5),
        ("afford", 1.0),
        ("charge", 1.0),
        ("lower", 1.0),
    ],
    "resolve_disagreement": [
        ("disagree", 2.0),
        ("don't agree", 2.0),
        ("do not agree", 2.0),
        ("not what we agreed", 2.0),
        ("we agreed", 1.0),
        ("misunderstanding", 2.0),
        ("conflict", 1.5),
        ("dispute", 1.5),
        ("different", 0.5),
    ],
}

TONE_KEYWORDS: dict[str, list[tuple[str, float]]] = {
    "frustrated": [
        ("frustrating", 2.0),
        ("frustrated", 2.0),
        ("ridiculous", 2.0),
        ("unacceptable", 2.0),
        ("taking too long", 2.0),
        ("disappointed", 1.5),
        ("angry", 2.0),
        ("upset", 1.5),
        ("again", 0.5),
        ("still not", 1.5),
        ("third time", 1.5),
    ],
    "anxious": [
        ("worried", 2.0),
        ("anxious", 2.0),
        ("concerned", 1.5),
        ("not sure", 1.5),
        ("afraid", 2.0),
        ("nervous", 2.0),
        ("hope", 0.5),
        ("urgent", 1.0),
    ],
    "diplomatic": [
        ("would it be possible", 2.0),
        ("could you", 1.5),
        ("would you", 1.5),
        ("please", 1.0),
        ("appreciate", 1.0),
        ("wondering", 1.0),
        ("kindly", 1.5),
        ("happy to", 0.5),
    ],
    "appreciative": [
        ("thank", 2.0),
        ("thanks", 2.0),
        ("great work", 2.0),
        ("appreciate", 1.0),
        ("excellent", 2.0),
        ("amazing", 1.5),
        ("love", 1.0),
    ],
    "direct": [
        ("need", 1.0),
        ("must", 1.5),
        ("today", 0.5),
        ("asap", 2.0),
        ("immediately", 2.0),
        ("now", 0.5),
        ("as soon as possible", 2.0),
        ("required", 1.0),
    ],
}

# Phrases that signal a possible face-threatening act, grouped by the face
# they most plausibly concern. These are *signals*, not proof: the output
# always labels the FTA as "possible" and never claims to know the
# recipient's reaction.
FTA_NEGATIVE_FACE: list[tuple[str, float]] = [
    ("need", 1.0),
    ("must", 1.5),
    ("today", 0.5),
    ("deadline", 1.0),
    ("invoice", 1.0),
    ("payment", 1.0),
    ("asap", 1.5),
    ("immediately", 1.5),
    ("extra", 1.0),
    ("scope", 0.5),
    ("delayed", 1.0),
]

FTA_POSITIVE_FACE: list[tuple[str, float]] = [
    ("poor", 2.0),
    ("wrong", 2.0),
    ("bad", 1.5),
    ("disagree", 2.0),
    ("mistake", 1.5),
    ("disappointed", 1.5),
    ("terrible", 2.0),
    ("not good", 2.0),
]

_WEEKDAYS = (
    "monday|tuesday|wednesday|thursday|friday|saturday|sunday"
)
_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
    "|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
_DATE_RE = re.compile(
    rf"\b(?:today|tomorrow|next week|this week|{_WEEKDAYS}"
    rf"|(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?"
    rf"|\d{{4}}-\d{{2}}-\d{{2}})\b",
    re.IGNORECASE,
)
_INVOICE_RE = re.compile(r"invoice\s*#?\s*([A-Za-z0-9][A-Za-z0-9\-]*)", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"(\$|£|€|Rs\.?)\s?(\d[\d,]*(?:\.\d{1,2})?)", re.IGNORECASE)


def _phrase_regex(phrase: str) -> re.Pattern:
    """Word-boundary regex for a (possibly multi-word) keyword phrase."""
    parts = [re.escape(word) for word in phrase.split()]
    return re.compile(r"\b" + r"\s+".join(parts) + r"\b", re.IGNORECASE)


def _score(text: str, keywords: list[tuple[str, float]]) -> float:
    score = 0.0
    for phrase, weight in keywords:
        if _phrase_regex(phrase).search(text):
            score += weight
    return score


def _best_label(
    text: str,
    keyword_map: dict[str, list[tuple[str, float]]],
    *,
    goal_hint: str | None = None,
    unknown_label: str = "unknown",
) -> tuple[str, float, float]:
    """Return (label, confidence, best_score).

    Confidence is a saturating function of the winning keyword score, so a
    single weak match is honest about its uncertainty:
        confidence = 0.35 + 0.55 * (1 - exp(-score / 2))
    A score of 1 -> ~0.57; 3 -> ~0.78; 6 -> ~0.87. When nothing matches,
    the label is ``unknown`` with confidence 0.20.
    """
    scores = {label: _score(text, kws) for label, kws in keyword_map.items()}
    best = max(scores, key=lambda label: (scores[label], label == goal_hint))
    best_score = scores[best]
    if best_score <= 0:
        return unknown_label, 0.20, 0.0
    confidence = round(min(0.95, 0.35 + 0.55 * (1 - math.exp(-best_score / 2))), 2)
    return best, confidence, best_score


def extract_facts(message: str) -> dict:
    """Pull reusable facts from the user's own message.

    Only these three fact types are extracted; anything else is left
    generic so the draft can never invent a date, invoice or amount.
    Returns {"date": str|None, "invoice": str|None, "amount": str|None}.
    """
    invoice_match = _INVOICE_RE.search(message)
    amount_match = _AMOUNT_RE.search(message)
    date_match = _DATE_RE.search(message)
    amount = None
    if amount_match:
        amount = f"{amount_match.group(1).rstrip('.')} {amount_match.group(2)}"
        amount = " ".join(amount.split())
    return {
        "date": date_match.group(0) if date_match else None,
        "invoice": f"#{invoice_match.group(1)}" if invoice_match else None,
        "amount": amount,
    }


def _draft_core(intent: str, facts: dict) -> str:
    """Template core per intent, reusing only extracted facts."""
    if intent == "request_payment":
        if facts["invoice"]:
            return (
                f"I wanted to check in on invoice {facts['invoice']}. "
                "Could you let me know when the payment will be sent?"
            )
        return (
            "I wanted to check in on the outstanding payment. "
            "Could you let me know when it will be sent?"
        )
    if intent == "negotiate_deadline":
        if facts["date"]:
            return (
                f"Would it be possible to move the deadline to {facts['date']}? "
                "I want to make sure the quality stays high."
            )
        return (
            "Would it be possible to move the deadline a little? "
            "I want to make sure the quality stays high."
        )
    if intent == "set_boundary":
        if facts["date"]:
            return (
                "That change is outside the agreed scope, so I'd like to treat "
                f"it as a separate task. Could we schedule it for {facts['date']} instead?"
            )
        return (
            "That change is outside the agreed scope, so I'd like to treat it "
            "as a separate task. I'm happy to schedule it once we've agreed on it."
        )
    if intent == "clarify_requirements":
        return (
            "Could you clarify the details on this, so I can get it right? "
            "A short note on what you need would help a lot."
        )
    if intent == "respond_to_criticism":
        return (
            "Could you tell me specifically what didn't work, so I can "
            "address it properly? I want to make sure the next version is right."
        )
    if intent == "negotiate_budget":
        if facts["amount"]:
            return (
                f"My rate is {facts['amount']}, and I'm happy to adjust the scope "
                "so it fits your budget."
            )
        return "I'm happy to adjust the scope so it fits your budget."
    if intent == "resolve_disagreement":
        return (
            "I see it a bit differently — could we talk through what needs to "
            "change, so we can agree on the next step?"
        )
    return "Could you help me understand what you need here, so I can respond properly?"


_CLOSES = {
    "negative_politeness": "Please let me know what works for you.",
    "positive_politeness": "I'd love to find an approach that works for both of us.",
    "bald_on_record": "Thanks — let me know once it's done.",
    "off_record": "Just let me know what you think.",
    "avoidance": "I'll check back later this week.",
}

# Goal-specific closes (FR-09): the strategy close is generic, and for
# some goals it misfires — a payment chase is not a scheduling request,
# so "what works for you" is the wrong ending. When the goal has its own
# close it wins over the strategy close; the close is still only wording,
# never a new fact.
_INTENT_CLOSES = {
    "request_payment": "Thank you — please let me know once the payment is on its way.",
}

# Draft tone + directness (FR-09): the tone selector and the directness
# selector in the result panel re-run the engine with these values, and
# the draft text actually changes. Tones change the greeting and the
# close; directness changes how hedged the wording is.
_TONE_GREETINGS = {
    "Professional": "Hello,",
    "Friendly": "Hi there,",
    "Diplomatic": "Hi,",
    "Assertive": "Hi,",
    "Empathetic": "Hi, I hope you're doing well —",
}
_VALID_TONES = frozenset(_TONE_GREETINGS)
_VALID_DIRECTNESS = frozenset({"direct", "balanced", "gentle"})

# Hedge phrases a "direct" draft drops in favour of plain requests.
_DIRECT_REPLACEMENTS = [
    ("Would it be possible to", "Please"),
    ("would it be possible to", "please"),
    ("Could you let me know", "Please let me know"),
    ("could you let me know", "please let me know"),
    ("I wanted to check in on", "I'm following up on"),
    ("I wanted to check in", "I'm following up"),
]


def _style_draft(core: str, close: str, tone: str, directness: str) -> str:
    """Assemble the draft from the intent core, tone and directness.

    ``tone`` picks the greeting; ``directness`` scales the hedging:
    "direct" swaps hedged requests for plain ones and shortens the close,
    "gentle" adds a softener to the close. The factual core (dates,
    invoices, amounts) and the strategy close are never rewritten — only
    the framing around them changes.
    """
    greeting = _TONE_GREETINGS[tone]
    if directness == "direct":
        for old, new in _DIRECT_REPLACEMENTS:
            core = core.replace(old, new)
        close = "Please let me know."
    elif directness == "gentle":
        close = f"{close} Whenever you have a moment."
    return f"{greeting}\n\n{core}\n\n{close}"


def _choose_strategy(
    intent: str, power: str, social_distance: str, imposition: str
) -> tuple[str, str]:
    """Strategy engine — rules R1-R7, first match wins (see module docstring)."""
    if intent in {"respond_to_criticism", "resolve_disagreement"}:
        # R1: criticism/disagreement threatens positive face; hedging or
        # stepping back keeps the relationship intact.
        if imposition == "high" and social_distance == "high":
            return (
                "avoidance",
                (
                "The message is a high-imposition criticism with high social "
                "distance. The safest move is to not do the face-threatening "
                "act now and return to it later."
                ),
            )
        if imposition == "high":
            return (
                "off_record",
                (
                "The message is a high-imposition criticism, so a hint leaves "
                "room for the other person to respond without direct pressure."
                ),
            )
        return (
            "positive_politeness",
            (
            "Criticism and disagreement threaten the recipient's positive "
            "face, so the response leans on solidarity and shared goals."
            ),
        )
    if intent in {"request_payment", "negotiate_deadline"}:
        # R2: payment and deadline pressure constrain the recipient's time.
        return (
            "negative_politeness",
            (
            "Payment and deadline pressure constrain the recipient's time, "
            "so the response hedges and leaves room to respond."
            ),
        )
    if power == "high" and imposition in {"medium", "high"}:
        # R3: the recipient holds more power, so the response defers and
        # hedges rather than pressing the request directly.
        return (
            "negative_politeness",
            (
            "The recipient holds more power in this relationship and the "
            "request is not trivial, so the response defers and hedges."
            ),
        )
    if imposition == "high" and social_distance in {"unknown", "high"}:
        # R4: high imposition without a close relationship needs hedging.
        return (
            "negative_politeness",
            (
            "The request is high-imposition and the relationship is not "
            "close, so the response hedges and respects the recipient's autonomy."
            ),
        )
    if imposition == "low" and social_distance == "low":
        # R5: low imposition with a close relationship can be direct.
        return (
            "bald_on_record",
            (
            "The request is low-imposition and the relationship is close, "
            "so a direct response is appropriate."
            ),
        )
    if intent == "clarify_requirements" and imposition in {"unknown", "low"}:
        # R6: asking for information is low-threat; a direct question is fine.
        return (
            "bald_on_record",
            (
            "Asking for clarification is a low-threat request, so a direct "
            "question is appropriate."
            ),
        )
    # R7: the safe default — hedge rather than risk a face threat.
    return (
        "negative_politeness",
        (
        "No rule strongly favours a direct response, so the response hedges "
        "and respects the recipient's autonomy."
        ),
    )


def analyze(
    message: str,
    goal: str,
    context: dict | None = None,
    draft_tone: str = "Diplomatic",
    draft_directness: str = "balanced",
) -> dict:
    """Run the rule-based analysis and return the exact output contract
    from 05-ai-ml/AI_ML_ARCHITECTURE.md.

    ``context`` maps "power" / "social_distance" / "imposition" to
    "unknown" | "low" | "medium" | "high". Missing values are "unknown".
    P/D/R are never inferred from the message — the requester's context is
    the only source.

    ``draft_tone`` (one of Professional/Friendly/Diplomatic/Assertive/
    Empathetic) and ``draft_directness`` ("direct" | "balanced" |
    "gentle") change the draft text only — intent, tone label, FTA and
    strategy are computed from the message and context, not from the
    styling. (Named ``draft_*`` because the detected tone label is a
    local called ``tone`` further down.)
    """
    context = context or {}
    power = context.get("power", "unknown")
    social_distance = context.get("social_distance", "unknown")
    imposition = context.get("imposition", "unknown")
    for value in (power, social_distance, imposition):
        if value not in {"unknown", "low", "medium", "high"}:
            raise ValueError(f"Invalid context level: {value!r}")
    if draft_tone not in _VALID_TONES:
        raise ValueError(f"Invalid tone: {draft_tone!r}")
    if draft_directness not in _VALID_DIRECTNESS:
        raise ValueError(f"Invalid directness: {draft_directness!r}")

    text = message.strip()
    intent, intent_conf, _ = _best_label(
        text, INTENT_KEYWORDS, goal_hint=goal if goal in INTENT_KEYWORDS else None
    )
    tone, tone_conf, tone_score = _best_label(text, TONE_KEYWORDS, unknown_label="neutral")
    if tone_score <= 0:
        tone, tone_conf = "neutral", 0.30

    neg_score = _score(text, FTA_NEGATIVE_FACE)
    pos_score = _score(text, FTA_POSITIVE_FACE)
    fta_detected = (neg_score + pos_score) > 0
    face_concern: list[str] = []
    if fta_detected:
        if neg_score > 0:
            face_concern.append("negative_face")
        if pos_score > 0:
            face_concern.append("positive_face")
        if neg_score >= pos_score:
            fta_description = (
                "Possible request or pressure that may constrain the "
                "recipient's time or autonomy"
            )
        else:
            fta_description = (
                "Possible disagreement or criticism that may threaten the "
                "recipient's sense of being valued"
            )
    else:
        fta_description = "No face-threatening act detected"

    strategy_label, rationale = _choose_strategy(
        intent, power, social_distance, imposition
    )

    facts = extract_facts(text)
    close = _INTENT_CLOSES.get(intent, _CLOSES[strategy_label])
    draft = _style_draft(
        _draft_core(intent, facts),
        close,
        draft_tone,
        draft_directness,
    )

    limitations = [
        "This is a rule-based prototype analysis, not a human judgement.",
        "The recipient's true intent and emotions are unknown.",
    ]
    if "unknown" in (power, social_distance, imposition):
        limitations.append(
            "Relationship context is incomplete: power, social distance or "
            "imposition is unknown, so the strategy is a conservative default."
        )
    if intent == "unknown":
        limitations.append(
            "No clear intent signal was found in the message, so the draft "
            "is generic — please check it before sending."
        )

    return {
        "intent": {"label": intent, "confidence": intent_conf},
        "tone": {"label": tone, "confidence": tone_conf},
        "fta": {"detected": fta_detected, "description": fta_description},
        "face_concern": face_concern,
        "context_factors": {
            "power": power,
            "social_distance": social_distance,
            "imposition": imposition,
        },
        "strategy": {"label": strategy_label, "rationale": rationale},
        "draft": draft,
        "limitations": limitations,
        "model_version": MODEL_VERSION,
    }


def evaluate_examples(examples: list[dict]) -> dict:
    """Score the engine against hand-labelled examples (see eval/golden.json).

    Returns the counts and per-example disagreements so the test can print
    and assert on them. Agreement is on intent label and strategy label.
    """
    intent_ok = 0
    strategy_ok = 0
    disagreements: list[dict] = []
    for item in examples:
        result = analyze(
            item["message"],
            item["goal"],
            item.get("context", {}),
        )
        got_intent = result["intent"]["label"]
        got_strategy = result["strategy"]["label"]
        intent_match = got_intent == item["expected_intent"]
        strategy_match = got_strategy == item["expected_strategy"]
        intent_ok += int(intent_match)
        strategy_ok += int(strategy_match)
        if not (intent_match and strategy_match):
            disagreements.append(
                {
                    "message": item["message"][:60],
                    "expected_intent": item["expected_intent"],
                    "got_intent": got_intent,
                    "expected_strategy": item["expected_strategy"],
                    "got_strategy": got_strategy,
                }
            )
    total = len(examples)
    return {
        "total": total,
        "intent_agreement": f"{intent_ok}/{total}",
        "strategy_agreement": f"{strategy_ok}/{total}",
        "intent_correct": intent_ok,
        "strategy_correct": strategy_ok,
        "disagreements": disagreements,
    }
