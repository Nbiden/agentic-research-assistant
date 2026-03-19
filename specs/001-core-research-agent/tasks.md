---

description: "Task list for Core Research Agent implementation"
---

# Tasks: Core Research Agent

**Input**: Design documents from `/specs/001-core-research-agent/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.md ✅

**Tests**: Included — constitutionally required (Principle II: every module MUST have a
corresponding unit test file).

**Organization**: Tasks grouped by user story to enable independent implementation and
testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- All file paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Project initialization and tooling configuration

- [x] T001 Initialize Poetry project in pyproject.toml with all runtime and dev dependencies: langgraph>=1.1.3,<2.0, anthropic, tavily-python, faiss-cpu, sentence-transformers, pydantic>=2.0, fastapi, uvicorn, structlog, python-dotenv, tenacity, typer; dev group: pytest, pytest-asyncio, pytest-cov, ruff, httpx
- [x] T002 Create full src/ and tests/ directory structure with empty __init__.py files per plan.md: src/agent/, src/tools/, src/models/, src/api/, src/cli/, tests/unit/test_agent/, tests/unit/test_tools/, tests/unit/test_models/, tests/integration/, tests/contract/
- [x] T003 [P] Create .env.example at repository root with all required variables: ANTHROPIC_API_KEY, TAVILY_API_KEY, CLAUDE_MODEL, LOG_LEVEL, FAISS_INDEX_PATH, FAISS_DOCUMENTS_PATH, MAX_RETRIES, RETRY_BASE_DELAY
- [x] T004 [P] Configure Ruff in pyproject.toml: [tool.ruff] target-version="py311", line-length=100, select=["E","W","F","I","UP","B"]; add .ruff_cache to .gitignore
- [x] T005 [P] Configure pytest in pyproject.toml: [tool.pytest.ini_options] asyncio_mode="auto", testpaths=["tests"], python_files="test_*.py"; add pytest-asyncio asyncio_mode to pyproject.toml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure required before any user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Implement src/config.py: load all settings from environment via python-dotenv (Settings dataclass with ANTHROPIC_API_KEY, TAVILY_API_KEY, CLAUDE_MODEL, LOG_LEVEL, FAISS_INDEX_PATH, MAX_RETRIES, RETRY_BASE_DELAY); configure structlog at module import with JSONRenderer, contextvars processors, PrintLoggerFactory per research.md Decision 5
- [x] T007 [P] Implement ResearchQuestion Pydantic v2 model in src/models/request.py: fields question (str, min_length=1, max_length=2000), submitted_at (datetime, default UTC now), max_sources (int, default=5, ge=1, le=20), include_trace (bool, default=True); module docstring
- [x] T008 [P] Implement SourceType enum, Source, ToolCall, DecisionTrace, and ResearchResponse Pydantic v2 models in src/models/response.py per data-model.md; include model validator on ResearchResponse: if confidence_score < 0.5, answer must contain an uncertainty phrase; module docstring
- [x] T009 [P] Implement AgentState(MessagesState) class and ToolResult TypedDict in src/agent/state.py per data-model.md: all fields typed, annotations with Annotated where reducers needed, module docstring
- [x] T010 [P] Implement BaseTool abstract base class and ToolRegistry in src/tools/base.py: ToolRegistry stores list of registered async @tool functions; register(tool_fn) method; build_tool_list() → list; module docstring

**Checkpoint**: Foundation complete — all four user story phases can now proceed

---

## Phase 3: User Story 1 — Ask a Complex Question, Get a Cited Answer (Priority: P1) 🎯 MVP

**Goal**: End-to-end flow: question in → structured ResearchResponse out via CLI

**Independent Test**: `poetry run research-agent "What is retrieval-augmented generation?"` returns a response with non-empty answer, at least one source, and a confidence score in [0, 1]

### Implementation for User Story 1

- [x] T011 [P] [US1] Implement async web_search tool function in src/tools/web_search.py: decorated with @tool, accepts query: str, calls Tavily async client, wraps call in tenacity retry (3 attempts, exponential backoff min=2s max=32s, retry on httpx.TimeoutException + httpx.ConnectError), returns list[ToolResult] or empty list on exhausted retries; sets degraded flag via exception; module docstring
- [x] T012 [P] [US1] Implement async knowledge_base tool function in src/tools/knowledge_base.py: decorated with @tool, accepts query: str, loads FAISS IndexFlatL2 from FAISS_INDEX_PATH (returns empty list gracefully if path missing or index empty), encodes query with sentence-transformers all-MiniLM-L6-v2, searches top-k passages, returns list[ToolResult] with relevance scores normalized to [0,1]; module docstring
- [x] T013 [US1] Implement synthesizer helper (not a @tool) in src/tools/synthesizer.py: combine_sources(web_results, kb_results) → str cited answer with [N] inline markers; compute_confidence(sources, degraded, contradiction_detected) → float using weighted heuristic from data-model.md (avg_relevance×0.5 + source_count_heuristic×0.3 − penalties); module docstring
- [x] T014 [US1] Implement async agent_node function in src/agent/nodes.py: binds all tools from ToolRegistry to LLM via llm.bind_tools(); invokes LLM asynchronously; appends AIMessage to state.messages; logs node entry/exit with structlog (node_name, input summary, elapsed_ms); updates state.nodes_visited
- [x] T015 [US1] Implement research_router function in src/agent/router.py: calls tools_condition(state) from langgraph.prebuilt; remaps return value "__end__" → "synthesize"; returns "tools" or "synthesize"; module docstring
- [x] T016 [US1] Implement async synthesize_node and format_response_node in src/agent/nodes.py: synthesize_node calls synthesizer.combine_sources() and synthesizer.compute_confidence(), updates state.synthesized_answer and state.confidence_score; format_response_node builds final ResearchResponse from AgentState, respects include_trace flag; logs with structlog
- [x] T017 [US1] Wire StateGraph in src/agent/graph.py: StateGraph(AgentState); add_node for agent, tools (ToolNode(registry.build_tool_list())), synthesize, format_response; add_edge(START, "agent"); add_conditional_edges("agent", research_router, {"tools": "tools", "synthesize": "synthesize"}); add_edge("tools", "agent"); add_edge("synthesize", "format_response"); add_edge("format_response", END); compile(); expose async run(question, max_sources, include_trace) → ResearchResponse wrapper; module docstring
- [x] T018 [US1] Register web_search and knowledge_base tools via ToolRegistry in src/tools/__init__.py: this is the single registration location; import and call registry.register() for each tool function
- [x] T019 [US1] Implement CLI entry point in src/cli/main.py: typer app with question as optional argument (falls back to stdin if not a TTY); --max-sources (default 5), --no-trace, --json flags; calls asyncio.run(graph.run(...)); human-readable output formatter and --json raw mode; exit codes 0/1/2/3 per contracts/api.md; module docstring

### Tests for User Story 1

- [x] T020 [P] [US1] Unit tests for web_search in tests/unit/test_tools/test_web_search.py: mock TavilyClient; test successful search returns ToolResult list; test single retry on timeout; test empty list returned after 3 exhausted retries (no exception raised)
- [x] T021 [P] [US1] Unit tests for knowledge_base in tests/unit/test_tools/test_knowledge_base.py: mock FAISS index; test successful query returns scored results; test missing index file returns empty list without exception; test empty index returns empty list
- [x] T022 [P] [US1] Unit tests for Pydantic models in tests/unit/test_models/test_request.py and tests/unit/test_models/test_response.py: question length validation; confidence_score bounds; SourceType enum values; ResearchResponse model validator (low confidence requires uncertainty phrase)
- [x] T023 [US1] Unit tests for agent nodes and router in tests/unit/test_agent/test_nodes.py and tests/unit/test_agent/test_router.py: mock LLM responses with and without tool_calls; verify agent_node appends AIMessage; verify research_router maps "__end__"→"synthesize" and "tools"→"tools"
- [x] T024 [US1] Unit tests for graph compilation in tests/unit/test_agent/test_graph.py: verify graph compiles without error; mock all tool calls; call graph.run() and verify ResearchResponse is returned with correct fields populated
- [x] T025 [US1] Integration test for end-to-end P1 flow in tests/integration/test_research_flow.py: stub Tavily (return fixture results) and FAISS (return fixture passages); submit question; assert response.answer is non-empty, len(response.sources) >= 1, 0 <= response.confidence_score <= 1

**Checkpoint**: User Story 1 complete — `poetry run research-agent "test question"` returns a full ResearchResponse

---

## Phase 4: User Story 2 — Transparent Decision Trace (Priority: P2)

**Goal**: Every response includes a complete, accurate decision_trace with per-tool rationale, elapsed time, and success status

**Independent Test**: Submit any question with `include_trace=True`; assert `response.decision_trace.tool_calls` has one entry per tool invoked, each with non-empty `rationale`, `input_summary`, `output_summary`, and `elapsed_ms >= 0`

### Implementation for User Story 2

- [x] T026 [US2] Update agent_node in src/agent/nodes.py to extract and log ToolCall records: for each entry in AIMessage.tool_calls, capture tool_name, rationale (from tool_call.get("name") + LLM reasoning summary), input_summary; record start timestamp before ToolNode execution for elapsed_ms calculation; append partial ToolCall to state.tool_calls_log
- [x] T027 [US2] Update format_response_node in src/agent/nodes.py to finalize ToolCall records (add output_summary, success flag, elapsed_ms) and build DecisionTrace (nodes_visited, total_elapsed_ms = sum of all elapsed_ms); when include_trace=False, set decision_trace=None in ResearchResponse
- [x] T028 [US2] Ensure structlog emits one structured JSON log line per node at both entry (node, question_summary) and exit (node, elapsed_ms, output_summary, success) in all node functions in src/agent/nodes.py; bind node name via structlog.contextvars.bind_contextvars at node entry

### Tests for User Story 2

- [x] T029 [P] [US2] Unit tests for trace construction in tests/unit/test_agent/test_nodes.py: verify ToolCall populated with all required fields; verify include_trace=False produces decision_trace=None; verify nodes_visited list order matches execution order
- [x] T030 [US2] Integration tests for trace in tests/integration/test_research_flow.py: 2-tool query → trace has 2 entries; no-tool query → trace records LLM-only decision; failed tool → trace records success=False and error_message

**Checkpoint**: User Stories 1 AND 2 independently functional

---

## Phase 5: User Story 3 — Extend the Agent with a New Tool (Priority: P3)

**Goal**: A new tool can be added by registering it in src/tools/__init__.py only — no changes to graph.py, nodes.py, or router.py

**Independent Test**: Add stub `echo_tool` to ToolRegistry in tests/, run agent, confirm `echo_tool` appears in decision_trace.tool_calls without modifying any file outside src/tools/__init__.py

### Implementation for User Story 3

- [x] T031 [US3] Verify and harden ToolRegistry in src/tools/base.py: confirm register() accepts any async @tool-decorated callable; build_tool_list() returns current snapshot; add deregister(tool_name) method for test teardown; add list_tools() → list[str] method; update module docstring
- [x] T032 [US3] Verify src/agent/graph.py builds ToolNode dynamically from ToolRegistry.build_tool_list() at compile() time (not from a hardcoded import list); graph must re-read registry on each compile() call so newly registered tools are picked up

### Tests for User Story 3

- [x] T033 [P] [US3] Unit tests for ToolRegistry in tests/unit/test_tools/test_base.py: register new stub tool → appears in build_tool_list(); deregister → absent from list; list_tools() returns correct names; ToolNode built from registry includes stub tool
- [x] T034 [US3] Integration test in tests/integration/test_research_flow.py: register stub async @tool("echo_tool") that returns a fixed ToolResult; run agent with question that would invoke it; assert "echo_tool" appears in response.decision_trace.tool_calls; deregister after test; confirm graph.py was not modified

**Checkpoint**: User Stories 1, 2, AND 3 independently functional

---

## Phase 6: User Story 4 — Honest Uncertainty Expression (Priority: P4)

**Goal**: When evidence is insufficient, confidence_score < 0.5 and answer contains an explicit uncertainty statement; no hallucination

**Independent Test**: Submit a question about a future event (e.g., "Who won the 2099 World Cup?") with all tools stubbed to return empty results; assert response.confidence_score < 0.5 and "uncertain" or "insufficient" appears in response.answer

### Implementation for User Story 4

- [x] T035 [US4] Complete confidence heuristic in src/tools/synthesizer.py: implement full weighted formula from data-model.md (avg_relevance×0.5 + min(source_count/4,1.0)×0.3 minus contradiction_penalty=0.15 if contradictions detected, minus 0.1 if web degraded, minus 0.05 if KB degraded); clamp result to [0.0, 1.0]
- [x] T036 [US4] Update synthesize_node in src/agent/nodes.py: when computed confidence_score < 0.5, prepend an explicit uncertainty statement to the synthesized answer (e.g., "I have limited reliable information on this topic. "); ensure the Pydantic model validator in ResearchResponse (T008) accepts the result

### Tests for User Story 4

- [x] T037 [P] [US4] Unit tests for confidence heuristic in tests/unit/test_tools/test_synthesizer.py: 0-source input → score < 0.5; 4-source high-relevance input → score >= 0.7; degraded=True reduces score; contradiction flag reduces score; all outputs in [0.0, 1.0]
- [x] T038 [US4] Integration tests for uncertainty in tests/integration/test_research_flow.py: stub all tools to return empty results → confidence < 0.5 and uncertainty phrase in answer; stub conflicting results → confidence < 0.8 and answer presents both perspectives

**Checkpoint**: All four user stories independently functional

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: REST API layer, docstring completeness, lint gate, and quickstart validation

- [x] T039 [P] Implement FastAPI app and POST /research + GET /health routes in src/api/routes.py and src/api/__init__.py: POST /research accepts ResearchQuestion JSON body, calls asyncio.run(graph.run(...)) or await in async handler, returns ResearchResponse; GET /health returns {"status":"ok","version":"0.1.0"}; 500 handler returns user-friendly JSON error with degraded=True, never raw stack trace; module docstring
- [x] T040 [P] Contract tests for REST API in tests/contract/test_api_routes.py: use FastAPI TestClient; POST /research happy path returns 200 with full ResearchResponse schema; POST /research with empty question returns 422; GET /health returns 200 {"status":"ok"}
- [x] T041 [P] Audit all src/ modules for missing module-level docstrings and missing public function/class docstrings; add any missing (constitution Principle II compliance)
- [x] T042 Run ruff check . and ruff format . across the entire repository; fix all reported violations before marking complete (constitution Principle I linting gate)
- [x] T043 [P] Validate specs/001-core-research-agent/quickstart.md: confirm all commands execute successfully against the actual implementation (poetry install, pytest, ruff, CLI invocation, API server start); update any commands that have drifted

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2/3/4
- **US2 (Phase 4)**: Depends on Phase 3 (extends agent nodes and format_response)
- **US3 (Phase 5)**: Depends on Phase 3 (extends ToolRegistry and graph.py)
- **US4 (Phase 6)**: Depends on Phase 3 (extends synthesizer and synthesize node)
- **Polish (Phase N)**: Depends on all user story phases being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no dependency on US2/3/4
- **US2 (P2)**: Depends on US1 (modifies nodes.py and format_response_node)
- **US3 (P3)**: Depends on US1 (modifies ToolRegistry and graph.py compile step)
- **US4 (P4)**: Depends on US1 (modifies synthesizer.py and synthesize_node)
- **US2, US3, US4**: Can proceed in parallel after US1 completes

### Within Each User Story

- Tool implementations [P] before node implementations (nodes call tools)
- Node implementations before graph wiring
- Graph wiring before CLI entry point
- Unit tests [P] for tools can start alongside tool implementation (different files)
- Integration tests after all implementation tasks in the story

### Parallel Opportunities

- All Phase 1 [P] tasks can run in parallel (T003, T004, T005)
- All Phase 2 [P] tasks can run in parallel (T007, T008, T009, T010)
- Within US1: T011 and T012 are parallel (different tool files)
- Within US1: T020, T021, T022 can all start in parallel once implementations begin
- Once US1 completes: US2, US3, US4 can run in parallel (different files)
- Within Polish: T039, T040, T041, T043 are all parallel

---

## Parallel Example: User Story 1

```bash
# Start both tool implementations together:
Task: T011 — "Implement web_search tool in src/tools/web_search.py"
Task: T012 — "Implement knowledge_base tool in src/tools/knowledge_base.py"

# Start corresponding unit tests alongside (different files):
Task: T020 — "Unit tests for web_search in tests/unit/test_tools/test_web_search.py"
Task: T021 — "Unit tests for knowledge_base in tests/unit/test_tools/test_knowledge_base.py"
Task: T022 — "Unit tests for Pydantic models in tests/unit/test_models/"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `poetry run research-agent "What is RAG?"` returns full response
5. Demonstrate to stakeholders if ready

### Incremental Delivery

1. Setup + Foundational → project compiles and tests pass
2. User Story 1 → CLI works end-to-end, basic trace included
3. User Story 2 → Complete trace with structlog; audit observability
4. User Story 3 → Tool extensibility verified; new tools addable without graph changes
5. User Story 4 → Uncertainty expressed; confidence heuristic tuned
6. Polish → REST API, docstrings, lint gate, quickstart validated

### Parallel Team Strategy (if 2+ developers)

After Foundational completes:
- Developer A: User Story 1 (full core flow)
- (After US1) Developer A: User Story 2 | Developer B: User Story 3 | Developer C: User Story 4

---

## Notes

- `[P]` tasks operate on different files — safe to run in parallel
- `[Story]` label maps each task to its user story for traceability
- Each user story checkpoint produces an independently testable increment
- Constitution Principle II: all unit test files are mandatory, not optional
- Pin `langgraph>=1.1.3,<2.0` — `langgraph.prebuilt` migration risk noted in research.md
- Commit after each completed task or logical group (Principle VII: atomic commits)
