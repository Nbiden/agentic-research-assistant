"""LangGraph StateGraph definition and compilation for the research agent.

Wires together all nodes, the prebuilt ToolNode, and conditional edges.
The ToolNode is built from ToolRegistry.build_tool_list() at compile time,
so newly registered tools are automatically available without modifying this file.

Graph topology (verified against LangGraph v1.1.3):
    START → agent → research_router → tools → agent (loop)
                                    → synthesize → format_response → END
"""

from __future__ import annotations

import structlog
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from src.agent.nodes import agent_node, format_response_node, synthesize_node
from src.agent.router import research_router
from src.agent.state import AgentState
from src.models.response import ResearchResponse
from src.tools.base import registry

logger = structlog.get_logger(__name__)

_compiled_graph = None


def _build_graph() -> StateGraph:
    """Build and compile the research agent StateGraph.

    Called once on first use. Reads the current ToolRegistry snapshot
    so all registered tools are included in the ToolNode.

    Returns:
        Compiled LangGraph StateGraph ready for invocation.
    """
    tools = registry.build_tool_list()
    tool_node = ToolNode(tools) if tools else ToolNode([])

    builder = StateGraph(AgentState)

    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("synthesize", synthesize_node)
    builder.add_node("format_response", format_response_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        research_router,
        {"tools": "tools", "synthesize": "synthesize"},
    )
    builder.add_edge("tools", "agent")
    builder.add_edge("synthesize", "format_response")
    builder.add_edge("format_response", END)

    return builder.compile()


def get_graph():  # type: ignore[return]
    """Return the compiled graph, building it on first call (lazy singleton).

    Returns:
        Compiled LangGraph CompiledStateGraph.
    """
    global _compiled_graph  # noqa: PLW0603
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


def reset_graph() -> None:
    """Force graph recompilation on next get_graph() call.

    Used in tests when the ToolRegistry is modified between test cases.
    """
    global _compiled_graph  # noqa: PLW0603
    _compiled_graph = None


async def run(
    question: str,
    max_sources: int = 5,
    include_trace: bool = True,
) -> ResearchResponse:
    """Execute the research agent graph for a given question.

    Initialises AgentState, invokes the compiled graph asynchronously,
    and extracts the ResearchResponse from the final state.

    Args:
        question: The natural-language research question.
        max_sources: Maximum number of sources to include.
        include_trace: Whether to include the decision trace in the response.

    Returns:
        ResearchResponse with answer, sources, confidence, and optional trace.
    """
    logger.info("graph.run.start", question=question[:100])

    graph = get_graph()

    initial_state: dict = {
        "question": question,
        "include_trace": include_trace,
        "max_sources": max_sources,
        "messages": [HumanMessage(content=question)],
        "web_results": [],
        "kb_results": [],
        "tool_calls_log": [],
        "nodes_visited": [],
        "synthesized_answer": None,
        "sources": [],
        "confidence_score": None,
        "degraded": False,
        "error_context": None,
        "_response": None,
    }

    final_state = await graph.ainvoke(initial_state)

    response: ResearchResponse | None = final_state.get("_response")
    if response is None:
        # Fallback: build a minimal degraded response if something went wrong.
        logger.error("graph.run.no_response")
        response = ResearchResponse(
            answer=(
                "I have limited reliable information on this topic. "
                "An unexpected error occurred while processing your question."
            ),
            sources=[],
            confidence_score=0.0,
            decision_trace=None,
            degraded=True,
        )

    logger.info(
        "graph.run.complete",
        confidence=response.confidence_score,
        degraded=response.degraded,
    )
    return response
