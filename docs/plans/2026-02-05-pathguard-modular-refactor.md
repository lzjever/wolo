# PathGuard Modular Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor PathGuard from a monolithic, tightly-coupled implementation into a clean, modular architecture following SOLID, KISS, DRY, and YAGNI principles.

**Architecture:**
- **Core Layer**: Pure path checking logic with no external dependencies
- **Config Layer**: Unified configuration management with clear priority rules
- **Interaction Layer**: Pluggable confirmation strategies (CLI/auto/deny)
- **Integration Layer**: Middleware pattern for tool integration
- **Persistence Layer**: Session storage abstraction

**Tech Stack:** Python 3.10+, pathlib, dataclasses, abc, asyncio, pytest

**Design Principles:**
- **No global singletons** - Use dependency injection throughout
- **Interface-based design** - Abstract base classes for extensibility
- **Single responsibility** - Each module has one clear purpose
- **No backward compatibility needed** - Clean slate design

---

## Phase 1: Create Core Abstractions

### Task 1: Create Core PathGuard Module Structure

**Files:**
- Create: `wolo/path_guard/__init__.py`
- Create: `wolo/path_guard/exceptions.py`
- Create: `wolo/path_guard/models.py`
- Test: `tests/path_safety/test_exceptions.py`

**Step 1: Create the exceptions module**

```python
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


class PathConfirmationRequired(PathGuardError):
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
        super().__init__(f"Path confirmation required for {operation} on {path}")


class SessionCancelled(PathGuardError):
    """Raised when user cancels the session during confirmation.

    This is a control flow exception for clean session termination.
    """

    pass
```

**Step 2: Create the models module**

```python
# wolo/path_guard/models.py
"""Core data models for PathGuard.

This module defines the pure data structures used throughout PathGuard.
These models have no dependencies on other PathGuard components.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Operation(Enum):
    """File operation types.

    Only READ and WRITE are currently implemented.
    Future operations can be added as needed (YAGNI principle).
    """

    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class CheckResult:
    """Immutable result of a path safety check.

    Attributes:
        allowed: Whether the operation is allowed without confirmation
        requires_confirmation: Whether user confirmation is required
        reason: Human-readable explanation (always provided)
        operation: The operation being checked
    """

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
    def requires_confirmation(cls, path: Path, operation: Operation) -> "CheckResult":
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
```

**Step 3: Create the package init file**

```python
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
```

**Step 4: Write tests for exceptions**

```python
# tests/path_safety/test_exceptions.py
import pytest

from wolo.path_guard.exceptions import (
    PathCheckError,
    PathConfirmationRequired,
    PathGuardError,
    SessionCancelled,
)
from wolo.path_guard.models import CheckResult, Operation


class TestPathGuardExceptions:
    def test_path_guard_error_is_base_exception(self):
        """PathGuardError should be the base exception."""
        assert issubclass(PathGuardError, Exception)

    def test_path_check_error_attributes(self):
        """PathCheckError should store path and reason."""
        exc = PathCheckError("/etc/passwd", "protected system file")
        assert exc.path == "/etc/passwd"
        assert exc.reason == "protected system file"
        assert "Path check failed" in str(exc)

    def test_path_confirmation_required_attributes(self):
        """PathConfirmationRequired should store path and operation."""
        exc = PathConfirmationRequired("/workspace/file.py", "write")
        assert exc.path == "/workspace/file.py"
        assert exc.operation == "write"
        assert "requires confirmation" in str(exc).lower()

    def test_path_confirmation_required_default_operation(self):
        """PathConfirmationRequired should default to 'write' operation."""
        exc = PathConfirmationRequired("/tmp/file.txt")
        assert exc.operation == "write"

    def test_session_cancelled_is_simple(self):
        """SessionCancelled should be a simple exception."""
        exc = SessionCancelled()
        assert isinstance(exc, PathGuardError)
        assert "cancelled" in str(exc).lower()


class TestCheckResult:
    def test_allowed_for_factory(self):
        """allowed_for should create an allowed result."""
        result = CheckResult.allowed_for(Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False
        assert result.operation == Operation.WRITE

    def test_requires_confirmation_factory(self):
        """requires_confirmation should create a confirmation result."""
        path = "/workspace/test.py"
        result = CheckResult.requires_confirmation(path, Operation.WRITE)
        assert result.allowed is False
        assert result.requires_confirmation is True
        assert path in result.reason
        assert result.operation == Operation.WRITE

    def test_denied_factory(self):
        """denied should create a denied result."""
        path = "/etc/passwd"
        reason = "protected file"
        result = CheckResult.denied(path, Operation.WRITE, reason)
        assert result.allowed is False
        assert result.requires_confirmation is False
        assert reason in result.reason
        assert result.operation == Operation.WRITE

    def test_check_result_is_immutable(self):
        """CheckResult should be immutable (frozen dataclass)."""
        result = CheckResult.allowed_for(Operation.READ)
        with pytest.raises(Exception):  # FrozenInstanceError
            result.allowed = False
```

**Step 5: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_exceptions.py -v -o addopts=""
```

Expected: All tests PASS (these are simple data structures)

**Step 6: Commit**

```bash
git add wolo/path_guard/ tests/path_safety/test_exceptions.py
git commit -m "refactor(path_guard): create core abstractions - exceptions and models

- Create modular path_guard package structure
- Define exception hierarchy with PathGuardError base
- Create immutable CheckResult dataclass with factory methods
- Define Operation enum (READ, WRITE)
- Add comprehensive tests for exceptions and models
- Follow SOLID principles: single responsibility, interface segregation"
```

---

### Task 2: Create PathChecker Core Logic

**Files:**
- Create: `wolo/path_guard/checker.py`
- Test: `tests/path_safety/test_checker.py`

**Step 1: Write tests for PathChecker**

```python
# tests/path_safety/test_checker.py
import pytest
from pathlib import Path

from wolo.path_guard.checker import PathChecker, PathWhitelist
from wolo.path_guard.models import CheckResult, Operation


@pytest.fixture
def reset_checker():
    """Ensure no global state between tests."""
    yield
    # PathChecker has no global state after refactor


class TestPathWhitelist:
    def test_empty_whitelist_denies_everything(self):
        """Empty whitelist should deny all paths except defaults."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
        )
        assert whitelist.is_whitelisted(Path("/tmp/test.txt"))
        assert not whitelist.is_whitelisted(Path("/workspace/test.txt"))

    def test_workdir_has_highest_priority(self):
        """Workdir should allow paths within it."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=Path("/workspace"),
        )
        assert whitelist.is_whitelisted(Path("/workspace/test.txt"))
        assert whitelist.is_whitelisted(Path("/workspace/subdir/file.py"))
        assert not whitelist.is_whitelisted(Path("/etc/passwd"))

    def test_cli_paths_are_whitelisted(self):
        """CLI-provided paths should be whitelisted."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths={Path("/allowed")},
            workdir=None,
        )
        assert whitelist.is_whitelisted(Path("/allowed/file.txt"))
        assert not whitelist.is_whitelisted(Path("/workspace/file.txt"))

    def test_config_paths_are_whitelisted(self):
        """Config paths should be whitelisted."""
        whitelist = PathWhitelist(
            config_paths={Path("/project")},
            cli_paths=set(),
            workdir=None,
        )
        assert whitelist.is_whitelisted(Path("/project/file.txt"))
        assert not whitelist.is_whitelisted(Path("/etc/passwd"))

    def test_tmp_is_always_allowed(self):
        """/tmp should always be allowed as default safe directory."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
        )
        assert whitelist.is_whitelisted(Path("/tmp/file.txt"))
        assert whitelist.is_whitelisted(Path("/tmp/subdir/file.py"))

    def test_confirmed_dirs_are_whitelisted(self):
        """User-confirmed directories should be whitelisted."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
            confirmed_dirs={Path("/home/user/project")},
        )
        assert whitelist.is_whitelisted(Path("/home/user/project/file.txt"))
        assert not whitelist.is_whitelisted(Path("/etc/passwd"))


class TestPathChecker:
    def test_check_returns_allowed_result_for_whitelisted(self):
        """Should return allowed result for whitelisted paths."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths={Path("/workspace")},
                cli_paths=set(),
                workdir=None,
            )
        )
        result = checker.check("/workspace/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

    def test_check_returns_confirmation_for_unknown_path(self):
        """Should return confirmation required for unknown paths."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )
        result = checker.check("/workspace/file.py", Operation.WRITE)
        assert result.allowed is False
        assert result.requires_confirmation is True

    def test_check_normalizes_paths(self):
        """Should normalize relative paths and symlinks."""
        import tempfile
        import os

        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )

        # Test with /tmp which is always allowed
        result = checker.check("./test.py", Operation.WRITE)
        # ./test.py resolves to cwd/tmp/test.py or similar
        # The exact behavior depends on test environment
        assert isinstance(result, CheckResult)

    def test_check_handles_invalid_path(self):
        """Should return denied result for invalid paths."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )

        # Create a path that can't be resolved
        # This is environment-dependent, so we just check it doesn't crash
        result = checker.check("/nonexistent/path/../../etc/passwd", Operation.WRITE)
        assert isinstance(result, CheckResult)

    def test_read_operation_always_allowed(self):
        """Read operations should always be allowed (no confirmation)."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )
        result = checker.check("/any/path/file.txt", Operation.READ)
        assert result.allowed is True
        assert result.requires_confirmation is False

    def test_add_confirmed_directory(self):
        """Should be able to add confirmed directories."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )
        checker.confirm_directory("/workspace")

        # After confirmation, path should be allowed
        result = checker.check("/workspace/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

    def test_confirm_directory_for_file(self):
        """Confirming a file path should confirm its parent directory."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )
        checker.confirm_directory("/workspace/file.py")

        # Parent directory should be confirmed
        result = checker.check("/workspace/other.py", Operation.WRITE)
        assert result.allowed is True

    def test_get_confirmed_directories(self):
        """Should return list of confirmed directories."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )
        checker.confirm_directory("/workspace")
        checker.confirm_directory("/tmp/project")

        confirmed = checker.get_confirmed_dirs()
        assert len(confirmed) == 2
        assert any(p == Path("/workspace") for p in confirmed)
        assert any(p == Path("/tmp/project") for p in confirmed)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_checker.py -v -o addopts=""
```

Expected: `ModuleNotFoundError: No module named 'wolo.path_guard.checker'`

**Step 3: Implement PathChecker**

```python
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
        return CheckResult.requires_confirmation(normalized, operation)

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
```

**Step 4: Update package init to export new classes**

```python
# wolo/path_guard/__init__.py (add to exports)

from wolo.path_guard.checker import PathChecker, PathWhitelist

# Update __all__
__all__ = [
    # ... existing exports ...
    # Core
    "PathChecker",
    "PathWhitelist",
]
```

**Step 5: Run tests**

```bash
pytest tests/path_safety/test_checker.py -v -o addopts=""
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add wolo/path_guard/ tests/path_safety/test_checker.py
git commit -m "refactor(path_guard): implement PathChecker core logic

- Create PathWhitelist frozen dataclass for whitelist management
- Implement PathChecker with pure checking logic (no side effects)
- Read operations always allowed (KISS principle)
- Path normalization handles symlinks and relative paths
- Add comprehensive test coverage
- Remove global state - use dependency injection"
```

---

## Phase 2: Create Configuration Management

### Task 3: Create PathGuardConfig

**Files:**
- Create: `wolo/path_guard/config.py`
- Test: `tests/path_safety/test_config.py`

**Step 1: Write tests for configuration**

```python
# tests/path_safety/test_config.py
import pytest
from pathlib import Path

from wolo.path_guard.config import PathGuardConfig
from wolo.path_guard.checker import PathChecker, PathWhitelist


class TestPathGuardConfig:
    def test_default_config(self):
        """Default config should have sensible defaults."""
        config = PathGuardConfig()

        assert config.config_paths == []
        assert config.cli_paths == []
        assert config.workdir is None

        whitelist = config.create_whitelist(confirmed_dirs=set())
        assert isinstance(whitelist, PathWhitelist)
        assert whitelist.config_paths == set()
        assert whitelist.cli_paths == set()
        assert whitelist.workdir is None

    def test_config_with_paths(self):
        """Should store and use provided paths."""
        config = PathGuardConfig(
            config_paths=[Path("/workspace"), Path("/project")],
            cli_paths=[Path("/tmp/allowed")],
            workdir=Path("/home/user/cwd"),
        )

        assert len(config.config_paths) == 2
        assert len(config.cli_paths) == 1
        assert config.workdir == Path("/home/user/cwd")

    def test_create_whitelist_includes_config_paths(self):
        """Created whitelist should include config paths."""
        config = PathGuardConfig(
            config_paths=[Path("/allowed")]
        )

        whitelist = config.create_whitelist(confirmed_dirs=set())
        assert Path("/allowed") in whitelist.config_paths

    def test_create_whitelist_includes_cli_paths(self):
        """Created whitelist should include CLI paths."""
        config = PathGuardConfig(
            cli_paths=[Path("/cli-allowed")]
        )

        whitelist = config.create_whitelist(confirmed_dirs=set())
        assert Path("/cli-allowed") in whitelist.cli_paths

    def test_create_whitelist_includes_workdir(self):
        """Created whitelist should include workdir."""
        config = PathGuardConfig(
            workdir=Path("/workspace")
        )

        whitelist = config.create_whitelist(confirmed_dirs=set())
        assert whitelist.workdir == Path("/workspace")

    def test_create_whitelist_includes_confirmed_dirs(self):
        """Created whitelist should include confirmed dirs."""
        config = PathGuardConfig()

        confirmed = {Path("/home/user/project")}
        whitelist = config.create_whitelist(confirmed_dirs=confirmed)
        assert whitelist.confirmed_dirs == confirmed

    def test_create_checker(self):
        """Should be able to create a PathChecker from config."""
        config = PathGuardConfig(
            config_paths=[Path("/workspace")]
        )

        confirmed = {Path("/tmp/project")}
        checker = config.create_checker(confirmed_dirs=confirmed)

        assert isinstance(checker, PathChecker)

        # Check that whitelisted paths work
        from wolo.path_guard.models import Operation
        result = checker.check("/workspace/file.py", Operation.WRITE)
        assert result.allowed is True

    def test_from_dict(self):
        """Should be able to create config from dict (for YAML loading)."""
        data = {
            "config_paths": ["/workspace", "/project"],
            "cli_paths": ["/tmp/allowed"],
            "workdir": "/home/user/cwd",
        }

        config = PathGuardConfig.from_dict(data)

        assert len(config.config_paths) == 2
        assert Path("/workspace") in config.config_paths
        assert len(config.cli_paths) == 1
        assert config.workdir == Path("/home/user/cwd")

    def test_from_dict_with_none_values(self):
        """Should handle None values in dict."""
        data = {
            "config_paths": None,
            "cli_paths": None,
            "workdir": None,
        }

        config = PathGuardConfig.from_dict(data)

        assert config.config_paths == []
        assert config.cli_paths == []
        assert config.workdir is None

    def test_from_dict_with_empty_list(self):
        """Should handle empty lists in dict."""
        data = {
            "config_paths": [],
            "cli_paths": [],
        }

        config = PathGuardConfig.from_dict(data)

        assert config.config_paths == []
        assert config.cli_paths == []
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_config.py -v -o addopts=""
```

Expected: `ModuleNotFoundError: No module named 'wolo.path_guard.config'`

**Step 3: Implement PathGuardConfig**

```python
# wolo/path_guard/config.py
"""Configuration management for PathGuard.

This module handles loading and managing PathGuard configuration
from various sources (config file, CLI args, workdir).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wolo.path_guard.checker import PathChecker, PathWhitelist


@dataclass
class PathGuardConfig:
    """Configuration for PathGuard path protection.

    This is a simple data container that knows how to create
    PathWhitelist and PathChecker instances.

    Attributes:
        config_paths: Paths from config file (path_safety.allowed_write_paths)
        cli_paths: Paths from --allow-path/-P CLI arguments
        workdir: Working directory from -C/--workdir
    """

    config_paths: list[Path] = field(default_factory=list)
    cli_paths: list[Path] = field(default_factory=list)
    workdir: Path | None = None

    def create_whitelist(self, confirmed_dirs: set[Path]) -> PathWhitelist:
        """Create a PathWhitelist from this configuration.

        Args:
            confirmed_dirs: User-confirmed directories from session

        Returns:
            PathWhitelist with all configured sources
        """
        return PathWhitelist(
            config_paths=set(p.resolve() for p in self.config_paths),
            cli_paths=set(p.resolve() for p in self.cli_paths),
            workdir=Path(self.workdir).resolve() if self.workdir else None,
            confirmed_dirs=confirmed_dirs,
        )

    def create_checker(self, confirmed_dirs: set[Path] | None = None) -> PathChecker:
        """Create a PathChecker from this configuration.

        Args:
            confirmed_dirs: User-confirmed directories (defaults to empty set)

        Returns:
            PathChecker instance ready to use
        """
        if confirmed_dirs is None:
            confirmed_dirs = set()

        whitelist = self.create_whitelist(confirmed_dirs)
        return PathChecker(whitelist)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PathGuardConfig":
        """Create config from dictionary (for YAML loading).

        Args:
            data: Dictionary with config keys

        Returns:
            PathGuardConfig instance
        """
        config_paths = data.get("config_paths") or []
        cli_paths = data.get("cli_paths") or []
        workdir = data.get("workdir")

        return cls(
            config_paths=[Path(p).expanduser() for p in config_paths],
            cli_paths=[Path(p).expanduser() for p in cli_paths],
            workdir=Path(workdir).expanduser().resolve() if workdir else None,
        )
```

**Step 4: Update package init**

```python
# wolo/path_guard/__init__.py (add to exports)

from wolo.path_guard.config import PathGuardConfig

# Update __all__
__all__ = [
    # ... existing exports ...
    # Configuration
    "PathGuardConfig",
]
```

**Step 5: Run tests**

```bash
pytest tests/path_safety/test_config.py -v -o addopts=""
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add wolo/path_guard/ tests/path_safety/test_config.py
git commit -m "refactor(path_guard): add PathGuardConfig management

- Create PathGuardConfig dataclass for configuration
- Implement create_whitelist() method
- Implement create_checker() factory method
- Add from_dict() classmethod for YAML loading
- Add comprehensive configuration tests
- Separate configuration from core logic"
```

---

## Phase 3: Create Confirmation Strategy

### Task 4: Create Confirmation Strategy Interface

**Files:**
- Create: `wolo/path_guard/strategy.py`
- Test: `tests/path_safety/test_strategy.py`

**Step 1: Write tests for confirmation strategy**

```python
# tests/path_safety/test_strategy.py
import pytest

from wolo.path_guard.strategy import (
    AutoDenyConfirmationStrategy,
    ConfirmationStrategy,
    SessionCancelled,
)
from wolo.path_guard.exceptions import PathConfirmationRequired


class MockConfirmationStrategy(ConfirmationStrategy):
    """Mock strategy for testing."""

    def __init__(self, response: bool):
        self.response = response
        self.confirm_called = False
        self.confirm_path = None
        self.confirm_operation = None

    async def confirm(self, path: str, operation: str) -> bool:
        self.confirm_called = True
        self.confirm_path = path
        self.confirm_operation = operation
        return self.response


class TestConfirmationStrategy:
    def test_is_abstract_base_class(self):
        """ConfirmationStrategy should be an abstract base class."""
        # Can't instantiate abstract class
        with pytest.raises(TypeError):
            ConfirmationStrategy()

    def test_requires_confirm_method(self):
        """Subclasses must implement confirm method."""
        # MockConfirmationStrategy implements confirm, so it works
        strategy = MockConfirmationStrategy(response=True)
        assert hasattr(strategy, "confirm")


class TestMockConfirmationStrategy:
    @pytest.mark.asyncio
    async def test_confirm_returns_true(self):
        """Should return True when configured."""
        strategy = MockConfirmationStrategy(response=True)
        result = await strategy.confirm("/workspace/file.py", "write")
        assert result is True

    @pytest.mark.asyncio
    async def test_confirm_returns_false(self):
        """Should return False when configured."""
        strategy = MockConfirmationStrategy(response=False)
        result = await strategy.confirm("/workspace/file.py", "write")
        assert result is False

    @pytest.mark.asyncio
    async def test_confirm_tracks_call(self):
        """Should track that confirm was called."""
        strategy = MockConfirmationStrategy(response=True)
        await strategy.confirm("/workspace/file.py", "write")

        assert strategy.confirm_called is True
        assert strategy.confirm_path == "/workspace/file.py"
        assert strategy.confirm_operation == "write"


class TestAutoDenyConfirmationStrategy:
    @pytest.mark.asyncio
    async def test_always_denies(self):
        """AutoDeny should always return False."""
        strategy = AutoDenyConfirmationStrategy()
        result = await strategy.confirm("/any/path", "any_operation")
        assert result is False

    @pytest.mark.asyncio
    async def test_does_not_raise_session_cancelled(self):
        """AutoDeny should not raise SessionCancelled."""
        strategy = AutoDenyConfirmationStrategy()
        # Should not raise
        result = await strategy.confirm("/any/path", "write")
        assert result is False
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_strategy.py -v -o addopts=""
```

Expected: `ModuleNotFoundError: No module named 'wolo.path_guard.strategy'`

**Step 3: Implement confirmation strategy**

```python
# wolo/path_guard/strategy.py
"""Confirmation strategy for path protection.

This module defines the pluggable confirmation strategy interface.
Different environments can use different strategies (CLI, auto-deny, auto-allow).
"""

from abc import ABC, abstractmethod


class ConfirmationStrategy(ABC):
    """Abstract base class for path confirmation strategies.

    A confirmation strategy decides what to do when a path operation
    requires user confirmation.

    Implementations:
        - CLIConfirmationStrategy: Interactive prompts (in separate module)
        - AutoDenyConfirmationStrategy: Always deny (non-interactive)
        - AutoAllowConfirmationStrategy: Always allow (dangerous, for tests)
    """

    @abstractmethod
    async def confirm(self, path: str, operation: str) -> bool:
        """Request user confirmation for a path operation.

        Args:
            path: The path requiring confirmation
            operation: The operation type (write/edit/etc)

        Returns:
            True if the operation should be allowed, False if denied

        Raises:
            SessionCancelled: If the user wants to cancel the entire session
        """
        pass


class AutoDenyConfirmationStrategy(ConfirmationStrategy):
    """Confirmation strategy that always denies.

    This is useful for:
        - Non-interactive environments (CI/CD, scripts)
        - Automated testing
        - Safety-first configurations
    """

    async def confirm(self, path: str, operation: str) -> bool:
        """Always deny the operation.

        Args:
            path: The path requiring confirmation (ignored)
            operation: The operation type (ignored)

        Returns:
            Always False (deny)
        """
        return False


class AutoAllowConfirmationStrategy(ConfirmationStrategy):
    """Confirmation strategy that always allows.

    WARNING: This is dangerous and should only be used for testing.

    Using this in production defeats the purpose of path protection.
    """

    async def confirm(self, path: str, operation: str) -> bool:
        """Always allow the operation.

        Args:
            path: The path requiring confirmation (ignored)
            operation: The operation type (ignored)

        Returns:
            Always True (allow)
        """
        return True
```

**Step 4: Update package init**

```python
# wolo/path_guard/__init__.py (add to exports)

from wolo.path_guard.strategy import (
    AutoAllowConfirmationStrategy,
    AutoDenyConfirmationStrategy,
    ConfirmationStrategy,
)

# Update __all__
__all__ = [
    # ... existing exports ...
    # Strategies
    "ConfirmationStrategy",
    "AutoDenyConfirmationStrategy",
    "AutoAllowConfirmationStrategy",
]
```

**Step 5: Run tests**

```bash
pytest tests/path_safety/test_strategy.py -v -o addopts=""
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add wolo/path_guard/ tests/path_safety/test_strategy.py
git commit -m "refactor(path_guard): add pluggable confirmation strategy

- Create ConfirmationStrategy abstract base class
- Implement AutoDenyConfirmationStrategy for non-interactive mode
- Implement AutoAllowConfirmationStrategy for testing (dangerous!)
- Add comprehensive strategy tests
- Enable dependency injection of confirmation behavior"
```

---

### Task 5: Create CLI Confirmation Strategy

**Files:**
- Create: `wolo/path_guard/cli_strategy.py`
- Test: `tests/path_safety/test_cli_strategy.py`

**Step 1: Write tests for CLI strategy**

```python
# tests/path_safety/test_cli_strategy.py
import pytest
from unittest.mock import patch, MagicMock

from wolo.path_guard.cli_strategy import CLIConfirmationStrategy
from wolo.path_guard.exceptions import SessionCancelled


class TestCLIConfirmationStrategy:
    @patch("sys.stdin.isatty", return_value=False)
    @pytest.mark.asyncio
    async def test_non_interactive_denies(self, mock_isatty):
        """Non-interactive mode should deny without prompting."""
        strategy = CLIConfirmationStrategy()
        result = await strategy.confirm("/workspace/file.py", "write")

        assert result is False

    @patch("sys.stdin.isatty", return_value=True)
    @patch("wolo.path_guard.cli_strategy.Console")
    @pytest.mark.asyncio
    async def test_yes_confirms(self, mock_console_class, mock_isatty):
        """User entering 'y' should confirm."""
        mock_console = MagicMock()
        mock_console.input.return_value = "y"
        mock_console_class.return_value = mock_console

        # Mock get_path_guard to avoid global state
        with patch("wolo.path_guard.cli_strategy.get_path_guard") as mock_guard:
            mock_guard_instance = MagicMock()
            mock_guard.return_value = mock_guard_instance

            strategy = CLIConfirmationStrategy()
            result = await strategy.confirm("/workspace/file.py", "write")

            assert result is True
            mock_guard_instance.confirm_directory.assert_called_once()

    @patch("sys.stdin.isatty", return_value=True)
    @patch("wolo.path_guard.cli_strategy.Console")
    @pytest.mark.asyncio
    async def test_no_denies(self, mock_console_class, mock_isatty):
        """User entering 'n' should deny."""
        mock_console = MagicMock()
        mock_console.input.return_value = "n"
        mock_console_class.return_value = mock_console

        strategy = CLIConfirmationStrategy()
        result = await strategy.confirm("/workspace/file.py", "write")

        assert result is False

    @patch("sys.stdin.isatty", return_value=True)
    @patch("wolo.path_guard.cli_strategy.Console")
    @pytest.mark.asyncio
    async def test_q_raises_session_cancelled(self, mock_console_class, mock_isatty):
        """User entering 'q' should raise SessionCancelled."""
        mock_console = MagicMock()
        mock_console.input.return_value = "q"
        mock_console_class.return_value = mock_console

        strategy = CLIConfirmationStrategy()

        with pytest.raises(SessionCancelled):
            await strategy.confirm("/workspace/file.py", "write")

    @patch("sys.stdin.isatty", return_value=True)
    @patch("wolo.path_guard.cli_strategy.Console")
    @pytest.mark.asyncio
    async def test_a_confirms_directory(self, mock_console_class, mock_isatty):
        """User entering 'a' should confirm entire directory."""
        mock_console = MagicMock()
        mock_console.input.return_value = "a"
        mock_console_class.return_value = mock_console

        with patch("wolo.path_guard.cli_strategy.get_path_guard") as mock_guard:
            mock_guard_instance = MagicMock()
            mock_guard.return_value = mock_guard_instance

            strategy = CLIConfirmationStrategy()
            result = await strategy.confirm("/workspace/project/file.py", "write")

            assert result is True
            # Should confirm parent directory
            mock_guard_instance.confirm_directory.assert_called_once()

    @patch("sys.stdin.isatty", return_value=True)
    @patch("wolo.path_guard.cli_strategy.Console")
    @pytest.mark.asyncio
    async def test_default_empty_is_yes(self, mock_console_class, mock_isatty):
        """Empty input (Enter) should be treated as 'y'."""
        mock_console = MagicMock()
        mock_console.input.return_value = ""
        mock_console_class.return_value = mock_console

        with patch("wolo.path_guard.cli_strategy.get_path_guard") as mock_guard:
            mock_guard_instance = MagicMock()
            mock_guard.return_value = mock_guard_instance

            strategy = CLIConfirmationStrategy()
            result = await strategy.confirm("/workspace/file.py", "write")

            assert result is True
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_cli_strategy.py -v -o addopts=""
```

Expected: `ModuleNotFoundError: No module named 'wolo.path_guard.cli_strategy'`

**Step 3: Implement CLI confirmation strategy**

```python
# wolo/path_guard/cli_strategy.py
"""CLI-based confirmation strategy.

This module implements the interactive confirmation prompts
for terminal usage.
"""

import sys
from pathlib import Path

from rich.console import Console

from wolo.path_guard.strategy import ConfirmationStrategy
from wolo.path_guard.exceptions import SessionCancelled


class CLIConfirmationStrategy(ConfirmationStrategy):
    """Interactive confirmation strategy for CLI usage.

    Prompts the user with Y/n/a/q options:
        Y/yes: Allow this operation
        N/no: Deny this operation
        A/allow: Allow entire directory
        Q/quit: Cancel the session
    """

    def __init__(self) -> None:
        """Initialize the CLI confirmation strategy."""
        self._console = Console()

    async def confirm(self, path: str, operation: str) -> bool:
        """Request user confirmation via CLI prompt.

        Args:
            path: The path requiring confirmation
            operation: The operation type

        Returns:
            True if allowed, False if denied

        Raises:
            SessionCancelled: If user enters 'q'
        """
        # Import here to avoid circular dependency
        # This is a temporary solution during refactor
        from wolo.path_guard import get_path_guard

        self._console.print("\n⚠️  [yellow]Path Confirmation Required[/yellow]")
        self._console.print(f"Operation: [cyan]{operation}[/cyan]")
        self._console.print(f"Path: [cyan]{path}[/cyan]")
        self._console.print(
            "This path is not in the default allowlist (/tmp) or configured whitelist."
        )

        # Non-interactive mode: auto-deny
        if not sys.stdin.isatty():
            self._console.print("[dim]Non-interactive mode, operation denied.[/dim]")
            self._console.print(
                "Tip: Configure path_safety.allowed_write_paths in ~/.wolo/config.yaml"
            )
            return False

        # Interactive prompt
        while True:
            response = (
                self._console.input(
                    "\n[yellow]Allow this operation?[/yellow] [Y/n/a/q] "
                )
                .strip()
                .lower()
            )

            if response in ("", "y", "yes"):
                guard = get_path_guard()
                guard.confirm_directory(path)
                return True
            elif response in ("n", "no"):
                return False
            elif response == "a":
                guard = get_path_guard()
                parent = Path(path).parent
                guard.confirm_directory(parent)
                self._console.print(
                    f"[green]✓[/green] {parent} and subdirectories added to session whitelist"
                )
                return True
            elif response == "q":
                self._console.print("[red]Session cancelled[/red]")
                raise SessionCancelled()
            else:
                self._console.print("[dim]Please enter Y/n/a/q[/dim]")
```

**Step 4: Update package init**

```python
# wolo/path_guard/__init__.py (add to exports)

from wolo.path_guard.cli_strategy import CLIConfirmationStrategy

# Update __all__
__all__ = [
    # ... existing exports ...
    # CLI Strategy
    "CLIConfirmationStrategy",
]
```

**Step 5: Run tests**

```bash
pytest tests/path_safety/test_cli_strategy.py -v -o addopts=""
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add wolo/path_guard/ tests/path_safety/test_cli_strategy.py
git commit -m "refactor(path_guard): add CLI confirmation strategy

- Implement CLIConfirmationStrategy with interactive prompts
- Support Y/n/a/q responses
- Handle non-interactive mode (auto-deny)
- Add comprehensive tests with mocks
- Note: Uses get_path_guard() temporarily during refactor"
```

---

## Phase 4: Create Middleware Layer

### Task 6: Create PathGuard Middleware

**Files:**
- Create: `wolo/path_guard/middleware.py`
- Test: `tests/path_safety/test_middleware.py`

**Step 1: Write tests for middleware**

```python
# tests/path_safety/test_middleware.py
import pytest

from wolo.path_guard.middleware import PathGuardMiddleware
from wolo.path_guard.checker import PathChecker, PathWhitelist
from wolo.path_guard.strategy import AutoDenyConfirmationStrategy, MockConfirmationStrategy
from wolo.path_guard.exceptions import PathConfirmationRequired, SessionCancelled
from wolo.path_guard.models import Operation


class MockToolFunction:
    """Mock tool function for testing."""

    def __init__(self, should_fail=False):
        self.call_count = 0
        self.last_path = None
        self.should_fail = should_fail

    async def __call__(self, file_path: str, **kwargs):
        self.call_count += 1
        self.last_path = file_path
        if self.should_fail:
            raise RuntimeError("Tool execution failed")
        return {"output": f"Written to {file_path}", "metadata": {}}


class TestPathGuardMiddleware:
    @pytest.mark.asyncio
    async def test_allowed_path_executes_tool(self):
        """Should execute tool for allowed paths."""
        whitelist = PathWhitelist(
            config_paths={},
            cli_paths={},
            workdir=None,
        )
        checker = PathChecker(whitelist)
        strategy = MockConfirmationStrategy(response=True)

        middleware = PathGuardMiddleware(checker, strategy)
        tool = MockToolFunction()

        result = await middleware.execute_with_path_check(
            tool, file_path="/tmp/test.txt"
        )

        assert result["output"] == "Written to /tmp/test.txt"
        assert tool.call_count == 1

    @pytest.mark.asyncio
    async def test_confirmation_required_allowed(self):
        """Should prompt for confirmation and execute if allowed."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
        )
        checker = PathChecker(whitelist)
        strategy = MockConfirmationStrategy(response=True)

        middleware = PathGuardMiddleware(checker, strategy)
        tool = MockToolFunction()

        result = await middleware.execute_with_path_check(
            tool, file_path="/workspace/test.txt"
        )

        assert result["output"] == "Written to /workspace/test.txt"
        assert tool.call_count == 1

    @pytest.mark.asyncio
    async def test_confirmation_required_denied(self):
        """Should return error when confirmation denied."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
        )
        checker = PathChecker(whitelist)
        strategy = MockConfirmationStrategy(response=False)

        middleware = PathGuardMiddleware(checker, strategy)
        tool = MockToolFunction()

        result = await middleware.execute_with_path_check(
            tool, file_path="/workspace/test.txt"
        )

        assert "Permission denied" in result["output"]
        assert tool.call_count == 0

    @pytest.mark.asyncio
    async def test_session_cancelled_propagates(self):
        """Should propagate SessionCancelled exception."""
        from wolo.path_guard.exceptions import SessionCancelled

        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
        )

        class CancelStrategy:
            async def confirm(self, path: str, operation: str) -> bool:
                raise SessionCancelled()

        checker = PathChecker(whitelist)
        strategy = CancelStrategy()

        middleware = PathGuardMiddleware(checker, strategy)
        tool = MockToolFunction()

        with pytest.raises(SessionCancelled):
            await middleware.execute_with_path_check(
                tool, file_path="/workspace/test.txt"
            )

        assert tool.call_count == 0

    @pytest.mark.asyncio
    async def test_tool_execution_error_propagates(self):
        """Should propagate tool execution errors."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
        )
        checker = PathChecker(whitelist)
        strategy = MockConfirmationStrategy(response=True)

        middleware = PathGuardMiddleware(checker, strategy)
        tool = MockToolFunction(should_fail=True)

        with pytest.raises(RuntimeError, match="Tool execution failed"):
            await middleware.execute_with_path_check(
                tool, file_path="/tmp/test.txt"
            )

    @pytest.mark.asyncio
    async def test_passes_kwargs_to_tool(self):
        """Should pass all kwargs to tool function."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
        )
        checker = PathChecker(whitelist)
        strategy = MockConfirmationStrategy(response=True)

        # Track received kwargs
        received_kwargs = {}

        async def tool_with_kwargs(file_path: str, content: str, **kwargs):
            received_kwargs["content"] = content
            received_kwargs.update(kwargs)
            return {"output": "OK", "metadata": {}}

        middleware = PathGuardMiddleware(checker, strategy)

        await middleware.execute_with_path_check(
            tool_with_kwargs,
            file_path="/tmp/test.txt",
            content="Hello, World!",
            extra_arg="value",
        )

        assert received_kwargs["content"] == "Hello, World!"
        assert received_kwargs["extra_arg"] == "value"

    @pytest.mark.asyncio
    async def test_read_operation_skips_check(self):
        """Read operations should skip path checking."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
        )
        checker = PathChecker(whitelist)
        strategy = MockConfirmationStrategy(response=True)

        middleware = PathGuardMiddleware(checker, strategy)
        tool = MockToolFunction()

        result = await middleware.execute_with_path_check(
            tool, file_path="/etc/passwd", operation=Operation.READ
        )

        assert result["output"] == "Written to /etc/passwd"
        assert tool.call_count == 1
        assert strategy.confirm_called is False
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_middleware.py -v -o addopts=""
```

Expected: `ModuleNotFoundError: No module named 'wolo.path_guard.middleware'`

**Step 3: Implement middleware**

```python
# wolo/path_guard/middleware.py
"""Middleware for path-checked tool execution.

This module provides the middleware layer that wraps tool execution
with path checking and confirmation handling.
"""

from typing import Any, Callable
from collections.abc import Awaitable

from wolo.path_guard.checker import PathChecker
from wolo.path_guard.strategy import ConfirmationStrategy
from wolo.path_guard.exceptions import PathConfirmationRequired, SessionCancelled
from wolo.path_guard.models import Operation


class PathGuardMiddleware:
    """Middleware for path-checked tool execution.

    This class wraps tool execution with path protection:
        1. Check path with PathChecker
        2. If confirmation required, use ConfirmationStrategy
        3. Execute tool if allowed
        4. Return result or error

    Usage:
        middleware = PathGuardMiddleware(checker, strategy)
        result = await middleware.execute_with_path_check(
            write_tool,
            file_path="/workspace/file.txt",
            content="Hello",
        )
    """

    def __init__(self, checker: PathChecker, strategy: ConfirmationStrategy) -> None:
        """Initialize middleware with dependencies.

        Args:
            checker: PathChecker for path validation
            strategy: ConfirmationStrategy for user interaction
        """
        self._checker = checker
        self._strategy = strategy

    async def execute_with_path_check(
        self,
        tool_func: Callable[..., Awaitable[dict[str, Any]]],
        *,
        file_path: str,
        operation: Operation = Operation.WRITE,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a tool function with path checking.

        Args:
            tool_func: Async tool function to execute
            file_path: Path parameter for the operation
            operation: Type of operation (default: WRITE)
            **kwargs: Additional arguments to pass to tool_func

        Returns:
            Tool execution result

        Raises:
            SessionCancelled: If user cancels during confirmation
            Exception: Any exception from tool_func execution
        """
        # Step 1: Check path
        check_result = self._checker.check(file_path, operation)

        # Step 2: Handle confirmation requirement
        if check_result.requires_confirmation:
            allowed = await self._strategy.confirm(file_path, operation.value)

            if not allowed:
                return {
                    "output": f"Permission denied by user: {file_path}",
                    "metadata": {"error": "path_denied_by_user"},
                }

            # After confirmation, check should pass
            # (strategy called confirm_directory)
            check_result = self._checker.check(file_path, operation)

        # Step 3: Verify allowed
        if not check_result.allowed:
            return {
                "output": f"Permission denied: {check_result.reason}",
                "metadata": {"error": "path_not_allowed"},
            }

        # Step 4: Execute tool
        return await tool_func(file_path=file_path, **kwargs)
```

**Step 4: Update package init**

```python
# wolo/path_guard/__init__.py (add to exports)

from wolo.path_guard.middleware import PathGuardMiddleware

# Update __all__
__all__ = [
    # ... existing exports ...
    # Middleware
    "PathGuardMiddleware",
]
```

**Step 5: Run tests**

```bash
pytest tests/path_safety/test_middleware.py -v -o addopts=""
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add wolo/path_guard/ tests/path_safety/test_middleware.py
git commit -m "refactor(path_guard): add middleware layer for tool execution

- Create PathGuardMiddleware for path-checked execution
- Handle confirmation flow transparently
- Propagate tool execution errors
- Support all tool kwargs
- Skip path checking for READ operations (KISS)
- Add comprehensive middleware tests"
```

---

## Phase 5: Create Session Persistence

### Task 7: Create Session Persistence

**Files:**
- Create: `wolo/path_guard/persistence.py`
- Test: `tests/path_safety/test_persistence.py`

**Step 1: Write tests for persistence**

```python
# tests/path_safety/test_persistence.py
import pytest
import json
from pathlib import Path
from datetime import datetime

from wolo.path_guard.persistence import PathGuardPersistence


class TestPathGuardPersistence:
    def test_save_and_load(self, tmp_path):
        """Should save and load confirmed directories."""
        persistence = PathGuardPersistence(session_dir=tmp_path)

        confirmed = [Path("/workspace"), Path("/tmp/project")]
        persistence.save_confirmed_dirs("test_session", confirmed)

        loaded = persistence.load_confirmed_dirs("test_session")
        assert len(loaded) == 2
        assert any(p == Path("/workspace") for p in loaded)
        assert any(p == Path("/tmp/project") for p in loaded)

    def test_load_nonexistent_returns_empty(self, tmp_path):
        """Loading non-existent session should return empty list."""
        persistence = PathGuardPersistence(session_dir=tmp_path)

        loaded = persistence.load_confirmed_dirs("nonexistent_session")
        assert loaded == []

    def test_save_creates_correct_file(self, tmp_path):
        """Save should create correct JSON file."""
        persistence = PathGuardPersistence(session_dir=tmp_path)

        confirmed = [Path("/workspace")]
        persistence.save_confirmed_dirs("test", confirmed)

        file_path = tmp_path / "test" / "path_confirmations.json"
        assert file_path.exists()

        data = json.loads(file_path.read_text())
        assert "confirmed_dirs" in data
        assert "confirmation_count" in data
        assert "last_updated" in data
        assert data["confirmation_count"] == 1

    def test_overwrites_existing_save(self, tmp_path):
        """Saving should overwrite existing data."""
        persistence = PathGuardPersistence(session_dir=tmp_path)

        # First save
        persistence.save_confirmed_dirs("test", [Path("/dir1")])

        # Second save (overwrite)
        persistence.save_confirmed_dirs("test", [Path("/dir2"), Path("/dir3")])

        loaded = persistence.load_confirmed_dirs("test")
        assert len(loaded) == 2
        assert any(p == Path("/dir2") for p in loaded)

    def test_handles_unicode_paths(self, tmp_path):
        """Should handle paths with unicode characters."""
        persistence = PathGuardPersistence(session_dir=tmp_path)

        # Note: actual unicode path handling depends on filesystem
        confirmed = [Path("/tmp/测试")]
        persistence.save_confirmed_dirs("test", confirmed)

        loaded = persistence.load_confirmed_dirs("test")
        assert len(loaded) == 1
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_persistence.py -v -o addopts=""
```

Expected: `ModuleNotFoundError: No module named 'wolo.path_guard.persistence'`

**Step 3: Implement persistence**

```python
# wolo/path_guard/persistence.py
"""Session persistence for PathGuard.

This module handles saving and loading confirmed directories
to/from session storage.
"""

import json
from datetime import datetime
from pathlib import Path


class PathGuardPersistence:
    """Persistence layer for PathGuard session data.

    This class handles file I/O for confirmed directories.
    It's separated from the core logic for testability.
    """

    def __init__(self, session_dir: Path) -> None:
        """Initialize persistence with session directory.

        Args:
            session_dir: Base directory for session storage
        """
        self._session_dir = session_dir

    def _get_confirmation_file(self, session_id: str) -> Path:
        """Get the confirmation file path for a session.

        Args:
            session_id: Session identifier

        Returns:
            Path to the confirmation JSON file
        """
        return self._session_dir / session_id / "path_confirmations.json"

    def save_confirmed_dirs(self, session_id: str, confirmed_dirs: list[Path]) -> None:
        """Save confirmed directories to session storage.

        Args:
            session_id: Session identifier
            confirmed_dirs: List of confirmed directory paths
        """
        file_path = self._get_confirmation_file(session_id)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "confirmed_dirs": [str(p) for p in confirmed_dirs],
            "confirmation_count": len(confirmed_dirs),
            "last_updated": datetime.now().isoformat(),
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_confirmed_dirs(self, session_id: str) -> list[Path]:
        """Load confirmed directories from session storage.

        Args:
            session_id: Session identifier

        Returns:
            List of confirmed directory paths (empty if file doesn't exist)
        """
        file_path = self._get_confirmation_file(session_id)

        if not file_path.exists():
            return []

        with open(file_path) as f:
            data = json.load(f)

        return [Path(p) for p in data.get("confirmed_dirs", [])]
```

**Step 4: Update package init**

```python
# wolo/path_guard/__init__.py (add to exports)

from wolo.path_guard.persistence import PathGuardPersistence

# Update __all__
__all__ = [
    # ... existing exports ...
    # Persistence
    "PathGuardPersistence",
]
```

**Step 5: Run tests**

```bash
pytest tests/path_safety/test_persistence.py -v -o addopts=""
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add wolo/path_guard/ tests/path_safety/test_persistence.py
git commit -m "refactor(path_guard): add session persistence layer

- Create PathGuardPersistence for session data
- Implement save_confirmed_dirs() method
- Implement load_confirmed_dirs() method
- Handle missing files gracefully
- Add comprehensive persistence tests
- Separate I/O from business logic"
```

---

## Phase 6: Integration and Cleanup

### Task 8: Update Integration Points

**Files:**
- Modify: `wolo/tools_pkg/file_write.py`
- Modify: `wolo/tools_pkg/executor.py`
- Modify: `wolo/cli/main.py` (for _initialize_path_guard)
- Delete: `wolo/path_guard.py` (old monolithic file)
- Delete: `wolo/path_guard_exceptions.py` (old exceptions)
- Delete: `wolo/cli/path_confirmation.py` (moved to path_guard)

**Step 1: Update file_write.py to use new PathGuard**

First, let's read the current file to understand what to change:

The current implementation:
- Imports `get_path_guard()` from `wolo.path_guard`
- Imports `PathConfirmationRequiredError` from `wolo.path_guard_exceptions`
- Calls `guard.check()` and raises exception if confirmation required

New implementation should:
- Use the middleware pattern or direct PathChecker usage
- Not raise exceptions (middleware handles confirmation)
- Keep tools simple and focused

```python
# wolo/tools_pkg/file_write.py (refactored)
"""File writing and editing tools."""

from pathlib import Path
from typing import Any

from wolo.smart_replace import smart_replace


async def write_execute(file_path: str, content: str) -> dict[str, Any]:
    """Write content to a file.

    Note: Path checking is handled by the executor middleware,
    not by individual tool functions.
    """
    path = Path(file_path)

    try:
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        path.write_text(content, encoding="utf-8")

        return {
            "title": file_path,
            "output": f"Successfully wrote {len(content)} bytes to {file_path}",
            "metadata": {"size": len(content)},
        }
    except Exception as e:
        return {
            "title": file_path,
            "output": f"Error writing file: {e}",
            "metadata": {"error": str(e)},
        }


async def edit_execute(file_path: str, old_text: str, new_text: str) -> dict[str, Any]:
    """Edit a file by replacing old_text with new_text using smart matching.

    Note: Path checking is handled by the executor middleware.
    """
    import difflib

    path = Path(file_path)

    if not path.exists():
        return {
            "title": file_path,
            "output": f"File not found: {file_path}",
            "metadata": {"error": "not_found"},
        }

    try:
        content = path.read_text(encoding="utf-8", errors="replace")

        # Use smart replace with multiple matching strategies
        try:
            new_content = smart_replace(content, old_text, new_text)
        except LookupError:
            return {
                "title": file_path,
                "output": f"Old text not found in file (tried multiple matching strategies).\nPreview: {old_text[:100]}...",
                "metadata": {"error": "text_not_found", "old_text_preview": old_text[:200]},
            }
        except ValueError as e:
            return {"title": file_path, "output": str(e), "metadata": {"error": "multiple_matches"}}

        # Generate diff
        diff_lines = list(
            difflib.unified_diff(
                content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
            )
        )
        diff_text = "".join(diff_lines)

        # Count changes
        additions = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
        deletions = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))

        # Write file
        path.write_text(new_content, encoding="utf-8")

        output = f"Successfully edited {file_path}\n"
        output += f"Changes: +{additions} -{deletions} lines\n\n"
        if diff_text:
            output += f"```diff\n{diff_text}\n```"

        return {
            "title": file_path,
            "output": output,
            "metadata": {
                "additions": additions,
                "deletions": deletions,
                "diff": diff_text,
            },
        }
    except Exception as e:
        return {
            "title": file_path,
            "output": f"Error editing file: {e}",
            "metadata": {"error": str(e)},
        }


async def multiedit_execute(edits: list[dict[str, str]]) -> dict[str, Any]:
    """Edit multiple files at once.

    Note: Each edit will be checked individually by the middleware.
    """
    results = []
    success_count = 0

    for edit in edits:
        file_path = edit.get("file_path", "")
        old_text = edit.get("old_text", "")
        new_text = edit.get("new_text", "")

        result = await edit_execute(file_path, old_text, new_text)
        results.append(result)

        if "error" not in result.get("metadata", {}):
            success_count += 1

    # Format output
    output_lines = [f"Multi-edit completed: {success_count}/{len(edits)} files edited\n"]
    for r in results:
        metadata = r.get("metadata", {})
        status = "✓" if "error" not in metadata else "✗"
        output_lines.append(f"{status} {r['title']}: {r['output'].split(chr(10))[0]}")

    return {
        "title": f"multiedit: {len(edits)} files",
        "output": "\n".join(output_lines),
        "metadata": {
            "total": len(edits),
            "success": success_count,
            "failed": len(edits) - success_count,
        },
    }
```

**Step 2: Update executor.py to use middleware**

```python
# wolo/tools_pkg/executor.py (modifications needed)

# Add imports at top:
from wolo.path_guard import PathGuardConfig, PathGuardMiddleware, CLIConfirmationStrategy

# In execute_tool function, for write and edit tools:

# Replace the current try/except blocks for write and edit with middleware usage

# For write (around line 107):
elif tool_part.tool == "write":
    file_path = tool_part.input.get("file_path", "")
    content = tool_part.input.get("content", "")

    # Check if file was modified externally
    if session_id:
        try:
            FileTime.assert_not_modified(session_id, file_path)
        except FileModifiedError:
            tool_part.status = "error"
            tool_part.output = (
                f"File '{file_path}' has been modified since you last read it. "
                f"Please read the file again to see the current contents before writing."
            )
            raise

    # Execute with path checking middleware
    # Note: We need access to the middleware instance
    # This will be passed in or created elsewhere
    result = await execute_with_path_guard(
        write_execute,
        file_path=file_path,
        content=content,
    )

    tool_part.output = result["output"]
    if result.get("metadata", {}).get("error"):
        tool_part.status = "error"
    else:
        tool_part.status = "completed"

    # Update file time after successful write
    if session_id and not result.get("metadata", {}).get("error"):
        FileTime.update(session_id, file_path)
```

**Step 3: Create a helper function for middleware usage**

```python
# wolo/tools_pkg/path_guard_executor.py (new file)

"""PathGuard middleware integration for tool execution.

This module provides the integration between PathGuard and tool execution.
It creates and manages the middleware instance.
"""

from wolo.path_guard import (
    PathGuardConfig,
    PathGuardMiddleware,
    PathChecker,
    CLIConfirmationStrategy,
)
from wolo.path_guard.models import Operation


# Global middleware instance (set during initialization)
_middleware: PathGuardMiddleware | None = None


def initialize_path_guard_middleware(
    config_paths: list,
    cli_paths: list,
    workdir: str | None,
    confirmed_dirs: list | None = None,
) -> None:
    """Initialize the global PathGuard middleware.

    Args:
        config_paths: Paths from config file
        cli_paths: Paths from --allow-path CLI args
        workdir: Working directory from -C/--workdir
        confirmed_dirs: Previously confirmed directories (for session resume)
    """
    global _middleware

    from pathlib import Path

    guard_config = PathGuardConfig(
        config_paths=[Path(p) for p in config_paths],
        cli_paths=[Path(p) for p in cli_paths],
        workdir=Path(workdir) if workdir else None,
    )

    confirmed = set(Path(p) for p in confirmed_dirs) if confirmed_dirs else set()
    checker = guard_config.create_checker(confirmed_dirs=confirmed)
    strategy = CLIConfirmationStrategy()

    _middleware = PathGuardMiddleware(checker, strategy)


def get_path_guard_middleware() -> PathGuardMiddleware:
    """Get the global PathGuard middleware.

    Returns:
        PathGuardMiddleware instance

    Raises:
        RuntimeError: If middleware hasn't been initialized
    """
    if _middleware is None:
        raise RuntimeError("PathGuard middleware not initialized. Call initialize_path_guard_middleware() first.")
    return _middleware


async def execute_with_path_guard(func, /, **kwargs):
    """Execute a function with PathGuard middleware.

    This is a convenience wrapper that handles the middleware call.

    Args:
        func: Async function to execute
        **kwargs: Arguments to pass to the function

    Returns:
        Function result

    Raises:
        RuntimeError: If middleware not initialized
        SessionCancelled: If user cancels during confirmation
    """
    middleware = get_path_guard_middleware()

    # Extract file_path and operation from kwargs
    file_path = kwargs.pop("file_path")
    operation = kwargs.pop("operation", Operation.WRITE)

    return await middleware.execute_with_path_check(
        func,
        file_path=file_path,
        operation=operation,
        **kwargs,
    )
```

**Step 4: Update _initialize_path_guard in main.py**

```python
# wolo/cli/main.py (refactor _initialize_path_guard)

def _initialize_path_guard(
    config,
    cli_paths: list[str],
    session_id: str,
    workdir: str | None,
) -> None:
    """Initialize PathGuard with config and CLI-provided paths.

    This now uses the new modular PathGuard architecture.

    Args:
        config: Configuration object containing path_safety settings
        cli_paths: List of paths provided via --allow-path CLI argument
        session_id: Session identifier for loading saved confirmations
        workdir: Working directory from -C/--workdir
    """
    from wolo.path_guard import PathGuardPersistence
    from wolo.tools_pkg.path_guard_executor import initialize_path_guard_middleware

    # Get config paths
    config_paths = config.path_safety.allowed_write_paths

    # Load previously confirmed directories
    import os
    session_dir = Path.home() / ".wolo" / "sessions"
    persistence = PathGuardPersistence(session_dir=session_dir)
    confirmed_dirs = persistence.load_confirmed_dirs(session_id)

    # Initialize middleware
    initialize_path_guard_middleware(
        config_paths=[str(p) for p in config_paths],
        cli_paths=cli_paths,
        workdir=workdir,
        confirmed_dirs=[str(p) for p in confirmed_dirs],
    )
```

**Step 5: Save confirmed directories on session save**

Add to session save logic:

```python
# In session save logic (wherever save_session is called)

def save_session_with_path_confirmations(session_id: str) -> None:
    """Save session including path confirmations."""
    from wolo.tools_pkg.path_guard_executor import get_path_guard_middleware
    from wolo.path_guard import PathGuardPersistence

    # Save regular session data
    save_session(session_id)

    # Save path confirmations
    try:
        middleware = get_path_guard_middleware()
        confirmed = middleware._checker.get_confirmed_dirs()

        session_dir = Path.home() / ".wolo" / "sessions"
        persistence = PathGuardPersistence(session_dir=session_dir)
        persistence.save_confirmed_dirs(session_id, confirmed)
    except RuntimeError:
        # PathGuard not initialized, skip
        pass
```

**Step 6: Remove old files**

```bash
# After confirming new implementation works
git rm wolo/path_guard.py
git rm wolo/path_guard_exceptions.py
git rm wolo/cli/path_confirmation.py
```

**Step 7: Update imports across codebase**

Search for and update imports:
- `from wolo.path_guard import` → `from wolo.path_guard import` (keep these)
- `from wolo.path_guard_exceptions import` → `from wolo.path_guard.exceptions import`
- `from wolo.cli.path_confirmation import` → `from wolo.path_guard.cli_strategy import`

**Step 8: Run all tests**

```bash
pytest tests/path_safety/ -v -o addopts=""
pytest tests/ -v -o addopts=""  # Run all tests to check for breakage
```

**Step 9: Fix any failing tests**

Update test imports and assertions as needed.

**Step 10: Commit**

```bash
git add -A
git commit -m "refactor(path_guard): complete migration to modular architecture

- Update file_write.py to remove path checking (handled by middleware)
- Update executor.py to use PathGuardMiddleware
- Create path_guard_executor.py for integration
- Update _initialize_path_guard in main.py
- Add session save/load for confirmed directories
- Remove old monolithic files (path_guard.py, path_guard_exceptions.py)
- Remove old cli/path_confirmation.py (moved to path_guard/cli_strategy.py)
- Update all imports across codebase

Breaking changes:
- Tools no longer do path checking directly
- PathGuard is now a proper package with modules
- Uses dependency injection instead of global singletons"
```

---

### Task 9: Update Config Integration

**Files:**
- Modify: `wolo/config.py`
- Modify: `wolo/cli/main.py` (config loading)

**Step 1: Update config.py to use new PathGuardConfig**

The current `PathSafetyConfig` in config.py can be simplified since
configuration is now handled by `wolo.path_guard.PathGuardConfig`.

```python
# wolo/config.py (modify PathSafetyConfig)

@dataclass
class PathSafetyConfig:
    """Configuration for path safety protection.

    This is now a simple data container that converts to PathGuardConfig.
    """

    allowed_write_paths: list[Path] = field(default_factory=list)

    def to_path_guard_config(self, cli_paths: list[Path] = None, workdir: Path = None) -> "PathGuardConfig":
        """Convert to PathGuardConfig.

        Args:
            cli_paths: Additional paths from CLI arguments
            workdir: Working directory

        Returns:
            PathGuardConfig instance
        """
        from wolo.path_guard import PathGuardConfig

        return PathGuardConfig(
            config_paths=self.allowed_write_paths,
            cli_paths=cli_paths or [],
            workdir=workdir,
        )
```

**Step 2: Simplify config loading in from_env**

Remove the complex path_safety loading logic since it's now
handled by the PathGuard module.

**Step 3: Commit**

```bash
git add wolo/config.py
git commit -m "refactor(path_guard): simplify config integration

- Add to_path_guard_config() conversion method
- PathGuardConfig is now the source of truth
- Remove duplicated path handling logic"
```

---

### Task 10: Documentation and Final Tests

**Files:**
- Update: `docs/PATH_SAFETY.md`
- Test: All tests

**Step 1: Update documentation**

```markdown
# PathGuard Architecture

## Overview

PathGuard is a modular path protection system with clear separation of concerns:

### Core Components

1. **Models** (`wolo/path_guard/models.py`)
   - `CheckResult`: Immutable result of path checking
   - `Operation`: Enum of operation types (READ, WRITE)

2. **Checker** (`wolo/path_guard/checker.py`)
   - `PathWhitelist`: Immutable whitelist configuration
   - `PathChecker`: Pure path checking logic

3. **Configuration** (`wolo/path_guard/config.py`)
   - `PathGuardConfig`: Configuration data container

4. **Strategy** (`wolo/path_guard/strategy.py`)
   - `ConfirmationStrategy`: Abstract confirmation interface
   - `AutoDenyConfirmationStrategy`: Always deny (non-interactive)
   - `AutoAllowConfirmationStrategy`: Always allow (testing only)

5. **CLI Strategy** (`wolo/path_guard/cli_strategy.py`)
   - `CLIConfirmationStrategy`: Interactive prompts

6. **Middleware** (`wolo/path_guard/middleware.py`)
   - `PathGuardMiddleware`: Wraps tool execution with path checking

7. **Persistence** (`wolo/path_guard/persistence.py`)
   - `PathGuardPersistence`: Session data storage

## Usage

### Basic Usage

```python
from wolo.path_guard import PathGuardConfig, PathGuardMiddleware, CLIConfirmationStrategy

# Create configuration
config = PathGuardConfig(
    config_paths=[Path("/workspace")],
    cli_paths=[Path("/tmp/allowed")],
    workdir=Path("/home/user/cwd"),
)

# Create checker and middleware
checker = config.create_checker()
strategy = CLIConfirmationStrategy()
middleware = PathGuardMiddleware(checker, strategy)

# Execute with path checking
result = await middleware.execute_with_path_check(
    write_func,
    file_path="/workspace/file.txt",
    content="Hello",
)
```

### Initialization

```python
from wolo.tools_pkg.path_guard_executor import initialize_path_guard_middleware

initialize_path_guard_middleware(
    config_paths=["/workspace"],
    cli_paths=["/tmp/custom"],
    workdir="/home/user/project",
    confirmed_dirs=["/home/user/previous"],
)
```

## Design Principles

1. **No Global State**: Uses dependency injection
2. **Pure Functions**: PathChecker has no side effects
3. **Immutable Data**: CheckResult and PathWhitelist are frozen
4. **Interface-Based**: ConfirmationStrategy is abstract
5. **Single Responsibility**: Each module has one purpose
```

**Step 2: Run full test suite**

```bash
pytest tests/ -v -o addopts="" --tb=short
```

**Step 3: Run specific path safety tests**

```bash
pytest tests/path_safety/ -v -o addopts=""
```

**Step 4: Fix any remaining issues**

**Step 5: Final commit**

```bash
git add docs/ tests/
git commit -m "refactor(path_guard): update documentation and tests

- Update PATH_SAFETY.md with new architecture
- Add comprehensive documentation
- Ensure all tests pass
- Document design principles and usage examples"
```

---

## Verification Checklist

After completing all tasks:

- [ ] All old files removed (path_guard.py, path_guard_exceptions.py, cli/path_confirmation.py)
- [ ] New package structure complete (wolo/path_guard/)
- [ ] All tests passing (pytest tests/ -v)
- [ ] No global singletons (dependency injection used)
- [ ] Tools are simple (no path checking logic)
- [ ] Middleware handles confirmation flow
- [ ] Session persistence works
- [ ] Documentation updated
- [ ] Imports updated across codebase
- [ ] Config integration simplified

---

## Summary of Changes

### Before (Monolithic)
```
wolo/path_guard.py              # Everything in one file
wolo/path_guard_exceptions.py   # Exceptions
wolo/cli/path_confirmation.py   # CLI interaction
```

### After (Modular)
```
wolo/path_guard/
├── __init__.py              # Public API exports
├── models.py                # CheckResult, Operation
├── checker.py               # PathChecker, PathWhitelist
├── config.py                # PathGuardConfig
├── strategy.py              # ConfirmationStrategy, AutoDeny, AutoAllow
├── cli_strategy.py          # CLIConfirmationStrategy
├── middleware.py            # PathGuardMiddleware
├── persistence.py           # PathGuardPersistence
└── exceptions.py            # All exceptions
```

### Architecture Improvements

| Principle | Before | After |
|-----------|--------|-------|
| **SRP** | PathGuard did everything | Each module has one responsibility |
| **OCP** | Hard to extend | Strategy pattern for extensions |
| **DIP** | Global singletons | Dependency injection |
| **KISS** | 5-level priority system | Clear whitelist checking |
| **DRY** | Exception handling repeated | Middleware handles once |
| **YAGNI** | Unused operation types | Only READ, WRITE implemented |

---

**End of Implementation Plan**
