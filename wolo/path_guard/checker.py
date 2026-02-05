# wolo/path_guard/checker.py
"""Core path checking logic.

This module contains the pure path checking logic with no external
dependencies. It's testable in isolation and follows single responsibility.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PathWhitelist:
    """Immutable collection of whitelisted paths.

    Priority order (for documentation):
        1. workdir (highest)
        2. cli_paths
        3. config_paths
        4. /tmp (default)
        5. confirmed_dirs

    Attributes:
        config_paths: Paths from config file (path_safety.allowed_write_paths)
        cli_paths: Paths from --allow-path/-P CLI arguments
        workdir: Working directory from -C/--workdir (highest priority)
        confirmed_dirs: Directories confirmed by user during session
    """

    config_paths: set[Path] = field(default_factory=set)
    cli_paths: set[Path] = field(default_factory=set)
    workdir: Path | None = None
    confirmed_dirs: set[Path] = field(default_factory=set)

    # Default safe directory
    _default_allowed: set[Path] = field(default_factory=lambda: {Path("/tmp").resolve()})

    def is_whitelisted(self, path: Path) -> bool:
        """Check if a path is in the whitelist.

        Args:
            path: Normalized absolute path to check

        Returns:
            True if path is whitelisted, False otherwise
        """
        # 1. Check workdir (highest priority)
        if self.workdir:
            try:
                resolved = path.resolve()
                if resolved.is_relative_to(self.workdir) or resolved == self.workdir:
                    return True
            except (OSError, RuntimeError):
                pass

        # 2. Check default allowed (/tmp)
        for allowed in self._default_allowed:
            try:
                if path.is_relative_to(allowed) or path == allowed:
                    return True
            except (OSError, RuntimeError):
                pass

        # 3. Check CLI paths
        for cli_path in self.cli_paths:
            try:
                if path.is_relative_to(cli_path) or path == cli_path:
                    return True
            except (OSError, RuntimeError):
                pass

        # 4. Check config paths
        for config_path in self.config_paths:
            try:
                if path.is_relative_to(config_path) or path == config_path:
                    return True
            except (OSError, RuntimeError):
                pass

        # 5. Check confirmed directories
        for confirmed in self.confirmed_dirs:
            try:
                if path.is_relative_to(confirmed):
                    return True
            except (OSError, RuntimeError):
                pass

        return False


class PathChecker:
    """Core path checking logic.

    This class is pure logic with no side effects. It doesn't do I/O,
    doesn't interact with the user, and doesn't depend on global state.

    Usage:
        checker = PathChecker(whitelist=config.get_whitelist())
        result = checker.check("/tmp/file.txt", Operation.WRITE)
        if result.requires_confirmation:
            # Handle confirmation
        elif not result.allowed:
            # Handle denial
    """

    def __init__(self, whitelist: PathWhitelist) -> None:
        """Initialize with a whitelist configuration.

        Args:
            whitelist: PathWhitelist containing all allowed path sources
        """
        self._whitelist = whitelist
        self._confirmed_dirs: set[Path] = set(whitelist.confirmed_dirs)

    def check(self, path: str | Path, operation) -> "CheckResult":
        """Check if a path operation is allowed.

        Args:
            path: Path to check (can be relative, absolute, or symlinks)
            operation: Operation type (from Operation enum)

        Returns:
            CheckResult with the check outcome
        """
        from wolo.path_guard.models import CheckResult, Operation

        # Read operations are always allowed (KISS principle)
        if operation == Operation.READ:
            return CheckResult.allowed_for(operation)

        # Normalize the path
        try:
            normalized = Path(path).resolve()
        except (OSError, RuntimeError) as e:
            return CheckResult.denied(
                Path(path) if isinstance(path, Path) else Path(path),
                operation,
                f"path resolution failed: {e}",
            )

        # Check whitelist
        if self._whitelist.is_whitelisted(normalized):
            return CheckResult.allowed_for(operation)

        # Check confirmed directories
        for confirmed in self._confirmed_dirs:
            if normalized.is_relative_to(confirmed):
                return CheckResult.allowed_for(operation)

        # Requires confirmation
        return CheckResult.needs_confirmation(normalized, operation)

    def confirm_directory(self, directory: str | Path) -> None:
        """Mark a directory as confirmed by the user.

        For file paths, confirms the parent directory.
        For non-existent paths, confirms the parent directory.

        Args:
            directory: Directory or file path to confirm
        """
        normalized = Path(directory).resolve()

        # For files, use parent directory
        if normalized.is_file():
            normalized = normalized.parent
        elif not normalized.exists():
            # For non-existent paths, use parent directory
            normalized = normalized.parent

        self._confirmed_dirs.add(normalized)

    def get_confirmed_dirs(self) -> list[Path]:
        """Get list of confirmed directories.

        Returns:
            List of confirmed directory paths
        """
        return list(self._confirmed_dirs)
