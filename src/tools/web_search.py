"""Web search tool for the Agentic Research Assistant.

Provides an async @tool function that queries the Tavily API for current
web information. Implements manual retry with exponential backoff and
returns an empty result list (rather than raising) on exhausted retries,
enabling graceful degradation per FR-010, FR-011, FR-012.
"""

from __future__ import annotations

import asyncio

import structlog
from langchain_core.tools import tool
from tavily import AsyncTavilyClient  # type: ignore[import]

from src.agent.state import ToolResult
from src.config import settings

logger = structlog.get_logger(__name__)


@tool
async def web_search(query: str) -> list[ToolResult]:
    """Search the internet for current information using Tavily.

    Retries up to MAX_RETRIES times with exponential backoff on transient
    failures. Returns an empty list if all retries are exhausted so the
    agent can fall back gracefully.

    Args:
        query: The search query string derived from the research question.

    Returns:
        List of ToolResult dicts with content, URL, relevance score, and type.
        Empty list if Tavily is unavailable after all retries.
    """
    log = logger.bind(tool="web_search", query=query[:100])
    log.info("web_search.start")

    async def _search() -> list[ToolResult]:
        client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        response = await client.search(
            query=query,
            max_results=5,
            include_raw_content=False,
        )
        results: list[ToolResult] = []
        for item in response.get("results", []):
            results.append(
                ToolResult(
                    content=item.get("content", ""),
                    identifier=item.get("url", ""),
                    relevance_score=float(item.get("score", 0.5)),
                    source_type="web",
                    title=item.get("title"),
                )
            )
        return results

    last_error: Exception | None = None
    delay = settings.retry_base_delay

    for attempt in range(settings.max_retries):
        try:
            results = await _search()
            log.info("web_search.success", result_count=len(results))
            return results
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log.warning(
                "web_search.retry",
                attempt=attempt + 1,
                max_retries=settings.max_retries,
                error=str(exc),
            )
            if attempt < settings.max_retries - 1:
                await asyncio.sleep(min(delay, settings.retry_base_delay * 16))
                delay *= 2

    log.error(
        "web_search.exhausted",
        attempts=settings.max_retries,
        error=str(last_error),
    )
    return []
