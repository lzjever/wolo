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
"""

from wolo.path_guard.exceptions import (
    PathCheckError,
    PathConfirmationRequired,
    PathGuardError,
    SessionCancelled,
)
from wolo.path_guard.models import CheckResult, Operation

# Export public API
__all__ = [
    # Exceptions
    "PathGuardError",
    "PathCheckError",
    "PathConfirmationRequired",
    "SessionCancelled",
    # Models
    "CheckResult",
    "Operation",
]
