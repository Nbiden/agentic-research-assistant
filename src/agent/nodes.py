"""LangGraph node functions for the Agentic Research Assistant.

Defines the three graph nodes:
- agent_node: Invokes the LLM with bound tools; records ToolCall metadata.
- synthesize_node: Combines tool results into a cited answer and confidence score.
- format_response_node: Builds the final ResearchResponse from AgentState.

All nodes are async, emit structlog JSON-lines at entry and exit, and update
AgentState.nodes_visited for the decision trace.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agent.state import AgentState, ToolResult
from src.config import settings
from src.models.response import (
    DecisionTrace,
    ResearchResponse,
    Source,
    SourceType,
    ToolCall,
)
from src.tools.base import registry
from src.tools.synthesizer import (
    UNCERTAINTY_PREFIX,
    combine_sources,
    compute_confidence,
)

logger = structlog.get_logger(__name__)


def _get_llm() -> ChatAnthropic:
    """Instantiate the ChatAnthropic LLM from current settings."""
    return ChatAnthropic(
        model=settings.claude_model,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
    )


async def agent_node(state: AgentState) -> dict:
    """Invoke the LLM with all registered tools bound.

    Appends the resulting AIMessage (which may contain tool_calls) to
    state.messages. Records partial ToolCall metadata for each tool call
    found in the response, to be finalised by format_response_node.

    Args:
        state: Current AgentState.

    Returns:
        Partial state update dict with updated messages, tool_calls_log,
        and nodes_visited.
    """
    structlog.contextvars.bind_contextvars(node="agent")
    start = time.monotonic()
    logger.info("agent_node.enter", question=state["question"][:100])

    llm = _get_llm()
    tools = registry.build_tool_list()
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    messages = list(state.get("messages", []))
    if not messages or not isinstance(messages[-1], HumanMessage):
        messages = [HumanMessage(content=state["question"])] + messages[1:]

    response: AIMessage = await llm_with_tools.ainvoke(messages)

    # Record partial ToolCall entries for each tool the LLM wants to invoke.
    new_tool_calls: list[ToolCall] = []
    for tc in getattr(response, "tool_calls", []) or []:
        new_tool_calls.append(
            ToolCall(
                tool_name=tc.get("name", "unknown"),
                rationale=(
                    f"LLM selected tool '{tc.get('name')}' for query: {state['question'][:80]}"
                ),
                input_summary=str(tc.get("args", {}))[:200],
                output_summary="pending",
                success=True,
                elapsed_ms=0,
            )
        )

    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "agent_node.exit",
        elapsed_ms=elapsed_ms,
        tool_calls_requested=len(new_tool_calls),
    )

    existing_log = list(state.get("tool_calls_log", []))
    visited = list(state.get("nodes_visited", []))
    visited.append("agent")

    return {
        "messages": [response],
        "tool_calls_log": existing_log + new_tool_calls,
        "nodes_visited": visited,
    }


async def synthesize_node(state: AgentState) -> dict:
    """Combine tool results into a cited answer and compute confidence.

    Reads ToolMessage results from state.messages, calls the synthesizer
    to combine sources, prompts the LLM to generate a final cited answer,
    and computes the heuristic confidence score.

    Args:
        state: Current AgentState after all tool calls have completed.

    Returns:
        Partial state update with synthesized_answer, sources, confidence_score,
        and updated nodes_visited.
    """
    structlog.contextvars.bind_contextvars(node="synthesize")
    start = time.monotonic()
    logger.info("synthesize_node.enter")

    web_results: list[ToolResult] = list(state.get("web_results", []))
    kb_results: list[ToolResult] = list(state.get("kb_results", []))

    # Extract ToolMessage results from messages if web/kb results not pre-populated.
    # LangGraph's ToolNode serialises list results as a JSON string in msg.content.
    if not web_results and not kb_results:
        for msg in state.get("messages", []):
            if isinstance(msg, ToolMessage):
                content = msg.content
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except (json.JSONDecodeError, ValueError):
                        content = []
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "source_type" in item:
                            if item["source_type"] == "web":
                                web_results.append(ToolResult(**item))
                            elif item["source_type"] == "knowledge_base":
                                kb_results.append(ToolResult(**item))

    sources, citation_context = combine_sources(
        web_results, kb_results, max_sources=state.get("max_sources", 5)
    )

    degraded = bool(state.get("degraded", False))
    web_degraded = degraded and not web_results
    kb_degraded = degraded and not kb_results

    # Ask LLM to synthesize a final answer using the retrieved context.
    llm = _get_llm()
    if sources:
        synthesis_prompt = (
            f"Answer the following research question using the provided sources. "
            f"Include inline citations like [1], [2] where appropriate.\n\n"
            f"Question: {state['question']}\n\n"
            f"Sources:\n{citation_context}\n\n"
            f"Provide a clear, comprehensive answer:"
        )
    else:
        synthesis_prompt = (
            f"Answer the following research question using only your training knowledge. "
            f"No external sources were available.\n\nQuestion: {state['question']}"
        )

    synthesis_response: AIMessage = await llm.ainvoke([HumanMessage(content=synthesis_prompt)])
    answer_text = synthesis_response.content or ""

    contradiction_detected = (
        any(
            word in answer_text.lower()
            for word in ["however", "contradicts", "conflicting", "disagree", "on the other hand"]
        )
        and len(sources) > 1
    )

    confidence = compute_confidence(
        sources=sources,
        degraded=degraded,
        web_degraded=web_degraded,
        kb_degraded=kb_degraded,
        contradiction_detected=contradiction_detected,
    )

    if confidence < 0.5 and UNCERTAINTY_PREFIX.lower() not in answer_text.lower():
        answer_text = UNCERTAINTY_PREFIX + answer_text

    if not sources:
        sources = [
            Source(
                content=answer_text[:300],
                identifier="llm_knowledge",
                relevance_score=confidence,
                source_type=SourceType.LLM,
                title="LLM Knowledge",
            )
        ]

    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "synthesize_node.exit",
        elapsed_ms=elapsed_ms,
        confidence=confidence,
        source_count=len(sources),
    )

    visited = list(state.get("nodes_visited", []))
    visited.append("synthesize")

    return {
        "synthesized_answer": answer_text,
        "sources": sources,
        "confidence_score": confidence,
        "web_results": web_results,
        "kb_results": kb_results,
        "nodes_visited": visited,
    }


async def format_response_node(state: AgentState) -> dict:
    """Build the final ResearchResponse from the completed AgentState.

    Finalises ToolCall records (output_summary, elapsed_ms), constructs the
    DecisionTrace, and returns the complete ResearchResponse. Respects the
    include_trace flag per the original request.

    Args:
        state: Completed AgentState after synthesis.

    Returns:
        Partial state update with the final response stored for extraction.
    """
    structlog.contextvars.bind_contextvars(node="format_response")
    start = time.monotonic()
    logger.info("format_response_node.enter")

    visited = list(state.get("nodes_visited", []))
    visited.append("format_response")

    tool_calls_log = list(state.get("tool_calls_log", []))
    include_trace = state.get("include_trace", True)

    # Finalise ToolCall output summaries from ToolMessages in state.
    tool_messages = [m for m in state.get("messages", []) if isinstance(m, ToolMessage)]
    for i, tc in enumerate(tool_calls_log):
        if i < len(tool_messages):
            content = tool_messages[i].content
            summary = str(content)[:200] if content else "no output"
            tool_calls_log[i] = ToolCall(
                tool_name=tc.tool_name,
                rationale=tc.rationale,
                input_summary=tc.input_summary,
                output_summary=summary,
                success=tc.success,
                elapsed_ms=tc.elapsed_ms,
                error_message=tc.error_message,
            )

    decision_trace: DecisionTrace | None = None
    if include_trace:
        total_ms = sum(tc.elapsed_ms for tc in tool_calls_log)
        decision_trace = DecisionTrace(
            tool_calls=tool_calls_log,
            total_elapsed_ms=total_ms,
            nodes_visited=visited,
        )

    answer = state.get("synthesized_answer") or "Unable to generate an answer."
    confidence = state.get("confidence_score") or 0.0
    sources = list(state.get("sources", []))
    degraded = bool(state.get("degraded", False))

    response = ResearchResponse(
        answer=answer,
        sources=sources,
        confidence_score=confidence,
        decision_trace=decision_trace,
        generated_at=datetime.now(UTC),
        degraded=degraded,
    )

    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "format_response_node.exit",
        elapsed_ms=elapsed_ms,
        degraded=degraded,
        confidence=confidence,
    )

    # Store the final response on the state for extraction by graph.run().
    return {
        "nodes_visited": visited,
        "_response": response,
    }
