from __future__ import annotations

"""Agent package for the JewelryOps AutoGen-based support agent.

This package exposes a service-style interface for the agent while keeping
implementation details (tools, MCP wiring, streaming, etc.) organized in
separate modules.
"""

from .agent import (
    JewelryOpsAgentService,
    get_mcp_tools,
    get_mcp_tools_async,
    get_session,
    run_agent_stream,
)

__all__ = [
    "JewelryOpsAgentService",
    "get_mcp_tools",
    "get_mcp_tools_async",
    "get_session",
    "run_agent_stream",
]

