"""Custom exception hierarchy for Wolo.

This module defines the standard exception types used throughout the Wolo
codebase, providing consistent error handling with session tracking and
structured context metadata.
"""

from typing import Any


class WoloError(Exception):
    """Base exception for all Wolo-specific errors.

    Attributes:
        message: The error message.
        session_id: Optional session identifier for tracking errors within
            a specific agent session.
        context: Arbitrary keyword arguments providing additional error context.

    Example:
        >>> raise WoloError("File not found", session_id="sess_123", path="/foo/bar")
    """

    def __init__(self, message: str, session_id: str | None = None, **context: Any) -> None:
        """Initialize a WoloError.

        Args:
            message: Human-readable error message.
            session_id: Optional session identifier for tracking.
            **context: Additional contextual information as keyword arguments.
        """
        super().__init__(message)
        self.message = message
        self.session_id = session_id
        self.context = context

    def __str__(self) -> str:
        """Return the error message."""
        return self.message

    def __repr__(self) -> str:
        """Return a detailed representation of the error."""
        parts = [self.__class__.__name__, f"message={self.message!r}"]

        if self.session_id:
            parts.append(f"session_id={self.session_id!r}")

        if self.context:
            ctx_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            parts.append(f"context={{{ctx_str}}}")

        return f"{self.__class__.__name__}({', '.join(parts[1:])})"


class WoloConfigError(WoloError):
    """Exception raised for configuration-related errors.

    Use this for:
    - Missing or invalid configuration files
    - Invalid API keys or credentials
    - Malformed configuration values
    - Missing required environment variables
    """


class WoloToolError(WoloError):
    """Exception raised for tool execution failures.

    Use this for:
    - Tool execution timeout
    - Tool not found
    - Invalid tool arguments
    - Tool execution errors
    """


class WoloSessionError(WoloError):
    """Exception raised for session lifecycle errors.

    Use this for:
    - Session not found
    - Session load/save failures
    - Session PID conflicts
    - Corrupted session data
    """


class WoloLLMError(WoloError):
    """Exception raised for LLM API errors.

    Use this for:
    - API authentication failures
    - Rate limiting errors
    - Network/timeout errors
    - Invalid API responses
    - Token limit exceeded
    """


class WoloPathSafetyError(WoloError):
    """Exception raised for path validation violations.

    Use this for:
    - Attempts to access protected system paths
    - Path traversal attempts
    - Unsafe file operations
    - Path validation failures
    """
