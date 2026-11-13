"""Typed request/response schemas for the Phase 0-2 API (FastAPI + Pydantic v2).

Contract authority: ``docs/openapi.yaml`` (Option A, 2026-11-13 — the
code was aligned to the spec, not the other way round):

- request field is ``text`` (1-4000 chars); ``goal`` is an optional
  **free string** (max 300 chars), NOT one of the 7 engine intents —
  the API maps free-text goals to intents internally (see
  ``services/suggest.resolve_goal_intent``) and the engine detects the
  intent from the text when no usable goal is given;
- ``POST /v1/suggest`` returns ``replies`` as ``[{tone, text}]`` objects
  (3 replies, tones polite/friendly/firm/formal) plus a ``suggestion_id``
  (uuid) and an **integer** ``score`` 0-100;
- ``POST /v1/analyze`` returns the spec fields ``scenario``,
  ``face_threat`` (low/medium/high), ``detected_strategy`` and
  ``issues[]`` as its primary fields;
- strategies are the spec enum only: bald_on_record, positive_politeness,
  negative_politeness, off_record. The rule engine can still return
  ``avoidance`` internally (its golden set has one such case); the API
  boundary maps it to ``off_record`` (see ``services/suggest``).

Extra response fields (``intent``, ``strategy_rationale``, ``source``,
``llm_status``) are kept alongside the spec fields so the caller always
knows whether the answer came from the LLM or the rule-based fallback
and which engine intent was detected — they do not change the spec
shape. P/D/R values are from {unknown, low, medium, high} and are never
inferred from the message text.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

ContextLevel = Literal["unknown", "low", "medium", "high"]

# The 7 intents of the rule-based engine (live repo, prototype-0.1).
# Used only as an internal mapping target — never as a request constraint.
GOALS = (
    "set_boundary",
    "request_payment",
    "negotiate_deadline",
    "clarify_requirements",
    "respond_to_criticism",
    "negotiate_budget",
    "resolve_disagreement",
)

# The 10 scenarios of the FYP plan (docs/DATASET_SPEC.md §10.1).
SCENARIOS = (
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
)

# Strategy enum from docs/openapi.yaml (4 values — no 'avoidance').
STRATEGIES = (
    "bald_on_record",
    "positive_politeness",
    "negative_politeness",
    "off_record",
)

TONES = ("polite", "friendly", "firm", "formal")
ENGINE_TONES = ("Professional", "Friendly", "Diplomatic", "Assertive", "Empathetic")
DIRECTNESS_OPTIONS = ("direct", "balanced", "gentle")


class ContextFactors(BaseModel):
    power: ContextLevel = "unknown"
    social_distance: ContextLevel = "unknown"
    imposition: ContextLevel = "unknown"


class Reply(BaseModel):
    """One suggested reply (openapi.yaml ``Reply`` schema)."""

    tone: str = Field(..., description="polite | friendly | firm | formal")
    text: str = Field(..., min_length=1, max_length=2000)

    def model_post_init(self, __context, /) -> None:
        if self.tone not in TONES:
            raise ValueError(f"tone must be one of {', '.join(TONES)}.")


class SuggestRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    goal: str | None = Field(
        default=None,
        max_length=300,
        description="Optional free-text goal (e.g. 'ask for payment'); mapped to an engine intent internally.",
    )
    context: ContextFactors = Field(default_factory=ContextFactors)
    tone: str = Field(default="polite", description="polite | friendly | firm | formal")
    directness: str = Field(default="balanced", description="direct | balanced | gentle")

    def model_post_init(self, __context, /) -> None:
        if self.tone not in TONES:
            raise ValueError(f"tone must be one of {', '.join(TONES)}.")
        if self.directness not in DIRECTNESS_OPTIONS:
            raise ValueError(
                f"directness must be one of {', '.join(DIRECTNESS_OPTIONS)}."
            )


class AnalyzeRequest(BaseModel):
    """Same input as /v1/suggest; answered by the rule engine only."""

    text: str = Field(..., min_length=1, max_length=4000)
    goal: str | None = Field(
        default=None,
        max_length=300,
        description="Optional free-text goal; the engine detects the intent from the text when absent.",
    )
    context: ContextFactors = Field(default_factory=ContextFactors)
    tone: str = Field(default="polite", description="polite | friendly | firm | formal")
    directness: str = Field(default="balanced", description="direct | balanced | gentle")

    def model_post_init(self, __context, /) -> None:
        if self.tone not in TONES:
            raise ValueError(f"tone must be one of {', '.join(TONES)}.")
        if self.directness not in DIRECTNESS_OPTIONS:
            raise ValueError(
                f"directness must be one of {', '.join(DIRECTNESS_OPTIONS)}."
            )


class SuggestResponse(BaseModel):
    """openapi.yaml ``SuggestResponse`` + honest extras (see module docstring)."""

    scenario: str
    strategy: str
    replies: list[Reply] = Field(..., min_length=3, max_length=3)
    explanation: str
    score: int = Field(..., ge=0, le=100, description="Politeness score, integer 0-100.")
    model_version: str
    suggestion_id: uuid.UUID = Field(..., description="UUID generated per suggestion.")
    # Extras beyond the spec shape (never replace a spec field):
    intent: str
    strategy_rationale: str
    llm_score: int | None = Field(
        default=None, description="Score the LLM itself reported, if any."
    )
    source: str = Field(..., description="'llm' or 'rule_based'.")
    llm_status: str = Field(
        ...,
        description="ok | disabled | rate_limited | invalid_response | blocked_injection | error",
    )
    limitations: list[str] = Field(default_factory=list)

    def model_post_init(self, __context, /) -> None:
        if self.strategy not in STRATEGIES:
            raise ValueError(f"strategy must be one of {', '.join(STRATEGIES)}.")


class AnalyzeResponse(BaseModel):
    """Spec fields first (openapi.yaml / API_SPEC.md), engine detail alongside."""

    # Spec fields (primary):
    scenario: str
    face_threat: Literal["low", "medium", "high"]
    detected_strategy: str
    issues: list[str] = Field(default_factory=list)
    # Engine detail (verbatim from the rule engine, prototype-0.1):
    intent: dict
    tone: dict
    fta: dict
    face_concern: list[str]
    context_factors: ContextFactors
    strategy: dict
    draft: str
    limitations: list[str]
    model_version: str
    source: str = "rule_based"

    def model_post_init(self, __context, /) -> None:
        if self.detected_strategy not in STRATEGIES:
            raise ValueError(
                f"detected_strategy must be one of {', '.join(STRATEGIES)}."
            )
