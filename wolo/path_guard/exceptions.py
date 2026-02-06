# wolo/path_guard/exceptions.py
"""PathGuard exception hierarchy.

All exceptions inherit from PathGuardError for consistent error handling.
"""


class PathGuardError(Exception):
    """Base exception for all PathGuard errors."""

    pass


class PathCheckError(PathGuardError):
    """Raised when path validation fails."""

    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Path check failed for '{path}': {reason}")


class PathConfirmationRequired(PathGuardError):  # noqa: N818
    """Raised when a path operation requires user confirmation.

    This is a control flow exception, not an error condition.
    It signals that the path protection layer requires user approval
    before proceeding with the operation.

    Attributes:
        path: The path that requires confirmation
        operation: The operation type (write/edit/etc)
    """

    def __init__(self, path: str, operation: str = "write"):
        self.path = path
        self.operation = operation
        super().__init__(f"Path requires confirmation for {operation} on {path}")


class SessionCancelled(PathGuardError):  # noqa: N818
    """Raised when user cancels the session during confirmation.

    This is a control flow exception for clean session termination.
    """

    def __init__(self):
        super().__init__("Session cancelled")
