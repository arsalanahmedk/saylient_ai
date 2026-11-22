"""Rule-based engine tests, ported from the live repo.

The golden set (``eval/golden.json``, 12 hand-labelled examples) is the
live repo's own evaluation: the test requires >= 10/12 agreement on both
intent and strategy, and the live repo measured 12/12 on 2026-11-12.
The same bar applies here — the port must not change engine behaviour.

Honest caveat (live repo README): the golden set is small, hand-written
and keyword-aligned with the engine, so it measures rule consistency,
not generalisation to real freelancer messages. Real evaluation needs
the held-out, double-annotated dataset (``ml/data/``).
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.services import analysis_engine

GOLDEN_PATH = pathlib.Path(__file__).resolve().parent.parent / "eval" / "golden.json"


@pytest.fixture(scope="module")
def golden_examples() -> list[dict]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_golden_set_has_12_examples(golden_examples) -> None:
    assert len(golden_examples) == 12


def test_golden_set_agreement(golden_examples) -> None:
    result = analysis_engine.evaluate_examples(golden_examples)
    print(result)  # visible with `pytest -s`, like the live repo
    assert result["intent_correct"] >= 10, result["disagreements"]
    assert result["strategy_correct"] >= 10, result["disagreements"]


def test_golden_set_full_agreement(golden_examples) -> None:
    """The live repo measured 12/12 on both; the port must match it."""
    result = analysis_engine.evaluate_examples(golden_examples)
    assert result["intent_correct"] == 12, result["disagreements"]
    assert result["strategy_correct"] == 12, result["disagreements"]


def test_pdr_unknown_is_never_guessed() -> None:
    result = analysis_engine.analyze(
        "The invoice is overdue, please pay soon.",
        "request_payment",
        {"power": "unknown", "social_distance": "unknown", "imposition": "unknown"},
    )
    assert result["context_factors"] == {
        "power": "unknown",
        "social_distance": "unknown",
        "imposition": "unknown",
    }
    assert any("unknown" in limitation for limitation in result["limitations"])


def test_draft_reuses_only_facts_from_the_message() -> None:
    result = analysis_engine.analyze(
        "Hi, invoice #1048 for $250 was due on Friday. Could you check?",
        "request_payment",
        {"power": "unknown", "social_distance": "medium", "imposition": "high"},
    )
    assert "#1048" in result["draft"]
    assert "$250" not in result["draft"]  # amounts are not reused in the core
    assert result["model_version"] == "prototype-0.1"
    assert result["limitations"]  # at least one limitation, always


def test_invoice_word_after_invoice_is_not_a_reference() -> None:
    """Regression: 'invoice when...' must not render 'invoice #when'.

    Only a real invoice number/reference (digits, or an alnum code
    containing digits such as INV-1048) is reused in the draft.
    """
    ctx = {"power": "unknown", "social_distance": "medium", "imposition": "high"}
    # Plain word after "invoice" -> no invoice fact, no "#when" in the draft.
    assert (
        analysis_engine.extract_facts(
            "Could you check in on invoice when the payment will be sent?"
        )["invoice"]
        is None
    )
    result = analysis_engine.analyze(
        "Could you check in on invoice when the payment will be sent?",
        "request_payment",
        ctx,
    )
    assert "#when" not in result["draft"]
    assert "invoice #" not in result["draft"]
    # Real references are still kept: bare digits and alnum codes.
    assert (
        analysis_engine.extract_facts("Following up on invoice 1048, please.")[
            "invoice"
        ]
        == "#1048"
    )
    assert (
        analysis_engine.extract_facts("Following up on invoice INV-1048, please.")[
            "invoice"
        ]
        == "#INV-1048"
    )
    assert (
        analysis_engine.extract_facts("Following up on invoice #1048, please.")[
            "invoice"
        ]
        == "#1048"
    )
    numbered = analysis_engine.analyze(
        "Following up on invoice INV-1048, please pay soon.",
        "request_payment",
        ctx,
    )
    assert "#INV-1048" in numbered["draft"]


def test_invalid_context_level_raises() -> None:
    with pytest.raises(ValueError):
        analysis_engine.analyze(
            "Hello.", "set_boundary", {"power": "huge", "social_distance": "low", "imposition": "low"}
        )


def test_empty_message_intent_is_unknown() -> None:
    result = analysis_engine.analyze(
        "Hello there.", "set_boundary",
        {"power": "unknown", "social_distance": "unknown", "imposition": "unknown"},
    )
    assert result["intent"]["label"] == "unknown"
    assert result["intent"]["confidence"] == 0.20
