"""
MCP tool cache for faster startup.

This module provides caching for MCP tool schemas so that tools
are available immediately on startup without waiting for MCP
servers to fully initialize.

Cache file: ~/.wolo/mcp_cache.json
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Cache version for compatibility checks
CACHE_VERSION = 1

# Default cache TTL in seconds (24 hours)
DEFAULT_CACHE_TTL = 24 * 60 * 60


@dataclass
class CachedServerTools:
    """Cached tools for a single MCP server."""

    tools: list[dict[str, Any]] = field(default_factory=list)
    status: str = "unknown"
    cached_at: float = 0.0

    def is_expired(self, ttl: float = DEFAULT_CACHE_TTL) -> bool:
        """Check if cache entry is expired."""
        return time.time() - self.cached_at > ttl


@dataclass
class MCPCache:
    """MCP tools cache."""

    version: int = CACHE_VERSION
    updated_at: float = 0.0
    servers: dict[str, CachedServerTools] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "servers": {
                name: {
                    "tools": server.tools,
                    "status": server.status,
                    "cached_at": server.cached_at,
                }
                for name, server in self.servers.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPCache":
        """Create from dictionary."""
        cache = cls()
        cache.version = data.get("version", CACHE_VERSION)
        cache.updated_at = data.get("updated_at", 0.0)

        servers_data = data.get("servers", {})
        for name, server_data in servers_data.items():
            cache.servers[name] = CachedServerTools(
                tools=server_data.get("tools", []),
                status=server_data.get("status", "unknown"),
                cached_at=server_data.get("cached_at", 0.0),
            )
        return cache


def get_cache_path() -> Path:
    """Get the path to the MCP cache file."""
    # Use the same base directory as sessions
    return Path.home() / ".wolo" / "mcp_cache.json"


def load_cache() -> MCPCache | None:
    """
    Load MCP cache from disk.

    Returns:
        MCPCache if valid cache exists, None otherwise
    """
    cache_path = get_cache_path()

    if not cache_path.exists():
        logger.debug("MCP cache file not found")
        return None

    try:
        with open(cache_path) as f:
            data = json.load(f)

        cache = MCPCache.from_dict(data)

        # Check version compatibility
        if cache.version != CACHE_VERSION:
            logger.info(
                f"MCP cache version mismatch ({cache.version} != {CACHE_VERSION}), ignoring"
            )
            return None

        logger.debug(f"Loaded MCP cache: {len(cache.servers)} servers")
        return cache

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"Failed to load MCP cache: {e}")
        return None


def save_cache(cache: MCPCache) -> None:
    """
    Save MCP cache to disk.

    Args:
        cache: Cache to save
    """
    cache_path = get_cache_path()

    # Ensure directory exists
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    # Update timestamp
    cache.updated_at = time.time()

    try:
        # Write to temp file first, then rename (atomic)
        temp_path = cache_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(cache.to_dict(), f, indent=2)
        temp_path.rename(cache_path)
        logger.debug(f"Saved MCP cache: {len(cache.servers)} servers")
    except Exception as e:
        logger.warning(f"Failed to save MCP cache: {e}")
        # Clean up temp file on error
        temp_path = cache_path.with_suffix(".tmp")
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


def update_server_cache(
    cache: MCPCache | None,
    server_name: str,
    tools: list[dict[str, Any]],
    status: str = "running",
) -> MCPCache:
    """
    Update cache for a single server.

    Args:
        cache: Existing cache (or None to create new)
        server_name: Server name
        tools: List of tool schemas
        status: Server status

    Returns:
        Updated cache
    """
    if cache is None:
        cache = MCPCache()

    cache.servers[server_name] = CachedServerTools(
        tools=tools,
        status=status,
        cached_at=time.time(),
    )

    return cache


def get_cached_tool_schemas(cache: MCPCache | None) -> list[dict[str, Any]]:
    """
    Get all cached tool schemas in LLM format.

    Args:
        cache: Cache to extract schemas from

    Returns:
        List of tool schemas
    """
    if not cache:
        return []

    schemas = []
    for server_name, server_cache in cache.servers.items():
        if server_cache.status == "running":
            for tool in server_cache.tools:
                # Convert to LLM schema format if needed
                if "function" in tool:
                    schemas.append(tool)
                else:
                    # Legacy format: convert
                    schemas.append(
                        {
                            "type": "function",
                            "function": {
                                "name": f"mcp_{server_name}__{tool.get('name', 'unknown')}",
                                "description": f"[MCP:{server_name}] {tool.get('description', '')}",
                                "parameters": tool.get("input_schema", tool.get("inputSchema", {})),
                            },
                        }
                    )
    return schemas


def get_cached_tools_by_server(cache: MCPCache | None) -> dict[str, list[dict[str, Any]]]:
    """
    Get cached tools grouped by server.

    Args:
        cache: Cache to extract tools from

    Returns:
        Dict mapping server name to list of tool info
    """
    if not cache:
        return {}

    result = {}
    for server_name, server_cache in cache.servers.items():
        if server_cache.status == "running":
            result[server_name] = server_cache.tools

    return result


def clear_cache() -> None:
    """Clear the MCP cache file."""
    cache_path = get_cache_path()
    if cache_path.exists():
        try:
            cache_path.unlink()
            logger.info("Cleared MCP cache")
        except Exception as e:
            logger.warning(f"Failed to clear MCP cache: {e}")


def is_cache_valid(cache: MCPCache | None, ttl: float = DEFAULT_CACHE_TTL) -> bool:
    """
    Check if cache is valid and not expired.

    Args:
        cache: Cache to check
        ttl: Time-to-live in seconds

    Returns:
        True if cache is valid and fresh
    """
    if not cache:
        return False

    if cache.version != CACHE_VERSION:
        return False

    # Check if any server has valid (non-expired) data
    for server in cache.servers.values():
        if not server.is_expired(ttl) and server.tools:
            return True

    return False


def filter_cache_by_servers(
    cache: MCPCache | None,
    server_names: set[str],
) -> MCPCache | None:
    """
    Filter cache to only include specified servers.

    This removes cached data for servers that are no longer in the configuration.

    Args:
        cache: Cache to filter
        server_names: Set of server names to keep

    Returns:
        Filtered cache, or None if input was None
    """
    if not cache:
        return None

    # Remove servers not in the current configuration
    servers_to_remove = [name for name in cache.servers if name not in server_names]
    for name in servers_to_remove:
        del cache.servers[name]
        logger.debug(f"Removed stale cache entry for server: {name}")

    return cache


def remove_server_from_cache(cache: MCPCache | None, server_name: str) -> MCPCache | None:
    """
    Remove a specific server from cache.

    Args:
        cache: Cache to modify
        server_name: Server name to remove

    Returns:
        Modified cache
    """
    if not cache:
        return None

    if server_name in cache.servers:
        del cache.servers[server_name]
        logger.debug(f"Removed server from cache: {server_name}")

    return cache


def mark_server_error(cache: MCPCache | None, server_name: str, error: str = "") -> MCPCache | None:
    """
    Mark a server as having an error in the cache.

    Args:
        cache: Cache to modify
        server_name: Server name
        error: Error message

    Returns:
        Modified cache
    """
    if not cache:
        cache = MCPCache()

    if server_name in cache.servers:
        cache.servers[server_name].status = "error"
        cache.servers[server_name].cached_at = time.time()
    else:
        # Add error entry
        cache.servers[server_name] = CachedServerTools(
            tools=[],
            status="error",
            cached_at=time.time(),
        )

    return cache


def rebuild_cache_from_servers(
    cache: MCPCache | None,
    server_states: dict[str, dict[str, Any]],
) -> MCPCache:
    """
    Rebuild cache from actual server states.

    This creates a fresh cache based on the actual connection status,
    removing any stale entries.

    Args:
        cache: Existing cache (can be None)
        server_states: Dict mapping server name to state dict with:
                       - "tools": list of tool dicts
                       - "status": "running" or other status

    Returns:
        New cache with only currently connected servers
    """
    new_cache = MCPCache()

    for server_name, state in server_states.items():
        if state.get("status") == "running" and state.get("tools"):
            new_cache.servers[server_name] = CachedServerTools(
                tools=state["tools"],
                status="running",
                cached_at=time.time(),
            )

    return new_cache
