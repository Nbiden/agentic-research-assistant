"""Unit tests for the research_router conditional edge function."""

from __future__ import annotations

from unittest.mock import patch

from src.agent.router import research_router


def test_router_returns_synthesize_when_no_tool_calls() -> None:
    """When tools_condition returns __end__, router returns 'synthesize'."""
    state = {"messages": []}
    with patch("src.agent.router.tools_condition", return_value="__end__"):
        result = research_router(state)
    assert result == "synthesize"


def test_router_returns_tools_when_tool_calls_present() -> None:
    """When tools_condition returns 'tools', router returns 'tools'."""
    state = {"messages": []}
    with patch("src.agent.router.tools_condition", return_value="tools"):
        result = research_router(state)
    assert result == "tools"


def test_router_never_returns_end() -> None:
    """Router should never return '__end__' — it always maps to 'synthesize'."""
    state = {"messages": []}
    with patch("src.agent.router.tools_condition", return_value="__end__"):
        result = research_router(state)
    assert result != "__end__"
