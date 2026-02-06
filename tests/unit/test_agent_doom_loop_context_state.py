"""Tests for doom loop detection using context-state."""

import pytest

# Check if lexilux is available (required for agent.py imports)
try:
    import lexilux  # noqa: F401

    LEXILUX_AVAILABLE = True
except ImportError:
    LEXILUX_AVAILABLE = False

if not LEXILUX_AVAILABLE:
    pytest.skip("lexilux not installed - requires local path dependency", allow_module_level=True)

from wolo.agent import _check_doom_loop
from wolo.context_state import (
    add_doom_loop_entry,
    clear_doom_loop_history,
    get_doom_loop_history,
)


def test_check_doom_loop_uses_context_state():
    """Doom loop detection uses context-state for history."""
    clear_doom_loop_history()

    # Same call DOOM_LOOP_THRESHOLD (5) times triggers doom loop
    tool_input = {"path": "/tmp/test.txt"}

    # First 4 calls should not trigger doom loop
    for _ in range(4):
        result = _check_doom_loop("write", tool_input)
        assert result is False

    # 5th call should detect doom loop
    result = _check_doom_loop("write", tool_input)
    assert result is True


def test_doom_loop_history_isolated():
    """Doom loop history is isolated in context-state."""
    clear_doom_loop_history()

    add_doom_loop_entry(("read", "hash1", ""))
    add_doom_loop_entry(("grep", "hash2", ""))

    history = get_doom_loop_history()
    assert len(history) == 2
    assert history[0] == ("read", "hash1", "")
    assert history[1] == ("grep", "hash2", "")


def test_doom_loop_read_only_tools_exempt():
    """Read-only tools are exempt from doom loop detection."""
    clear_doom_loop_history()

    tool_input = {"path": "/tmp/test.txt"}

    # Read-only tools should not trigger doom loop
    for tool_name in ["read", "glob", "grep", "file_exists", "get_env"]:
        for _ in range(10):
            result = _check_doom_loop(tool_name, tool_input)
            assert result is False, f"{tool_name} should be exempt from doom loop detection"


def test_doom_loop_shell_read_only_commands_exempt():
    """Shell commands with read-only prefixes are exempt from doom loop detection."""
    clear_doom_loop_history()

    read_only_commands = [
        "python3 -m py_compile test.py",
        "ls -la",
        "cat /tmp/file.txt",
        "echo hello",
        "git status",
        "git diff",
    ]

    for command in read_only_commands:
        tool_input = {"command": command}
        for _ in range(10):
            result = _check_doom_loop("shell", tool_input)
            assert result is False, f"Command '{command}' should be exempt from doom loop detection"


def test_doom_loop_threshold():
    """Doom loop threshold is correctly applied."""
    clear_doom_loop_history()

    tool_input = {"path": "/tmp/test.txt"}

    # First 4 calls should not trigger doom loop
    for _ in range(4):
        result = _check_doom_loop("write", tool_input)
        assert result is False

    # 5th call with same input should trigger
    result = _check_doom_loop("write", tool_input)
    assert result is True


def test_doom_loop_different_inputs():
    """Different tool inputs don't trigger doom loop."""
    clear_doom_loop_history()

    # Same tool, different inputs - should not trigger
    for i in range(10):
        tool_input = {"path": f"/tmp/test{i}.txt"}
        result = _check_doom_loop("write", tool_input)
        assert result is False

    history = get_doom_loop_history()
    # Should have 5 entries (DOOM_LOOP_THRESHOLD)
    assert len(history) <= 5
