# wolo/path_guard.py
"""Path safety protection for file operations.

This module provides whitelist-based path protection for file write operations.
Only /tmp is allowed by default; all other paths require user confirmation.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable


class Operation(Enum):
    """File operation types"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"


@dataclass
class CheckResult:
    """Result of a path safety check"""
    allowed: bool
    requires_confirmation: bool
    reason: str = ""
    operation: Operation = Operation.WRITE


class PathGuard:
    """Path protection class using whitelist mode.

    Default behavior:
        - Only /tmp is allowed without confirmation
        - All other paths require user confirmation
        - Confirmed directories are stored per session

    Whitelist sources (in priority order):
        1. Default allowed paths (/tmp)
        2. Config file paths
        3. CLI-provided paths
        4. User-confirmed paths (stored in session)
    """

    def __init__(
        self,
        config_paths: Iterable[Path] = (),
        cli_paths: Iterable[Path] = (),
        session_confirmed: Iterable[Path] = (),
    ):
        # Default: only allow /tmp
        self._default_allowed = {Path("/tmp").resolve()}

        # Merge all whitelist sources
        self._allowed_paths = set(self._default_allowed)
        for p in config_paths:
            self._allowed_paths.add(Path(p).resolve())
        for p in cli_paths:
            self._allowed_paths.add(Path(p).resolve())

        # Session-confirmed directories
        self._confirmed_dirs = set()
        for p in session_confirmed:
            self._confirmed_dirs.add(Path(p).resolve())

        self._audit_log: list[dict] = []
        self._confirmation_count = 0

    def check(self, path: str | Path, operation: Operation = Operation.WRITE) -> CheckResult:
        """Check if a path operation is allowed.

        Args:
            path: Path to check
            operation: Type of operation (READ/WRITE/DELETE/EXECUTE)

        Returns:
            CheckResult with allowed status and confirmation requirement
        """
        # 1. Normalize path (resolves symlinks and relative paths)
        try:
            normalized = Path(path).resolve()
        except (OSError, RuntimeError) as e:
            self._audit_log.append({
                "path": str(path),
                "operation": operation.value,
                "result": "denied",
                "reason": f"path resolution failed: {e}"
            })
            return CheckResult(
                allowed=False,
                requires_confirmation=False,
                reason=f"Invalid path: {e}",
                operation=operation
            )

        # 2. Check default allowed list (only /tmp)
        for allowed in self._default_allowed:
            if normalized.is_relative_to(allowed) or normalized == allowed:
                return CheckResult(
                    allowed=True,
                    requires_confirmation=False,
                    operation=operation
                )

        # 3. Check config/CLI whitelist
        for allowed in self._allowed_paths:
            if normalized.is_relative_to(allowed) or normalized == allowed:
                return CheckResult(
                    allowed=True,
                    requires_confirmation=False,
                    operation=operation
                )

        # 4. Check session-confirmed directories
        for confirmed in self._confirmed_dirs:
            if normalized.is_relative_to(confirmed):
                return CheckResult(
                    allowed=True,
                    requires_confirmation=False,
                    operation=operation
                )

        # 5. Requires user confirmation
        return CheckResult(
            allowed=False,
            requires_confirmation=True,
            reason=f"Operation '{operation.value}' on {normalized} requires confirmation",
            operation=operation
        )

    def confirm_directory(self, directory: str | Path) -> bool:
        """Mark a directory as confirmed by the user.

        Args:
            directory: Directory path to confirm

        Returns:
            True if confirmation was recorded
        """
        normalized = Path(directory).resolve()

        # For files, use parent directory
        if normalized.is_file():
            normalized = normalized.parent
        elif not normalized.exists():
            # For non-existent paths, use parent directory
            normalized = normalized.parent

        self._confirmed_dirs.add(normalized)
        self._confirmation_count += 1
        return True

    def get_confirmed_dirs(self) -> list[Path]:
        """Get list of confirmed directories for session persistence."""
        return list(self._confirmed_dirs)

    def get_audit_log(self) -> list[dict]:
        """Get audit log of denied operations."""
        return self._audit_log.copy()


# Global singleton (session-level)
_path_guard: PathGuard | None = None


def get_path_guard() -> PathGuard:
    """Get the session-level PathGuard instance."""
    global _path_guard
    if _path_guard is None:
        _path_guard = PathGuard()
    return _path_guard


def set_path_guard(guard: PathGuard) -> None:
    """Set the PathGuard instance (for testing or session initialization)."""
    global _path_guard
    _path_guard = guard


def reset_path_guard() -> None:
    """Reset the PathGuard instance (for testing)."""
    global _path_guard
    _path_guard = None
