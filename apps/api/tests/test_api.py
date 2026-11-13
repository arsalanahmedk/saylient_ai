"""HTTP endpoint tests (no LLM key configured in this environment, so
``POST /v1/suggest`` is exercised on its rule-based fallback path;
the LLM paths are covered in ``test_llm_client.py`` / ``test_suggest.py``).

Contract under test is ``docs/openapi.yaml`` (Option A): request field
``text`` (max 4,000), free-text ``goal``, replies as ``{tone, text}``
objects + ``suggestion_id`` + integer ``score``, spec analyze fields,
16 KB body cap.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_health_reports_llm_disabled() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_enabled"] is False
    assert body["llm_provider"] == "none"
    assert response.headers["X-Request-Id"]


def test_suggest_falls_back_to_rule_engine_without_key() -> None:
    response = client.post(
        "/v1/suggest",
        json={
            "text": "The invoice #1048 is two weeks overdue. When will I be paid?",
            "goal": "ask for my payment",
            "context": {"power": "unknown", "social_distance": "medium", "imposition": "high"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "rule_based"
    assert body["llm_status"] == "disabled"
    assert body["scenario"] == "late_payment"
    assert body["intent"] == "request_payment"
    assert body["strategy"] in {
        "bald_on_record",
        "positive_politeness",
        "negative_politeness",
        "off_record",
    }
    # Spec shape: 3 reply objects, valid suggestion_id, integer score.
    assert len(body["replies"]) == 3
    assert [reply["tone"] for reply in body["replies"]] == [
        "polite",
        "friendly",
        "firm",
    ]
    assert "#1048" in body["replies"][0]["text"]
    uuid.UUID(body["suggestion_id"])  # raises unless a valid uuid string
    assert isinstance(body["score"], int)
    assert 0 <= body["score"] <= 100


def test_suggest_free_text_goal_is_accepted() -> None:
    """Spec: goal is a free string, not an intent label (Option A)."""
    response = client.post(
        "/v1/suggest",
        json={"text": "Can we move the deadline to Friday?", "goal": "I need more time"},
    )
    assert response.status_code == 200
    assert response.json()["scenario"] == "deadline_extension"


def test_suggest_without_goal_still_works() -> None:
    response = client.post(
        "/v1/suggest",
        json={"text": "The invoice #1048 is two weeks overdue. When will I be paid?"},
    )
    assert response.status_code == 200
    assert response.json()["scenario"] == "late_payment"


def test_analyze_returns_spec_fields() -> None:
    response = client.post(
        "/v1/analyze",
        json={
            "text": "Could we move the deadline to Friday?",
            "goal": "negotiate the deadline",
            "context": {"power": "unknown", "social_distance": "medium", "imposition": "medium"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "rule_based"
    # Spec fields (primary):
    assert body["scenario"] == "deadline_extension"
    assert body["face_threat"] in {"low", "medium", "high"}
    assert body["detected_strategy"] in {
        "bald_on_record",
        "positive_politeness",
        "negative_politeness",
        "off_record",
    }
    assert isinstance(body["issues"], list)
    # Engine detail kept alongside:
    assert body["intent"]["label"] == "negotiate_deadline"
    assert body["strategy"]["label"] == "negative_politeness"
    assert body["model_version"] == "prototype-0.1"
    assert body["draft"]
    assert body["limitations"]


def test_analyze_without_goal_still_works() -> None:
    response = client.post(
        "/v1/analyze", json={"text": "Could we move the deadline to Friday?"}
    )
    assert response.status_code == 200
    assert response.json()["scenario"] == "deadline_extension"


def test_suggest_rejects_empty_text() -> None:
    response = client.post("/v1/suggest", json={"text": "", "goal": "ask for payment"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_suggest_rejects_text_over_4000_chars() -> None:
    response = client.post("/v1/suggest", json={"text": "x" * 4001})
    assert response.status_code == 422


def test_suggest_rejects_goal_over_300_chars() -> None:
    response = client.post(
        "/v1/suggest", json={"text": "Hello.", "goal": "x" * 301}
    )
    assert response.status_code == 422


def test_oversized_body_is_413() -> None:
    # Spec body cap is 16 KB; a ~17 KB text body must be rejected first.
    response = client.post(
        "/v1/suggest",
        json={"text": "x" * 17_000, "goal": "ask for payment"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "TOO_LARGE"


def test_unknown_route_uses_the_error_envelope() -> None:
    response = client.get("/v1/nope")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["request_id"]
    assert response.headers["X-Request-Id"]


def test_security_headers_present() -> None:
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
