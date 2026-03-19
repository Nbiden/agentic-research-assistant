"""Tool registration for the Agentic Research Assistant.

This is the SINGLE location where tools are registered with the ToolRegistry.
To add a new tool: import it here and call registry.register(your_tool_fn).
No other file (graph.py, nodes.py, router.py) needs to change.
"""

from src.tools.base import registry
from src.tools.knowledge_base import knowledge_base
from src.tools.web_search import web_search

registry.register(web_search)
registry.register(knowledge_base)

__all__ = ["registry", "web_search", "knowledge_base"]
