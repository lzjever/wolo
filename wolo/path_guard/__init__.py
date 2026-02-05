# wolo/path_guard/__init__.py
"""PathGuard - Modular path protection for file operations.

This package provides a clean, modular architecture for path safety:
- Core checking logic with no external dependencies
- Pluggable confirmation strategies
- Dependency injection instead of global state
- Clear separation of concerns

Public API:
    PathChecker: Core path checking logic
    PathGuardConfig: Configuration management
    ConfirmationStrategy: Abstract confirmation handler
    PathGuardMiddleware: Middleware for path-checked tool execution
    PathGuardPersistence: Session persistence for confirmed directories
"""

from wolo.path_guard.checker import PathChecker, PathWhitelist
from wolo.path_guard.cli_strategy import CLIConfirmationStrategy
from wolo.path_guard.config import PathGuardConfig
from wolo.path_guard.exceptions import (
    PathCheckError,
    PathConfirmationRequired,
    PathGuardError,
    SessionCancelled,
)
from wolo.path_guard.middleware import PathGuardMiddleware
from wolo.path_guard.models import CheckResult, Operation
from wolo.path_guard.persistence import PathGuardPersistence
from wolo.path_guard.strategy import (
    AutoAllowConfirmationStrategy,
    AutoDenyConfirmationStrategy,
    ConfirmationStrategy,
)

# Global instance (temporary during refactor - will be removed in Task 8)
_path_checker: PathChecker | None = None


def get_path_guard() -> PathChecker:
    """Get the global PathGuard instance (temporary during refactor).

    NOTE: This is a transitional helper during the refactor.
    It will be removed in Task 8 when proper dependency injection is implemented.
    """
    global _path_checker
    if _path_checker is None:
        # Create default instance
        _path_checker = PathChecker(PathWhitelist())
    return _path_checker


def set_path_guard(checker: PathChecker) -> None:
    """Set the global PathGuard instance (temporary during refactor).

    NOTE: This is a transitional helper during the refactor.
    It will be removed in Task 8 when proper dependency injection is implemented.
    """
    global _path_checker
    _path_checker = checker


# Export public API
__all__ = [
    # Core
    "PathChecker",
    "PathWhitelist",
    # Exceptions
    "PathGuardError",
    "PathCheckError",
    "PathConfirmationRequired",
    "SessionCancelled",
    # Models
    "CheckResult",
    "Operation",
    # Configuration
    "PathGuardConfig",
    # Strategies
    "ConfirmationStrategy",
    "AutoDenyConfirmationStrategy",
    "AutoAllowConfirmationStrategy",
    "CLIConfirmationStrategy",
    # Middleware
    "PathGuardMiddleware",
    # Persistence
    "PathGuardPersistence",
    # Temporary globals (will be removed in Task 8)
    "get_path_guard",
    "set_path_guard",
]
