"""
MCP (Model Context Protocol) implementation for Wolo.

This module provides:
- MCP Client using official MCP Python SDK
- Server Manager for managing multiple servers
- Node.js detection

Uses the official MCP SDK: https://modelcontextprotocol.io/docs/develop/build-client
"""

from .client import MCPClient, MCPConnectionError, MCPError, MCPResource, MCPTimeoutError, MCPTool
from .node_check import check_node_available, check_npx_available, ensure_node_available
from .server_manager import MCPServerManager, ServerStatus

__all__ = [
    # Client
    "MCPClient",
    "MCPError",
    "MCPConnectionError",
    "MCPTimeoutError",
    "MCPTool",
    "MCPResource",
    # Server Manager
    "MCPServerManager",
    "ServerStatus",
    # Node check
    "check_node_available",
    "check_npx_available",
    "ensure_node_available",
]
