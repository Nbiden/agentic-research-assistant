"""Unit tests for the knowledge_base tool.

Tests cover: successful query, missing index file returns empty list,
empty index returns empty list, and relevance score normalisation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import src.tools.knowledge_base as kb_module
from src.tools.knowledge_base import knowledge_base


@pytest.fixture(autouse=True)
def reset_kb_cache():
    """Reset module-level cache between tests."""
    kb_module._faiss_index = None
    kb_module._documents = None
    kb_module._embedding_model = None
    yield
    kb_module._faiss_index = None
    kb_module._documents = None
    kb_module._embedding_model = None


def _make_mock_model() -> MagicMock:
    mock_model = MagicMock()
    mock_model.encode.return_value = np.random.rand(1, 384).astype("float32")
    return mock_model


def _make_mock_index(ntotal: int = 3) -> MagicMock:
    mock_index = MagicMock()
    mock_index.ntotal = ntotal
    mock_index.search.return_value = (
        np.array([[0.1, 0.5, 1.0]]),
        np.array([[0, 1, 2]]),
    )
    return mock_index


@pytest.mark.asyncio()
async def test_knowledge_base_returns_results() -> None:
    """Successful query returns a non-empty ToolResult list."""
    mock_model = _make_mock_model()
    mock_index = _make_mock_index(ntotal=3)
    docs = [
        {"content": "doc A", "id": "doc_0", "title": "Doc A"},
        {"content": "doc B", "id": "doc_1", "title": "Doc B"},
        {"content": "doc C", "id": "doc_2", "title": "Doc C"},
    ]

    with (
        patch(
            "src.tools.knowledge_base._load_resources",
            return_value=(mock_index, docs, mock_model),
        ),
    ):
        results = await knowledge_base.ainvoke({"query": "test query"})

    assert len(results) > 0
    assert results[0]["source_type"] == "knowledge_base"
    assert 0.0 <= results[0]["relevance_score"] <= 1.0


@pytest.mark.asyncio()
async def test_knowledge_base_missing_index_returns_empty() -> None:
    """Missing index file returns empty list without raising an exception."""
    with patch(
        "src.tools.knowledge_base._load_resources",
        return_value=(None, None, MagicMock()),
    ):
        results = await knowledge_base.ainvoke({"query": "test"})

    assert results == []


@pytest.mark.asyncio()
async def test_knowledge_base_empty_index_returns_empty() -> None:
    """Index with zero documents returns empty list."""
    mock_index = MagicMock()
    mock_index.ntotal = 0
    with patch(
        "src.tools.knowledge_base._load_resources",
        return_value=(mock_index, [], MagicMock()),
    ):
        results = await knowledge_base.ainvoke({"query": "test"})

    assert results == []


@pytest.mark.asyncio()
async def test_knowledge_base_relevance_scores_normalised() -> None:
    """All returned relevance scores are in [0, 1]."""
    mock_model = _make_mock_model()
    mock_index = _make_mock_index(ntotal=3)
    docs = [{"content": f"doc {i}", "id": f"doc_{i}"} for i in range(3)]

    with patch(
        "src.tools.knowledge_base._load_resources",
        return_value=(mock_index, docs, mock_model),
    ):
        results = await knowledge_base.ainvoke({"query": "test"})

    for r in results:
        assert 0.0 <= r["relevance_score"] <= 1.0
