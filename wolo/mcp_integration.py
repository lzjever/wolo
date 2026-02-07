"""
MCP and Claude integration for Wolo.

This module provides the high-level integration between:
- Claude configuration (skills, MCP servers)
- Wolo's MCP server manager
- Tool registry
"""

import logging

from .claude import ClaudeSkill, load_claude_mcp_servers
from .claude.mcp_config import MCPServerConfig, merge_mcp_configs
from .claude.skill_loader import load_all_skills
from .config import Config
from .mcp import MCPServerManager, check_npx_available
from .tool_registry import ToolCategory, ToolSpec, get_registry

try:
    from builtins import BaseExceptionGroup
except ImportError:
    from exceptiongroup import BaseExceptionGroup

logger = logging.getLogger(__name__)


# Global state
_mcp_manager: MCPServerManager | None = None
_skills: list[ClaudeSkill] = []  # Renamed from _claude_skills


async def initialize_mcp(config: Config) -> MCPServerManager:
    """
    Initialize MCP integration.

    This loads configurations from:
    1. Claude Desktop (if claude.enabled and claude.load_mcp)
    2. Wolo config (mcp.servers)

    And starts all configured MCP servers.

    Args:
        config: Wolo configuration

    Returns:
        MCPServerManager instance
    """
    global _mcp_manager  # _skills is already global (line 29)

    # Determine node strategy
    node_strategy = config.mcp.node_strategy
    if config.claude.enabled:
        node_strategy = config.claude.node_strategy or node_strategy

    # Create server manager
    _mcp_manager = MCPServerManager(node_strategy=node_strategy)

    # Load Claude MCP configuration
    claude_servers: dict[str, MCPServerConfig] = {}
    if config.claude.enabled and config.claude.load_mcp:
        claude_servers = load_claude_mcp_servers()
        logger.info(f"Loaded {len(claude_servers)} MCP servers from Claude config")

    # Load Wolo MCP configuration
    wolo_servers: dict[str, MCPServerConfig] = {}
    for name, server_data in config.mcp.servers.items():
        if isinstance(server_data, dict):
            server_type = server_data.get("type", "local")

            if server_type == "remote":
                # Remote HTTP/SSE server
                wolo_servers[name] = MCPServerConfig(
                    name=name,
                    type="remote",
                    url=server_data.get("url"),
                    headers=server_data.get("headers", {}),
                    auth_token=server_data.get("auth_token"),
                    enabled=server_data.get("enabled", True),
                    timeout=server_data.get("timeout", 60000),
                )
            else:
                # Local stdio server
                # Support both "command" as string and as list
                command = server_data.get("command", "")
                args = server_data.get("args", [])

                # If command is a list, split it
                if isinstance(command, list):
                    if command:
                        args = command[1:] + args
                        command = command[0]
                    else:
                        command = ""

                wolo_servers[name] = MCPServerConfig(
                    name=name,
                    type="local",
                    command=command,
                    args=args,
                    env=server_data.get("env", server_data.get("environment", {})),
                    enabled=server_data.get("enabled", True),
                    timeout=server_data.get("timeout", 60000),
                )

    # Merge configurations (Wolo takes precedence)
    all_servers = merge_mcp_configs(claude_servers, wolo_servers)

    # Add servers to manager
    _mcp_manager.add_servers(all_servers)

    # Load skills from Wolo and optionally Claude directories (sync, fast)
    global _skills
    claude_skills_dir = config.claude.config_dir / "skills" if config.claude.config_dir else None
    _skills = load_all_skills(
        wolo_skills_dir=None,  # Use default ~/.wolo/skills
        claude_skills_dir=claude_skills_dir,
        claude_enabled=config.claude.enabled and config.claude.load_skills,
    )
    logger.info(f"Loaded {len(_skills)} skills total")

    # Start MCP servers in background (non-blocking)
    _mcp_manager.start_background_init()

    return _mcp_manager


async def initialize_mcp_blocking(config: Config) -> MCPServerManager:
    """
    Initialize MCP integration (blocking version).

    Same as initialize_mcp but waits for all servers to start.
    Use this for testing or when you need all MCP tools immediately.

    Args:
        config: Wolo configuration

    Returns:
        MCPServerManager instance
    """
    manager = await initialize_mcp(config)

    # Wait for background init to complete
    if manager._init_task:
        await manager._init_task

    # Register MCP tools after all servers are ready
    _register_mcp_tools()

    return manager


_registered_mcp_tools: set[str] = set()


def _register_mcp_tools() -> None:
    """
    Register MCP tools with the tool registry.

    This is idempotent - calling it multiple times will only register
    new tools that haven't been registered yet.
    """
    global _registered_mcp_tools

    if not _mcp_manager:
        return

    registry = get_registry()

    # Register tools from MCP servers
    for server_name, tool in _mcp_manager.get_all_tools():
        tool_name = f"mcp_{server_name}__{tool.name}"

        # Skip if already registered
        if tool_name in _registered_mcp_tools:
            continue

        # Create ToolSpec for MCP tool
        spec = ToolSpec(
            name=tool_name,
            description=f"[MCP:{server_name}] {tool.description}",
            parameters=tool.input_schema.get("properties", {}),
            required_params=tool.input_schema.get("required", []),
            category=ToolCategory.WEB,
            icon="🔌",
            show_output=False,
        )
        registry.register(spec)
        _registered_mcp_tools.add(tool_name)
        logger.debug(f"Registered MCP tool: {tool_name}")


async def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """
    Call an MCP tool.

    Args:
        tool_name: Tool name (prefixed with mcp_<server>__)
        arguments: Tool arguments

    Returns:
        Tool result
    """
    if not _mcp_manager:
        raise ValueError("MCP not initialized")

    if not tool_name.startswith("mcp_"):
        raise ValueError(f"Invalid MCP tool name: {tool_name}")

    return await _mcp_manager.call_tool_by_name(tool_name, arguments)


def get_mcp_tool_schemas() -> list[dict]:
    """
    Get all MCP tool schemas for LLM.

    Returns:
        List of tool schemas
    """
    if not _mcp_manager:
        return []

    return _mcp_manager.get_tool_schemas()


def get_claude_skills() -> list[ClaudeSkill]:
    """Get loaded skills (from both Wolo and Claude directories)."""
    return _skills


def find_matching_skill(query: str) -> ClaudeSkill | None:
    """
    Find a skill matching a query.

    Args:
        query: User query or task description

    Returns:
        Matching skill or None
    """
    from .claude.skill_loader import find_matching_skills

    matches = find_matching_skills(_skills, query)
    return matches[0] if matches else None


async def shutdown_mcp() -> None:
    """Shutdown MCP integration."""
    global _mcp_manager

    # Stop MCP servers
    if _mcp_manager:
        try:
            await _mcp_manager.stop_all()
        except (RuntimeError, BaseExceptionGroup) as e:
            # Suppress "cancel scope in different task" errors from anyio
            # This is expected during shutdown when cleanup happens in different tasks
            error_str = str(e)
            if (
                "cancel scope" in error_str
                or "stdio_client" in error_str
                or "async_generator" in error_str
            ):
                logger.debug(f"Ignoring expected MCP shutdown error: {e}")
            else:
                logger.warning(f"Error during MCP shutdown: {e}")
        except Exception as e:
            error_str = str(e)
            if (
                "stdio_client" in error_str
                or "async_generator" in error_str
                or "cancel scope" in error_str
            ):
                logger.debug(f"Ignoring expected MCP shutdown error: {e}")
            else:
                logger.warning(f"Error during MCP shutdown: {e}")
        finally:
            _mcp_manager = None

    logger.info("MCP integration shutdown complete")


def is_mcp_tool(tool_name: str) -> bool:
    """Check if a tool is an MCP tool."""
    return tool_name.startswith("mcp_")


def get_mcp_status() -> dict:
    """
    Get MCP integration status.

    Returns:
        Dictionary with:
        - enabled: Whether MCP manager exists
        - initializing: Whether background init is in progress
        - initialized: Whether init is complete
        - servers: Per-server status dict
        - skills_count: Number of loaded skills
        - node_available: Whether Node.js is available
    """
    if not _mcp_manager:
        return {
            "enabled": False,
            "initializing": False,
            "initialized": False,
            "servers": {},
            "skills_count": len(_skills),
            "node_available": check_npx_available(),
        }

    return {
        "enabled": True,
        "initializing": _mcp_manager.is_initializing,
        "initialized": _mcp_manager.is_initialized,
        "servers": _mcp_manager.get_status(),
        "skills_count": len(_skills),
        "node_available": check_npx_available(),
    }


def refresh_mcp_tools() -> None:
    """
    Refresh MCP tools in the registry.

    Call this periodically during background init to make newly
    connected server tools available.
    """
    _register_mcp_tools()
