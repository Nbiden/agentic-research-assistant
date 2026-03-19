"""Pydantic v2 request models for the Agentic Research Assistant.

Defines the ResearchQuestion model that validates all incoming questions
submitted via CLI or HTTP API.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ResearchQuestion(BaseModel):
    """A validated natural-language research question submitted by the user."""

    question: str = Field(
        min_length=1,
        max_length=2000,
        description="The natural-language research question.",
    )
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of submission.",
    )
    max_sources: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of sources to include in the response.",
    )
    include_trace: bool = Field(
        default=True,
        description="Whether to include the decision trace in the response.",
    )
