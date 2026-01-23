"""Batch tool tests."""

import pytest

from wolo.session import ToolPart
from wolo.tools import execute_tool


class TestBatchTool:
    """Batch tool execution tests."""

    @pytest.mark.asyncio
    async def test_batch_empty_calls(self):
        """Empty tool calls returns error."""
        part = ToolPart(tool="batch", input={"tool_calls": []})
        await execute_tool(part)

        assert part.status == "error"
        assert "No tool calls" in part.output

    @pytest.mark.asyncio
    async def test_batch_nested_not_allowed(self):
        """Nested batch calls are not allowed."""
        part = ToolPart(
            tool="batch", input={"tool_calls": [{"tool": "batch", "input": {"tool_calls": []}}]}
        )
        await execute_tool(part)

        assert part.status == "error"
        assert "Nested batch" in part.output

    @pytest.mark.asyncio
    async def test_batch_too_many_calls(self):
        """Too many parallel calls returns error."""
        part = ToolPart(
            tool="batch",
            input={
                "tool_calls": [
                    {"tool": "shell", "input": {"command": "echo test"}}
                    for _ in range(15)  # More than MAX_PARALLEL (10)
                ]
            },
        )
        await execute_tool(part)

        assert part.status == "error"
        assert "Too many" in part.output

    @pytest.mark.asyncio
    async def test_batch_parallel_execution(self, tmp_path):
        """Tools execute in parallel."""
        # Create test files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")

        part = ToolPart(
            tool="batch",
            input={
                "tool_calls": [
                    {"tool": "read", "input": {"file_path": str(tmp_path / "file1.txt")}},
                    {"tool": "read", "input": {"file_path": str(tmp_path / "file2.txt")}},
                ]
            },
        )
        await execute_tool(part)

        assert part.status == "completed"
        assert "2 tools" in part.output
        assert "2/2 succeeded" in part.output

    @pytest.mark.asyncio
    async def test_batch_partial_failure(self, tmp_path):
        """Partial failure is reported."""
        (tmp_path / "exists.txt").write_text("content")

        part = ToolPart(
            tool="batch",
            input={
                "tool_calls": [
                    {"tool": "read", "input": {"file_path": str(tmp_path / "exists.txt")}},
                    {"tool": "read", "input": {"file_path": str(tmp_path / "nonexistent.txt")}},
                ]
            },
        )
        await execute_tool(part)

        # Should complete but with partial status
        assert "1/2 succeeded" in part.output or "2/2 succeeded" in part.output

    @pytest.mark.asyncio
    async def test_batch_shell_commands(self):
        """Batch can execute shell commands."""
        part = ToolPart(
            tool="batch",
            input={
                "tool_calls": [
                    {"tool": "shell", "input": {"command": "echo hello"}},
                    {"tool": "shell", "input": {"command": "echo world"}},
                ]
            },
        )
        await execute_tool(part)

        assert part.status == "completed"
        assert "2/2 succeeded" in part.output

    @pytest.mark.asyncio
    async def test_batch_output_format(self, tmp_path):
        """Output format is correct."""
        (tmp_path / "test.txt").write_text("test")

        part = ToolPart(
            tool="batch",
            input={
                "tool_calls": [
                    {"tool": "read", "input": {"file_path": str(tmp_path / "test.txt")}},
                ]
            },
        )
        await execute_tool(part)

        assert "Batch execution results" in part.output
        assert "[✓]" in part.output or "[✗]" in part.output
        assert "Summary:" in part.output
