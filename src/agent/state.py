"""LangGraph agent state definitions for the Agentic Research Assistant.

Defines AgentState (extending MessagesState) as the shared mutable state
that accumulates tool results and metadata as the graph executes. Also
defines ToolResult as an intermediate TypedDict for raw tool output.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph.message import MessagesState

from src.models.response import ResearchResponse, Source, ToolCall


class ToolResult(TypedDict):
    """Intermediate result from a single tool invocation stored in AgentState."""

    content: str
    identifier: str
    relevance_score: float
    source_type: str  # "web" | "knowledge_base"
    title: str | None


class AgentState(MessagesState):
    """Shared state accumulated across all nodes in the research agent graph.

    Extends MessagesState to inherit the messages field with the add_messages
    reducer, which correctly merges lists of LangChain messages on each step.
    All custom fields use standard Python typing; LangGraph handles serialisation.
    """

    # Input parameters (set at graph entry)
    question: str
    include_trace: bool
    max_sources: int

    # Accumulated tool results
    web_results: list[ToolResult]
    kb_results: list[ToolResult]

    # Decision trace construction
    tool_calls_log: list[ToolCall]
    nodes_visited: list[str]

    # Synthesis outputs
    synthesized_answer: str | None
    sources: list[Source]
    confidence_score: float | None

    # Degradation and error context
    degraded: bool
    error_context: str | None

    # Final response (populated by format_response_node for extraction by run())
    _response: ResearchResponse | None
