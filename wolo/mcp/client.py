"""
MCP Client wrapper using official MCP Python SDK.

This module wraps the official MCP SDK to provide a simplified interface
for Wolo's MCP integration.

Supports two transport types:
- Stdio: For local MCP servers (command + args)
- HTTP: For remote MCP servers (url + headers)
"""

import logging
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Tool as MCPToolType

logger = logging.getLogger(__name__)

# Suppress MCP server stderr output by redirecting to /dev/null
# This is a module-level file that stays open for the process lifetime
_devnull = open(os.devnull, 'w')


class MCPError(Exception):
    """Base exception for MCP errors."""
    pass


class MCPConnectionError(MCPError):
    """Failed to connect to MCP server."""
    pass


class MCPTimeoutError(MCPError):
    """MCP operation timed out."""
    pass


@dataclass
class MCPTool:
    """MCP tool definition."""
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
    
    @classmethod
    def from_mcp_tool(cls, tool: MCPToolType) -> "MCPTool":
        """Create MCPTool from official SDK tool type."""
        return cls(
            name=tool.name,
            description=tool.description or "",
            input_schema=tool.inputSchema if tool.inputSchema else {},
        )


@dataclass
class MCPResource:
    """MCP resource definition."""
    uri: str
    name: str
    description: str = ""
    mime_type: Optional[str] = None


class MCPClient:
    """
    MCP Client using official MCP Python SDK.
    
    Supports two transport types:
    - Stdio: For local MCP servers via subprocess
    - HTTP: For remote MCP servers via HTTP/SSE
    """
    
    def __init__(
        self,
        # Stdio transport params
        command: Optional[str] = None,
        args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        # HTTP transport params
        url: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        # Common params
        timeout: float = 30.0,
    ):
        """
        Initialize MCP client.
        
        For stdio transport (local servers):
            MCPClient(command="npx", args=["-y", "@z_ai/mcp-server"], env={...})
        
        For HTTP transport (remote servers):
            MCPClient(url="https://...", headers={"Authorization": "Bearer ..."})
        
        Args:
            command: Command to run the MCP server (stdio transport)
            args: Command arguments (stdio transport)
            env: Environment variables for the server process (stdio transport)
            url: URL of the remote MCP server (HTTP transport)
            headers: HTTP headers for authentication (HTTP transport)
            timeout: Default timeout for operations (seconds)
        """
        # Determine transport type
        if url:
            self._transport_type = "http"
            self.url = url
            self.headers = headers or {}
        elif command:
            self._transport_type = "stdio"
            self.command = command
            self.args = args or []
            self.env = env
        else:
            raise ValueError("Either 'url' (for HTTP) or 'command' (for stdio) must be provided")
        
        self.timeout = timeout
        
        self._session: Optional[ClientSession] = None
        self._exit_stack = AsyncExitStack()
        self._connected = False
        
        # Server info (populated after connect)
        self.server_name: str = ""
        self.server_version: str = ""
    
    async def connect(self) -> None:
        """
        Connect to the MCP server.
        
        Uses stdio or HTTP transport based on initialization parameters.
        """
        try:
            if self._transport_type == "http":
                await self._connect_http()
            else:
                await self._connect_stdio()
            
            self._connected = True
            logger.info(f"Connected to MCP server: {self.server_name} v{self.server_version}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            await self.disconnect()
            raise MCPConnectionError(f"Failed to connect: {e}")
    
    async def _connect_stdio(self) -> None:
        """Connect via stdio transport (local server)."""
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env,
        )
        
        # Create stdio transport, suppress server stderr to /dev/null
        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params, errlog=_devnull)
        )
        
        # Unpack the transport tuple (read, write streams)
        read_stream, write_stream = stdio_transport
        
        # Create and initialize session
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        
        # Initialize the MCP session
        result = await self._session.initialize()
        
        # Store server info
        if result.serverInfo:
            self.server_name = result.serverInfo.name
            self.server_version = result.serverInfo.version or ""
    
    async def _connect_http(self) -> None:
        """Connect via HTTP transport (remote server)."""
        # Create HTTP transport using official SDK's streamable HTTP client
        http_transport = await self._exit_stack.enter_async_context(
            streamablehttp_client(
                url=self.url,
                headers=self.headers,
                timeout=self.timeout,
            )
        )
        
        # Unpack the transport tuple (read_stream, write_stream, get_session_id)
        read_stream, write_stream, get_session_id = http_transport
        
        # Create and initialize session
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        
        # Initialize the MCP session
        result = await self._session.initialize()
        
        # Store server info
        if result.serverInfo:
            self.server_name = result.serverInfo.name
            self.server_version = result.serverInfo.version or ""
    
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        self._connected = False
        self._session = None
        
        try:
            await self._exit_stack.aclose()
        except RuntimeError as e:
            # Ignore "cancel scope in different task" errors from anyio
            # This happens when disconnect is called from a different task
            # than the one that created the connection (common at shutdown)
            if "cancel scope" in str(e):
                logger.debug(f"Ignoring expected shutdown error: {e}")
            else:
                logger.warning(f"Error during disconnect: {e}")
        except BaseExceptionGroup as e:
            # Handle exception groups (Python 3.11+)
            # Suppress cancel scope errors from anyio
            suppressed = False
            for exc in e.exceptions:
                if isinstance(exc, RuntimeError) and "cancel scope" in str(exc):
                    suppressed = True
                elif "stdio_client" in str(exc) or "async_generator" in str(exc):
                    suppressed = True
            if not suppressed:
                logger.warning(f"Error during disconnect: {e}")
        except Exception as e:
            # Suppress stdio_client async generator errors
            if "stdio_client" in str(e) or "async_generator" in str(e) or "cancel scope" in str(e):
                logger.debug(f"Ignoring expected shutdown error: {e}")
            else:
                logger.warning(f"Error during disconnect: {e}")
        
        self._session = None
        self._connected = False
        # Create new exit stack for potential reconnection
        self._exit_stack = AsyncExitStack()
        logger.debug("Disconnected from MCP server")
    
    async def list_tools(self) -> list[MCPTool]:
        """
        List available tools from the server.
        
        Returns:
            List of MCPTool objects
        """
        if not self._session:
            raise MCPConnectionError("Not connected to server")
        
        try:
            result = await self._session.list_tools()
            tools = [MCPTool.from_mcp_tool(t) for t in result.tools]
            logger.debug(f"Listed {len(tools)} tools")
            return tools
        except Exception as e:
            raise MCPError(f"Failed to list tools: {e}")
    
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Call a tool on the server.
        
        Args:
            name: Tool name
            arguments: Tool arguments
        
        Returns:
            Tool result as dict with 'content' and 'isError' keys
        """
        if not self._session:
            raise MCPConnectionError("Not connected to server")
        
        try:
            result = await self._session.call_tool(name, arguments)
            
            # Convert result to dict format
            content = []
            for item in result.content:
                if hasattr(item, 'text'):
                    content.append({"type": "text", "text": item.text})
                elif hasattr(item, 'data'):
                    content.append({"type": "image", "data": item.data})
                else:
                    content.append({"type": "unknown", "value": str(item)})
            
            return {
                "content": content,
                "isError": result.isError if hasattr(result, 'isError') else False,
            }
        except Exception as e:
            logger.error(f"Tool call failed: {name} - {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            }
    
    async def list_resources(self) -> list[MCPResource]:
        """
        List available resources from the server.
        
        Returns:
            List of MCPResource objects
        """
        if not self._session:
            raise MCPConnectionError("Not connected to server")
        
        try:
            result = await self._session.list_resources()
            resources = [
                MCPResource(
                    uri=r.uri,
                    name=r.name,
                    description=r.description or "",
                    mime_type=r.mimeType,
                )
                for r in result.resources
            ]
            logger.debug(f"Listed {len(resources)} resources")
            return resources
        except Exception as e:
            raise MCPError(f"Failed to list resources: {e}")
    
    async def read_resource(self, uri: str) -> str:
        """
        Read a resource from the server.
        
        Args:
            uri: Resource URI
        
        Returns:
            Resource content as string
        """
        if not self._session:
            raise MCPConnectionError("Not connected to server")
        
        try:
            result = await self._session.read_resource(uri)
            # Combine all text content
            texts = []
            for item in result.contents:
                if hasattr(item, 'text'):
                    texts.append(item.text)
            return "\n".join(texts)
        except Exception as e:
            raise MCPError(f"Failed to read resource: {e}")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to server."""
        return self._connected and self._session is not None
    
    @property
    def transport_type(self) -> str:
        """Get the transport type (stdio or http)."""
        return self._transport_type
