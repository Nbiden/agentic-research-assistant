"""Synthesis helpers for combining multi-source results into a cited answer.

Provides two pure functions used by the synthesize_node in the agent graph:
- combine_sources: formats retrieved passages into a cited answer string
- compute_confidence: applies the weighted heuristic from data-model.md

These are intentionally NOT @tool functions — they are called directly by
the synthesize node, not via the LangGraph ToolNode dispatch.
"""

from __future__ import annotations

from src.agent.state import ToolResult
from src.models.response import Source, SourceType


def combine_sources(
    web_results: list[ToolResult],
    kb_results: list[ToolResult],
    max_sources: int = 5,
) -> tuple[list[Source], str]:
    """Combine web and knowledge base results into a sorted source list and citation map.

    Merges and deduplicates results, sorts by relevance, and returns both the
    structured Source list and a formatted citation block for the synthesize node
    to pass to the LLM for answer generation.

    Args:
        web_results: Raw ToolResult dicts from the web_search tool.
        kb_results: Raw ToolResult dicts from the knowledge_base tool.
        max_sources: Maximum number of sources to include.

    Returns:
        Tuple of (sources list sorted by relevance, citation context string).
    """
    all_results: list[ToolResult] = web_results + kb_results
    all_results.sort(key=lambda r: r["relevance_score"], reverse=True)
    all_results = all_results[:max_sources]

    sources: list[Source] = []
    citation_lines: list[str] = []

    for idx, result in enumerate(all_results, start=1):
        source_type = (
            SourceType(result["source_type"])
            if result["source_type"] in ("web", "knowledge_base")
            else SourceType.LLM
        )
        sources.append(
            Source(
                content=result["content"],
                identifier=result["identifier"],
                relevance_score=result["relevance_score"],
                source_type=source_type,
                title=result.get("title"),
            )
        )
        title_part = f" — {result['title']}" if result.get("title") else ""
        citation_lines.append(
            f"[{idx}] ({result['source_type']}) {result['identifier']}{title_part}\n"
            f"    {result['content'][:300]}"
        )

    citation_context = "\n\n".join(citation_lines)
    return sources, citation_context


def compute_confidence(
    sources: list[Source],
    degraded: bool = False,
    web_degraded: bool = False,
    kb_degraded: bool = False,
    contradiction_detected: bool = False,
) -> float:
    """Compute a heuristic confidence score for the synthesized answer.

    Uses the weighted formula from data-model.md:
        score = (avg_relevance × 0.5) + (source_count_heuristic × 0.3)
                − contradiction_penalty − degradation_penalties

    Args:
        sources: The final list of Source objects used in the answer.
        degraded: True if any tool failed (applies general degradation penalty).
        web_degraded: True if the web search tool specifically failed.
        kb_degraded: True if the knowledge base tool specifically failed.
        contradiction_detected: True if the LLM detected conflicting claims.

    Returns:
        Confidence score clamped to [0.0, 1.0].
    """
    if not sources:
        base_relevance = 0.0
        count_heuristic = 0.0
    else:
        avg_relevance = sum(s.relevance_score for s in sources) / len(sources)
        base_relevance = avg_relevance * 0.5
        count_heuristic = min(len(sources) / 4.0, 1.0) * 0.3

    score = base_relevance + count_heuristic

    if contradiction_detected:
        score -= 0.15
    if web_degraded:
        score -= 0.10
    if kb_degraded:
        score -= 0.05

    return max(0.0, min(1.0, score))


UNCERTAINTY_PREFIX = (
    "I have limited reliable information on this topic. "
    "The following answer is based on incomplete evidence — "
    "please verify with additional sources. "
)
