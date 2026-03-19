"""Unit tests for the web_search tool.

Tests cover: successful search, retry on timeout, exhausted retries return
empty list (no exception), and result shape validation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.tools.web_search import web_search


@pytest.fixture()
def tavily_success_response() -> dict:
    return {
        "results": [
            {
                "content": "RAG combines retrieval with generation.",
                "url": "https://example.com/rag",
                "score": 0.92,
                "title": "Understanding RAG",
            }
        ]
    }


@pytest.mark.asyncio()
async def test_web_search_returns_results(tavily_success_response: dict) -> None:
    """Successful Tavily call returns a non-empty ToolResult list."""
    mock_client = AsyncMock()
    mock_client.search.return_value = tavily_success_response

    with patch("src.tools.web_search.AsyncTavilyClient", return_value=mock_client):
        # web_search is a @tool — invoke its underlying function.
        results = await web_search.ainvoke({"query": "what is RAG?"})

    assert len(results) == 1
    assert results[0]["source_type"] == "web"
    assert results[0]["relevance_score"] == pytest.approx(0.92)
    assert results[0]["identifier"] == "https://example.com/rag"


@pytest.mark.asyncio()
async def test_web_search_retries_on_exception() -> None:
    """Tool retries on exception and returns results on second attempt."""
    mock_client = AsyncMock()
    mock_client.search.side_effect = [
        ConnectionError("timeout"),
        {"results": [{"content": "retry worked", "url": "https://x.com", "score": 0.8}]},
    ]

    with patch("src.tools.web_search.AsyncTavilyClient", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await web_search.ainvoke({"query": "test"})

    assert len(results) == 1
    assert results[0]["content"] == "retry worked"


@pytest.mark.asyncio()
async def test_web_search_returns_empty_list_on_exhausted_retries() -> None:
    """After all retries fail, tool returns empty list — no exception raised."""
    mock_client = AsyncMock()
    mock_client.search.side_effect = ConnectionError("persistent failure")

    with patch("src.tools.web_search.AsyncTavilyClient", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await web_search.ainvoke({"query": "test"})

    assert results == []


@pytest.mark.asyncio()
async def test_web_search_result_fields_present(tavily_success_response: dict) -> None:
    """Each ToolResult contains all required fields."""
    mock_client = AsyncMock()
    mock_client.search.return_value = tavily_success_response

    with patch("src.tools.web_search.AsyncTavilyClient", return_value=mock_client):
        results = await web_search.ainvoke({"query": "test"})

    result = results[0]
    assert "content" in result
    assert "identifier" in result
    assert "relevance_score" in result
    assert "source_type" in result
    assert "title" in result
