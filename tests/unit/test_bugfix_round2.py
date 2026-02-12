"""Regression tests for bugfix round 2 (N01-N05) and round 3 (P0-P2)."""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from wolo.agents import AgentConfig, PermissionRule
from wolo.exceptions import WoloPathSafetyError, WoloToolError
from wolo.session import (
    Message,
    TextPart,
    ToolPart,
    _deserialize_part,
    _serialize_part,
    to_llm_messages,
)

# ==================== N01a: executor except blocks set error status ====================


class TestN01aExecutorErrorStatus(unittest.IsolatedAsyncioTestCase):
    """N01a: Exception handlers must set tool_part.status='error' before re-raising."""

    @patch("wolo.tools_pkg.executor.bus", new_callable=MagicMock)
    @patch("wolo.tools_pkg.executor.get_registry")
    async def test_wolo_tool_error_sets_error_status(self, mock_registry, mock_bus):
        """WoloToolError should set status='error' on the tool_part."""
        from wolo.tools_pkg.executor import execute_tool

        mock_bus.publish = AsyncMock()
        reg = MagicMock()
        reg.format_tool_start.return_value = {}
        reg.format_tool_complete.return_value = {}
        mock_registry.return_value = reg

        tool_part = ToolPart(tool="shell", input={"command": "echo hi"})

        with patch(
            "wolo.tools_pkg.executor.shell_execute",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(WoloToolError):
                await execute_tool(tool_part)

        self.assertEqual(tool_part.status, "error")
        self.assertIn("boom", tool_part.output)

    @patch("wolo.tools_pkg.executor.bus", new_callable=MagicMock)
    @patch("wolo.tools_pkg.executor.get_registry")
    async def test_file_not_found_sets_error_status(self, mock_registry, mock_bus):
        """FileNotFoundError should set status='error' on the tool_part."""
        from wolo.tools_pkg.executor import execute_tool

        mock_bus.publish = AsyncMock()
        reg = MagicMock()
        reg.format_tool_start.return_value = {}
        reg.format_tool_complete.return_value = {}
        mock_registry.return_value = reg

        tool_part = ToolPart(tool="read", input={"file_path": "/no/such/file"})

        with patch(
            "wolo.tools_pkg.executor.read_execute",
            new_callable=AsyncMock,
            side_effect=FileNotFoundError("/no/such/file"),
        ):
            with self.assertRaises(WoloToolError):
                await execute_tool(tool_part)

        self.assertEqual(tool_part.status, "error")
        self.assertIn("File not found", tool_part.output)

    @patch("wolo.tools_pkg.executor.bus", new_callable=MagicMock)
    @patch("wolo.tools_pkg.executor.get_registry")
    async def test_tool_complete_event_shows_error_status(self, mock_registry, mock_bus):
        """The tool-complete event published in finally should see status='error'."""
        from wolo.tools_pkg.executor import execute_tool

        mock_bus.publish = AsyncMock()
        reg = MagicMock()
        reg.format_tool_start.return_value = {}
        reg.format_tool_complete.return_value = {}
        mock_registry.return_value = reg

        tool_part = ToolPart(tool="shell", input={"command": "fail"})

        with patch(
            "wolo.tools_pkg.executor.shell_execute",
            new_callable=AsyncMock,
            side_effect=OSError("disk full"),
        ):
            with self.assertRaises(WoloToolError):
                await execute_tool(tool_part)

        # Verify format_tool_complete was called with "error" status
        reg.format_tool_complete.assert_called_once()
        call_args = reg.format_tool_complete.call_args
        self.assertEqual(call_args[0][2], "error")  # third positional arg is status


# ==================== N01b: _handle_pending_tools catches tool errors ====================


class TestN01bHandlePendingToolsCatch(unittest.IsolatedAsyncioTestCase):
    """N01b: _handle_pending_tools must catch tool errors without crashing."""

    @patch("wolo.agent.update_message")
    @patch("wolo.agent.bus", new_callable=MagicMock)
    @patch("wolo.agent.execute_tool", new_callable=AsyncMock)
    async def test_tool_error_does_not_crash_loop(self, mock_exec, mock_bus, mock_update):
        """WoloToolError from execute_tool should be caught, not crash."""
        from wolo.agent import _handle_pending_tools

        mock_bus.publish = AsyncMock()

        tool_part = ToolPart(tool="shell", input={"command": "fail"}, status="pending")
        msg = Message(id="msg1", role="assistant")
        msg.parts = [tool_part]
        msg.finished = False

        mock_exec.side_effect = WoloToolError("tool broke", session_id="s1", tool_name="shell")

        config = MagicMock()
        config.path_safety = MagicMock()
        config.path_safety.wild_mode = False
        agent_config = AgentConfig(name="test", description="", permissions=[], system_prompt="")

        should_cont, user_input, step, dur = await _handle_pending_tools(
            msg, None, None, agent_config, "s1", config, 1, "Test"
        )

        # Should continue, not crash
        self.assertTrue(should_cont)
        self.assertEqual(tool_part.status, "error")

    @patch("wolo.agent.update_message")
    @patch("wolo.agent.bus", new_callable=MagicMock)
    @patch("wolo.agent.execute_tool", new_callable=AsyncMock)
    async def test_path_safety_error_propagates(self, mock_exec, mock_bus, mock_update):
        """WoloPathSafetyError should propagate (user cancelled)."""
        from wolo.agent import _handle_pending_tools

        mock_bus.publish = AsyncMock()

        tool_part = ToolPart(tool="write", input={}, status="pending")
        msg = Message(id="msg1", role="assistant")
        msg.parts = [tool_part]
        msg.finished = False

        mock_exec.side_effect = WoloPathSafetyError("cancelled", session_id="s1", path="/foo")

        config = MagicMock()
        config.path_safety = MagicMock()
        config.path_safety.wild_mode = False
        agent_config = AgentConfig(name="test", description="", permissions=[], system_prompt="")

        with self.assertRaises(WoloPathSafetyError):
            await _handle_pending_tools(msg, None, None, agent_config, "s1", config, 1, "Test")


# ==================== N02: to_llm_messages handles interrupted tools ====================


class TestN02InterruptedTools(unittest.TestCase):
    """N02: interrupted tool calls must appear in LLM messages."""

    def test_interrupted_tool_included_in_llm_messages(self):
        """An interrupted tool should produce both tool_call and tool result."""
        msg = Message(id="m1", role="assistant")
        text_part = TextPart(text="Let me run that.")
        tool_part = ToolPart(
            id="tc1",
            tool="shell",
            input={"command": "long_running"},
            output="[Tool execution interrupted by user]",
            status="interrupted",
        )
        msg.parts = [text_part, tool_part]
        msg.finished = True

        result = to_llm_messages([msg])

        # Should have assistant message with tool_calls AND a tool result
        self.assertEqual(len(result), 2)

        # First: assistant message with tool_calls
        self.assertEqual(result[0]["role"], "assistant")
        self.assertIn("tool_calls", result[0])
        self.assertEqual(result[0]["tool_calls"][0]["id"], "tc1")

        # Second: tool result
        self.assertEqual(result[1]["role"], "tool")
        self.assertEqual(result[1]["tool_call_id"], "tc1")
        self.assertIn("interrupted", result[1]["content"])

    def test_interrupted_tool_without_output_uses_default(self):
        """An interrupted tool with empty output should use default message."""
        msg = Message(id="m1", role="assistant")
        tool_part = ToolPart(
            id="tc1",
            tool="shell",
            input={"command": "x"},
            output="",
            status="interrupted",
        )
        msg.parts = [tool_part]
        msg.finished = True

        result = to_llm_messages([msg])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["content"], "[Tool execution interrupted by user]")


# ==================== N03: batch tool passes agent_config ====================


class TestN03BatchAgentConfig(unittest.IsolatedAsyncioTestCase):
    """N03: batch tool must pass agent_config to sub-tool execute_tool calls."""

    @patch("wolo.tools_pkg.executor.bus", new_callable=MagicMock)
    @patch("wolo.tools_pkg.executor.get_registry")
    async def test_batch_sub_tools_get_agent_config(self, mock_registry, mock_bus):
        """Sub-tools in batch should receive agent_config for permission checks."""
        from wolo.tools_pkg.executor import execute_tool

        mock_bus.publish = AsyncMock()
        reg = MagicMock()
        reg.format_tool_start.return_value = {}
        reg.format_tool_complete.return_value = {}
        reg.get_all.return_value = []
        mock_registry.return_value = reg

        agent_config = AgentConfig(
            name="restricted",
            description="",
            permissions=[PermissionRule(tool="shell", action="deny")],
            system_prompt="",
        )

        tool_part = ToolPart(
            tool="batch",
            input={
                "tool_calls": [
                    {"tool": "shell", "input": {"command": "whoami"}},
                ]
            },
        )

        await execute_tool(tool_part, agent_config=agent_config, session_id="s1")

        # The sub-tool should have been denied by permission check
        # The batch output should mention the denial
        self.assertIn("denied", tool_part.output.lower())

    @patch("wolo.tools_pkg.executor.bus", new_callable=MagicMock)
    @patch("wolo.tools_pkg.executor.get_registry")
    async def test_batch_without_agent_config_allows_tools(self, mock_registry, mock_bus):
        """Without agent_config, batch sub-tools should execute normally."""
        from wolo.tools_pkg.executor import execute_tool

        mock_bus.publish = AsyncMock()
        reg = MagicMock()
        reg.format_tool_start.return_value = {}
        reg.format_tool_complete.return_value = {}
        mock_registry.return_value = reg

        tool_part = ToolPart(
            tool="batch",
            input={
                "tool_calls": [
                    {"tool": "glob", "input": {"pattern": "*.py", "path": "."}},
                ]
            },
        )

        with patch(
            "wolo.tools_pkg.executor.glob_execute",
            new_callable=AsyncMock,
            return_value={"output": "file.py", "metadata": {"matches": 1}},
        ):
            await execute_tool(tool_part, session_id="s1")

        self.assertEqual(tool_part.status, "completed")


# ==================== N05: ToolPart metadata serialization ====================


class TestN05MetadataSerialization(unittest.TestCase):
    """N05: ToolPart.metadata must survive serialize/deserialize round-trip."""

    def test_metadata_serialized_when_present(self):
        """ToolPart with metadata should include it in serialized form."""
        part = ToolPart(id="t1", tool="shell", input={}, output="ok", status="completed")
        part.metadata = {"pruned": True, "pruned_at": 1234567890.0, "original_output_tokens": 500}

        serialized = _serialize_part(part)

        self.assertIn("metadata", serialized)
        self.assertTrue(serialized["metadata"]["pruned"])
        self.assertEqual(serialized["metadata"]["original_output_tokens"], 500)

    def test_metadata_not_serialized_when_absent(self):
        """ToolPart without metadata should not include metadata key."""
        part = ToolPart(id="t1", tool="shell", input={}, output="ok", status="completed")

        serialized = _serialize_part(part)

        self.assertNotIn("metadata", serialized)

    def test_metadata_deserialized(self):
        """Deserialized ToolPart should have metadata restored."""
        data = {
            "type": "tool",
            "id": "t1",
            "tool": "shell",
            "input": {},
            "output": "[pruned]",
            "status": "completed",
            "start_time": 0.0,
            "end_time": 1.0,
            "metadata": {"pruned": True, "original_output_tokens": 300},
        }

        part = _deserialize_part(data)

        self.assertIsInstance(part, ToolPart)
        self.assertIsNotNone(part.metadata)
        self.assertTrue(part.metadata["pruned"])
        self.assertEqual(part.metadata["original_output_tokens"], 300)

    def test_metadata_absent_in_data_gives_none(self):
        """Deserialized ToolPart without metadata key should have metadata=None."""
        data = {
            "type": "tool",
            "id": "t1",
            "tool": "shell",
            "input": {},
            "output": "ok",
            "status": "completed",
        }

        part = _deserialize_part(data)

        self.assertIsInstance(part, ToolPart)
        self.assertIsNone(part.metadata)

    def test_roundtrip_with_metadata(self):
        """Serialize then deserialize should preserve metadata."""
        original = ToolPart(id="t1", tool="read", input={}, output="[pruned]", status="completed")
        original.metadata = {"pruned": True, "pruned_at": 9999.0}
        original.start_time = 1.0
        original.end_time = 2.0

        restored = _deserialize_part(_serialize_part(original))

        self.assertEqual(restored.metadata, original.metadata)
        self.assertEqual(restored.tool, original.tool)
        self.assertEqual(restored.output, original.output)

    def test_roundtrip_without_metadata(self):
        """Serialize then deserialize without metadata should give None."""
        original = ToolPart(id="t1", tool="read", input={}, output="ok", status="completed")

        restored = _deserialize_part(_serialize_part(original))

        self.assertIsNone(restored.metadata)


# ==================== P0: MCP tool name uses double underscore ====================


class TestP0McpToolNameFormat(unittest.TestCase):
    """P0: MCP tool names must use double underscore to match server_manager format."""

    @patch("wolo.mcp_integration._mcp_manager")
    @patch("wolo.mcp_integration.get_registry")
    def test_refresh_mcp_tools_uses_double_underscore(self, mock_registry, mock_manager):
        """refresh_mcp_tools should register tools with double underscore separator."""
        # Reset module state
        import wolo.mcp_integration as mcp_mod
        from wolo.mcp_integration import refresh_mcp_tools

        old_registered = mcp_mod._registered_mcp_tools
        mcp_mod._registered_mcp_tools = set()

        try:
            mock_tool = MagicMock()
            mock_tool.name = "search"
            mock_tool.description = "Search the web"
            mock_tool.input_schema = {"properties": {}, "required": []}
            mock_manager.get_all_tools.return_value = [("web-search", mock_tool)]

            reg = MagicMock()
            mock_registry.return_value = reg

            refresh_mcp_tools()

            # Verify the registered tool name uses double underscore
            reg.register.assert_called_once()
            registered_spec = reg.register.call_args[0][0]
            self.assertEqual(registered_spec.name, "mcp_web-search__search")
            self.assertIn("mcp_web-search__search", mcp_mod._registered_mcp_tools)
        finally:
            mcp_mod._registered_mcp_tools = old_registered


# ==================== P1: get_token_usage handles LookupError ====================


class TestP1TokenUsageSafety(unittest.TestCase):
    """P1: get_token_usage must not crash in a fresh context."""

    def test_get_token_usage_returns_zeros_on_fresh_context(self):
        """get_token_usage should return zeroed dict when ContextVar is unset."""
        import contextvars

        from wolo.llm_adapter import get_token_usage

        # Run in a completely fresh context where _token_usage_ctx is not set
        result = contextvars.Context().run(get_token_usage)

        self.assertEqual(result["prompt_tokens"], 0)
        self.assertEqual(result["completion_tokens"], 0)
        self.assertEqual(result["total_tokens"], 0)

    def test_get_token_usage_returns_values_when_set(self):
        """get_token_usage should return actual values when ContextVar is set."""
        from wolo.llm_adapter import _token_usage_ctx, get_token_usage

        _token_usage_ctx.set({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        result = get_token_usage()

        self.assertEqual(result["prompt_tokens"], 100)
        self.assertEqual(result["completion_tokens"], 50)
        self.assertEqual(result["total_tokens"], 150)


# ==================== P2: config env var fallback ====================


class TestP2ConfigEnvVarFallback(unittest.TestCase):
    """P2: Malformed env vars should fall back to defaults, not crash."""

    @patch("wolo.config.Config._get_endpoints", return_value=[])
    @patch("wolo.config.Config._load_config_file", return_value={})
    @patch.dict(
        os.environ,
        {"WOLO_API_KEY": "test-key", "WOLO_TEMPERATURE": "not_a_number"},
        clear=False,
    )
    def test_malformed_temperature_uses_default(self, _mock_load, _mock_ep):
        """Invalid WOLO_TEMPERATURE should fall back to 0.7."""
        from wolo.config import Config

        config = Config.from_env()
        self.assertEqual(config.temperature, 0.7)

    @patch("wolo.config.Config._get_endpoints", return_value=[])
    @patch("wolo.config.Config._load_config_file", return_value={})
    @patch.dict(
        os.environ,
        {"WOLO_API_KEY": "test-key", "WOLO_MAX_TOKENS": "abc"},
        clear=False,
    )
    def test_malformed_max_tokens_uses_default(self, _mock_load, _mock_ep):
        """Invalid WOLO_MAX_TOKENS should fall back to 16384."""
        from wolo.config import Config

        config = Config.from_env()
        self.assertEqual(config.max_tokens, 16384)

    @patch("wolo.config.Config._get_endpoints", return_value=[])
    @patch("wolo.config.Config._load_config_file", return_value={})
    @patch.dict(
        os.environ,
        {"WOLO_API_KEY": "test-key", "WOLO_CONTEXT_WINDOW": ""},
        clear=False,
    )
    def test_empty_context_window_uses_default(self, _mock_load, _mock_ep):
        """Empty WOLO_CONTEXT_WINDOW should fall back to 128000."""
        from wolo.config import Config

        config = Config.from_env()
        self.assertEqual(config.context_window, 128000)
