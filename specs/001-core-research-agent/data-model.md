# Data Model: Core Research Agent

**Feature**: 001-core-research-agent
**Date**: 2026-03-19

---

## Overview

All models are implemented with Pydantic v2. External-facing models (request/response)
are defined in `src/models/`. Internal agent state is defined in `src/agent/state.py` as
a TypedDict to satisfy LangGraph's state requirements.

---

## External Models

### ResearchQuestion

**Location**: `src/models/request.py`
**Purpose**: The validated input received from CLI or API.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `question` | `str` | min_length=1, max_length=2000 | Natural-language research question |
| `submitted_at` | `datetime` | default=now (UTC) | Timestamp of submission |
| `max_sources` | `int` | default=5, ge=1, le=20 | Max sources to include in response |
| `include_trace` | `bool` | default=True | Whether to populate decision_trace in response |

---

### ResearchResponse

**Location**: `src/models/response.py`
**Purpose**: The complete structured output returned to the caller.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `answer` | `str` | min_length=1 | Natural-language answer with inline citations |
| `sources` | `list[Source]` | min_length=0 | Retrieved evidence, sorted by relevance desc |
| `confidence_score` | `float` | ge=0.0, le=1.0 | Heuristic confidence in the answer |
| `decision_trace` | `DecisionTrace \| None` | nullable | Tool call history; None if include_trace=False |
| `generated_at` | `datetime` | default=now (UTC) | Timestamp of response generation |
| `degraded` | `bool` | default=False | True if one or more tools failed during processing |

**Validation rule**: If `confidence_score < 0.5`, the `answer` field MUST contain an
explicit uncertainty marker (validated by a model validator).

---

### Source

**Location**: `src/models/response.py`
**Purpose**: A single piece of retrieved evidence cited in the answer.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `content` | `str` | min_length=1 | The retrieved text snippet |
| `identifier` | `str` | min_length=1 | URL (web) or document ID (knowledge base) |
| `relevance_score` | `float` | ge=0.0, le=1.0 | Relevance to the research question |
| `source_type` | `SourceType` | enum | One of: `web`, `knowledge_base`, `llm` |
| `title` | `str \| None` | nullable | Page title or document name if available |

**Enum**: `SourceType`
- `web` — retrieved from Tavily web search
- `knowledge_base` — retrieved from local FAISS index
- `llm` — answered from LLM training knowledge (no external retrieval)

---

### ToolCall

**Location**: `src/models/response.py`
**Purpose**: A record of one tool invocation within the reasoning loop.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `tool_name` | `str` | min_length=1 | Name of the tool invoked |
| `rationale` | `str` | min_length=1 | LLM's stated reason for invoking this tool |
| `input_summary` | `str` | min_length=1 | Brief summary of what was passed to the tool |
| `output_summary` | `str` | min_length=1 | Brief summary of what the tool returned |
| `success` | `bool` | required | True if the tool completed without error |
| `elapsed_ms` | `int` | ge=0 | Wall-clock time for the tool call in milliseconds |
| `error_message` | `str \| None` | nullable | Human-readable error if success=False |

---

### DecisionTrace

**Location**: `src/models/response.py`
**Purpose**: Ordered record of all tool calls for a single query.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `tool_calls` | `list[ToolCall]` | min_length=0 | Ordered list of all tool invocations |
| `total_elapsed_ms` | `int` | ge=0 | Sum of all tool elapsed times |
| `nodes_visited` | `list[str]` | min_length=1 | Ordered list of LangGraph node names visited |

---

## Internal Agent State

### AgentState

**Location**: `src/agent/state.py`
**Type**: Extends `MessagesState` from `langgraph.graph.message` (verified v1.1.3)
**Purpose**: Shared mutable state accumulating results as the graph executes.

`MessagesState` provides the `messages: Annotated[list[AnyMessage], add_messages]`
field with the `add_messages` reducer built-in. `AgentState` adds custom fields on top:

```python
from langgraph.graph.message import MessagesState

class AgentState(MessagesState):
    question: str
    include_trace: bool
    max_sources: int
    web_results: list[ToolResult]
    kb_results: list[ToolResult]
    tool_calls_log: list[ToolCall]
    nodes_visited: list[str]
    synthesized_answer: str | None
    sources: list[Source]
    confidence_score: float | None
    degraded: bool
    error_context: str | None
```

| Field | Type | Description |
|---|---|---|
| `messages` | `list[AnyMessage]` | **Inherited from MessagesState**; managed by `add_messages` reducer |
| `question` | `str` | The original research question |
| `include_trace` | `bool` | Whether to build the decision trace |
| `max_sources` | `int` | Max sources to include |
| `web_results` | `list[ToolResult]` | Accumulated web search results |
| `kb_results` | `list[ToolResult]` | Accumulated knowledge base results |
| `tool_calls_log` | `list[ToolCall]` | In-progress decision trace entries |
| `nodes_visited` | `list[str]` | Ordered node names visited so far |
| `synthesized_answer` | `str \| None` | Output of the synthesize node |
| `sources` | `list[Source]` | Finalized source list after synthesis |
| `confidence_score` | `float \| None` | Computed confidence (set by synthesize node) |
| `degraded` | `bool` | Set to True if any tool failed during execution |
| `error_context` | `str \| None` | Last user-friendly error message if a tool failed |

---

### ToolResult

**Location**: `src/agent/state.py`
**Type**: `TypedDict`
**Purpose**: Intermediate result from a single tool invocation, stored in AgentState.

| Field | Type | Description |
|---|---|---|
| `content` | `str` | Retrieved text content |
| `identifier` | `str` | URL or document ID |
| `relevance_score` | `float` | Score in [0, 1] |
| `source_type` | `str` | `"web"` or `"knowledge_base"` |
| `title` | `str \| None` | Optional title |

---

## State Transitions

Using LangGraph v1.1.3 prebuilt `ToolNode` + `tools_condition`:

```text
START
  └─► agent (LLM with bound tools)
        └─► tools_condition
              ├─► "tools"      → ToolNode (dispatches to web_search OR knowledge_lookup
              │                  based on tool_calls; appends ToolMessage to messages)
              │                      └─► back to agent (loop until no more tool_calls)
              └─► "synthesize" → synthesize
                                    └─► format_response
                                              └─► END
```

**Conditional routing logic** (in `src/agent/router.py`):

```python
from langgraph.prebuilt import tools_condition

def research_router(state: AgentState) -> str:
    """Route to tools if tool_calls present; otherwise to synthesize."""
    next_node = tools_condition(state)
    return "synthesize" if next_node == "__end__" else next_node
```

- The `agent` node calls `llm.bind_tools([web_search_fn, kb_fn])` and invokes the LLM.
- The LLM's `AIMessage` (with or without `tool_calls`) is appended to `state.messages`.
- `tools_condition` inspects the latest message: `"tools"` if `tool_calls` present,
  `"__end__"` otherwise. The `research_router` wrapper remaps `"__end__"` → `"synthesize"`.
- `ToolNode` automatically dispatches to the named tool, wraps results in `ToolMessage`,
  and returns control to the agent. This loop continues until no tool calls remain.
- The `synthesize` node reads `state.messages` (all `ToolMessage` results) to produce
  the cited answer and confidence score.

---

## Confidence Score Heuristic

Computed in the `synthesize` node using the following rules:

| Condition | Score Adjustment |
|---|---|
| 0 sources retrieved | base = 0.3 |
| 1 source retrieved | base = 0.5 |
| 2–3 sources retrieved | base = 0.7 |
| 4+ sources retrieved | base = 0.85 |
| All sources from same type | −0.05 |
| Web search degraded (failed) | −0.1 |
| KB degraded (empty/failed) | −0.05 |
| Sources contain contradictions (detected by LLM) | −0.15 |

Final score clamped to `[0.0, 1.0]`.
