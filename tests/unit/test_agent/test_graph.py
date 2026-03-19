"""Unit tests for graph compilation and the run() async wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.agent.graph import get_graph, reset_graph
from src.models.response import ResearchResponse


@pytest.fixture(autouse=True)
def reset_graph_between_tests():
    reset_graph()
    yield
    reset_graph()


def test_graph_compiles_without_error() -> None:
    """Graph builds and compiles without raising."""
    with patch("src.agent.graph.registry") as mock_reg:
        mock_reg.build_tool_list.return_value = []
        graph = get_graph()
    assert graph is not None


@pytest.mark.asyncio()
async def test_graph_run_returns_research_response() -> None:
    """graph.run() returns a ResearchResponse with all required fields."""
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="RAG stands for retrieval-augmented generation.")
    )

    with (
        patch("src.agent.nodes._get_llm", return_value=mock_llm),
        patch("src.agent.graph.registry") as mock_reg,
    ):
        mock_reg.build_tool_list.return_value = []
        reset_graph()

        from src.agent.graph import run

        response = await run("What is RAG?", max_sources=3, include_trace=True)

    assert isinstance(response, ResearchResponse)
    assert response.answer
    assert 0.0 <= response.confidence_score <= 1.0
    assert response.sources is not None


@pytest.mark.asyncio()
async def test_graph_run_populates_decision_trace() -> None:
    """graph.run() with include_trace=True returns a non-None decision_trace."""
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Answer text here."))

    with (
        patch("src.agent.nodes._get_llm", return_value=mock_llm),
        patch("src.agent.graph.registry") as mock_reg,
    ):
        mock_reg.build_tool_list.return_value = []
        reset_graph()

        from src.agent.graph import run

        response = await run("What is RAG?", include_trace=True)

    assert response.decision_trace is not None
    assert len(response.decision_trace.nodes_visited) >= 1
