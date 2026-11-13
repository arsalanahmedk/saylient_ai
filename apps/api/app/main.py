"""Application factory (Phase 0-2).

Stateless by design for this phase: no database, no auth — the live
repo already owns auth/history/templates, and this monorepo's API grows
those in a later phase (see ``docs/API_SPEC.md`` and ``docs/ROADMAP.md``).
What this app does:

- ``GET /health`` — liveness, includes whether an LLM is configured
  (never the key, never the model output).
- ``POST /v1/analyze`` — rule-engine-only analysis (deterministic).
- ``POST /v1/suggest`` — LLM-first suggestion with rule-based fallback.

Wiring (adapted from the live repo's ``backend/app/main.py``):
- one error envelope for every failure, ``X-Request-Id`` on every
  response, 16 KB JSON body cap per the spec (413 above it), security
  headers, CORS from ``ALLOWED_ORIGINS``, structured logs that never
  contain message bodies.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.schemas import AnalyzeRequest, AnalyzeResponse, SuggestRequest, SuggestResponse
from app.services import suggest as suggest_service

logger = logging.getLogger("saylient")


def _error_response(
    request: Request, *, status: int, code: str, message: str,
    details: list | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    body = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": details or [],
        }
    }
    return JSONResponse(
        status_code=status, content=body, headers={"X-Request-Id": request_id}
    )


_HTTP_STATUS_TO_CODE = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "VALIDATION_ERROR",
    409: "CONFLICT",
    413: "TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        logger.info(
            json.dumps(
                {
                    "level": "info",
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "request_id": request_id,
                }
            )
        )
        return response


class BodySizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        body = await request.body()
        if len(body) > settings.max_body_bytes:
            return _error_response(
                request,
                status=413,
                code="TOO_LARGE",
                message="The request body is too large.",
            )
        return await call_next(request)


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    app = FastAPI(
        title="Saylient AI API",
        description=(
            "AI-based freelancer communication assistant — monorepo Phase 0-2: "
            "rule-based baseline + LLM provider adapter (Gemini / Groq)."
        ),
        version="0.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
    )
    app.add_middleware(BodySizeMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Strip "input"/"ctx": they can contain the user's raw message.
        details = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg", "")}
            for err in exc.errors()
        ]
        return _error_response(
            request,
            status=422,
            code="VALIDATION_ERROR",
            message="Please review the submitted fields.",
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = _HTTP_STATUS_TO_CODE.get(exc.status_code, "INTERNAL")
        message = exc.detail if isinstance(exc.detail, str) else "Not found."
        return _error_response(
            request, status=exc.status_code, code=code, message=message
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            json.dumps(
                {
                    "level": "error",
                    "path": request.url.path,
                    "request_id": getattr(request.state, "request_id", None),
                    "error": type(exc).__name__,
                }
            )
        )
        return _error_response(
            request,
            status=500,
            code="INTERNAL",
            message="Something went wrong. Please try again.",
        )

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "llm_provider": settings.provider,
            "llm_enabled": settings.llm_enabled,
            "llm_model": settings.llm_model if settings.llm_enabled else None,
        }

    @app.post("/v1/analyze", response_model=AnalyzeResponse)
    def analyze_endpoint(payload: AnalyzeRequest) -> AnalyzeResponse:
        return suggest_service.analyze(
            text=payload.text,
            goal=payload.goal,
            context=payload.context,
            tone=payload.tone,
            directness=payload.directness,
        )

    @app.post("/v1/suggest", response_model=SuggestResponse)
    def suggest_endpoint(payload: SuggestRequest) -> SuggestResponse:
        return suggest_service.suggest(
            text=payload.text,
            goal=payload.goal,
            context=payload.context,
            tone=payload.tone,
            directness=payload.directness,
        )

    return app


app = create_app()

__all__ = ["app", "create_app"]
