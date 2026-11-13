"""Suggestion orchestration: LLM first, rule-based engine as fallback.

Contract authority: ``docs/openapi.yaml`` (Option A, 2026-11-13).

``POST /v1/suggest`` always returns a useful answer:

1. If an LLM provider is configured, ask it (see ``llm_client``).
2. On **any** LLM failure — no key, 429 quota/rate-limit, timeout,
   invalid JSON after the repair retry, blocked injection — fall back to
   the rule-based engine (``prototype-0.1``) and say so in the response
   (``source="rule_based"`` + ``llm_status``). The user never sees an
   LLM error as their error.
3. Replies are always 3 ``{tone, text}`` objects (spec shape), the
   score is an integer, and every suggestion carries a ``suggestion_id``
   (uuid4). The rule engine's single draft becomes 3 replies by
   re-styling it in the polite / friendly / firm tones (requested tone
   first); the LLM's 3 replies are used as returned, tones included.
4. Strategies are the spec enum only. The engine can return
   ``avoidance`` internally (one golden-set case); the API boundary maps
   it to ``off_record`` — the closest spec strategy (a hint that leaves
   room to respond, same as the engine's avoidance rationale) — and
   records the mapping here, never silently.

``POST /v1/analyze`` is rule-engine-only by design (deterministic,
no external call, no key needed) — it is the evaluation baseline. It
returns the spec fields (``scenario``, ``face_threat``,
``detected_strategy``, ``issues``) first, with the engine's richer
detail alongside.
"""

from __future__ import annotations

import logging
import uuid

from app.core.config import Settings, get_settings
from app.schemas import (
    AnalyzeResponse,
    ContextFactors,
    Reply,
    SuggestResponse,
)
from app.services import analysis_engine
from app.services.llm_client import (
    LLMBlocked,
    LLMClient,
    LLMDisabled,
    LLMError,
    LLMInvalidResponse,
    LLMOutput,
    LLMRateLimited,
)
from app.services.politeness import politeness_score

logger = logging.getLogger("saylient.suggest")

# Best-effort mapping from the engine's 7 intents to the plan's 10
# scenarios. Where an intent spans two scenarios the message text
# decides (scope/extra/revision wording -> scope_creep, otherwise the
# boundary default). Documented here because it is a judgement call,
# not a fact the engine asserts.
_SCOPE_WORDS = ("scope", "extra", "revision", "revisions", "additional")


def intent_to_scenario(intent: str, text: str) -> str:
    lowered = text.lower()
    mapping = {
        "request_payment": "late_payment",
        "negotiate_deadline": "deadline_extension",
        "negotiate_budget": "low-budget_offer",
        "respond_to_criticism": "rude_client",
        "resolve_disagreement": "rude_client",
        "clarify_requirements": "scope_creep",
    }
    if intent == "set_boundary":
        return (
            "scope_creep"
            if any(word in lowered for word in _SCOPE_WORDS)
            else "boundary_setting"
        )
    return mapping.get(intent, "boundary_setting")


def to_spec_strategy(label: str) -> str:
    """Map an engine/LLM strategy label onto the spec enum.

    The spec (openapi.yaml) has 4 strategies; the engine also uses
    ``avoidance``. Avoidance is a hint that leaves room to respond
    without direct pressure — the same family as ``off_record`` — so
    that is the mapping. Anything already in the spec enum passes
    through unchanged; anything else is a bug and raises.
    """
    if label == "avoidance":
        return "off_record"
    if label in {
        "bald_on_record",
        "positive_politeness",
        "negative_politeness",
        "off_record",
    }:
        return label
    raise ValueError(f"unknown strategy label: {label!r}")


# Free-text goal -> engine intent, by keyword. The spec's ``goal`` is a
# free string ("ask for payment"), not an intent label; this maps the
# common wordings onto the engine's 7 intents. Returns None when the
# goal says nothing usable — the engine then detects the intent from
# the message text alone.
_GOAL_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("request_payment", ("pay", "payment", "invoice", "overdue", "owed", "money")),
    ("negotiate_deadline", ("deadline", "delay", "extend", "extension", "due date")),
    ("set_boundary", ("scope", "extra", "revision", "boundary", "weekend", "unpaid work")),
    ("negotiate_budget", ("budget", "rate", "price", "fee", "cheap", "low pay")),
    ("respond_to_criticism", ("critic", "rude", "complaint", "poor work", "unhappy")),
    ("resolve_disagreement", ("disagree", "dispute", "argument", "conflict")),
    ("clarify_requirements", ("clarif", "unclear", "confus", "detail", "requirement")),
)


def resolve_goal_intent(goal: str | None, text: str) -> str | None:
    """Map a free-text goal (or None) to an engine intent hint, or None."""
    if goal:
        lowered = goal.strip().lower()
        if lowered in {
            "set_boundary",
            "request_payment",
            "negotiate_deadline",
            "clarify_requirements",
            "respond_to_criticism",
            "negotiate_budget",
            "resolve_disagreement",
        }:
            return lowered
        for intent, words in _GOAL_KEYWORDS:
            if any(word in lowered for word in words):
                return intent
    # Fall back to the message text itself: the engine's keyword
    # scoring is the same mechanism, just on the message instead.
    for intent, words in _GOAL_KEYWORDS:
        if any(word in text.lower() for word in words):
            return intent
    return None


# The engine's draft tones are Professional/Friendly/Diplomatic/
# Assertive/Empathetic; the suggest API takes polite/friendly/firm/formal.
_TONE_MAP = {
    "polite": "Diplomatic",
    "friendly": "Friendly",
    "firm": "Assertive",
    "formal": "Professional",
}

# Reply tones for the rule-based path: the requested tone first, then
# the remaining two of the spec example's polite/friendly/firm trio.
_REPLY_TONES = ("polite", "friendly", "firm")


def _reply_tone_order(requested: str) -> tuple[str, str, str]:
    ordered = [requested] if requested in _REPLY_TONES + ("formal",) else ["polite"]
    for tone in _REPLY_TONES:
        if tone not in ordered:
            ordered.append(tone)
    return tuple(ordered[:3])  # type: ignore[return-value]


def _rule_based_suggestion(
    *, text: str, goal: str | None, context: ContextFactors,
    tone: str, directness: str, llm_status: str,
) -> SuggestResponse:
    """Build a SuggestResponse from the rule-based engine (3 replies)."""
    hint = resolve_goal_intent(goal, text)
    base = analysis_engine.analyze(
        text,
        hint,  # type: ignore[arg-type]
        context.model_dump(),
        draft_tone=_TONE_MAP.get(tone, "Diplomatic"),
        draft_directness=directness,
    )
    intent = base["intent"]["label"]
    strategy = to_spec_strategy(base["strategy"]["label"])
    replies: list[Reply] = []
    for reply_tone in _reply_tone_order(tone):
        if reply_tone == tone:
            draft = base["draft"]
        else:
            draft = analysis_engine.analyze(
                text,
                hint,  # type: ignore[arg-type]
                context.model_dump(),
                draft_tone=_TONE_MAP[reply_tone],
                draft_directness=directness,
            )["draft"]
        replies.append(Reply(tone=reply_tone, text=draft))
    return SuggestResponse(
        scenario=intent_to_scenario(intent, text),
        strategy=strategy,
        replies=replies,
        explanation=(
            "Rule-based baseline reply (prototype-0.1): "
            f"{base['strategy']['rationale']}"
        ),
        score=round(politeness_score(replies[0].text)),
        model_version=analysis_engine.MODEL_VERSION,
        suggestion_id=uuid.uuid4(),
        intent=intent,
        strategy_rationale=base["strategy"]["rationale"],
        llm_score=None,
        source="rule_based",
        llm_status=llm_status,
        limitations=base["limitations"],
    )


def _llm_suggestion(output: LLMOutput, *, intent: str) -> SuggestResponse:
    """Build a SuggestResponse from a validated LLM answer."""
    replies = [
        Reply(tone=reply.tone, text=reply.text) for reply in output.replies
    ]
    return SuggestResponse(
        scenario=output.scenario,
        strategy=to_spec_strategy(output.strategy),
        replies=replies,
        explanation=output.explanation,
        score=round(politeness_score(replies[0].text)),
        model_version="llm",
        suggestion_id=uuid.uuid4(),
        intent=intent,
        strategy_rationale=output.explanation,
        llm_score=round(output.score),
        source="llm",
        llm_status="ok",
        limitations=[
            (
                "LLM-generated reply: check it before sending; it may not "
                "match the client's exact situation."
            )
        ],
    )


def suggest(
    *,
    text: str,
    goal: str | None = None,
    context: ContextFactors | None = None,
    tone: str = "polite",
    directness: str = "balanced",
    settings: Settings | None = None,
    llm_client: LLMClient | None = None,
) -> SuggestResponse:
    """Return a suggestion, LLM-first with rule-based fallback."""
    settings = settings or get_settings()
    context = context or ContextFactors()
    client = llm_client or LLMClient(settings)

    # The rule engine's intent (cheap, deterministic) is used as the
    # ``intent`` label in both paths, so LLM and fallback answers are
    # comparable in evaluation.
    try:
        engine_intent = analysis_engine.analyze(
            text, resolve_goal_intent(goal, text),
            context.model_dump(),
        )["intent"]["label"]
    except ValueError:
        engine_intent = "unknown"

    try:
        output = client.generate(text=text, goal=goal, tone=tone)
    except LLMDisabled:
        logger.info("LLM disabled (no provider/key); using rule-based engine.")
        return _rule_based_suggestion(
            text=text, goal=goal, context=context, tone=tone,
            directness=directness, llm_status="disabled",
        )
    except LLMBlocked as exc:
        logger.warning("LLM blocked by injection guardrail: %s", exc.reason)
        return _rule_based_suggestion(
            text=text, goal=goal, context=context, tone=tone,
            directness=directness, llm_status="blocked_injection",
        )
    except LLMRateLimited:
        logger.warning("LLM rate-limited (429); using rule-based engine.")
        return _rule_based_suggestion(
            text=text, goal=goal, context=context, tone=tone,
            directness=directness, llm_status="rate_limited",
        )
    except LLMInvalidResponse:
        logger.warning("LLM returned invalid JSON twice; using rule-based engine.")
        return _rule_based_suggestion(
            text=text, goal=goal, context=context, tone=tone,
            directness=directness, llm_status="invalid_response",
        )
    except LLMError as exc:
        logger.warning("LLM error (%s); using rule-based engine.", exc)
        return _rule_based_suggestion(
            text=text, goal=goal, context=context, tone=tone,
            directness=directness, llm_status="error",
        )

    return _llm_suggestion(output, intent=engine_intent)


def _face_threat(imposition: str, fta_detected: bool) -> str:
    """Map the engine's imposition level to the spec's face_threat.

    Known imposition passes through. When it is unknown, a detected
    face-threatening act is a medium threat, otherwise low — a neutral
    default, never a guess at high.
    """
    if imposition in {"low", "medium", "high"}:
        return imposition
    return "medium" if fta_detected else "low"


def _analyze_issues(
    *, tone_label: str, intent: str, strategy: str, imposition: str
) -> list[str]:
    """Derive the spec's ``issues`` list from the engine's labels."""
    issues: list[str] = []
    if tone_label == "direct":
        issues.append("too direct")
    if tone_label == "frustrated":
        issues.append("sounds frustrated")
    if tone_label == "anxious":
        issues.append("sounds anxious")
    if intent == "unknown":
        issues.append("intent unclear")
    if strategy == "bald_on_record" and imposition == "high":
        issues.append("too blunt for a high-imposition request")
    return issues


def analyze(
    *,
    text: str,
    goal: str | None = None,
    context: ContextFactors | None = None,
    tone: str = "polite",
    directness: str = "balanced",
) -> AnalyzeResponse:
    """Rule-engine-only analysis (deterministic baseline, no LLM call).

    Spec fields (``scenario``, ``face_threat``, ``detected_strategy``,
    ``issues``) are derived from the engine result; the engine's own
    fields are kept alongside, verbatim.
    """
    context = context or ContextFactors()
    hint = resolve_goal_intent(goal, text)
    result = analysis_engine.analyze(
        text,
        hint,  # type: ignore[arg-type]
        context.model_dump(),
        draft_tone=_TONE_MAP.get(tone, "Diplomatic"),
        draft_directness=directness,
    )
    intent = result["intent"]["label"]
    imposition = result["context_factors"]["imposition"]
    detected = to_spec_strategy(result["strategy"]["label"])
    return AnalyzeResponse(
        scenario=intent_to_scenario(intent, text),
        face_threat=_face_threat(imposition, result["fta"]["detected"]),  # type: ignore[arg-type]
        detected_strategy=detected,
        issues=_analyze_issues(
            tone_label=result["tone"]["label"],
            intent=intent,
            strategy=detected,
            imposition=imposition,
        ),
        intent=result["intent"],
        tone=result["tone"],
        fta=result["fta"],
        face_concern=result["face_concern"],
        context_factors=ContextFactors(**result["context_factors"]),
        strategy=result["strategy"],
        draft=result["draft"],
        limitations=result["limitations"],
        model_version=result["model_version"],
    )
