# agentic-research-assistant Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-19

## Active Technologies

- **001-core-research-agent**: Python 3.11+, LangGraph, anthropic SDK, tavily-python,
  faiss-cpu, sentence-transformers, Pydantic v2, FastAPI, structlog, tenacity,
  python-dotenv, Poetry

## Project Structure

```text
src/
├── agent/        # LangGraph StateGraph, nodes, state, router
├── tools/        # BaseTool, web_search, knowledge_base, synthesizer
├── models/       # Pydantic v2 request/response models
├── api/          # FastAPI routes
├── cli/          # CLI entry point
└── config.py     # python-dotenv settings

tests/
├── unit/         # Per-module unit tests
├── integration/  # End-to-end flow tests
└── contract/     # FastAPI TestClient contract tests
```

## Commands

```bash
# Install dependencies
poetry install

# Run all tests
poetry run pytest

# Lint
poetry run ruff check .

# Format check
poetry run ruff format --check .

# Run CLI
poetry run research-agent "Your question here"

# Run API server
poetry run uvicorn src.api.routes:app --reload
```

## Code Style

- Python 3.11+ with full type annotations on every function and method
- PEP 8 enforced via Ruff; all `Any` annotations require an inline justification comment
- Every module MUST have a module-level docstring; every public class/function MUST have a docstring
- All secrets via environment variables (python-dotenv); never hardcoded
- All I/O-bound operations use `async/await`; no blocking calls in async context
- structlog JSON-lines at every LangGraph node; log level via `LOG_LEVEL` env var
- tenacity retry (3 attempts, exponential backoff 2–32s) on all external tool calls

## Recent Changes

- 2026-03-19 (001-core-research-agent): Initial project setup — LangGraph agent with
  Tavily web search, FAISS knowledge base, synthesis, CLI + FastAPI

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
