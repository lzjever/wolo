"""
MCP (Model Context Protocol) implementation for Wolo.

This module provides:
- MCP Client using official MCP Python SDK
- Server Manager for managing multiple servers
- Node.js detection
- Tool caching for fast startup

Uses the official MCP SDK: https://modelcontextprotocol.io/docs/develop/build-client
"""

from .cache import (
    CACHE_VERSION,
    MCPCache,
    clear_cache,
    is_cache_valid,
    load_cache,
    save_cache,
)
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
    # Cache
    "MCPCache",
    "load_cache",
    "save_cache",
    "clear_cache",
    "is_cache_valid",
    "CACHE_VERSION",
]
