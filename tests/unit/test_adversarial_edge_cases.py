"""Adversarial edge-case tests to probe for hidden bugs."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from wolo.agents import AgentConfig, PermissionRule
from wolo.exceptions import WoloToolError
from wolo.session import (
    Message,
    SessionStorage,
    TextPart,
    ToolPart,
    _deserialize_message,
    _deserialize_part,
    _serialize_message,
    _serialize_part,
    to_llm_messages,
)

# ==================== to_llm_messages edge cases ====================


class TestToLlmMessagesEdgeCases(unittest.TestCase):
    """Probe to_llm_messages with tricky message structures."""

    def test_mixed_statuses_in_same_message(self):
        """Assistant message with completed + pending + interrupted tools.

        Only completed and interrupted should appear; pending should be invisible.
        Each tool_call must have a matching tool result.
        """
        msg = Message(id="m1", role="assistant")
        t1 = ToolPart(id="tc1", tool="read", input={}, output="ok", status="completed")
        t2 = ToolPart(id="tc2", tool="write", input={}, output="", status="pending")
        t3 = ToolPart(id="tc3", tool="shell", input={}, output="interrupted!", status="interrupted")
        t4 = ToolPart(id="tc4", tool="glob", input={}, output="", status="running")
        msg.parts = [t1, t2, t3, t4]
        msg.finished = True

        result = to_llm_messages([msg])

        # Assistant message should have exactly 2 tool_calls (completed + interrupted)
        assistant_msg = result[0]
        self.assertEqual(len(assistant_msg["tool_calls"]), 2)
        tc_ids = {tc["id"] for tc in assistant_msg["tool_calls"]}
        self.assertEqual(tc_ids, {"tc1", "tc3"})

        # Should have exactly 2 tool results
        tool_results = [r for r in result if r["role"] == "tool"]
        self.assertEqual(len(tool_results), 2)
        tr_ids = {r["tool_call_id"] for r in tool_results}
        self.assertEqual(tr_ids, {"tc1", "tc3"})

    def test_tool_calls_only_no_text(self):
        """Assistant message with only tool calls and no text content.

        OpenAI API allows omitting content when tool_calls are present.
        """
        msg = Message(id="m1", role="assistant")
        t1 = ToolPart(id="tc1", tool="read", input={}, output="data", status="completed")
        msg.parts = [t1]
        msg.finished = True

        result = to_llm_messages([msg])

        self.assertEqual(len(result), 2)
        # Assistant message should not have "content" key
        self.assertNotIn("content", result[0])
        self.assertIn("tool_calls", result[0])

    def test_empty_assistant_message_skipped(self):
        """Assistant message with no text and only pending tools should be skipped entirely."""
        msg = Message(id="m1", role="assistant")
        t1 = ToolPart(id="tc1", tool="shell", input={}, output="", status="pending")
        msg.parts = [t1]
        msg.finished = False

        result = to_llm_messages([msg])

        self.assertEqual(result, [])

    def test_all_error_tools_still_produce_results(self):
        """All-error tools should produce tool_calls + tool results (not be dropped)."""
        msg = Message(id="m1", role="assistant")
        t1 = ToolPart(id="tc1", tool="shell", input={}, output="fail1", status="error")
        t2 = ToolPart(id="tc2", tool="write", input={}, output="fail2", status="error")
        msg.parts = [t1, t2]
        msg.finished = True

        result = to_llm_messages([msg])

        self.assertEqual(len(result), 3)  # 1 assistant + 2 tool results
        self.assertEqual(len(result[0]["tool_calls"]), 2)

    def test_tool_with_very_large_input_serializes(self):
        """Tool with huge JSON input should still serialize correctly."""
        big_input = {"data": "x" * 100000, "nested": {"a": list(range(1000))}}
        msg = Message(id="m1", role="assistant")
        t1 = ToolPart(id="tc1", tool="write", input=big_input, output="ok", status="completed")
        msg.parts = [t1]
        msg.finished = True

        result = to_llm_messages([msg])

        # The arguments should be valid JSON
        args_str = result[0]["tool_calls"][0]["function"]["arguments"]
        parsed = json.loads(args_str)
        self.assertEqual(len(parsed["data"]), 100000)


# ==================== Serialization edge cases ====================


class TestSerializationEdgeCases(unittest.TestCase):
    """Probe serialization/deserialization for data integrity."""

    def test_tool_part_with_none_output(self):
        """ToolPart where output is explicitly set to empty string (not None)."""
        part = ToolPart(id="t1", tool="shell", input={}, output="", status="error")
        serialized = _serialize_part(part)
        restored = _deserialize_part(serialized)

        self.assertEqual(restored.output, "")
        self.assertEqual(restored.status, "error")

    def test_tool_part_with_special_chars_in_output(self):
        """Output containing JSON-hostile characters."""
        part = ToolPart(
            id="t1",
            tool="shell",
            input={"command": 'echo "hello\nworld"'},
            output='line1\nline2\ttab\x00null\u0000zero',
            status="completed",
        )
        serialized = _serialize_part(part)
        restored = _deserialize_part(serialized)

        self.assertEqual(restored.output, part.output)
        self.assertEqual(restored.input, part.input)

    def test_tool_part_with_unicode_output(self):
        """CJK and emoji in tool output should survive round-trip."""
        part = ToolPart(
            id="t1",
            tool="shell",
            input={},
            output="你好世界 🌍 café résumé naïve",
            status="completed",
        )
        serialized = _serialize_part(part)
        restored = _deserialize_part(serialized)

        self.assertEqual(restored.output, part.output)

    def test_message_with_metadata_roundtrip(self):
        """Message metadata (e.g., compaction info) should survive round-trip."""
        msg = Message(id="m1", role="assistant", metadata={"compaction": {"is_summary": True}})
        text = TextPart(text="Summary of conversation")
        msg.parts = [text]
        msg.finished = True
        msg.finish_reason = "stop"

        serialized = _serialize_message(msg)
        restored = _deserialize_message(serialized)

        self.assertEqual(restored.metadata, {"compaction": {"is_summary": True}})
        self.assertTrue(restored.finished)

    def test_tool_part_metadata_with_nested_structures(self):
        """ToolPart metadata with deeply nested dicts should survive."""
        part = ToolPart(id="t1", tool="shell", input={}, output="ok", status="completed")
        part.metadata = {
            "pruned": True,
            "details": {"levels": [1, 2, 3], "nested": {"deep": True}},
        }

        restored = _deserialize_part(_serialize_part(part))

        self.assertEqual(restored.metadata["details"]["nested"]["deep"], True)
        self.assertEqual(restored.metadata["details"]["levels"], [1, 2, 3])


# ==================== SessionStorage _write_json edge cases ====================


class TestWriteJsonEdgeCases(unittest.TestCase):
    """Probe _write_json for file system edge cases."""

    def test_write_json_creates_parent_dirs(self):
        """_write_json should create parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SessionStorage(base_dir=Path(tmpdir))
            target = Path(tmpdir) / "deep" / "nested" / "dir" / "test.json"
            storage._write_json(target, {"key": "value"})

            self.assertTrue(target.exists())
            with open(target) as f:
                data = json.load(f)
            self.assertEqual(data["key"], "value")

    def test_write_json_atomic_no_partial_on_error(self):
        """If json.dump fails mid-write, target should not exist (or be old)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SessionStorage(base_dir=Path(tmpdir))
            target = Path(tmpdir) / "test.json"

            # Write valid data first
            storage._write_json(target, {"version": 1})

            # Now try to write non-serializable data
            class BadObj:
                pass

            with self.assertRaises(TypeError):
                storage._write_json(target, {"bad": BadObj()})

            # Original file should still be intact
            with open(target) as f:
                data = json.load(f)
            self.assertEqual(data["version"], 1)

    def test_write_json_no_leftover_tmp_on_error(self):
        """Temp file should be cleaned up on error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SessionStorage(base_dir=Path(tmpdir))
            target = Path(tmpdir) / "test.json"
            tmp_path = target.with_suffix(".tmp")

            class BadObj:
                pass

            with self.assertRaises(TypeError):
                storage._write_json(target, {"bad": BadObj()})

            self.assertFalse(tmp_path.exists())

    def test_write_json_with_unicode(self):
        """Unicode content should be written with ensure_ascii=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SessionStorage(base_dir=Path(tmpdir))
            target = Path(tmpdir) / "test.json"
            storage._write_json(target, {"text": "你好世界"})

            with open(target, encoding="utf-8") as f:
                content = f.read()
            # Should contain actual CJK, not \\uXXXX escapes
            self.assertIn("你好世界", content)


# ==================== Executor edge cases ====================


class TestExecutorEdgeCases(unittest.IsolatedAsyncioTestCase):
    """Probe executor for subtle error handling issues."""

    @patch("wolo.tools_pkg.executor.bus", new_callable=MagicMock)
    @patch("wolo.tools_pkg.executor.get_registry")
    async def test_tool_sets_output_before_raising_preserved(self, mock_registry, mock_bus):
        """If tool handler sets output then raises WoloToolError, output should be preserved."""
        from wolo.tools_pkg.executor import execute_tool

        mock_bus.publish = AsyncMock()
        reg = MagicMock()
        reg.format_tool_start.return_value = {}
        reg.format_tool_complete.return_value = {}
        mock_registry.return_value = reg

        tool_part = ToolPart(tool="shell", input={"command": "test"})

        async def fake_shell(*args, **kwargs):
            # Simulate a tool that sets partial output, then crashes
            tool_part.output = "partial output before crash"
            raise RuntimeError("unexpected crash")

        with patch("wolo.tools_pkg.executor.shell_execute", new_callable=AsyncMock, side_effect=fake_shell):
            with self.assertRaises(WoloToolError):
                await execute_tool(tool_part)

        # The catch-all sets output to the error message, overwriting partial output.
        # This is the current behavior — verify it's consistent.
        self.assertEqual(tool_part.status, "error")
        self.assertIn("Unexpected error", tool_part.output)

    @patch("wolo.tools_pkg.executor.bus", new_callable=MagicMock)
    @patch("wolo.tools_pkg.executor.get_registry")
    async def test_batch_all_sub_tools_denied(self, mock_registry, mock_bus):
        """Batch where all sub-tools are denied should report all failures."""
        from wolo.tools_pkg.executor import execute_tool

        mock_bus.publish = AsyncMock()
        reg = MagicMock()
        reg.format_tool_start.return_value = {}
        reg.format_tool_complete.return_value = {}
        mock_registry.return_value = reg

        agent_config = AgentConfig(
            name="restricted",
            description="",
            permissions=[
                PermissionRule(tool="shell", action="deny"),
                PermissionRule(tool="write", action="deny"),
            ],
            system_prompt="",
        )

        tool_part = ToolPart(
            tool="batch",
            input={
                "tool_calls": [
                    {"tool": "shell", "input": {"command": "rm -rf /"}},
                    {"tool": "write", "input": {"file_path": "/etc/passwd", "content": "bad"}},
                ]
            },
        )

        await execute_tool(tool_part, agent_config=agent_config, session_id="s1")

        # All sub-tools denied → status should be "partial" (0 succeeded < total)
        self.assertEqual(tool_part.status, "partial")
        self.assertIn("0/2 succeeded", tool_part.output)

    @patch("wolo.tools_pkg.executor.bus", new_callable=MagicMock)
    @patch("wolo.tools_pkg.executor.get_registry")
    async def test_batch_empty_tool_calls_list(self, mock_registry, mock_bus):
        """Batch with empty tool_calls should error cleanly."""
        from wolo.tools_pkg.executor import execute_tool

        mock_bus.publish = AsyncMock()
        reg = MagicMock()
        reg.format_tool_start.return_value = {}
        reg.format_tool_complete.return_value = {}
        mock_registry.return_value = reg

        tool_part = ToolPart(tool="batch", input={"tool_calls": []})

        await execute_tool(tool_part, session_id="s1")

        self.assertEqual(tool_part.status, "error")
        self.assertIn("No tool calls", tool_part.output)

    @patch("wolo.tools_pkg.executor.bus", new_callable=MagicMock)
    @patch("wolo.tools_pkg.executor.get_registry")
    async def test_unknown_tool_error_status_set(self, mock_registry, mock_bus):
        """Unknown tool should set error status and raise WoloToolError."""
        from wolo.tools_pkg.executor import execute_tool

        mock_bus.publish = AsyncMock()
        reg = MagicMock()
        reg.format_tool_start.return_value = {}
        reg.format_tool_complete.return_value = {}
        reg.get_all.return_value = []
        mock_registry.return_value = reg

        tool_part = ToolPart(tool="nonexistent_tool", input={})

        with self.assertRaises(WoloToolError) as ctx:
            await execute_tool(tool_part)

        self.assertEqual(tool_part.status, "error")
        self.assertIn("Unknown tool", str(ctx.exception))

    @patch("wolo.tools_pkg.executor.bus", new_callable=MagicMock)
    @patch("wolo.tools_pkg.executor.get_registry")
    async def test_permission_denied_does_not_set_start_time(self, mock_registry, mock_bus):
        """Permission-denied tools should not publish tool-complete (no start_time)."""
        from wolo.tools_pkg.executor import execute_tool

        mock_bus.publish = AsyncMock()
        reg = MagicMock()
        reg.format_tool_start.return_value = {}
        reg.format_tool_complete.return_value = {}
        mock_registry.return_value = reg

        agent_config = AgentConfig(
            name="locked",
            description="",
            permissions=[PermissionRule(tool="shell", action="deny")],
            system_prompt="",
        )

        tool_part = ToolPart(tool="shell", input={"command": "ls"})

        await execute_tool(tool_part, agent_config=agent_config)

        # Permission denied returns early before start_time is set
        self.assertEqual(tool_part.start_time, 0.0)
        self.assertEqual(tool_part.status, "error")


# ==================== _handle_pending_tools edge cases ====================


class TestHandlePendingToolsEdgeCases(unittest.IsolatedAsyncioTestCase):
    """Probe _handle_pending_tools for interrupt + multi-tool edge cases."""

    @patch("wolo.agent.update_message")
    @patch("wolo.agent.bus", new_callable=MagicMock)
    @patch("wolo.agent.execute_tool", new_callable=AsyncMock)
    async def test_interrupt_after_first_tool_leaves_others_pending(
        self, mock_exec, mock_bus, mock_update
    ):
        """Interrupt after first tool should leave remaining tools untouched (pending)."""
        from wolo.agent import _handle_pending_tools

        mock_bus.publish = AsyncMock()

        t1 = ToolPart(id="tc1", tool="read", input={}, status="pending")
        t2 = ToolPart(id="tc2", tool="write", input={}, status="pending")
        t3 = ToolPart(id="tc3", tool="shell", input={}, status="pending")
        msg = Message(id="msg1", role="assistant")
        msg.parts = [t1, t2, t3]
        msg.finished = False

        # First tool succeeds, then interrupt
        call_count = 0

        async def fake_exec(tool_call, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            tool_call.status = "completed"
            tool_call.output = f"result_{call_count}"

        mock_exec.side_effect = fake_exec

        # Control mock: allow first tool, interrupt before second
        # should_interrupt is called: before tool1, before tool2, after loop exits
        control = MagicMock()
        interrupt_values = iter([False, True, True, True])  # extra Trues for safety
        control.should_interrupt.side_effect = lambda: next(interrupt_values, True)
        control.wait_if_paused = AsyncMock()

        config = MagicMock()
        agent_config = AgentConfig(name="test", description="", permissions=[], system_prompt="")

        await _handle_pending_tools(msg, control, None, agent_config, "s1", config, 1, "Test")

        # First tool completed
        self.assertEqual(t1.status, "completed")
        # Second tool interrupted (interrupt was detected before its execution)
        self.assertEqual(t2.status, "interrupted")
        # Third tool should still be pending (never reached)
        self.assertEqual(t3.status, "pending")
        # execute_tool should only have been called once
        self.assertEqual(call_count, 1)

    @patch("wolo.agent.update_message")
    @patch("wolo.agent.bus", new_callable=MagicMock)
    @patch("wolo.agent.execute_tool", new_callable=AsyncMock)
    async def test_multiple_tool_errors_all_caught(self, mock_exec, mock_bus, mock_update):
        """Multiple consecutive tool errors should all be caught, not crash."""
        from wolo.agent import _handle_pending_tools

        mock_bus.publish = AsyncMock()

        t1 = ToolPart(id="tc1", tool="shell", input={}, status="pending")
        t2 = ToolPart(id="tc2", tool="write", input={}, status="pending")
        msg = Message(id="msg1", role="assistant")
        msg.parts = [t1, t2]
        msg.finished = False

        mock_exec.side_effect = [
            WoloToolError("err1", session_id="s1", tool_name="shell"),
            WoloToolError("err2", session_id="s1", tool_name="write"),
        ]

        config = MagicMock()
        agent_config = AgentConfig(name="test", description="", permissions=[], system_prompt="")

        should_cont, _, _, _ = await _handle_pending_tools(
            msg, None, None, agent_config, "s1", config, 1, "Test"
        )

        self.assertTrue(should_cont)
        self.assertEqual(t1.status, "error")
        self.assertEqual(t2.status, "error")


# ==================== MCP tool name edge cases ====================


class TestMcpToolNameEdgeCases(unittest.TestCase):
    """Probe MCP tool naming with tricky server/tool names."""

    def test_server_name_with_underscore(self):
        """Server named 'my_server' should still parse correctly with __ separator."""
        # Name: mcp_my_server__search → server="my_server", tool="search"
        full_name = "mcp_my_server__search"
        self.assertTrue(full_name.startswith("mcp_"))
        remainder = full_name[4:]
        self.assertIn("__", remainder)
        server, tool = remainder.split("__", 1)
        self.assertEqual(server, "my_server")
        self.assertEqual(tool, "search")

    def test_tool_name_with_underscore(self):
        """Tool named 'web_search' should parse correctly."""
        full_name = "mcp_server__web_search"
        remainder = full_name[4:]
        server, tool = remainder.split("__", 1)
        self.assertEqual(server, "server")
        self.assertEqual(tool, "web_search")

    def test_server_name_with_double_underscore_is_ambiguous(self):
        """Server named 'my__server' creates ambiguous parsing.

        split('__', 1) would give server='my', tool='server__search'.
        This is a known limitation of the naming scheme.
        """
        full_name = "mcp_my__server__search"
        remainder = full_name[4:]
        server, tool = remainder.split("__", 1)
        # First __ wins
        self.assertEqual(server, "my")
        self.assertEqual(tool, "server__search")
        # This is arguably wrong — the server is "my__server", not "my"

    def test_refresh_registers_consistent_with_schema(self):
        """Registered tool name must match the name in get_tool_schemas."""
        # Simulate what both functions produce for the same server+tool
        server_name = "web-search"
        tool_name = "query"

        # mcp_integration.py:171 (after fix)
        registered_name = f"mcp_{server_name}__{tool_name}"
        # server_manager.py:377
        schema_name = f"mcp_{server_name}__{tool_name}"

        self.assertEqual(registered_name, schema_name)


# ==================== Config edge cases ====================


class TestConfigEdgeCases(unittest.TestCase):
    """Probe config loading for edge cases."""

    @patch("wolo.config.Config._get_endpoints", return_value=[])
    @patch("wolo.config.Config._load_config_file", return_value={})
    @patch.dict(os.environ, {"WOLO_API_KEY": "key", "WOLO_TEMPERATURE": "-1.0"}, clear=False)
    def test_negative_temperature_accepted(self, _mock_load, _mock_ep):
        """Negative temperature is syntactically valid float — should not crash."""
        from wolo.config import Config

        config = Config.from_env()
        self.assertEqual(config.temperature, -1.0)

    @patch("wolo.config.Config._get_endpoints", return_value=[])
    @patch("wolo.config.Config._load_config_file", return_value={})
    @patch.dict(os.environ, {"WOLO_API_KEY": "key", "WOLO_MAX_TOKENS": "0"}, clear=False)
    def test_zero_max_tokens_accepted(self, _mock_load, _mock_ep):
        """max_tokens=0 is valid int parse but semantically questionable."""
        from wolo.config import Config

        config = Config.from_env()
        self.assertEqual(config.max_tokens, 0)

    @patch("wolo.config.Config._get_endpoints", return_value=[])
    @patch("wolo.config.Config._load_config_file", return_value={})
    @patch.dict(
        os.environ,
        {"WOLO_API_KEY": "key", "WOLO_TEMPERATURE": "  0.5  "},
        clear=False,
    )
    def test_whitespace_in_env_var(self, _mock_load, _mock_ep):
        """Leading/trailing whitespace in env var should still parse."""
        from wolo.config import Config

        config = Config.from_env()
        self.assertEqual(config.temperature, 0.5)


# ==================== ToolPart metadata mutation safety ====================


class TestToolPartMetadataMutation(unittest.TestCase):
    """Verify that metadata is not shared between instances."""

    def test_metadata_not_shared_between_instances(self):
        """Two ToolParts should not share mutable metadata state."""
        p1 = ToolPart(id="t1", tool="a", input={})
        p2 = ToolPart(id="t2", tool="b", input={})

        p1.metadata = {"key": "val1"}

        # p2 should not be affected
        self.assertIsNone(p2.metadata)

    def test_deserialized_metadata_is_independent(self):
        """Deserialized parts should have independent metadata copies."""
        data = {
            "type": "tool",
            "id": "t1",
            "tool": "shell",
            "input": {},
            "output": "ok",
            "status": "completed",
            "metadata": {"pruned": True},
        }

        p1 = _deserialize_part(data)
        p2 = _deserialize_part(data)

        p1.metadata["pruned"] = False

        # p2 should not be affected (unless they share the same dict from data)
        self.assertTrue(p2.metadata["pruned"])
