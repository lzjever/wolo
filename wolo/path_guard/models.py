"""Core data models for PathGuard."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Operation(Enum):
    """File operation types."""

    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class CheckResult:
    """Immutable result of a path safety check."""

    allowed: bool
    requires_confirmation: bool
    reason: str
    operation: Operation

    @classmethod
    def allowed_for(cls, operation: Operation) -> "CheckResult":
        """Create a result for an allowed operation."""
        return cls(
            allowed=True,
            requires_confirmation=False,
            reason="Operation allowed",
            operation=operation,
        )

    @classmethod
    def needs_confirmation(cls, path: Path, operation: Operation) -> "CheckResult":
        """Create a result requiring user confirmation."""
        return cls(
            allowed=False,
            requires_confirmation=True,
            reason=f"Operation '{operation.value}' on {path} requires confirmation",
            operation=operation,
        )

    @classmethod
    def denied(cls, path: Path, operation: Operation, reason: str) -> "CheckResult":
        """Create a result for a denied operation."""
        return cls(
            allowed=False,
            requires_confirmation=False,
            reason=f"Operation '{operation.value}' on {path} denied: {reason}",
            operation=operation,
        )
