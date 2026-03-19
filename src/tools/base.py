"""Base tool infrastructure for the Agentic Research Assistant.

Provides the ToolRegistry, a central registry of async @tool-decorated
callables. Tools register themselves here; the agent graph reads from
the registry at compile time so new tools can be added without modifying
graph.py or any other core file.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ToolRegistry:
    """Central registry of async @tool-decorated functions.

    Tools register themselves by calling registry.register(fn). The agent
    graph calls registry.build_tool_list() when compiling the ToolNode,
    which picks up all currently registered tools automatically.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, tool_fn: Callable[..., Any]) -> Callable[..., Any]:
        """Register an async @tool function.

        Can be used as a decorator or called directly.

        Args:
            tool_fn: An async function decorated with @tool from langchain_core.

        Returns:
            The tool function unchanged (allows use as decorator).
        """
        name: str = getattr(tool_fn, "name", None) or getattr(tool_fn, "__name__", str(tool_fn))
        self._tools[name] = tool_fn
        return tool_fn

    def deregister(self, tool_name: str) -> None:
        """Remove a tool by name. Used primarily in tests for teardown.

        Args:
            tool_name: The name of the tool to remove.

        Raises:
            KeyError: If the tool name is not registered.
        """
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' is not registered.")
        del self._tools[tool_name]

    def build_tool_list(self) -> list[Callable[..., Any]]:
        """Return a snapshot of all currently registered tool functions.

        Called by graph.py at compile() time to build the ToolNode.

        Returns:
            List of registered async @tool callables.
        """
        return list(self._tools.values())

    def list_tools(self) -> list[str]:
        """Return the names of all currently registered tools.

        Returns:
            Sorted list of tool name strings.
        """
        return sorted(self._tools.keys())


# Module-level singleton — all tools register against this instance.
registry = ToolRegistry()
