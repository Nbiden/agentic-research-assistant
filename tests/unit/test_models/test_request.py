"""Unit tests for the ResearchQuestion Pydantic v2 model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.request import ResearchQuestion


def test_valid_question() -> None:
    q = ResearchQuestion(question="What is RAG?")
    assert q.question == "What is RAG?"
    assert q.max_sources == 5
    assert q.include_trace is True


def test_question_too_short() -> None:
    with pytest.raises(ValidationError, match="at least 1 character"):
        ResearchQuestion(question="")


def test_question_too_long() -> None:
    with pytest.raises(ValidationError):
        ResearchQuestion(question="x" * 2001)


def test_max_sources_bounds() -> None:
    with pytest.raises(ValidationError):
        ResearchQuestion(question="test", max_sources=0)
    with pytest.raises(ValidationError):
        ResearchQuestion(question="test", max_sources=21)


def test_max_sources_valid_bounds() -> None:
    q1 = ResearchQuestion(question="test", max_sources=1)
    q2 = ResearchQuestion(question="test", max_sources=20)
    assert q1.max_sources == 1
    assert q2.max_sources == 20


def test_submitted_at_defaults_to_now() -> None:
    q = ResearchQuestion(question="test")
    assert q.submitted_at is not None
