# wolo/path_guard/middleware.py
"""Middleware for path-checked tool execution."""

from typing import Any, Callable
from collections.abc import Awaitable

from wolo.path_guard.checker import PathChecker
from wolo.path_guard.strategy import ConfirmationStrategy
from wolo.path_guard.exceptions import SessionCancelled
from wolo.path_guard.models import Operation


class PathGuardMiddleware:
    """Middleware for path-checked tool execution.

    This middleware wraps tool functions with path checking logic.
    It handles confirmation requests and denial responses in a
    consistent way.

    Usage:
        middleware = PathGuardMiddleware(checker, strategy)
        result = await middleware.execute_with_path_check(
            write_tool_func,
            file_path="/tmp/file.txt",
            operation=Operation.WRITE,
            content="hello",
        )
    """

    def __init__(self, checker: PathChecker, strategy: ConfirmationStrategy) -> None:
        """Initialize the middleware.

        Args:
            checker: PathChecker instance for path validation
            strategy: ConfirmationStrategy for handling user confirmation
        """
        self._checker = checker
        self._strategy = strategy

    async def execute_with_path_check(
        self,
        tool_func: Callable[..., Awaitable[dict[str, Any]]],
        *,
        file_path: str,
        operation: Operation = Operation.WRITE,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a tool function with path checking.

        Args:
            tool_func: Async function to execute (e.g., write_execute)
            file_path: Path to check before execution
            operation: Type of operation being performed
            **kwargs: Additional arguments to pass to tool_func

        Returns:
            Result from tool_func, or error dict if denied

        Raises:
            SessionCancelled: If user cancels during confirmation
        """
        # Check path
        check_result = self._checker.check(file_path, operation)

        # Handle confirmation
        if check_result.requires_confirmation:
            allowed = await self._strategy.confirm(file_path, operation.value)
            if not allowed:
                return {
                    "output": f"Permission denied by user: {file_path}",
                    "metadata": {"error": "path_denied_by_user"},
                }
            # Re-check after confirmation
            check_result = self._checker.check(file_path, operation)

        # Verify allowed
        if not check_result.allowed:
            return {
                "output": f"Permission denied: {check_result.reason}",
                "metadata": {"error": "path_not_allowed"},
            }

        # Execute tool
        return await tool_func(file_path=file_path, **kwargs)
