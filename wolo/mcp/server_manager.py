"""
MCP Server Manager.

Manages multiple MCP server connections using the official MCP Python SDK.

Features:
- Server lifecycle (start, stop, restart)
- Tool aggregation from all servers
- Node.js dependency handling
- Stdio transport support via official SDK
- Background initialization with callbacks
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..claude.mcp_config import MCPServerConfig
from .client import MCPClient, MCPError, MCPTool
from .node_check import NodeNotAvailableError, check_npx_available

try:
    from builtins import BaseExceptionGroup
except ImportError:
    from exceptiongroup import BaseExceptionGroup

logger = logging.getLogger(__name__)

# Type alias for server connection callback
ServerConnectedCallback = Callable[[str, list[MCPTool]], Any]
# Type alias for initialization complete callback
InitCompleteCallback = Callable[[], Any]


class ServerStatus(Enum):
    """MCP server status."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class ServerState:
    """State of an MCP server."""

    config: MCPServerConfig
    status: ServerStatus = ServerStatus.STOPPED
    client: MCPClient | None = None
    tools: list[MCPTool] = field(default_factory=list)
    error: str | None = None


class MCPServerManager:
    """
    Manages multiple MCP server connections.

    Features:
    - Automatic connection management
    - Tool aggregation with server prefixes
    - Node.js fallback handling
    - Graceful error handling
    - Background initialization (non-blocking)
    - Callbacks for server connection events
    """

    def __init__(
        self,
        node_strategy: str = "auto",
    ):
        """
        Initialize server manager.

        Args:
            node_strategy: How to handle Node.js dependencies
                - "auto": Use Node if available, skip servers that need it otherwise
                - "require": Fail if Node is needed but not available
                - "skip": Skip all servers that need Node
                - "python_fallback": Use Python implementations when available
        """
        self.node_strategy = node_strategy
        self._servers: dict[str, ServerState] = {}
        self._node_available: bool | None = None

        # Background initialization state
        self._init_task: asyncio.Task | None = None
        self._init_started: bool = False
        self._init_complete: bool = False

        # Callbacks
        self._on_server_connected: ServerConnectedCallback | None = None
        self._on_init_complete: InitCompleteCallback | None = None

    def _check_node(self) -> bool:
        """Check if Node.js is available (cached)."""
        if self._node_available is None:
            self._node_available = check_npx_available()
        return self._node_available

    def add_server(self, config: MCPServerConfig) -> None:
        """
        Add a server configuration.

        Args:
            config: Server configuration
        """
        self._servers[config.name] = ServerState(config=config)
        logger.debug(f"Added MCP server: {config.name}")

    def add_servers(self, configs: dict[str, MCPServerConfig]) -> None:
        """
        Add multiple server configurations.

        Args:
            configs: Dictionary of server configurations
        """
        for name, config in configs.items():
            self.add_server(config)

    async def start_server(self, name: str) -> bool:
        """
        Start a specific server.

        Args:
            name: Server name

        Returns:
            True if started successfully
        """
        state = self._servers.get(name)
        if not state:
            logger.warning(f"Unknown server: {name}")
            return False

        if state.status == ServerStatus.RUNNING:
            return True

        if not state.config.enabled:
            state.status = ServerStatus.DISABLED
            return False

        # Check Node.js requirement
        if state.config.requires_node():
            if not self._check_node():
                if self.node_strategy == "require":
                    raise NodeNotAvailableError(name)
                elif self.node_strategy == "skip":
                    logger.info(f"Skipping {name}: requires Node.js (strategy=skip)")
                    state.status = ServerStatus.DISABLED
                    return False
                elif self.node_strategy == "python_fallback":
                    if state.config.python_fallback:
                        logger.info(f"Using Python fallback for {name}")
                        return await self._start_python_fallback(state)
                    else:
                        logger.info(f"Skipping {name}: requires Node.js, no fallback")
                        state.status = ServerStatus.DISABLED
                        return False
                else:  # auto
                    logger.info(f"Skipping {name}: requires Node.js")
                    state.status = ServerStatus.DISABLED
                    return False

        state.status = ServerStatus.STARTING

        try:
            if state.config.is_remote():
                return await self._start_remote_server(state)
            else:
                return await self._start_local_server(state)

        except Exception as e:
            state.status = ServerStatus.ERROR
            state.error = str(e)
            logger.error(f"Failed to start {name}: {e}")
            return False

    async def _start_local_server(self, state: ServerState) -> bool:
        """Start a local (stdio) MCP server using official SDK."""
        try:
            # Create client using official MCP SDK with stdio transport
            client = MCPClient(
                command=state.config.command,
                args=state.config.args,
                env=state.config.env,
            )

            # Connect to server
            await client.connect()

            # Get tools
            tools = await client.list_tools()

            state.client = client
            state.tools = tools
            state.status = ServerStatus.RUNNING
            state.error = None

            logger.info(f"Started local MCP server {state.config.name}: {len(tools)} tools")

            # Call callback if set
            if self._on_server_connected:
                try:
                    result = self._on_server_connected(state.config.name, tools)
                    # Handle async callbacks
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.warning(f"Callback error for {state.config.name}: {e}")

            return True

        except Exception as e:
            state.status = ServerStatus.ERROR
            state.error = str(e)
            logger.error(f"Failed to start local server {state.config.name}: {e}")
            return False

    async def _start_remote_server(self, state: ServerState) -> bool:
        """Start a remote (HTTP) MCP server using official SDK."""
        if not state.config.url:
            state.status = ServerStatus.ERROR
            state.error = "Remote server requires URL"
            return False

        try:
            # Create client using official MCP SDK with HTTP transport
            client = MCPClient(
                url=state.config.url,
                headers=state.config.headers,
                timeout=state.config.timeout / 1000,  # Convert ms to seconds
            )

            # Connect to server
            await client.connect()

            # Get tools
            tools = await client.list_tools()

            state.client = client
            state.tools = tools
            state.status = ServerStatus.RUNNING
            state.error = None

            logger.info(f"Started remote MCP server {state.config.name}: {len(tools)} tools")

            # Call callback if set
            if self._on_server_connected:
                try:
                    result = self._on_server_connected(state.config.name, tools)
                    # Handle async callbacks
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.warning(f"Callback error for {state.config.name}: {e}")

            return True

        except Exception as e:
            state.status = ServerStatus.ERROR
            state.error = str(e)
            logger.error(f"Failed to start remote server {state.config.name}: {e}")
            return False

    async def _start_python_fallback(self, state: ServerState) -> bool:
        """Start a Python fallback server."""
        # TODO: Implement Python fallback servers
        # For now, just mark as disabled
        state.status = ServerStatus.DISABLED
        state.error = "Python fallback not yet implemented"
        return False

    async def stop_server(self, name: str) -> None:
        """
        Stop a specific server.

        Args:
            name: Server name
        """
        state = self._servers.get(name)
        if not state or not state.client:
            return

        try:
            await state.client.disconnect()
        except (RuntimeError, BaseExceptionGroup) as e:
            # Suppress "cancel scope in different task" errors from anyio
            # This is expected during shutdown when cleanup happens in different tasks
            error_str = str(e)
            if (
                "cancel scope" in error_str
                or "stdio_client" in error_str
                or "async_generator" in error_str
            ):
                logger.debug(f"Ignoring expected shutdown error for {name}: {e}")
            else:
                logger.warning(f"Error stopping {name}: {e}")
        except Exception as e:
            error_str = str(e)
            if (
                "stdio_client" in error_str
                or "async_generator" in error_str
                or "cancel scope" in error_str
            ):
                logger.debug(f"Ignoring expected shutdown error for {name}: {e}")
            else:
                logger.warning(f"Error stopping {name}: {e}")

        state.client = None
        state.tools = []
        state.status = ServerStatus.STOPPED
        logger.debug(f"Stopped MCP server: {name}")

    async def start_all(self) -> dict[str, bool]:
        """
        Start all configured servers (blocking).

        Returns:
            Dictionary mapping server name to success status
        """
        results = {}

        # Start servers concurrently
        tasks = []
        names = []
        for name in self._servers:
            tasks.append(self.start_server(name))
            names.append(name)

        if tasks:
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            for name, outcome in zip(names, outcomes):
                if isinstance(outcome, Exception):
                    results[name] = False
                    logger.error(f"Error starting {name}: {outcome}")
                else:
                    results[name] = outcome

        self._init_complete = True
        return results

    def start_background_init(self) -> None:
        """
        Start background initialization (non-blocking).

        Servers will be initialized in the background. Tools become available
        as each server connects successfully.
        """
        if self._init_started:
            return

        self._init_started = True
        self._init_task = asyncio.create_task(self._background_init())
        logger.info("MCP background initialization started")

    def start_background_init_with_callback(
        self,
        on_connected: ServerConnectedCallback | None = None,
        on_complete: InitCompleteCallback | None = None,
    ) -> None:
        """
        Start background initialization with callbacks.

        The on_connected callback is called each time a server connects successfully,
        allowing immediate updates to tool registries and caches.

        The on_complete callback is called when all servers have been attempted,
        allowing final cache synchronization.

        Args:
            on_connected: Async or sync function called with (server_name, tools)
                          when a server connects.
            on_complete: Async or sync function called when initialization completes.
        """
        self._on_server_connected = on_connected
        self._on_init_complete = on_complete
        self.start_background_init()

    async def _background_init(self) -> None:
        """Background initialization task."""
        try:
            await self.start_all()
            logger.info("MCP background initialization complete")

            # Call completion callback if set
            if self._on_init_complete:
                try:
                    result = self._on_init_complete()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.warning(f"Init complete callback error: {e}")

        except Exception as e:
            logger.error(f"MCP background initialization failed: {e}")

    @property
    def is_initializing(self) -> bool:
        """Check if background initialization is in progress."""
        return self._init_started and not self._init_complete

    @property
    def is_initialized(self) -> bool:
        """Check if initialization is complete."""
        return self._init_complete

    async def stop_all(self) -> None:
        """Stop all servers."""
        tasks = [self.stop_server(name) for name in self._servers]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_all_tools(self) -> list[tuple[str, MCPTool]]:
        """
        Get all tools from all running servers.

        Returns:
            List of (server_name, tool) tuples
        """
        tools = []
        for name, state in self._servers.items():
            if state.status == ServerStatus.RUNNING:
                for tool in state.tools:
                    tools.append((name, tool))
        return tools

    def get_tool_schemas(self, prefix: bool = True) -> list[dict]:
        """
        Get all tools in LLM schema format.

        Args:
            prefix: If True, prefix tool names with "mcp_<server>_"

        Returns:
            List of tool schemas
        """
        schemas = []
        for server_name, tool in self.get_all_tools():
            name = f"mcp_{server_name}__{tool.name}" if prefix else tool.name
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": f"[MCP:{server_name}] {tool.description}",
                        "parameters": tool.input_schema,
                    },
                }
            )
        return schemas

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict,
    ) -> dict:
        """
        Call a tool on a specific server.

        Args:
            server_name: Server name
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        state = self._servers.get(server_name)
        if not state:
            raise MCPError(f"Unknown server: {server_name}")

        if state.status != ServerStatus.RUNNING or not state.client:
            raise MCPError(f"Server not running: {server_name}")

        return await state.client.call_tool(tool_name, arguments)

    async def call_tool_by_name(self, full_name: str, arguments: dict) -> dict:
        """
        Call a tool by its full prefixed name.

        Args:
            full_name: Full tool name (e.g., "mcp_web-search_search")
            arguments: Tool arguments

        Returns:
            Tool result
        """
        # Parse the name: mcp_<server>__<tool>
        if not full_name.startswith("mcp_"):
            raise MCPError(f"Invalid MCP tool name: {full_name}")

        remainder = full_name[4:]
        if "__" not in remainder:
            raise MCPError(f"Invalid MCP tool name format: {full_name}")

        server_name, tool_name = remainder.split("__", 1)
        return await self.call_tool(server_name, tool_name, arguments)

    def get_status(self) -> dict[str, dict[str, Any]]:
        """
        Get status of all servers.

        Returns:
            Dictionary mapping server name to status info
        """
        status = {}
        for name, state in self._servers.items():
            status[name] = {
                "status": state.status.value,
                "tools": len(state.tools),
                "error": state.error,
            }
        return status

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if a tool name is an MCP tool."""
        return tool_name.startswith("mcp_")
