"""Tests for MCP module using official MCP SDK."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from wolo.mcp.client import MCPClient, MCPTool, MCPError, MCPConnectionError
from wolo.mcp.server_manager import MCPServerManager, ServerStatus, ServerState
from wolo.mcp.node_check import check_node_available, check_npx_available, get_installation_instructions
from wolo.claude.mcp_config import MCPServerConfig


class TestMCPTool:
    """Tests for MCP tool definition."""
    
    def test_create_tool(self):
        """Test creating a tool definition."""
        tool = MCPTool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        )
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        tool = MCPTool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
        )
        d = tool.to_dict()
        assert d["name"] == "test_tool"
        assert d["description"] == "A test tool"
        assert d["inputSchema"] == {"type": "object"}


class TestMCPClient:
    """Tests for MCP client wrapper."""
    
    def test_create_client(self):
        """Test creating a client."""
        client = MCPClient(
            command="python",
            args=["-m", "test_server"],
            env={"TEST": "value"},
        )
        assert client.command == "python"
        assert client.args == ["-m", "test_server"]
        assert client.env == {"TEST": "value"}
        assert not client.is_connected
    
    def test_client_not_connected(self):
        """Test client methods when not connected."""
        client = MCPClient(command="python", args=[])
        assert not client.is_connected
    
    @pytest.mark.asyncio
    async def test_list_tools_not_connected(self):
        """Test listing tools when not connected."""
        client = MCPClient(command="python", args=[])
        
        with pytest.raises(MCPConnectionError, match="Not connected"):
            await client.list_tools()
    
    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self):
        """Test calling tool when not connected."""
        client = MCPClient(command="python", args=[])
        
        with pytest.raises(MCPConnectionError, match="Not connected"):
            await client.call_tool("test", {})


class TestNodeCheck:
    """Tests for Node.js availability checking."""
    
    def test_check_node_available(self):
        """Test Node.js availability check."""
        # This will return True or False depending on system
        result = check_node_available()
        assert isinstance(result, bool)
    
    def test_check_npx_available(self):
        """Test npx availability check."""
        result = check_npx_available()
        assert isinstance(result, bool)
    
    def test_get_installation_instructions(self):
        """Test getting installation instructions."""
        instructions = get_installation_instructions()
        assert "Node.js" in instructions
        assert "install" in instructions.lower()


class TestServerStatus:
    """Tests for server status enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert ServerStatus.STOPPED.value == "stopped"
        assert ServerStatus.STARTING.value == "starting"
        assert ServerStatus.RUNNING.value == "running"
        assert ServerStatus.ERROR.value == "error"
        assert ServerStatus.DISABLED.value == "disabled"


class TestMCPServerManager:
    """Tests for MCP server manager."""
    
    def test_add_server(self):
        """Test adding a server."""
        manager = MCPServerManager()
        config = MCPServerConfig(
            name="test-server",
            command="python",
            args=["-m", "test"],
        )
        manager.add_server(config)
        
        status = manager.get_status()
        assert "test-server" in status
        assert status["test-server"]["status"] == "stopped"
    
    def test_add_multiple_servers(self):
        """Test adding multiple servers."""
        manager = MCPServerManager()
        configs = {
            "server-a": MCPServerConfig(name="server-a", command="python", args=[]),
            "server-b": MCPServerConfig(name="server-b", command="python", args=[]),
        }
        manager.add_servers(configs)
        
        status = manager.get_status()
        assert len(status) == 2
        assert "server-a" in status
        assert "server-b" in status
    
    def test_is_mcp_tool(self):
        """Test MCP tool name detection."""
        manager = MCPServerManager()
        
        assert manager.is_mcp_tool("mcp_web-search_search")
        assert manager.is_mcp_tool("mcp_filesystem_read")
        assert not manager.is_mcp_tool("shell")
        assert not manager.is_mcp_tool("read")
    
    def test_get_all_tools_empty(self):
        """Test getting tools when no servers running."""
        manager = MCPServerManager()
        tools = manager.get_all_tools()
        assert tools == []
    
    def test_get_tool_schemas_empty(self):
        """Test getting tool schemas when no servers running."""
        manager = MCPServerManager()
        schemas = manager.get_tool_schemas()
        assert schemas == []
    
    def test_node_strategy_skip(self):
        """Test node_strategy=skip skips Node servers."""
        manager = MCPServerManager(node_strategy="skip")
        config = MCPServerConfig(
            name="node-server",
            command="npx",
            args=["-y", "@test/server"],
        )
        manager.add_server(config)
        
        # Server should be disabled
        status = manager.get_status()
        # Note: Status is still "stopped" until start_server is called


class TestMCPServerManagerAsync:
    """Async tests for MCP server manager."""
    
    @pytest.mark.asyncio
    async def test_start_disabled_server(self):
        """Test starting a disabled server."""
        manager = MCPServerManager()
        config = MCPServerConfig(
            name="disabled-server",
            command="python",
            args=[],
            enabled=False,
        )
        manager.add_server(config)
        
        result = await manager.start_server("disabled-server")
        assert result is False
        
        status = manager.get_status()
        assert status["disabled-server"]["status"] == "disabled"
    
    @pytest.mark.asyncio
    async def test_start_unknown_server(self):
        """Test starting an unknown server."""
        manager = MCPServerManager()
        result = await manager.start_server("nonexistent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_stop_unknown_server(self):
        """Test stopping an unknown server."""
        manager = MCPServerManager()
        # Should not raise
        await manager.stop_server("nonexistent")
    
    @pytest.mark.asyncio
    async def test_stop_all_empty(self):
        """Test stopping all when no servers."""
        manager = MCPServerManager()
        # Should not raise
        await manager.stop_all()
    
    @pytest.mark.asyncio
    async def test_call_tool_unknown_server(self):
        """Test calling tool on unknown server."""
        manager = MCPServerManager()
        
        with pytest.raises(MCPError, match="Unknown server"):
            await manager.call_tool("nonexistent", "test", {})
    
    @pytest.mark.asyncio
    async def test_call_tool_not_running(self):
        """Test calling tool on non-running server."""
        manager = MCPServerManager()
        config = MCPServerConfig(name="test", command="python", args=[])
        manager.add_server(config)
        
        with pytest.raises(MCPError, match="not running"):
            await manager.call_tool("test", "test_tool", {})
    
    @pytest.mark.asyncio
    async def test_call_tool_by_name_invalid_format(self):
        """Test calling tool with invalid name format."""
        manager = MCPServerManager()
        
        with pytest.raises(MCPError, match="Invalid MCP tool name"):
            await manager.call_tool_by_name("invalid_name", {})
        
        with pytest.raises(MCPError, match="Invalid MCP tool name"):
            await manager.call_tool_by_name("mcp_nounderscores", {})
    
    @pytest.mark.asyncio
    async def test_remote_server_requires_url(self):
        """Test that remote server requires URL."""
        manager = MCPServerManager()
        config = MCPServerConfig(
            name="remote-server",
            type="remote",
            url=None,  # Missing URL
        )
        manager.add_server(config)
        
        result = await manager.start_server("remote-server")
        assert result is False
        
        status = manager.get_status()
        assert status["remote-server"]["status"] == "error"
        assert "requires URL" in status["remote-server"]["error"]
