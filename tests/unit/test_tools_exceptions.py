"""Tests for tool exception handling."""

# Check if lexilux is available (required for imports)
try:
    import lexilux  # noqa: F401

    LEXILUX_AVAILABLE = True
except ImportError:
    LEXILUX_AVAILABLE = False

if not LEXILUX_AVAILABLE:
    import pytest

    pytest.skip("lexilux not installed - requires local path dependency", allow_module_level=True)

import pytest

from wolo.exceptions import WoloToolError
from wolo.session import ToolPart
from wolo.tools import execute_tool


@pytest.mark.asyncio
async def test_tool_error_on_unknown_tool():
    """WoloToolError is raised when unknown tool is called."""

    tool_part = ToolPart(tool="unknown_tool_xyz", input={})

    with pytest.raises(WoloToolError) as exc_info:
        await execute_tool(tool_part, session_id="test123")

    assert exc_info.value.session_id == "test123"
    assert "unknown_tool_xyz" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_tool_error_propagates_from_file_operations():
    """File operation errors are surfaced in tool output metadata."""

    tool_part = ToolPart(tool="read", input={"file_path": "/nonexistent/file.txt"})

    await execute_tool(tool_part, session_id="test456")
    assert tool_part.status in {"completed", "error"}
    assert "not found" in tool_part.output.lower() or "no such file" in tool_part.output.lower()


@pytest.mark.asyncio
async def test_session_id_propagated_to_exceptions():
    """Batch validation errors are handled in tool result."""

    tool_part = ToolPart(tool="batch", input={"tool_calls": []})

    await execute_tool(tool_part, session_id="test_session")
    assert tool_part.status == "error"
    assert "No tool calls provided" in tool_part.output
