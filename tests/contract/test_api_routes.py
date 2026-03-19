"""Contract tests for the FastAPI REST API routes.

Uses FastAPI's TestClient (synchronous) to verify the HTTP contract defined
in contracts/api.md: response shapes, status codes, and error behaviour.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.routes import app
from src.models.response import ResearchResponse


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _mock_run_response() -> ResearchResponse:
    return ResearchResponse(
        answer="RAG combines retrieval with generation.",
        sources=[],
        confidence_score=0.75,
        decision_trace=None,
        degraded=False,
    )


def test_health_returns_200(client: TestClient) -> None:
    """GET /health returns 200 with status=ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_research_happy_path(client: TestClient) -> None:
    """POST /research with valid body returns 200 with ResearchResponse schema."""
    with patch("src.api.routes.run", new_callable=AsyncMock, return_value=_mock_run_response()):
        response = client.post(
            "/research",
            json={"question": "What is retrieval-augmented generation?"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "confidence_score" in data
    assert "sources" in data


def test_research_empty_question_returns_422(client: TestClient) -> None:
    """POST /research with empty question returns 422 Unprocessable Entity."""
    response = client.post("/research", json={"question": ""})
    assert response.status_code == 422


def test_research_missing_question_returns_422(client: TestClient) -> None:
    """POST /research without question field returns 422."""
    response = client.post("/research", json={})
    assert response.status_code == 422


def test_research_500_returns_friendly_error(client: TestClient) -> None:
    """POST /research that raises an unhandled error returns 500 with error key, no stack trace."""
    with patch("src.api.routes.run", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        response = client.post("/research", json={"question": "test question"})
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert "boom" not in data["error"]  # Raw error detail not leaked
    assert "Traceback" not in str(data)
