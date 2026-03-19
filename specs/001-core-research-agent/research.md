# Research: Core Research Agent

**Feature**: 001-core-research-agent
**Date**: 2026-03-19
**Phase**: 0 — Resolve unknowns before design

All NEEDS CLARIFICATION items resolved. Findings below inform data-model.md, contracts/,
and implementation tasks.

---

## Decision 1: LangGraph Router Pattern

**Verified against**: LangGraph v1.1.3 (current stable, released 2026-03-18)

**Decision**: Use the prebuilt `ToolNode` and `tools_condition` from
`langgraph.prebuilt` rather than a custom router that manually inspects
`state["messages"][-1].tool_calls`.

```python
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState
```

**How it works**:
- The agent node calls `llm.bind_tools([web_search_tool, kb_tool])` and appends the
  resulting `AIMessage` (which may contain `tool_calls`) to `state["messages"]`.
- `ToolNode` automatically extracts `tool_calls` from the latest `AIMessage`, dispatches
  to the correct tool by name, and appends `ToolMessage` results back to state.
- `tools_condition` examines the latest message: returns `"tools"` if tool calls are
  present, `"__end__"` otherwise. We override the `"__end__"` branch to route to
  `"synthesize"` instead, keeping the dedicated synthesis node.

**Graph wiring**:
```
START → agent → tools_condition ──► "tools"     → ToolNode → back to agent
                                └─► "synthesize" → synthesize → format_response → END
```

**Rationale**: `ToolNode` handles parallel tool dispatch, error wrapping, and
`ToolMessage` construction automatically — replacing ~50 lines of custom node code per
tool. `tools_condition` is a one-liner that covers all routing logic correctly.
Using the prebuilt components keeps the graph lean and aligned with LangGraph's
maintained API surface.

**Alternatives Considered**: Custom `router.py` that checks
`state["messages"][-1].tool_calls` manually — this was the original plan and is
functionally equivalent, but it duplicates logic already tested in `ToolNode` and
makes the graph harder to maintain as the tool set grows. Structured output routing
(e.g., `{"action": "web_search"}`) — requires extra prompt engineering and parsing;
inferior to native function-calling.

**Impact on design**:
- `src/agent/router.py` is simplified to a single function wrapping `tools_condition`
  that remaps `"__end__"` → `"synthesize"`.
- `src/agent/graph.py` creates one `ToolNode([web_search_fn, kb_fn])` and registers it.
- Individual `web_search` and `knowledge_lookup` graph nodes are replaced by tool
  functions registered on the `ToolNode`; `synthesize` and `format_response` remain
  as explicit graph nodes.
- `AgentState` MUST include a `messages` key with the `add_messages` reducer (easiest
  via extending `MessagesState`).

**Version risk**: The research found a note that `langgraph.prebuilt` may be migrating
functionality to `langchain.agents` in a future major version. The import
`from langgraph.prebuilt import ToolNode, tools_condition` works in v1.1.3 and is
the documented stable API. Monitor the LangGraph changelog before upgrading to v2.x.

---

## Decision 2: Async Entry Point

**Decision**: Use `graph.ainvoke()` as the primary async entry point. This awaits the
complete final state and is suitable for both CLI (single invocation) and FastAPI
(async route handler).

**Rationale**: `ainvoke()` is the standard LangGraph async interface returning the full
final state. `astream()` is reserved for future streaming use cases (e.g., streaming
intermediate steps to a web UI).

**Alternatives Considered**: `astream_events()` — lower-level event tracking, useful for
observability but adds complexity; deferred to a future observability enhancement.

**Impact on design**: `src/agent/graph.py` exposes an `async def run(question, ...)`
wrapper that calls `await compiled_graph.ainvoke(initial_state)`.

---

## Decision 3: FAISS Index Strategy

**Decision**: Use `faiss.IndexFlatL2` (exact brute-force L2 search) for the initial
implementation. Document chunk size: 256–512 tokens using a sentence-aware splitter.

**Rationale**: `IndexFlatL2` is exact, deterministic, and requires no training. It is
appropriate for corpora up to ~1M vectors. The initial knowledge base is expected to be
small (developer documentation, domain papers). 256–512 token chunks balance retrieval
granularity with LLM context efficiency.

**Alternatives Considered**: `IndexIVFFlat` — faster at scale but requires a training
step and nlist tuning; appropriate if corpus grows beyond ~100k chunks. `IndexHNSW` —
better recall/speed tradeoff but higher memory footprint; defer to production scaling.

**Impact on design**: `src/tools/knowledge_base.py` loads a pre-built flat index file
from `FAISS_INDEX_PATH`. If the file does not exist, the tool returns an empty result set
(graceful degradation) rather than raising an exception.

---

## Decision 4: Confidence Score Heuristic

**Decision**: Weighted ensemble formula in the `synthesize` node:

```
confidence = (avg_relevance × 0.5) + (source_count_heuristic × 0.3) − contradiction_penalty
```

Where:
- `avg_relevance` = mean of all source `relevance_score` values (0–1)
- `source_count_heuristic` = `min(source_count / 4, 1.0)` (saturates at 4 sources)
- `contradiction_penalty` = 0.15 if the LLM detects conflicting claims, else 0.0
- Additional penalties: −0.1 if web search degraded, −0.05 if KB degraded

Final score clamped to `[0.0, 1.0]`. Matches the heuristic table in `data-model.md`.

**Rationale**: Average similarity score is the primary signal; source count adds
redundancy confidence; contradiction detection prevents over-confident answers when
sources disagree. No labeled training data required.

**Alternatives Considered**: Simple average of retrieval scores — ignores source count
and contradictions; LLM-based self-assessment prompt — possible but adds latency and
cost; defer a learned confidence model to a future feature.

**Impact on design**: `synthesize` node in `src/agent/nodes.py` computes confidence
after collecting all `AgentState.web_results` and `AgentState.kb_results`.

---

## Decision 5: structlog Configuration

**Decision**: Configure structlog with `JSONRenderer` for JSON-lines output, `contextvars`
processors for async safety, and a bound logger per module.

**Recommended configuration** (in `src/config.py`):
```python
import structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
```

Each LangGraph node calls `structlog.contextvars.bind_contextvars(node=node_name)` at
entry to stamp all subsequent log lines with the current node name.

**Rationale**: `contextvars` (not thread-locals) are safe across `async/await` boundaries.
`JSONRenderer` produces newline-delimited JSON, machine-readable by log aggregators.
`PrintLoggerFactory` writes to stdout, where container runtimes collect it.

**Alternatives Considered**: `python-json-logger` — simpler API but less flexible
processor pipeline; `loguru` — Pythonic but different async binding model; defer custom
renderers.

**Impact on design**: `src/config.py` initializes structlog at import time. All modules
use `logger = structlog.get_logger(__name__)`.

---

## Decision 6: Retry Parameters (tenacity)

**Decision**: Per external tool:

```python
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=32),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    reraise=False,
)
async def _call_with_retry(...):
    ...
```

- 3 attempts (not 5) to respect the 30s latency budget (SC-007): 2s + 4s + 8s = ~14s max
- Do NOT retry on `4xx` responses (client errors, invalid API key)
- On final failure, return a `ToolResult` with empty content and set `AgentState.degraded=True`

**Rationale**: Exponential backoff avoids thundering herd. 3 retries fit within the 30s
response budget while covering most transient network failures. `reraise=False` enables
graceful fallback rather than propagating exceptions to the graph.

**Alternatives Considered**: 5 attempts (standard recommendation) — exceeds latency
budget for the target SLO; fixed delay — less effective for bursty failures;
`wait_random_exponential` with jitter — marginal improvement, adds complexity.

**Impact on design**: `src/tools/web_search.py` and `src/tools/knowledge_base.py` wrap
their external calls with the above decorator. The base `BaseTool` class in
`src/tools/base.py` provides a shared `_execute_with_retry` helper.

---

## Decision 7: Poetry Dependency Groups

**Decision**: Split dependencies into groups per Poetry v1.2+ conventions:

```toml
[tool.poetry.dependencies]
# Runtime: langraph, anthropic, tavily-python, faiss-cpu,
#          sentence-transformers, pydantic, fastapi, structlog,
#          python-dotenv, tenacity, uvicorn, typer

[tool.poetry.group.dev.dependencies]
# Dev/test: pytest, pytest-asyncio, pytest-cov, ruff, httpx (for TestClient)
```

Install all groups locally: `poetry install`
Install runtime only in production: `poetry install --only main`

**Rationale**: Modern Poetry encourages explicit group declarations for clarity and
selective CI/CD installation. Aligns with PEP 735 intent and the project constitution's
Ruff requirement (linting in dev group only).

**Alternatives Considered**: Monolithic `[tool.poetry.dependencies]` — works but loses
environment parity controls; deprecated `[tool.poetry.dev-dependencies]` — still
supported but discouraged in Poetry v1.2+.

**Impact on design**: `pyproject.toml` uses the two-group structure above. CI runs
`poetry install --only main` for the production image and `poetry install` for test runs.
