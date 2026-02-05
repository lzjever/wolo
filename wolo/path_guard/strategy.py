# wolo/path_guard/strategy.py
"""Confirmation strategy for path protection."""

from abc import ABC, abstractmethod


class ConfirmationStrategy(ABC):
    """Abstract base class for path confirmation strategies.

    Implementations of this interface handle user interaction for
    path confirmation requests. Different strategies can be used
    for CLI, web UI, automated testing, or non-interactive modes.
    """

    @abstractmethod
    async def confirm(self, path: str, operation: str) -> bool:
        """Request user confirmation for a path operation.

        Args:
            path: The path that requires confirmation
            operation: The operation type (e.g., "write", "edit")

        Returns:
            True if allowed, False if denied

        Raises:
            SessionCancelled: If user wants to cancel the entire session
        """
        pass


class AutoDenyConfirmationStrategy(ConfirmationStrategy):
    """Always denies (for non-interactive mode).

    This strategy is useful when the agent is running in a context
    where user interaction is not possible (e.g., CI/CD, API mode).
    """

    async def confirm(self, path: str, operation: str) -> bool:
        """Always deny confirmation requests."""
        return False


class AutoAllowConfirmationStrategy(ConfirmationStrategy):
    """Always allows (DANGEROUS - for testing only).

    WARNING: This strategy bypasses all path protection and should
    only be used in controlled test environments.
    """

    async def confirm(self, path: str, operation: str) -> bool:
        """Always allow confirmation requests."""
        return True
