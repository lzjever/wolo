import json
from unittest.mock import MagicMock, patch

import pytest

from wolo.path_guard import set_path_guard
from wolo.path_guard.checker import PathChecker, PathWhitelist
from wolo.path_guard.cli_strategy import CLIConfirmationStrategy


@pytest.mark.asyncio
async def test_confirmations_exceed_limit_auto_deny():
    checker = PathChecker(PathWhitelist())
    set_path_guard(checker)

    mock_console = MagicMock()
    mock_console.input.return_value = "y"

    with patch("wolo.path_guard.cli_strategy.Console", return_value=mock_console):
        with patch("sys.stdin.isatty", return_value=True):
            strategy = CLIConfirmationStrategy(
                max_confirmations_per_session=1,
                audit_denied=False,
            )
            first = await strategy.confirm("/workspace/a.py", "write")
            second = await strategy.confirm("/workspace/b.py", "write")

    assert first is True
    assert second is False
    assert mock_console.input.call_count == 1


@pytest.mark.asyncio
async def test_denied_operation_writes_audit_log(tmp_path):
    checker = PathChecker(PathWhitelist())
    set_path_guard(checker)

    audit_file = tmp_path / "path_audit.log"
    mock_console = MagicMock()

    with patch("wolo.path_guard.cli_strategy.Console", return_value=mock_console):
        with patch("sys.stdin.isatty", return_value=False):
            strategy = CLIConfirmationStrategy(
                audit_denied=True,
                audit_log_file=audit_file,
            )
            allowed = await strategy.confirm("/workspace/blocked.py", "write")

    assert allowed is False
    assert audit_file.exists()

    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["path"] == "/workspace/blocked.py"
    assert entry["operation"] == "write"
    assert entry["reason"] == "non_interactive_auto_deny"
