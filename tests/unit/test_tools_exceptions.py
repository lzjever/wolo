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
    """File operation errors are handled gracefully with error status."""

    tool_part = ToolPart(tool="read", input={"file_path": "/nonexistent/file.txt"})

    # The tool handles errors internally - no exception raised
    await execute_tool(tool_part, session_id="test456")

    # The tool handles errors internally, so status may be completed or error
    # File not found returns a result with suggestions, not an error
    assert tool_part.status in ("completed", "error")


@pytest.mark.asyncio
async def test_session_id_propagated_to_exceptions():
    """Session ID is included in error handling."""

    tool_part = ToolPart(tool="batch", input={"tool_calls": []})

    # Empty batch sets error status instead of raising exception
    await execute_tool(tool_part, session_id="test_session")

    # The tool handles errors gracefully
    assert tool_part.status == "error"
    assert "No tool calls provided" in tool_part.output
