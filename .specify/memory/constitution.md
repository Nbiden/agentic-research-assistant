<!--
## Sync Impact Report

**Version Change**: unversioned template → 1.0.0
**Bump Type**: MINOR — Initial constitution population; all principles and sections
               are new additions derived from user-supplied governing rules.

### Modified Principles
- None (initial adoption; all principles created fresh from user input)

### Added Sections
- I. Code Quality & Style
- II. Documentation & Testing
- III. Security & Configuration
- IV. Resilience & Error Handling
- V. Observability
- VI. Async Patterns
- VII. Version Control Discipline
- Technology Stack (Section 2)
- Development Workflow (Section 3)
- Governance

### Removed Sections
- None

### Template Sync Status
- ✅ `.specify/templates/plan-template.md` — Constitution Check gate is runtime-filled
      by `/speckit.plan`; no structural template change required. Principles I–VII
      will appear as gate items at plan generation time.
- ✅ `.specify/templates/spec-template.md` — Mandatory sections (user stories,
      requirements, success criteria) align with Principles II and IV; no changes
      required.
- ✅ `.specify/templates/tasks-template.md` — Phase 2 foundational tasks already
      include logging infrastructure (T008) and environment config (T009), covering
      Principles III and V; no changes required.

### Deferred Items
- TODO(RATIFICATION_DATE): Set to 2026-03-19 (first constitution adoption date).
  Confirm with project owner if an earlier project start date should be used instead.
-->

# Agentic Research Assistant Constitution

## Core Principles

### I. Code Quality & Style

All Python source code MUST target Python 3.11+ and include full type annotations on
every function signature, method, and module-level variable. Code MUST conform to PEP 8
style. Ruff MUST be configured as the project linter and formatter; CI MUST fail on any
Ruff violation. Untyped `Any` annotations are PROHIBITED without an explicit justification
comment on the same line.

**Rationale**: Type safety and consistent style reduce defect rates and lower the cost of
onboarding contributors. Ruff provides fast, deterministic enforcement with zero ambiguity.

### II. Documentation & Testing

Every Python module MUST have a module-level docstring describing its purpose and public
API. Every public class and function MUST have a docstring. Every module MUST have a
corresponding unit test file; untested modules MUST NOT be merged to `main`.

**Rationale**: Docstrings are the primary onboarding surface for an AI-assisted codebase.
Unit test coverage gates prevent regressions as the LangGraph agent graph evolves.

### III. Security & Configuration

API keys, secrets, and credentials MUST never be hardcoded in source files, configuration
files, or committed to version control. All secrets MUST be loaded at runtime from
environment variables via `python-dotenv`. The `.env` file MUST be listed in `.gitignore`.
Any accidental secret commit MUST be treated as a security incident and the affected
credential MUST be rotated immediately.

**Rationale**: The project integrates multiple third-party APIs (Anthropic, Tavily). A
single leaked key can incur financial damage or expose user data.

### IV. Resilience & Error Handling

Every agent tool invocation MUST implement retry logic with exponential backoff for
transient failures. Each tool MUST define a fallback behavior when retries are exhausted
(e.g., return a structured error result rather than raising an uncaught exception). Error
messages surfaced to end users MUST be human-readable; raw stack traces MUST NOT be
exposed outside of debug or log channels.

**Rationale**: LLM-based agents calling external APIs (web search, vector store) will
encounter network failures. Graceful degradation keeps the assistant functional and
prevents confusing user experiences.

### V. Observability

Every agent decision node in the LangGraph graph MUST emit a structured log entry
capturing: node name, input summary, output summary, and elapsed time. Log entries MUST
use a consistent schema (JSON lines) to enable programmatic analysis. Log verbosity MUST
be configurable via the `LOG_LEVEL` environment variable.

**Rationale**: Agent behavior is non-deterministic. Structured logs are the primary
mechanism for debugging reasoning chains, auditing decisions, and improving prompts.

### VI. Async Patterns

All I/O-bound operations — including LLM API calls, web search requests, and vector store
queries — MUST use `async/await` patterns. Blocking synchronous calls inside an async
context are PROHIBITED. The LangGraph graph runner MUST be invoked via an async entry
point.

**Rationale**: The assistant performs multiple concurrent tool calls during research.
Async execution maximizes throughput and prevents blocking the event loop.

### VII. Version Control Discipline

Every Git commit MUST be atomic: one logical change per commit. Commit messages MUST
follow the Conventional Commits specification (`feat:`, `fix:`, `chore:`, `docs:`,
`refactor:`, `test:`). Pull requests MUST NOT be merged with a blanket squash that
discards meaningful commit history.

**Rationale**: Atomic conventional commits enable automated changelog generation, precise
`git bisect`, and clear audit trails across AI-assisted development sessions.

## Technology Stack

The following libraries and services constitute the approved core stack. Deviations
MUST be discussed and recorded as a constitution amendment or a justified exception
in the relevant feature plan's Complexity Tracking table.

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | Minimum version enforced by CI |
| Agent Orchestration | LangGraph | Primary graph execution framework |
| LLM Provider | Anthropic Claude API | Default model configurable via env var |
| Web Search Tool | Tavily API | Fallback: skip search node gracefully on failure |
| Vector Retrieval | FAISS | Local index; no external vector DB dependency |
| Linting / Formatting | Ruff | Replaces flake8 + black + isort |
| Secret Management | python-dotenv | Load from `.env`; `.env` MUST be git-ignored |
| Testing | pytest + pytest-asyncio | All tests MUST be runnable via `pytest` |

## Development Workflow

1. **Branch Strategy**: Feature branches cut from `main`; branch name follows
   `###-short-description` convention.
2. **Spec Before Code**: A feature specification (`spec.md`) MUST exist before
   implementation begins; use `/speckit.specify` to generate it.
3. **Plan Before Tasks**: An implementation plan (`plan.md`) MUST be produced via
   `/speckit.plan` and pass the Constitution Check gate before tasks are generated.
4. **Test-Write Sequence**: Unit tests MUST be written and confirmed failing before the
   corresponding implementation is written (Red → Green → Refactor).
5. **Linting Gate**: `ruff check .` and `ruff format --check .` MUST pass before a PR
   can be merged.
6. **Review**: All PRs targeting `main` MUST receive at least one human review.

## Governance

This constitution supersedes all other project conventions and ad-hoc agreements. When a
conflict arises between this document and any other guideline, this constitution takes
precedence.

**Amendment Procedure**:

1. Propose the amendment in a dedicated PR with a description of the change and rationale.
2. Update `CONSTITUTION_VERSION` per the versioning policy below.
3. Update `LAST_AMENDED_DATE` to the merge date.
4. Run `/speckit.constitution` to propagate changes to dependent templates.
5. PR requires at least one human approval before merge.

**Versioning Policy**:

- **MAJOR**: Removal or backward-incompatible redefinition of an existing principle.
- **MINOR**: New principle added or existing principle materially expanded.
- **PATCH**: Clarification, wording fix, or non-semantic refinement.

**Compliance Review**: The Constitution Check section of every `plan.md` MUST enumerate
which principles apply to the feature and flag any violations requiring justification in
the Complexity Tracking table.

**Version**: 1.0.0 | **Ratified**: 2026-03-19 | **Last Amended**: 2026-03-19
