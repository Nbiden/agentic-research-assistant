"""Unit tests for agent node functions: agent_node, synthesize_node, format_response_node."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage


def _base_state(**overrides) -> dict:
    state = {
        "question": "What is RAG?",
        "include_trace": True,
        "max_sources": 5,
        "messages": [HumanMessage(content="What is RAG?")],
        "web_results": [],
        "kb_results": [],
        "tool_calls_log": [],
        "nodes_visited": [],
        "synthesized_answer": None,
        "sources": [],
        "confidence_score": None,
        "degraded": False,
        "error_context": None,
    }
    state.update(overrides)
    return state


# --- agent_node ---


@pytest.mark.asyncio()
async def test_agent_node_appends_ai_message() -> None:
    """agent_node appends the LLM's AIMessage to state.messages."""
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="I'll search for that."))

    with (
        patch("src.agent.nodes._get_llm", return_value=mock_llm),
        patch("src.agent.nodes.registry") as mock_registry,
    ):
        mock_registry.build_tool_list.return_value = []
        result = await _import_and_call_agent_node(_base_state())

    assert "messages" in result
    assert any(isinstance(m, AIMessage) for m in result["messages"])


@pytest.mark.asyncio()
async def test_agent_node_records_tool_calls() -> None:
    """agent_node records partial ToolCall entries for each requested tool call."""
    tool_call = {"name": "web_search", "args": {"query": "RAG"}, "id": "call_1"}
    ai_message = AIMessage(content="", tool_calls=[tool_call])
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(return_value=ai_message)

    with (
        patch("src.agent.nodes._get_llm", return_value=mock_llm),
        patch("src.agent.nodes.registry") as mock_registry,
    ):
        mock_registry.build_tool_list.return_value = []
        result = await _import_and_call_agent_node(_base_state())

    assert len(result.get("tool_calls_log", [])) == 1
    assert result["tool_calls_log"][0].tool_name == "web_search"


@pytest.mark.asyncio()
async def test_agent_node_updates_nodes_visited() -> None:
    """agent_node appends 'agent' to nodes_visited."""
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="answer"))

    with (
        patch("src.agent.nodes._get_llm", return_value=mock_llm),
        patch("src.agent.nodes.registry") as mock_registry,
    ):
        mock_registry.build_tool_list.return_value = []
        result = await _import_and_call_agent_node(_base_state())

    assert "agent" in result["nodes_visited"]


# --- format_response_node ---


@pytest.mark.asyncio()
async def test_format_response_include_trace_true() -> None:
    """format_response_node builds DecisionTrace when include_trace=True."""
    from src.models.response import ToolCall

    tc = ToolCall(
        tool_name="web_search",
        rationale="needed info",
        input_summary="query",
        output_summary="pending",
        success=True,
        elapsed_ms=100,
    )
    state = _base_state(
        synthesized_answer="RAG combines retrieval and generation.",
        confidence_score=0.8,
        sources=[],
        tool_calls_log=[tc],
        include_trace=True,
    )
    result = await _import_and_call_format_response_node(state)

    assert result.get("_response") is not None
    response = result["_response"]
    assert response.decision_trace is not None
    assert len(response.decision_trace.tool_calls) == 1


@pytest.mark.asyncio()
async def test_format_response_include_trace_false() -> None:
    """format_response_node sets decision_trace=None when include_trace=False."""
    state = _base_state(
        synthesized_answer="RAG combines retrieval and generation.",
        confidence_score=0.8,
        sources=[],
        tool_calls_log=[],
        include_trace=False,
    )
    result = await _import_and_call_format_response_node(state)

    response = result["_response"]
    assert response.decision_trace is None


@pytest.mark.asyncio()
async def test_format_response_nodes_visited_order() -> None:
    """nodes_visited in the trace preserves insertion order."""
    state = _base_state(
        synthesized_answer="answer here",
        confidence_score=0.75,
        sources=[],
        nodes_visited=["agent", "tools", "synthesize"],
        include_trace=True,
    )
    result = await _import_and_call_format_response_node(state)

    response = result["_response"]
    assert response.decision_trace is not None
    assert response.decision_trace.nodes_visited[:3] == ["agent", "tools", "synthesize"]


# --- helpers ---


async def _import_and_call_agent_node(state: dict) -> dict:
    from src.agent.nodes import agent_node

    return await agent_node(state)


async def _import_and_call_format_response_node(state: dict) -> dict:
    from src.agent.nodes import format_response_node

    return await format_response_node(state)
