"""Unit tests for ToolRegistry in src/tools/base.py."""

from __future__ import annotations

import pytest
from langchain_core.tools import tool

from src.tools.base import ToolRegistry


@pytest.fixture()
def registry() -> ToolRegistry:
    return ToolRegistry()


@tool
async def stub_tool_a(query: str) -> list:  # type: ignore[return]
    """Stub tool A for testing."""
    return []


@tool
async def stub_tool_b(query: str) -> list:  # type: ignore[return]
    """Stub tool B for testing."""
    return []


def test_register_adds_to_list(registry: ToolRegistry) -> None:
    registry.register(stub_tool_a)
    assert "stub_tool_a" in registry.list_tools()


def test_build_tool_list_returns_registered_tools(registry: ToolRegistry) -> None:
    registry.register(stub_tool_a)
    registry.register(stub_tool_b)
    tools = registry.build_tool_list()
    names = [getattr(t, "name", None) or getattr(t, "__name__", "") for t in tools]
    assert "stub_tool_a" in names
    assert "stub_tool_b" in names


def test_deregister_removes_tool(registry: ToolRegistry) -> None:
    registry.register(stub_tool_a)
    registry.deregister("stub_tool_a")
    assert "stub_tool_a" not in registry.list_tools()


def test_deregister_unknown_raises_key_error(registry: ToolRegistry) -> None:
    with pytest.raises(KeyError, match="not registered"):
        registry.deregister("nonexistent_tool")


def test_list_tools_returns_sorted(registry: ToolRegistry) -> None:
    registry.register(stub_tool_b)
    registry.register(stub_tool_a)
    names = registry.list_tools()
    assert names == sorted(names)


def test_register_used_as_decorator(registry: ToolRegistry) -> None:
    @registry.register
    @tool
    async def my_tool(query: str) -> list:  # type: ignore[return]
        """My tool."""
        return []

    assert "my_tool" in registry.list_tools()


def test_empty_registry_returns_empty_list(registry: ToolRegistry) -> None:
    assert registry.build_tool_list() == []
    assert registry.list_tools() == []
