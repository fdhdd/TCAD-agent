"""LangGraph API server entry point.

Exports a compiled ``CompiledStateGraph`` as ``graph`` so that the
LangGraph API server (``langgraph dev`` / ``langgraph up``) can import
it and serve it via its standard HTTP + SSE endpoints.

Usage:
    langgraph dev --host 0.0.0.0 --port 2024
"""

from agent import build_agent

# The server provides its own persistence backend, so we do NOT pass
# a checkpointer — the default ``MemorySaver`` from ``build_agent()``
# would conflict with the server's checkpointing layer.
graph = build_agent(checkpointer=None)
