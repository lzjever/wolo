# wolo/tools_pkg/path_guard_executor.py

"""PathGuard middleware integration for tool execution.

This module provides the integration layer between the tool executor
and the PathGuard middleware. It manages the global middleware instance
and provides convenience functions for path-checked tool execution.
"""

from typing import Any
from collections.abc import Awaitable, Callable

from wolo.path_guard import (
    PathGuardConfig,
    PathGuardMiddleware,
    PathChecker,
    CLIConfirmationStrategy,
    set_path_guard,
)
from wolo.path_guard.models import Operation
from wolo.path_guard.checker import PathWhitelist


# Global middleware instance (set during initialization)
_middleware: PathGuardMiddleware | None = None
_path_checker: PathChecker | None = None


def initialize_path_guard_middleware(
    config_paths: list,
    cli_paths: list,
    workdir: str | None = None,
    confirmed_dirs: list | None = None,
) -> None:
    """Initialize the global PathGuard middleware and checker.

    Args:
        config_paths: Paths from config file (path_safety.allowed_write_paths)
        cli_paths: Paths from CLI arguments (--allow-path/-P)
        workdir: Working directory from -C/--workdir
        confirmed_dirs: Previously confirmed directories from session resume
    """
    global _middleware, _path_checker

    from pathlib import Path

    guard_config = PathGuardConfig(
        config_paths=[Path(p) for p in config_paths],
        cli_paths=[Path(p) for p in cli_paths],
        workdir=Path(workdir) if workdir else None,
    )

    confirmed = set(Path(p) for p in confirmed_dirs) if confirmed_dirs else set()

    # Create whitelist with all sources
    whitelist = guard_config.create_whitelist(confirmed_dirs=confirmed)

    # Create checker
    _path_checker = PathChecker(whitelist)

    # Set global path guard for CLIConfirmationStrategy to use
    set_path_guard(_path_checker)

    # Create middleware with CLI strategy
    strategy = CLIConfirmationStrategy()
    _middleware = PathGuardMiddleware(_path_checker, strategy)


def get_path_guard_middleware() -> PathGuardMiddleware:
    """Get the global PathGuard middleware."""
    if _middleware is None:
        raise RuntimeError("PathGuard middleware not initialized")
    return _middleware


def get_path_checker() -> PathChecker:
    """Get the global PathChecker instance."""
    if _path_checker is None:
        raise RuntimeError("PathChecker not initialized")
    return _path_checker


async def execute_with_path_guard(
    func: Callable[..., Awaitable[dict[str, Any]]],
    /,
    file_path: str,
    operation: Operation = Operation.WRITE,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute a function with PathGuard middleware.

    Args:
        func: Async function to execute (e.g., write_execute, edit_execute)
        file_path: Path to check before execution
        operation: Type of operation being performed
        **kwargs: Additional arguments to pass to func

    Returns:
        Result from func, or error dict if path check failed

    Raises:
        SessionCancelled: If user cancels during confirmation
    """
    middleware = get_path_guard_middleware()
    return await middleware.execute_with_path_check(
        func,
        file_path=file_path,
        operation=operation,
        **kwargs,
    )


def get_confirmed_dirs() -> list:
    """Get list of confirmed directories for session persistence.

    Returns:
        List of confirmed directory paths
    """
    checker = get_path_checker()
    return checker.get_confirmed_dirs()
