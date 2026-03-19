"""Root conftest: set required environment variables before any src imports."""

from __future__ import annotations

import os

# Provide stub values so Settings() doesn't raise KeyError during test collection.
_ENV_STUBS = {
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "TAVILY_API_KEY": "test-tavily-key",
}

for _key, _val in _ENV_STUBS.items():
    os.environ.setdefault(_key, _val)
