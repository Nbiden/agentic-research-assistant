# API Contract: Core Research Agent

**Feature**: 001-core-research-agent
**Date**: 2026-03-19
**Interface Type**: REST HTTP (FastAPI)
**Base Path**: `/`

---

## Endpoint: POST /research

Submit a research question to the agent and receive a structured response.

### Request

**Content-Type**: `application/json`

```json
{
  "question": "string (required, 1–2000 chars)",
  "max_sources": "integer (optional, default 5, range 1–20)",
  "include_trace": "boolean (optional, default true)"
}
```

**Example**:
```json
{
  "question": "What are the latest developments in retrieval-augmented generation?",
  "max_sources": 5,
  "include_trace": true
}
```

**Validation errors** return HTTP 422 with a Pydantic v2 error body.

---

### Response: 200 OK

**Content-Type**: `application/json`

```json
{
  "answer": "string — natural-language answer with inline [1], [2] citation markers",
  "sources": [
    {
      "content": "string — retrieved text snippet",
      "identifier": "string — URL or document ID",
      "relevance_score": "float [0.0, 1.0]",
      "source_type": "web | knowledge_base | llm",
      "title": "string | null"
    }
  ],
  "confidence_score": "float [0.0, 1.0]",
  "decision_trace": {
    "tool_calls": [
      {
        "tool_name": "string",
        "rationale": "string",
        "input_summary": "string",
        "output_summary": "string",
        "success": "boolean",
        "elapsed_ms": "integer >= 0",
        "error_message": "string | null"
      }
    ],
    "total_elapsed_ms": "integer >= 0",
    "nodes_visited": ["string"]
  },
  "generated_at": "string (ISO 8601 UTC datetime)",
  "degraded": "boolean"
}
```

**Notes**:
- `decision_trace` is `null` when `include_trace=false` was requested.
- `degraded=true` when one or more tools failed; the answer is still populated
  using available sources and LLM knowledge.
- Sources are sorted by `relevance_score` descending.
- When `confidence_score < 0.5`, the `answer` text will contain an explicit
  uncertainty statement.

---

### Response: 422 Unprocessable Entity

Returned when the request body fails Pydantic validation.

```json
{
  "detail": [
    {
      "loc": ["body", "question"],
      "msg": "String should have at least 1 character",
      "type": "string_too_short"
    }
  ]
}
```

---

### Response: 500 Internal Server Error

Returned only when the agent encounters an unrecoverable error (all tools failed AND
LLM invocation failed). The response body is always user-friendly — no stack traces.

```json
{
  "error": "string — user-friendly explanation of what went wrong",
  "degraded": true
}
```

---

## Endpoint: GET /health

Lightweight liveness check for deployment monitoring.

### Response: 200 OK

```json
{
  "status": "ok",
  "version": "string"
}
```

---

## CLI Contract

The CLI entry point (`python -m src.cli.main` or the installed `research-agent` script)
accepts the research question as a positional argument or from stdin.

### Usage

```text
research-agent "Your research question here" [--max-sources N] [--no-trace] [--json]
```

| Flag | Default | Description |
|---|---|---|
| `question` (positional) | required | The research question |
| `--max-sources N` | 5 | Maximum sources to include |
| `--no-trace` | (trace on by default) | Suppress decision trace in output |
| `--json` | (human output by default) | Output raw JSON instead of formatted text |

### Standard Output (human mode)

```text
Answer
──────
[Answer text with [1], [2] citation markers]

Sources
───────
[1] Title (web) — https://example.com — relevance: 0.92
[2] Document ID: doc_042 (knowledge_base) — relevance: 0.87

Confidence: 0.82  |  Tools used: web_search, knowledge_lookup  |  Time: 4.2s
```

### Standard Output (--json mode)

Identical JSON schema as the REST API response body.

### Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Input validation error |
| 2 | Agent error (all tools failed, LLM fallback used) |
| 3 | Fatal error (LLM itself unavailable) |

### Stdin Support

If no positional argument is given and stdin is not a TTY, the question is read from
stdin:

```bash
echo "What is RAG?" | research-agent
```
