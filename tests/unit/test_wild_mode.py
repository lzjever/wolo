from types import SimpleNamespace
from unittest.mock import patch

import pytest

from wolo.exceptions import WoloToolError
from wolo.session import ToolPart
from wolo.tools_pkg.executor import execute_tool
from wolo.tools_pkg.path_guard_executor import (
    execute_with_path_guard,
    initialize_path_guard_middleware,
)
from wolo.tools_pkg.shell import shell_execute


@pytest.mark.asyncio
async def test_path_guard_wild_mode_bypasses_checks():
    initialize_path_guard_middleware(
        config_paths=[],
        cli_paths=[],
        workdir=None,
        confirmed_dirs=[],
        wild_mode=True,
    )

    async def fake_tool(file_path: str, **kwargs):
        return {"title": file_path, "output": "ok", "metadata": {}}

    result = await execute_with_path_guard(fake_tool, file_path="/workspace/blocked.txt")
    assert result["output"] == "ok"


@pytest.mark.asyncio
async def test_shell_execute_wild_mode_skips_risk_guard():
    with patch(
        "wolo.tools_pkg.shell.should_allow_shell_command",
        side_effect=AssertionError("risk guard should be bypassed in wild mode"),
    ):
        result = await shell_execute("echo wild-ok", wild_mode=True, session_id="wild-sid")
    assert result["metadata"]["exit_code"] == 0


@pytest.mark.asyncio
async def test_execute_tool_wild_mode_bypasses_agent_permission_gate():
    config = SimpleNamespace(path_safety=SimpleNamespace(wild_mode=True))
    agent_config = SimpleNamespace(name="locked-agent", permissions=[])

    with patch("wolo.agents.check_permission", return_value="deny"):
        tool_part = ToolPart(tool="shell", input={"command": "echo ok"})
        await execute_tool(tool_part, agent_config=agent_config, config=config, session_id="wild")

    assert tool_part.status == "completed"
    assert "ok" in tool_part.output


@pytest.mark.asyncio
async def test_execute_tool_bash_alias_maps_to_shell():
    config = SimpleNamespace(path_safety=SimpleNamespace(wild_mode=False))
    tool_part = ToolPart(tool="bash", input={"command": "echo alias-ok"})
    await execute_tool(tool_part, config=config, session_id="alias")
    assert tool_part.tool == "shell"
    assert tool_part.status == "completed"
    assert "alias-ok" in tool_part.output


@pytest.mark.asyncio
async def test_execute_tool_unknown_tool_still_fails():
    config = SimpleNamespace(path_safety=SimpleNamespace(wild_mode=False))
    tool_part = ToolPart(tool="foobar_tool", input={"command": "echo alias-ok"})
    with pytest.raises(WoloToolError, match=r"Unknown tool: foobar_tool\.") as exc_info:
        await execute_tool(tool_part, config=config, session_id="alias")
    assert exc_info.value.context.get("error_type") == "UnknownToolError"
