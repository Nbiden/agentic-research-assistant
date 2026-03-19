"""Application configuration and logging setup for the Agentic Research Assistant.

Loads all settings from environment variables via python-dotenv and configures
structlog for JSON-lines structured logging with async-safe contextvars support.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """All application settings loaded from environment variables."""

    anthropic_api_key: str = field(default_factory=lambda: os.environ["ANTHROPIC_API_KEY"])
    tavily_api_key: str = field(default_factory=lambda: os.environ["TAVILY_API_KEY"])
    claude_model: str = field(
        default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    faiss_index_path: Path | None = field(
        default_factory=lambda: Path(p) if (p := os.getenv("FAISS_INDEX_PATH")) else None
    )
    faiss_documents_path: Path | None = field(
        default_factory=lambda: Path(p) if (p := os.getenv("FAISS_DOCUMENTS_PATH")) else None
    )
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))
    retry_base_delay: float = field(
        default_factory=lambda: float(os.getenv("RETRY_BASE_DELAY", "2.0"))
    )


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for JSON-lines output with async-safe contextvars.

    Uses structlog.contextvars for async-safe per-request context binding.
    All log output is JSON lines to stdout for container log aggregation.
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(message)s",
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


# Module-level singletons — initialised once on import
settings = Settings()
configure_logging(settings.log_level)
