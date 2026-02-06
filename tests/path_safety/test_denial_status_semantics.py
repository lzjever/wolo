import pytest

from wolo.session import ToolPart
from wolo.tools_pkg.executor import execute_tool
from wolo.tools_pkg.path_guard_executor import initialize_path_guard_middleware


@pytest.mark.asyncio
async def test_write_path_denial_sets_error_status():
    initialize_path_guard_middleware(
        config_paths=[],
        cli_paths=[],
        workdir=None,
        confirmed_dirs=[],
    )

    tool_part = ToolPart(
        tool="write",
        input={"file_path": "/workspace/blocked.txt", "content": "x"},
    )
    await execute_tool(tool_part, session_id="sid")

    assert tool_part.status == "error"
    assert "Permission denied by user" in tool_part.output


@pytest.mark.asyncio
async def test_edit_path_denial_sets_error_status():
    initialize_path_guard_middleware(
        config_paths=[],
        cli_paths=[],
        workdir=None,
        confirmed_dirs=[],
    )

    tool_part = ToolPart(
        tool="edit",
        input={"file_path": "/workspace/blocked.txt", "old_text": "a", "new_text": "b"},
    )
    await execute_tool(tool_part, session_id="sid")

    assert tool_part.status == "error"
    assert "Permission denied by user" in tool_part.output


@pytest.mark.asyncio
async def test_write_allowed_path_keeps_completed_status(tmp_path):
    file_path = tmp_path / "ok.txt"

    initialize_path_guard_middleware(
        config_paths=[],
        cli_paths=[],
        workdir=None,
        confirmed_dirs=[],
    )

    tool_part = ToolPart(
        tool="write",
        input={"file_path": str(file_path), "content": "ok"},
    )
    await execute_tool(tool_part, session_id="sid")

    assert tool_part.status == "completed"
