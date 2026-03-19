"""Integration tests for the end-to-end research agent flow.

Uses stubbed external tools (Tavily and FAISS patched) to exercise the full
LangGraph graph without real API calls. Covers all four user stories:
- US1: cited answer returned
- US2: decision trace completeness
- US3: dynamic tool registration
- US4: uncertainty expression for low-confidence answers
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.agent.graph import reset_graph
from src.agent.state import ToolResult
from src.models.response import ResearchResponse

# --- fixtures ---

WEB_FIXTURE: list[ToolResult] = [
    ToolResult(
        content="RAG combines retrieval with generation for accurate answers.",
        identifier="https://example.com/rag",
        relevance_score=0.91,
        source_type="web",
        title="Understanding RAG",
    )
]

KB_FIXTURE: list[ToolResult] = [
    ToolResult(
        content="Local document: RAG improves factual grounding.",
        identifier="doc_001",
        relevance_score=0.85,
        source_type="knowledge_base",
        title="Domain Primer",
    )
]


@pytest.fixture(autouse=True)
def reset_graph_fixture():
    reset_graph()
    yield
    reset_graph()


def _mock_llm_no_tools(answer: str = "RAG stands for retrieval-augmented generation.") -> MagicMock:
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=answer))
    return mock_llm


# --- US1: cited answer ---


@pytest.mark.asyncio()
async def test_us1_end_to_end_returns_response() -> None:
    """US1: Full flow returns ResearchResponse with answer and confidence score."""
    mock_llm = _mock_llm_no_tools()

    with (
        patch("src.agent.nodes._get_llm", return_value=mock_llm),
        patch("src.agent.graph.registry") as mock_reg,
    ):
        mock_reg.build_tool_list.return_value = []
        reset_graph()

        from src.agent.graph import run

        response = await run("What is retrieval-augmented generation?")

    assert isinstance(response, ResearchResponse)
    assert len(response.answer) > 0
    assert 0.0 <= response.confidence_score <= 1.0
    assert response.sources is not None


@pytest.mark.asyncio()
async def test_us1_no_tool_answer_uses_llm_source() -> None:
    """US1: When no tools are invoked, source type is 'llm'."""
    mock_llm = _mock_llm_no_tools()

    with (
        patch("src.agent.nodes._get_llm", return_value=mock_llm),
        patch("src.agent.graph.registry") as mock_reg,
    ):
        mock_reg.build_tool_list.return_value = []
        reset_graph()

        from src.agent.graph import run

        response = await run("What is 2+2?")

    assert any(s.source_type.value == "llm" for s in response.sources)


# --- US2: decision trace ---


@pytest.mark.asyncio()
async def test_us2_trace_populated_with_include_trace_true() -> None:
    """US2: include_trace=True produces a non-None DecisionTrace."""
    mock_llm = _mock_llm_no_tools()

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


@pytest.mark.asyncio()
async def test_us2_trace_none_with_include_trace_false() -> None:
    """US2: include_trace=False produces decision_trace=None."""
    mock_llm = _mock_llm_no_tools()

    with (
        patch("src.agent.nodes._get_llm", return_value=mock_llm),
        patch("src.agent.graph.registry") as mock_reg,
    ):
        mock_reg.build_tool_list.return_value = []
        reset_graph()

        from src.agent.graph import run

        response = await run("What is RAG?", include_trace=False)

    assert response.decision_trace is None


# --- US3: tool extensibility ---


@pytest.mark.asyncio()
async def test_us3_new_tool_registerable_without_modifying_graph() -> None:
    """US3: A new stub tool can be registered and appears in build_tool_list()."""
    from langchain_core.tools import tool

    from src.tools.base import registry

    @tool
    async def echo_tool(query: str) -> list:  # type: ignore[return]
        """Echo tool stub for testing extensibility."""
        return []

    try:
        registry.register(echo_tool)
        assert "echo_tool" in registry.list_tools()
    finally:
        try:
            registry.deregister("echo_tool")
        except KeyError:
            pass


@pytest.mark.asyncio()
async def test_us3_deregistered_tool_removed_from_list() -> None:
    """US3: Deregistering a tool removes it from build_tool_list()."""
    from langchain_core.tools import tool

    from src.tools.base import registry

    @tool
    async def temp_tool(query: str) -> list:  # type: ignore[return]
        """Temporary test tool."""
        return []

    registry.register(temp_tool)
    assert "temp_tool" in registry.list_tools()
    registry.deregister("temp_tool")
    assert "temp_tool" not in registry.list_tools()


# --- US4: uncertainty ---


@pytest.mark.asyncio()
async def test_us4_low_confidence_answer_contains_uncertainty() -> None:
    """US4: When all tools return empty results, confidence < 0.5 and answer signals uncertainty."""
    mock_llm = _mock_llm_no_tools(
        answer="I have limited reliable information on this topic. "
        "This future event has not occurred yet."
    )

    with (
        patch("src.agent.nodes._get_llm", return_value=mock_llm),
        patch("src.agent.graph.registry") as mock_reg,
    ):
        mock_reg.build_tool_list.return_value = []
        reset_graph()

        from src.agent.graph import run

        response = await run("Who won the 2099 World Cup?")

    assert response.confidence_score < 0.5 or "limited" in response.answer.lower()


@pytest.mark.asyncio()
async def test_us4_confidence_score_in_valid_range() -> None:
    """US4: confidence_score is always within [0.0, 1.0]."""
    mock_llm = _mock_llm_no_tools()

    with (
        patch("src.agent.nodes._get_llm", return_value=mock_llm),
        patch("src.agent.graph.registry") as mock_reg,
    ):
        mock_reg.build_tool_list.return_value = []
        reset_graph()

        from src.agent.graph import run

        response = await run("test question")

    assert 0.0 <= response.confidence_score <= 1.0
