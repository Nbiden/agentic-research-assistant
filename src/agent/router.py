"""Conditional edge routing for the Agentic Research Assistant graph.

Provides research_router, a thin wrapper around langgraph.prebuilt.tools_condition
that remaps the "__end__" branch to "synthesize" so the agent always passes
through the synthesis node before terminating (verified against LangGraph v1.1.3).
"""

from __future__ import annotations

from typing import Any

from langgraph.prebuilt import tools_condition


def research_router(state: Any) -> str:  # noqa: ANN401
    """Route the agent to the next node based on whether tool calls were made.

    Delegates to langgraph.prebuilt.tools_condition which inspects the latest
    AIMessage in state.messages:
    - If tool_calls present → returns "tools" (ToolNode dispatch)
    - If no tool_calls → returns "synthesize" (mapped from "__end__")

    Args:
        state: Current AgentState (dict-like, compatible with tools_condition).

    Returns:
        "tools" if the LLM requested tool calls, "synthesize" otherwise.
    """
    next_node = tools_condition(state)
    return "synthesize" if next_node == "__end__" else next_node
