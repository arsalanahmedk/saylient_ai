"""Pytest configuration for the Phase 0-2 API.

The API reads its settings once (``get_settings`` is cached) when
``app.main`` is imported, so the test environment is fixed here, before
any test module imports the app: no LLM provider, localhost CORS only.
Tests that need a provider pass explicit ``Settings`` / mock transports
to ``LLMClient`` instead of touching global state.
"""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AI_PROVIDER", "")
os.environ.setdefault("AI_API_KEY", "")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

from app.core.config import get_settings

get_settings.cache_clear()
