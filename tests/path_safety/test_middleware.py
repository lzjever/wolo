# tests/path_safety/test_middleware.py
"""Tests for PathGuardMiddleware module."""

from pathlib import Path

import pytest

from wolo.path_guard.checker import PathChecker, PathWhitelist
from wolo.path_guard.exceptions import SessionCancelled
from wolo.path_guard.middleware import PathGuardMiddleware
from wolo.path_guard.models import Operation
from wolo.path_guard.strategy import AutoAllowConfirmationStrategy, AutoDenyConfirmationStrategy


class MockToolFunc:
    """Mock async tool function."""

    def __init__(self, return_value=None):
        self.called_with = None
        self.return_value = return_value or {"output": "success", "metadata": {}}

    async def __call__(self, **kwargs):
        self.called_with = kwargs
        return self.return_value


class MockConfirmStrategy:
    """Mock strategy that confirms directory on allow."""

    def __init__(self, checker: PathChecker, allow: bool = True):
        self.checker = checker
        self.allow = allow

    async def confirm(self, path: str, operation: str) -> bool:
        if self.allow:
            # Confirm the directory like CLIConfirmationStrategy does
            self.checker.confirm_directory(path)
        return self.allow


@pytest.mark.asyncio
class TestPathGuardMiddleware:
    async def test_execute_allowed_path(self):
        """Should execute tool for allowed paths."""
        whitelist = PathWhitelist(config_paths={Path("/tmp")}, cli_paths=set())
        checker = PathChecker(whitelist)
        strategy = AutoAllowConfirmationStrategy()
        mock_tool = MockToolFunc()

        middleware = PathGuardMiddleware(checker, strategy)
        result = await middleware.execute_with_path_check(
            mock_tool, file_path="/tmp/file.txt", operation=Operation.WRITE
        )

        assert result["output"] == "success"
        assert mock_tool.called_with["file_path"] == "/tmp/file.txt"

    async def test_execute_denied_path(self):
        """Should deny and not execute for non-whitelisted paths."""
        whitelist = PathWhitelist(config_paths=set(), cli_paths=set(), workdir=None)
        checker = PathChecker(whitelist)
        strategy = AutoDenyConfirmationStrategy()
        mock_tool = MockToolFunc()

        middleware = PathGuardMiddleware(checker, strategy)
        result = await middleware.execute_with_path_check(
            mock_tool, file_path="/workspace/file.txt", operation=Operation.WRITE
        )

        assert result["metadata"]["error"] == "path_denied_by_user"
        assert mock_tool.called_with is None

    async def test_read_operation_always_allowed(self):
        """Read operations should always be allowed."""
        whitelist = PathWhitelist(config_paths=set(), cli_paths=set(), workdir=None)
        checker = PathChecker(whitelist)
        strategy = AutoDenyConfirmationStrategy()
        mock_tool = MockToolFunc()

        middleware = PathGuardMiddleware(checker, strategy)
        result = await middleware.execute_with_path_check(
            mock_tool, file_path="/any/path/file.txt", operation=Operation.READ
        )

        assert result["output"] == "success"
        assert mock_tool.called_with is not None

    async def test_confirmation_allowed(self):
        """Should execute after confirmation is allowed."""
        whitelist = PathWhitelist(config_paths=set(), cli_paths=set(), workdir=None)
        checker = PathChecker(whitelist)
        strategy = MockConfirmStrategy(checker, allow=True)
        mock_tool = MockToolFunc()

        middleware = PathGuardMiddleware(checker, strategy)
        result = await middleware.execute_with_path_check(
            mock_tool, file_path="/workspace/file.txt", operation=Operation.WRITE
        )

        assert result["output"] == "success"
        assert mock_tool.called_with is not None

    async def test_passes_kwargs_to_tool(self):
        """Should pass additional kwargs to tool function."""
        whitelist = PathWhitelist(config_paths={Path("/tmp")}, cli_paths=set())
        checker = PathChecker(whitelist)
        strategy = AutoAllowConfirmationStrategy()
        mock_tool = MockToolFunc()

        middleware = PathGuardMiddleware(checker, strategy)
        await middleware.execute_with_path_check(
            mock_tool,
            file_path="/tmp/file.txt",
            operation=Operation.WRITE,
            content="hello world",
            append=True,
        )

        assert mock_tool.called_with["file_path"] == "/tmp/file.txt"
        assert mock_tool.called_with["content"] == "hello world"
        assert mock_tool.called_with["append"] is True

    async def test_session_cancelled_propagates(self):
        """Should propagate SessionCancelled exception."""

        class CancelStrategy:
            async def confirm(self, path, operation):
                raise SessionCancelled()

        whitelist = PathWhitelist(config_paths=set(), cli_paths=set(), workdir=None)
        checker = PathChecker(whitelist)
        strategy = CancelStrategy()
        mock_tool = MockToolFunc()

        middleware = PathGuardMiddleware(checker, strategy)

        with pytest.raises(SessionCancelled):
            await middleware.execute_with_path_check(
                mock_tool, file_path="/workspace/file.txt", operation=Operation.WRITE
            )

        assert mock_tool.called_with is None

    async def test_confirmed_dir_allows_subsequent_operations(self):
        """After confirming a directory, subsequent operations should be allowed."""
        whitelist = PathWhitelist(config_paths=set(), cli_paths=set(), workdir=None)
        checker = PathChecker(whitelist)
        strategy = MockConfirmStrategy(checker, allow=True)
        mock_tool = MockToolFunc()

        middleware = PathGuardMiddleware(checker, strategy)

        # First operation requires confirmation but is allowed
        result1 = await middleware.execute_with_path_check(
            mock_tool, file_path="/workspace/file1.txt", operation=Operation.WRITE
        )
        assert result1["output"] == "success"

        # Second operation on same directory should be allowed without confirmation
        # (because the first operation confirmed the parent directory)
        result2 = await middleware.execute_with_path_check(
            mock_tool, file_path="/workspace/file2.txt", operation=Operation.WRITE
        )
        assert result2["output"] == "success"
