"""LLM provider adapter (Phase 2 baseline).

One small client for every provider, speaking the OpenAI-compatible
``/chat/completions`` API over ``httpx``:

- **Gemini (primary)** — Google AI Studio free tier, model
  ``gemini-2.5-flash`` by default, base URL
  ``https://generativelanguage.googleapis.com/v1beta/openai/``.
- **Groq (fallback)** — Groq free plan, model ``openai/gpt-oss-120b`` by
  default, base URL ``https://api.groq.com/openai/v1``.

See ``docs/LLM_CHOICE.md`` for the limits and caveats of both free
tiers. The fine-tuned model (Qwen2.5-3B-Instruct + QLoRA, ``ml/``) is
the FYP research contribution and is served separately later; it is not
a provider here yet.

Behaviour contract (the caller, ``services/suggest.py``, relies on it):

- No key configured, or provider ``none`` -> :class:`LLMDisabled`
  *without* making a network call.
- HTTP 429 (quota / rate limit) -> :class:`LLMRateLimited`.
- Any other HTTP error, timeout, or network failure -> :class:`LLMError`.
- The model answers with strict JSON matching :class:`LLMOutput`. If the
  first answer is not valid JSON, the client retries **once** with a
  repair message ("reply with JSON only"); a second failure raises
  :class:`LLMInvalidResponse`. The caller then falls back to the
  rule-based engine — an LLM failure never becomes a user-facing error.
- Prompt-injection guardrails live in ``guardrails.py`` and are applied
  here before any call: :func:`guardrails.detect_injection` decides,
  and the untrusted message is always sent inside delimiters, separate
  from the system prompt.
- ``transport`` exists only so tests can inject ``httpx.MockTransport``;
  production always uses a real ``httpx.Client`` with a 20 s timeout.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings, get_settings
from app.schemas import Reply
from app.services import guardrails

logger = logging.getLogger("saylient.llm")

# One retry for invalid JSON, then give up and let the caller fall back.
_MAX_ATTEMPTS = 2

_FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*(?P<body>\{.*?\})\s*```", re.IGNORECASE | re.DOTALL
)

_VALID_SCENARIOS = {
    "late_payment",
    "deadline_extension",
    "scope_creep",
    "revision_limit",
    "low-budget_offer",
    "ghosting_follow_up",
    "rude_client",
    "refund_demand",
    "boundary_setting",
    "compliment_negotiation",
}
# Spec enum (docs/openapi.yaml) — no 'avoidance'; the API boundary maps
# the engine's internal 'avoidance' to 'off_record', and the LLM must
# never return it (a violation fails validation -> repair retry).
_VALID_STRATEGIES = {
    "bald_on_record",
    "positive_politeness",
    "negative_politeness",
    "off_record",
}


class LLMError(Exception):
    """Base class: any LLM failure the caller should fall back from."""


class LLMDisabled(LLMError):
    """No provider / no key configured — fall back without a network call."""


class LLMRateLimited(LLMError):
    """Provider answered 429 (quota or rate limit) — fall back, don't retry."""


class LLMInvalidResponse(LLMError):
    """The model did not return valid contract JSON after one retry."""


class LLMBlocked(LLMError):
    """The message tripped the prompt-injection guardrail."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class LLMOutput(BaseModel):
    """Strict contract for the LLM's JSON answer (plan §10.2, openapi.yaml).

    Replies are ``{tone, text}`` objects — exactly 3, each with a
    distinct tone from polite/friendly/firm/formal — matching the spec's
    ``SuggestResponse`` shape. ``score`` is the LLM's own politeness
    estimate; the API's integer ``score`` is computed from the first
    reply instead (see ``services/suggest``).
    """

    scenario: str
    strategy: str
    replies: list[Reply] = Field(..., min_length=3, max_length=3)
    explanation: str = Field(..., min_length=1, max_length=1000)
    score: float = Field(..., ge=0, le=100)

    def model_post_init(self, __context, /) -> None:
        if self.scenario not in _VALID_SCENARIOS:
            raise ValueError(f"unknown scenario: {self.scenario!r}")
        if self.strategy not in _VALID_STRATEGIES:
            raise ValueError(f"unknown strategy: {self.strategy!r}")
        tones = [reply.tone for reply in self.replies]
        if len(set(tones)) != len(tones):
            raise ValueError("each reply must have a distinct tone")


def _extract_json(text: str) -> dict[str, Any]:
    """Parse the model's answer as JSON.

    Accepts bare JSON or JSON inside a single markdown fence — models
    often wrap it despite being told not to. Anything else is invalid.
    """
    candidate = (text or "").strip()
    if not candidate:
        raise ValueError("empty response")
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        fenced = _FENCED_JSON_RE.search(candidate)
        if not fenced:
            raise ValueError("response is not JSON") from None
        parsed = json.loads(fenced.group("body"))
    if not isinstance(parsed, dict):
        raise TypeError("response JSON is not an object")
    return parsed


def _user_prompt(text: str, goal: str | None, tone: str) -> str:
    goal_line = f"User's goal (free text): {goal}.\n" if goal else ""
    return (
        f"{goal_line}Preferred tone: {tone}.\n\n"
        "Write 3 polite reply options for the freelancer to send, "
        "from most gentle to most direct, each as an object with a "
        "distinct tone (polite, friendly, firm, formal).\n\n"
        f"{guardrails.wrap_user_message(text)}"
    )


class LLMClient:
    """Thin OpenAI-compatible chat-completions client for one provider."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._transport = transport

    # -- public API -----------------------------------------------------
    def generate(
        self, *, text: str, goal: str | None = None, tone: str = "polite"
    ) -> LLMOutput:
        """Ask the LLM for a suggestion, or raise an :class:`LLMError`.

        Raises :class:`LLMDisabled` without a network call when no
        provider/key is configured, :class:`LLMBlocked` when the
        injection guardrail trips, :class:`LLMRateLimited` on 429, and
        :class:`LLMInvalidResponse` after one failed JSON repair retry.
        """
        settings = self.settings
        if not settings.llm_enabled:
            raise LLMDisabled("no LLM provider/key configured (AI_PROVIDER/AI_API_KEY)")

        blocked_reason = guardrails.detect_injection(text)
        if blocked_reason:
            raise LLMBlocked(blocked_reason)

        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        messages: list[dict[str, str]] = [
            {"role": "system", "content": guardrails.SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(text, goal, tone)},
        ]

        last_error: Exception | None = None
        with httpx.Client(
            transport=self._transport, timeout=settings.llm_timeout_seconds
        ) as client:
            for attempt in range(1, _MAX_ATTEMPTS + 1):
                try:
                    response = client.post(
                        url,
                        headers=headers,
                        json={
                            "model": settings.llm_model,
                            "messages": messages,
                            "temperature": 0.7,
                            "max_tokens": 800,
                            "response_format": {"type": "json_object"},
                        },
                    )
                except httpx.TimeoutException as exc:
                    raise LLMError(f"LLM request timed out after {settings.llm_timeout_seconds}s") from exc
                except httpx.HTTPError as exc:
                    raise LLMError(f"LLM request failed: {exc}") from exc

                if response.status_code == 429:
                    raise LLMRateLimited(
                        "provider rate limit / quota exhausted (HTTP 429)"
                    )
                if response.status_code >= 400:
                    raise LLMError(
                        f"provider returned HTTP {response.status_code}"
                    )

                try:
                    payload = response.json()
                    content = payload["choices"][0]["message"]["content"]
                    return LLMOutput.model_validate(_extract_json(content))
                except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
                    last_error = exc
                    logger.warning(
                        "LLM invalid response (attempt %s/%s): %s",
                        attempt,
                        _MAX_ATTEMPTS,
                        exc,
                    )
                    if attempt == _MAX_ATTEMPTS:
                        break
                    # One repair retry: ask for JSON only, keeping the
                    # conversation (the model sees its own bad answer).
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your last reply was not valid JSON in the "
                                "required shape. Reply again with JSON ONLY, "
                                "exactly the shape from the system prompt, "
                                "no other text."
                            ),
                        }
                    )
        raise LLMInvalidResponse(
            f"LLM did not return valid contract JSON after {_MAX_ATTEMPTS} attempts: {last_error}"
        )


def generate_suggestion(
    *, text: str, goal: str | None = None, tone: str = "polite"
) -> LLMOutput:
    """Convenience wrapper using the default settings (one-shot call)."""
    return LLMClient().generate(text=text, goal=goal, tone=tone)
