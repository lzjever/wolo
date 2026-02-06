from pathlib import Path

import pytest

from wolo.session import ToolPart
from wolo.tools_pkg.executor import execute_tool
from wolo.tools_pkg.path_guard_executor import initialize_path_guard_middleware


@pytest.mark.asyncio
async def test_multiedit_denied_for_unallowed_path():
    initialize_path_guard_middleware(
        config_paths=[],
        cli_paths=[],
        workdir=None,
        confirmed_dirs=[],
    )

    tool_part = ToolPart(
        tool="multiedit",
        input={
            "edits": [
                {
                    "file_path": "/workspace/blocked.py",
                    "old_text": "a",
                    "new_text": "b",
                }
            ]
        },
    )

    await execute_tool(tool_part, session_id="test-session")

    assert tool_part.status == "error"
    assert "Permission denied by user" in tool_part.output


@pytest.mark.asyncio
async def test_multiedit_allowed_path_under_tmp(tmp_path: Path):
    file_path = tmp_path / "allowed.py"
    file_path.write_text("alpha=1\n", encoding="utf-8")

    initialize_path_guard_middleware(
        config_paths=[],
        cli_paths=[],
        workdir=None,
        confirmed_dirs=[],
    )

    tool_part = ToolPart(
        tool="multiedit",
        input={
            "edits": [
                {
                    "file_path": str(file_path),
                    "old_text": "alpha=1",
                    "new_text": "alpha=2",
                }
            ]
        },
    )

    await execute_tool(tool_part, session_id="test-session")

    assert tool_part.status == "completed"
    assert "1/1 files edited" in tool_part.output
    assert file_path.read_text(encoding="utf-8") == "alpha=2\n"
