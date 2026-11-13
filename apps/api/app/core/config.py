"""Application configuration, validated at startup.

Ported from the live repo (``backend/app/core/config.py``) and extended
with the LLM provider settings for Phase 2. No secret is ever committed;
put real values in a local ``.env`` file or in the deployment
environment. See ``docs/LLM_CHOICE.md`` for why these providers were
chosen and what their free-tier limits are.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

# OpenAI-compatible chat-completions endpoints. Gemini's is the
# Google AI Studio endpoint; Groq's is the standard Groq endpoint.
PROVIDER_BASE_URLS: dict[str, str] = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1",
}

DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-2.5-flash",
    "groq": "openai/gpt-oss-120b",
}

VALID_PROVIDERS = frozenset({"gemini", "groq", "none", ""})


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    allowed_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    # Spec (docs/API_SPEC.md): max body 16 KB -> 413 above it.
    max_body_bytes: int = 16_384
    llm_timeout_seconds: float = 20.0

    # LLM provider. "" or "none" means: no external calls, the rule-based
    # engine (prototype-0.1) answers everything. See docs/LLM_CHOICE.md.
    ai_provider: str = ""
    ai_api_key: str = ""
    ai_model: str = ""

    @property
    def provider(self) -> str:
        """Normalised provider name: ``gemini`` | ``groq`` | ``none``."""
        name = (self.ai_provider or "").strip().lower()
        return name if name else "none"

    @property
    def llm_enabled(self) -> bool:
        return self.provider in {"gemini", "groq"} and bool(self.ai_api_key)

    @property
    def llm_base_url(self) -> str:
        return PROVIDER_BASE_URLS.get(self.provider, "")

    @property
    def llm_model(self) -> str:
        if self.ai_model:
            return self.ai_model
        return DEFAULT_MODELS.get(self.provider, "")

    def validate(self) -> None:
        if self.provider not in VALID_PROVIDERS:
            raise ValueError(
                f"AI_PROVIDER must be one of gemini, groq or none, got {self.ai_provider!r}."
            )
        if self.provider in {"gemini", "groq"} and not self.ai_api_key:
            # Not fatal: the service degrades to the rule-based engine and
            # says so in every response (source=rule_based). Failing to
            # start would break local development without a key.
            pass


def _origins_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return tuple(o.strip() for o in raw.split(",") if o.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read configuration from the environment and validate it."""
    settings = Settings(
        app_env=os.environ.get("APP_ENV", "development").strip().lower()
        or "development",
        allowed_origins=_origins_env(
            "ALLOWED_ORIGINS",
            ("http://localhost:5173", "http://127.0.0.1:5173"),
        ),
        ai_provider=os.environ.get("AI_PROVIDER", "").strip(),
        ai_api_key=os.environ.get("AI_API_KEY", "").strip(),
        ai_model=os.environ.get("AI_MODEL", "").strip(),
        llm_timeout_seconds=float(
            os.environ.get("AI_TIMEOUT_SECONDS", "20") or 20
        ),
    )
    settings.validate()
    return settings
