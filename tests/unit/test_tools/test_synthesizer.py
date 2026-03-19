"""Unit tests for the synthesizer confidence heuristic and combine_sources helper."""

from __future__ import annotations

from src.models.response import Source, SourceType
from src.tools.synthesizer import combine_sources, compute_confidence


def _make_source(relevance: float = 0.8, source_type: str = "web") -> Source:
    return Source(
        content="test content",
        identifier="https://example.com",
        relevance_score=relevance,
        source_type=SourceType(source_type),
    )


# --- compute_confidence ---


def test_zero_sources_below_threshold() -> None:
    score = compute_confidence(sources=[])
    assert score < 0.5


def test_single_source_moderate_confidence() -> None:
    score = compute_confidence(sources=[_make_source(0.9)])
    assert score >= 0.4


def test_four_high_relevance_sources_above_threshold() -> None:
    sources = [_make_source(0.9) for _ in range(4)]
    score = compute_confidence(sources=sources)
    assert score >= 0.7


def test_web_degraded_reduces_score() -> None:
    sources = [_make_source(0.8) for _ in range(2)]
    score_normal = compute_confidence(sources=sources)
    score_degraded = compute_confidence(sources=sources, web_degraded=True)
    assert score_degraded < score_normal


def test_contradiction_reduces_score() -> None:
    sources = [_make_source(0.9) for _ in range(3)]
    score_normal = compute_confidence(sources=sources)
    score_contradicted = compute_confidence(sources=sources, contradiction_detected=True)
    assert score_contradicted < score_normal


def test_score_always_in_valid_range() -> None:
    """Score is always clamped to [0.0, 1.0] regardless of inputs."""
    for n in range(0, 6):
        sources = [_make_source(1.0) for _ in range(n)]
        score = compute_confidence(
            sources=sources,
            degraded=True,
            web_degraded=True,
            kb_degraded=True,
            contradiction_detected=True,
        )
        assert 0.0 <= score <= 1.0, f"Score {score} out of range for {n} sources"


def test_kb_degraded_reduces_score() -> None:
    sources = [_make_source(0.8)]
    score_normal = compute_confidence(sources=sources)
    score_kb_degraded = compute_confidence(sources=sources, kb_degraded=True)
    assert score_kb_degraded < score_normal


# --- combine_sources ---


def test_combine_sources_merges_web_and_kb() -> None:
    from src.agent.state import ToolResult

    web = [
        ToolResult(
            content="web content",
            identifier="https://w.com",
            relevance_score=0.9,
            source_type="web",
            title=None,
        )
    ]
    kb = [
        ToolResult(
            content="kb content",
            identifier="doc_1",
            relevance_score=0.7,
            source_type="knowledge_base",
            title=None,
        )
    ]

    sources, citation = combine_sources(web, kb)

    types = {s.source_type.value for s in sources}
    assert "web" in types
    assert "knowledge_base" in types


def test_combine_sources_respects_max_sources() -> None:
    from src.agent.state import ToolResult

    web = [
        ToolResult(
            content=f"w{i}",
            identifier=f"https://w{i}.com",
            relevance_score=0.9 - i * 0.1,
            source_type="web",
            title=None,
        )
        for i in range(10)
    ]
    sources, _ = combine_sources(web, [], max_sources=3)
    assert len(sources) <= 3


def test_combine_sources_sorted_by_relevance() -> None:
    from src.agent.state import ToolResult

    results = [
        ToolResult(
            content="low", identifier="low.com", relevance_score=0.3, source_type="web", title=None
        ),
        ToolResult(
            content="high",
            identifier="high.com",
            relevance_score=0.9,
            source_type="web",
            title=None,
        ),
    ]
    sources, _ = combine_sources(results, [])
    assert sources[0].relevance_score >= sources[1].relevance_score
