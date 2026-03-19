"""Pydantic v2 response models for the Agentic Research Assistant.

Defines the complete output structure: ResearchResponse, Source, ToolCall,
DecisionTrace, and the SourceType enum. Includes a model validator that
enforces explicit uncertainty language when confidence is low.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class SourceType(StrEnum):
    """The origin of a retrieved source."""

    WEB = "web"
    KNOWLEDGE_BASE = "knowledge_base"
    LLM = "llm"


class Source(BaseModel):
    """A single piece of retrieved evidence cited in the answer."""

    content: str = Field(min_length=1, description="The retrieved text snippet.")
    identifier: str = Field(min_length=1, description="URL or document identifier.")
    relevance_score: float = Field(
        ge=0.0, le=1.0, description="Relevance to the research question."
    )
    source_type: SourceType = Field(description="Origin of this source.")
    title: str | None = Field(default=None, description="Page title or document name.")


class ToolCall(BaseModel):
    """A record of one tool invocation within the agent's reasoning loop."""

    tool_name: str = Field(min_length=1, description="Name of the invoked tool.")
    rationale: str = Field(min_length=1, description="LLM's reason for invoking this tool.")
    input_summary: str = Field(min_length=1, description="Summary of tool inputs.")
    output_summary: str = Field(min_length=1, description="Summary of tool outputs.")
    success: bool = Field(description="True if the tool completed without error.")
    elapsed_ms: int = Field(ge=0, description="Wall-clock time in milliseconds.")
    error_message: str | None = Field(
        default=None, description="Human-readable error if success=False."
    )


class DecisionTrace(BaseModel):
    """The ordered record of all tool calls made during a single query."""

    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Ordered list of tool invocations."
    )
    total_elapsed_ms: int = Field(ge=0, description="Sum of all tool elapsed times.")
    nodes_visited: list[str] = Field(
        min_length=1, description="Ordered LangGraph node names visited."
    )


class ResearchResponse(BaseModel):
    """The complete structured response returned to the caller."""

    answer: str = Field(
        min_length=1,
        description="Natural-language answer with inline [N] citation markers.",
    )
    sources: list[Source] = Field(
        default_factory=list,
        description="Retrieved evidence sorted by relevance descending.",
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Heuristic confidence in the answer (0=uncertain, 1=confident).",
    )
    decision_trace: DecisionTrace | None = Field(
        default=None,
        description="Tool call history; None if include_trace=False.",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of response generation.",
    )
    degraded: bool = Field(
        default=False,
        description="True if one or more tools failed during processing.",
    )

    @model_validator(mode="after")
    def validate_uncertainty_language(self) -> ResearchResponse:
        """Ensure low-confidence answers contain explicit uncertainty language.

        When confidence_score < 0.5, the answer text MUST contain a phrase
        that explicitly signals uncertainty to the user (FR-007, SC-006).
        """
        uncertainty_phrases = [
            "uncertain",
            "insufficient",
            "limited information",
            "not confident",
            "unable to confirm",
            "limited reliable",
            "i have limited",
            "cannot confirm",
            "no reliable",
        ]
        if self.confidence_score < 0.5:
            answer_lower = self.answer.lower()
            if not any(phrase in answer_lower for phrase in uncertainty_phrases):
                raise ValueError(
                    "Answers with confidence_score < 0.5 MUST contain explicit "
                    "uncertainty language (e.g., 'I have limited reliable information')."
                )
        return self
