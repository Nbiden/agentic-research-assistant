"""Knowledge base retrieval tool for the Agentic Research Assistant.

Provides an async @tool function that queries a local FAISS IndexFlatL2
loaded with domain documents. Returns an empty result list gracefully when
the index is missing or empty, enabling degraded-mode operation (FR-012).
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
import structlog

from src.agent.state import ToolResult
from src.config import settings

logger = structlog.get_logger(__name__)

# Module-level cache so the index and model load only once per process.
_faiss_index: Any | None = None
_documents: list[dict[str, Any]] | None = None
_embedding_model: Any | None = None


def _load_resources() -> tuple[Any | None, list[dict[str, Any]] | None, Any | None]:
    """Load FAISS index, documents, and embedding model (cached after first call)."""
    global _faiss_index, _documents, _embedding_model  # noqa: PLW0603

    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import]

            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as exc:  # noqa: BLE001
            logger.warning("knowledge_base.model_load_failed", error=str(exc))
            return None, None, None

    index_path = settings.faiss_index_path
    docs_path = settings.faiss_documents_path

    if index_path is None or not Path(index_path).exists():
        logger.info("knowledge_base.index_not_found", path=str(index_path))
        return None, None, _embedding_model

    if _faiss_index is None:
        try:
            import faiss  # type: ignore[import]

            _faiss_index = faiss.read_index(str(index_path))
        except Exception as exc:  # noqa: BLE001
            logger.warning("knowledge_base.index_load_failed", error=str(exc))
            return None, None, _embedding_model

    if docs_path is not None and Path(docs_path).exists() and _documents is None:
        try:
            with open(docs_path, "rb") as f:
                _documents = pickle.load(f)  # noqa: S301
        except Exception as exc:  # noqa: BLE001
            logger.warning("knowledge_base.docs_load_failed", error=str(exc))

    return _faiss_index, _documents, _embedding_model


def _normalize_scores(distances: np.ndarray) -> list[float]:
    """Convert L2 distances to relevance scores in [0, 1].

    Lower L2 distance = higher relevance. Uses exponential decay.
    """
    return [float(np.exp(-d / 10.0)) for d in distances]


from langchain_core.tools import tool  # noqa: E402


@tool
async def knowledge_base(query: str) -> list[ToolResult]:
    """Query the local FAISS knowledge base for relevant document passages.

    Loads the FAISS IndexFlatL2 and document store from disk (cached after
    first call). Returns an empty list gracefully if the index is missing,
    empty, or fails to load — the agent continues with web search and LLM
    knowledge in that case.

    Args:
        query: The search query string derived from the research question.

    Returns:
        List of ToolResult dicts sorted by relevance score descending.
        Empty list if the index is unavailable.
    """
    log = logger.bind(tool="knowledge_base", query=query[:100])
    log.info("knowledge_base.start")

    index, documents, model = _load_resources()

    if index is None or model is None:
        log.info("knowledge_base.unavailable")
        return []

    if index.ntotal == 0:
        log.info("knowledge_base.empty_index")
        return []

    import asyncio

    loop = asyncio.get_event_loop()

    def _encode_and_search() -> tuple[np.ndarray, np.ndarray]:
        embedding = model.encode([query], normalize_embeddings=True)
        k = min(5, index.ntotal)
        distances, indices = index.search(embedding.astype("float32"), k)
        return distances[0], indices[0]

    distances, indices = await loop.run_in_executor(None, _encode_and_search)
    scores = _normalize_scores(distances)

    results: list[ToolResult] = []
    for score, idx in zip(scores, indices, strict=False):
        if idx < 0:
            continue
        doc: dict[str, Any] = documents[idx] if documents and idx < len(documents) else {}
        results.append(
            ToolResult(
                content=doc.get("content", f"Document {idx}"),
                identifier=doc.get("id", f"doc_{idx}"),
                relevance_score=max(0.0, min(1.0, score)),
                source_type="knowledge_base",
                title=doc.get("title"),
            )
        )

    log.info("knowledge_base.success", result_count=len(results))
    return results
