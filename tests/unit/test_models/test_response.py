"""Unit tests for response Pydantic v2 models and the uncertainty validator."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.response import (
    DecisionTrace,
    ResearchResponse,
    Source,
    SourceType,
    ToolCall,
)


def _make_source(**kwargs) -> Source:
    defaults = dict(
        content="test content",
        identifier="https://example.com",
        relevance_score=0.8,
        source_type=SourceType.WEB,
    )
    return Source(**(defaults | kwargs))


def _make_tool_call(**kwargs) -> ToolCall:
    defaults = dict(
        tool_name="web_search",
        rationale="needed current info",
        input_summary="query: test",
        output_summary="found 3 results",
        success=True,
        elapsed_ms=500,
    )
    return ToolCall(**(defaults | kwargs))


def test_source_type_enum_values() -> None:
    assert SourceType.WEB.value == "web"
    assert SourceType.KNOWLEDGE_BASE.value == "knowledge_base"
    assert SourceType.LLM.value == "llm"


def test_source_relevance_bounds() -> None:
    with pytest.raises(ValidationError):
        _make_source(relevance_score=-0.1)
    with pytest.raises(ValidationError):
        _make_source(relevance_score=1.1)


def test_tool_call_valid() -> None:
    tc = _make_tool_call()
    assert tc.success is True
    assert tc.elapsed_ms == 500
    assert tc.error_message is None


def test_tool_call_failed_with_message() -> None:
    tc = _make_tool_call(success=False, error_message="Connection refused")
    assert tc.success is False
    assert tc.error_message == "Connection refused"


def test_research_response_high_confidence_no_uncertainty_required() -> None:
    resp = ResearchResponse(
        answer="RAG combines retrieval with generation for better answers.",
        sources=[_make_source()],
        confidence_score=0.85,
    )
    assert resp.confidence_score == pytest.approx(0.85)


def test_research_response_low_confidence_requires_uncertainty_phrase() -> None:
    with pytest.raises(ValidationError, match="uncertainty language"):
        ResearchResponse(
            answer="RAG is a technique for improving LLMs.",
            sources=[],
            confidence_score=0.3,
        )


def test_research_response_low_confidence_with_uncertainty_phrase_passes() -> None:
    resp = ResearchResponse(
        answer="I have limited reliable information on this topic. RAG may refer to retrieval.",
        sources=[],
        confidence_score=0.3,
    )
    assert resp.confidence_score == pytest.approx(0.3)


def test_research_response_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        ResearchResponse(answer="test", sources=[], confidence_score=-0.1)
    with pytest.raises(ValidationError):
        ResearchResponse(answer="test", sources=[], confidence_score=1.1)


def test_decision_trace_valid() -> None:
    trace = DecisionTrace(
        tool_calls=[_make_tool_call()],
        total_elapsed_ms=500,
        nodes_visited=["agent", "tools", "synthesize"],
    )
    assert len(trace.tool_calls) == 1
    assert trace.nodes_visited[0] == "agent"
