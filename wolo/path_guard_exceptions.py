# wolo/path_guard_exceptions.py
"""Exceptions raised by PathGuard."""


class PathConfirmationRequired(Exception):
    """Raised when a path operation requires user confirmation.

    This exception is raised by write tools when the target path
    is not in the whitelist and requires user confirmation.

    Attributes:
        path: The path that requires confirmation
        operation: The operation type (read/write/delete/execute)
    """

    def __init__(self, path: str, operation: str = "write"):
        self.path = path
        self.operation = operation
        super().__init__(f"Path confirmation required for {operation} on {path}")
