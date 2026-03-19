# Implementation Plan: Core Research Agent

**Branch**: `001-core-research-agent` | **Date**: 2026-03-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-core-research-agent/spec.md`

## Summary

Build an agentic research assistant that accepts natural-language questions via CLI and
REST API, runs a LangGraph StateGraph to autonomously select and invoke tools (web search,
local FAISS knowledge base, and synthesis), and returns a structured response containing
a cited answer, ranked sources, a confidence score, and a full decision trace. The system
degrades gracefully when tools are unavailable and never exposes raw stack traces to users.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: LangGraph, anthropic SDK, tavily-python, faiss-cpu,
  sentence-transformers (all-MiniLM-L6-v2), Pydantic v2, FastAPI, structlog,
  python-dotenv, tenacity, Poetry
**Storage**: FAISS local flat L2 index (file-based, no external vector DB)
**Testing**: pytest + pytest-asyncio
**Target Platform**: Linux/macOS developer machine (CLI); optional FastAPI HTTP server
**Project Type**: CLI tool + optional web service (single-project layout)
**Performance Goals**: End-to-end response under 30 seconds for 1–2 tool calls (SC-007)
**Constraints**: Graceful degradation when Tavily unavailable; zero raw stack traces in
  user-facing output; API keys exclusively from environment variables
**Scale/Scope**: Single-user / small-team use; single-process deployment

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|---|---|---|
| I. Code Quality & Style | ✅ PASS | Python 3.11+; Pydantic v2 enforces types; Ruff configured in pyproject.toml |
| II. Documentation & Testing | ✅ PASS | pytest + pytest-asyncio; docstrings required on all modules per plan |
| III. Security & Configuration | ✅ PASS | python-dotenv for all keys; .env in .gitignore; .env.example committed |
| IV. Resilience & Error Handling | ✅ PASS | tenacity retry/backoff on every tool; fallback nodes in graph; user-friendly errors |
| V. Observability | ✅ PASS | structlog JSON-lines at every LangGraph node; LOG_LEVEL env var |
| VI. Async Patterns | ✅ PASS | graph.ainvoke() entry point; all tool calls async; no blocking I/O in async context |
| VII. Version Control Discipline | ✅ PASS | conventional commits; atomic per-task commits enforced in workflow |

**Gate result**: ✅ ALL PASS — proceed to Phase 0.

*Technology Stack additions vs constitution*: Poetry (dependency management) and tenacity
(retry) are additions to the approved stack. Both are aligned with constitution intent and
recorded here as justified additions. No Complexity Tracking entry required.

## Project Structure

### Documentation (this feature)

```text
specs/001-core-research-agent/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── api.md
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── agent/
│   ├── __init__.py
│   ├── graph.py          # StateGraph wiring: nodes, ToolNode, edges, compile()
│   ├── nodes.py          # Node functions: agent (LLM+bind_tools), synthesize,
│   │                     #   format_response
│   ├── state.py          # AgentState(MessagesState) + ToolResult TypedDict
│   └── router.py         # research_router: wraps tools_condition, remaps __end__
│                         #   → "synthesize" (langgraph.prebuilt, v1.1.3)
├── tools/
│   ├── __init__.py
│   ├── base.py           # BaseTool abstract class + ToolRegistry
│   ├── web_search.py     # Tavily web search (async @tool fn, retry, fallback)
│   ├── knowledge_base.py # FAISS retrieval (async @tool fn, relevance scoring)
│   └── synthesizer.py    # Synthesis helper (not a graph tool; called by synthesize node)
├── models/
│   ├── __init__.py
│   ├── request.py        # ResearchQuestion (Pydantic v2)
│   └── response.py       # ResearchResponse, Source, ToolCall, DecisionTrace
├── api/
│   ├── __init__.py
│   └── routes.py         # FastAPI router: POST /research
├── cli/
│   ├── __init__.py
│   └── main.py           # CLI entry point (argparse or typer)
└── config.py             # Settings loaded via python-dotenv

tests/
├── unit/
│   ├── test_agent/       # Graph, nodes, router unit tests
│   ├── test_tools/       # Each tool unit-tested in isolation (mocked externals)
│   └── test_models/      # Pydantic model validation tests
├── integration/
│   └── test_research_flow.py  # End-to-end flow with real or stubbed tools
└── contract/
    └── test_api_routes.py     # FastAPI TestClient contract tests

pyproject.toml            # Poetry; includes Ruff config
.env.example              # Non-secret template (committed)
.env                      # Real secrets (git-ignored)
```

**Structure Decision**: Single-project layout. The agent orchestration (`src/agent/`),
tools (`src/tools/`), data models (`src/models/`), API layer (`src/api/`), and CLI
(`src/cli/`) are separated by concern within a single `src/` tree. This avoids
premature multi-package complexity while keeping boundaries clean for future extraction.

## Complexity Tracking

> No constitution violations — table not required.
