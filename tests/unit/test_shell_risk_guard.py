from unittest.mock import MagicMock, patch

import pytest

from wolo.tools_pkg.shell import (
    clear_shell_state,
    detect_shell_high_risk_patterns,
    shell_execute,
    should_allow_shell_command,
)


def test_detect_shell_high_risk_patterns_matches_multiple_rules():
    matched = detect_shell_high_risk_patterns("git reset --hard && rm -rf /")
    ids = {item["id"] for item in matched}
    assert "git_reset_hard" in ids
    assert "rm_root_like" in ids


def test_should_allow_shell_command_non_risky():
    allowed, message = should_allow_shell_command("echo hello", session_id="sid-non-risk")
    assert allowed is True
    assert message is None


def test_should_allow_shell_command_non_interactive_denies():
    with patch("sys.stdin.isatty", return_value=False):
        allowed, message = should_allow_shell_command("git reset --hard", session_id="sid-ni")
    assert allowed is False
    assert "Denied high-risk shell command in non-interactive mode" in (message or "")


def test_should_allow_shell_command_allow_once_does_not_persist():
    session_id = "sid-once"
    clear_shell_state(session_id)
    mock_console = MagicMock()
    mock_console.input.side_effect = ["y", "n"]

    with patch("wolo.tools_pkg.shell.Console", return_value=mock_console):
        with patch("sys.stdin.isatty", return_value=True):
            first_allowed, _ = should_allow_shell_command("git reset --hard", session_id=session_id)
            second_allowed, _ = should_allow_shell_command(
                "git reset --hard", session_id=session_id
            )

    assert first_allowed is True
    assert second_allowed is False
    assert mock_console.input.call_count == 2


def test_should_allow_shell_command_allow_session_persists():
    session_id = "sid-session"
    clear_shell_state(session_id)
    mock_console = MagicMock()
    mock_console.input.side_effect = ["a"]

    with patch("wolo.tools_pkg.shell.Console", return_value=mock_console):
        with patch("sys.stdin.isatty", return_value=True):
            first_allowed, _ = should_allow_shell_command("git reset --hard", session_id=session_id)
            second_allowed, _ = should_allow_shell_command(
                "git reset --hard", session_id=session_id
            )

    assert first_allowed is True
    assert second_allowed is True
    assert mock_console.input.call_count == 1


@pytest.mark.asyncio
async def test_shell_execute_high_risk_denied_returns_error_metadata():
    with patch("sys.stdin.isatty", return_value=False):
        result = await shell_execute("git reset --hard", session_id="sid-deny")

    assert result["metadata"]["error"] == "high_risk_shell_denied"
    assert result["metadata"]["exit_code"] == -2
