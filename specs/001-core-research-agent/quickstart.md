# Quickstart: Core Research Agent

**Feature**: 001-core-research-agent
**Date**: 2026-03-19

---

## Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation) installed
- Anthropic API key (for Claude)
- Tavily API key (for web search)

---

## 1. Install Dependencies

```bash
poetry install
```

This installs all dependencies (including dev/test groups) declared in `pyproject.toml`.

---

## 2. Configure Environment

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# Required
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...

# Optional — defaults shown
CLAUDE_MODEL=claude-sonnet-4-20250514
LOG_LEVEL=INFO
FAISS_INDEX_PATH=./data/knowledge_base.index
FAISS_DOCUMENTS_PATH=./data/documents.pkl
MAX_RETRIES=3
RETRY_BASE_DELAY=1.0
```

**Never commit `.env` to version control.** It is listed in `.gitignore`.

---

## 3. Prepare the Knowledge Base (optional)

If you have domain documents to load into the local FAISS index, run the indexing
utility (out of scope for this feature — index is assumed pre-built):

```bash
# Placeholder — indexing script will be added in a future feature
poetry run python -m src.tools.knowledge_base --index ./data/my_documents/
```

If no index is available, the agent falls back to web search and LLM knowledge only.

---

## 4. Run via CLI

```bash
# Basic query
poetry run research-agent "What are the key differences between RAG and fine-tuning?"

# Limit sources, suppress trace
poetry run research-agent "Explain LangGraph state machines" --max-sources 3 --no-trace

# JSON output (for programmatic use)
poetry run research-agent "Latest news on AI safety" --json

# Stdin
echo "What is FAISS?" | poetry run research-agent
```

---

## 5. Run the REST API Server

```bash
poetry run uvicorn src.api.routes:app --host 0.0.0.0 --port 8000 --reload
```

Test with curl:

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"question": "What is retrieval-augmented generation?", "max_sources": 3}'
```

Health check:

```bash
curl http://localhost:8000/health
```

---

## 6. Run Tests

```bash
# All tests
poetry run pytest

# Unit tests only
poetry run pytest tests/unit/

# Integration tests only (requires valid API keys in .env)
poetry run pytest tests/integration/

# With coverage
poetry run pytest --cov=src --cov-report=term-missing
```

---

## 7. Lint and Format

```bash
# Check for violations
poetry run ruff check .

# Auto-fix safe violations
poetry run ruff check . --fix

# Format check
poetry run ruff format --check .

# Apply formatting
poetry run ruff format .
```

CI will fail if any Ruff violation exists.

---

## Validation Checklist

Before opening a PR, verify:

- [ ] `poetry run pytest` passes with no failures
- [ ] `poetry run ruff check .` reports no violations
- [ ] `poetry run ruff format --check .` reports no violations
- [ ] `poetry run research-agent "test question"` returns a structured response
- [ ] No API keys appear in any committed file (`git grep -r "sk-ant\|tvly-"`)
- [ ] `.env` is not staged (`git status` shows clean `.env`)
