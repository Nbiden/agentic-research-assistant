"""FastAPI routes for the Agentic Research Assistant REST API.

Exposes:
- POST /research — submit a question, receive a ResearchResponse
- GET /health    — liveness check

All errors are returned as user-friendly JSON. Raw stack traces are never
exposed to callers (Constitution Principle IV, FR-011, SC-008).
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import src.tools  # noqa: F401 — triggers tool registration
from src.agent.graph import run
from src.models.request import ResearchQuestion
from src.models.response import ResearchResponse

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Agentic Research Assistant",
    version="0.1.0",
    description="LangGraph-powered research agent with cited answers and decision traces.",
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return user-friendly JSON for any unhandled exception — no stack traces."""
    logger.error("api.unhandled_error", path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected error occurred while processing your request.",
            "degraded": True,
        },
    )


@app.post("/research", response_model=ResearchResponse)
async def research(question: ResearchQuestion) -> ResearchResponse:
    """Submit a natural-language research question and receive a structured response.

    Args:
        question: Validated ResearchQuestion with question text and options.

    Returns:
        ResearchResponse with answer, sources, confidence score, and optional trace.
    """
    structlog.contextvars.bind_contextvars(endpoint="POST /research")
    logger.info("api.research.start", question=question.question[:100])

    try:
        response = await run(
            question=question.question,
            max_sources=question.max_sources,
            include_trace=question.include_trace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("api.research.error", error=str(exc))
        raise  # Handled by generic_exception_handler

    logger.info(
        "api.research.complete",
        confidence=response.confidence_score,
        degraded=response.degraded,
    )
    return response


@app.get("/health")
async def health() -> dict:
    """Liveness check endpoint.

    Returns:
        JSON with status and application version.
    """
    return {"status": "ok", "version": "0.1.0"}
