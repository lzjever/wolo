# PathGuard Path Safety Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add whitelist-based path protection for file write operations in wolo AI agent, with `/tmp` as the only default allowed path and user confirmation for all other write locations.

**Architecture:** Centralized `PathGuard` class validates all write operations against a whitelist (config file + CLI args + session-confirmed directories). Tools raise `PathConfirmationRequired` exception, CLI layer handles user interaction, confirmed paths persist to session storage.

**Tech Stack:** Python 3.11+, pathlib, dataclasses, asyncio, pytest

---

## Task 1: Create PathGuard Core Module

**Files:**
- Create: `wolo/path_guard.py`
- Test: `tests/path_safety/test_path_guard.py`

**Step 1: Create tests directory**

```bash
mkdir -p tests/path_safety
touch tests/path_safety/__init__.py
```

**Step 2: Write the failing test for default behavior**

```python
# tests/path_safety/test_path_guard.py
import pytest
from pathlib import Path
from wolo.path_guard import PathGuard, Operation, reset_path_guard

@pytest.fixture(autouse=True)
def reset_guard():
    """Reset PathGuard before each test"""
    reset_path_guard()
    yield
    reset_path_guard()

class TestPathGuardBasics:
    def test_default_only_allows_tmp(self):
        """By default, only /tmp should be allowed without confirmation"""
        guard = PathGuard()

        # /tmp should be allowed
        result = guard.check("/tmp/test.txt", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

    def test_home_directory_requires_confirmation(self):
        """Home directory should require confirmation by default"""
        guard = PathGuard()

        result = guard.check("~/test.txt", Operation.WRITE)
        assert result.allowed is False
        assert result.requires_confirmation is True
        assert "requires confirmation" in result.reason.lower()

    def test_workspace_requires_confirmation_without_whitelist(self):
        """Random paths like /workspace require confirmation"""
        guard = PathGuard()

        result = guard.check("/workspace/file.py", Operation.WRITE)
        assert result.requires_confirmation is True
```

**Step 3: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_path_guard.py -v
```

Expected: `ModuleNotFoundError: No module named 'wolo.path_guard'`

**Step 4: Create minimal PathGuard implementation**

```python
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
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/path_safety/test_path_guard.py -v
```

Expected: All 3 tests PASS

**Step 6: Commit**

```bash
git add wolo/path_guard.py tests/path_safety/
git commit -m "feat: add PathGuard core module with whitelist-based path protection"
```

---

## Task 2: Create PathGuard Exception

**Files:**
- Create: `wolo/path_guard_exceptions.py`

**Step 1: Write the exception class**

```python
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
```

**Step 2: Write test for exception**

```python
# tests/path_safety/test_path_guard.py (add to existing file)

class TestPathConfirmationRequired:
    def test_exception_attributes(self):
        """Exception should store path and operation"""
        from wolo.path_guard_exceptions import PathConfirmationRequired

        exc = PathConfirmationRequired("/workspace/test.txt", "write")

        assert exc.path == "/workspace/test.txt"
        assert exc.operation == "write"
        assert "write" in str(exc)
        assert "/workspace/test.txt" in str(exc)
```

**Step 3: Run test**

```bash
pytest tests/path_safety/test_path_guard.py::TestPathConfirmationRequired -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add wolo/path_guard_exceptions.py tests/path_safety/test_path_guard.py
git commit -m "feat: add PathConfirmationRequired exception"
```

---

## Task 3: Add PathSafetyConfig to Config Module

**Files:**
- Modify: `wolo/config.py`

**Step 1: Write test for config loading**

```python
# tests/path_safety/test_config_integration.py
import pytest
from pathlib import Path
from wolo.config import PathSafetyConfig


class TestPathSafetyConfig:
    def test_default_values(self):
        """PathSafetyConfig should have sensible defaults"""
        config = PathSafetyConfig()

        assert config.allowed_write_paths == []
        assert config.max_confirmations_per_session == 10
        assert config.audit_denied is True
        assert config.audit_log_file == Path.home() / ".wolo" / "path_audit.log"

    def test_custom_values(self):
        """Should accept custom configuration values"""
        custom_path = Path("/custom/audit.log")
        config = PathSafetyConfig(
            allowed_write_paths=[Path("/workspace"), Path("/tmp")],
            max_confirmations_per_session=20,
            audit_denied=False,
            audit_log_file=custom_path
        )

        assert len(config.allowed_write_paths) == 2
        assert config.max_confirmations_per_session == 20
        assert config.audit_denied is False
        assert config.audit_log_file == custom_path
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/path_safety/test_config_integration.py -v
```

Expected: `ImportError: cannot import name 'PathSafetyConfig'`

**Step 3: Add PathSafetyConfig to config.py**

Add this after the `CompactionConfig` import section (around line 10-15):

```python
# wolo/config.py (add after existing imports)

@dataclass
class PathSafetyConfig:
    """Configuration for path safety protection.

    Attributes:
        allowed_write_paths: List of paths where write operations are allowed without confirmation
        max_confirmations_per_session: Maximum number of path confirmations per session
        audit_denied: Whether to audit denied operations
        audit_log_file: Path to audit log file
    """
    allowed_write_paths: list[Path] = field(default_factory=list)
    max_confirmations_per_session: int = 10
    audit_denied: bool = True
    audit_log_file: Path = field(
        default_factory=lambda: Path.home() / ".wolo" / "path_audit.log"
    )
```

**Step 4: Add PathSafetyConfig to Config dataclass**

In the `Config` dataclass (around line 50), add the field:

```python
# wolo/config.py (inside Config dataclass, after compaction field)

    # Path safety configuration
    path_safety: PathSafetyConfig = field(default_factory=PathSafetyConfig)
```

**Step 5: Run tests**

```bash
pytest tests/path_safety/test_config_integration.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add wolo/config.py tests/path_safety/test_config_integration.py
git commit -m "feat: add PathSafetyConfig to configuration module"
```

---

## Task 4: Load PathSafetyConfig in Config.from_env()

**Files:**
- Modify: `wolo/config.py` (Config.from_env method)

**Step 1: Write test for config loading from YAML**

```python
# tests/path_safety/test_config_integration.py (add to existing file)

import tempfile
import yaml

class TestPathSafetyConfigLoading:
    def test_load_from_yaml(self, tmp_path):
        """Should load path_safety section from config YAML"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "path_safety": {
                "allowed_write_paths": ["/workspace", "/var/tmp"],
                "max_confirmations_per_session": 15,
                "audit_denied": False
            }
        }
        config_file.write_text(yaml.dump(config_data))

        # Mock Config._load_config_file to use our test config
        from wolo import config
        original_load = config.Config._load_config_file
        config.Config._load_config_file = lambda: config_data

        try:
            loaded_config = Config.from_env()

            assert len(loaded_config.path_safety.allowed_write_paths) == 2
            assert any(p == Path("/workspace").resolve() for p in loaded_config.path_safety.allowed_write_paths)
            assert loaded_config.path_safety.max_confirmations_per_session == 15
            assert loaded_config.path_safety.audit_denied is False
        finally:
            config.Config._load_config_file = original_load

    def test_empty_config_uses_defaults(self, tmp_path):
        """Empty config should use default values"""
        # Mock to return empty dict
        from wolo import config
        original_load = config.Config._load_config_file
        config.Config._load_config_file = lambda: {}

        try:
            # Need to provide minimal required params
            loaded_config = Config.from_env(
                api_key="test_key",
                base_url="https://test.com",
                model="test_model"
            )

            assert loaded_config.path_safety.allowed_write_paths == []
            assert loaded_config.path_safety.max_confirmations_per_session == 10
            assert loaded_config.path_safety.audit_denied is True
        finally:
            config.Config._load_config_file = original_load
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_config_integration.py::TestPathSafetyConfigLoading -v
```

Expected: Tests fail because PathSafetyConfig is not being loaded

**Step 3: Update Config.from_env() to load path_safety config**

Find the section in `Config.from_env()` where other config sections are loaded (around line 230-240 in direct mode, and line 340-350 in config file mode). Add the path_safety loading:

```python
# wolo/config.py - in Config.from_env() method

# Find where compaction_config is loaded and add after it:

        # Load compaction config
        from wolo.compaction.config import load_compaction_config

        compaction_data = config_data.get("compaction", {})
        compaction_config = load_compaction_config(compaction_data)

        # Load path safety configuration
        path_safety_data = config_data.get("path_safety", {})
        path_safety_config = PathSafetyConfig(
            allowed_write_paths=[
                Path(p).expanduser().resolve()
                for p in path_safety_data.get("allowed_write_paths", [])
            ],
            max_confirmations_per_session=path_safety_data.get("max_confirmations_per_session", 10),
            audit_denied=path_safety_data.get("audit_denied", True),
        )

        return cls(
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=0.7,
            max_tokens=16384,
            mcp_servers=mcp_servers,
            enable_think=enable_think,
            claude=claude_config,
            mcp=mcp_config,
            compaction=compaction_config,
            path_safety=path_safety_config,  # Add this
        )
```

You need to add this in BOTH places where `Config` is returned (direct mode and config file mode).

**Step 4: Run tests**

```bash
pytest tests/path_safety/test_config_integration.py::TestPathSafetyConfigLoading -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add wolo/config.py tests/path_safety/test_config_integration.py
git commit -m "feat: load path_safety configuration from config file"
```

---

## Task 5: Update Config Schema

**Files:**
- Modify: `wolo/config_schema.py`

**Step 1: Write test for schema generation**

```python
# tests/path_safety/test_config_schema.py
from wolo.config_schema import get_config_schema
from wolo.config import PathSafetyConfig


class TestPathSafetySchema:
    def test_schema_includes_path_safety(self):
        """Config schema should include path_safety section"""
        from wolo.config import Config

        schema = get_config_schema(Config)

        assert "path_safety" in schema["properties"]
        path_safety_schema = schema["properties"]["path_safety"]

        assert path_safety_schema["type"] == "object"
        assert "allowed_write_paths" in path_safety_schema["properties"]
        assert "max_confirmations_per_session" in path_safety_schema["properties"]
        assert "audit_denied" in path_safety_schema["properties"]

    def test_allowed_write_paths_is_array(self):
        """allowed_write_paths should be an array type"""
        from wolo.config import Config

        schema = get_config_schema(Config)
        allowed_paths = schema["properties"]["path_safety"]["properties"]["allowed_write_paths"]

        assert allowed_paths["type"] == "array"
```

**Step 2: Run tests to verify they pass**

```bash
pytest tests/path_safety/test_config_schema.py -v
```

Expected: Tests should already pass (schema generation is automatic for dataclasses)

**Step 3: Verify schema documentation generates correctly**

```bash
python -c "from wolo.config import Config; from wolo.config_schema import generate_config_docs; print(generate_config_docs(Config))"
```

Expected: Output includes `path_safety` section

**Step 4: Commit**

```bash
git add tests/path_safety/test_config_schema.py
git commit -m "test: add config schema tests for path_safety"
```

---

## Task 6: Add CLI Argument --allow-path

**Files:**
- Modify: `wolo/cli/parser.py`

**Step 1: Write test for CLI argument parsing**

```python
# tests/path_safety/test_cli_integration.py
import pytest
from wolo.cli.parser import create_parser


class TestAllowPathArgument:
    def test_single_allow_path(self):
        """Should parse single --allow-path argument"""
        parser = create_parser()
        args = parser.parse_args(["--allow-path", "/workspace", "test prompt"])

        assert args.allowed_paths == ["/workspace"]

    def test_multiple_allow_paths(self):
        """Should parse multiple --allow-path arguments"""
        parser = create_parser()
        args = parser.parse_args([
            "--allow-path", "/workspace",
            "--allow-path", "/var/tmp",
            "test prompt"
        ])

        assert len(args.allowed_paths) == 2
        assert "/workspace" in args.allowed_paths
        assert "/var/tmp" in args.allowed_paths

    def test_short_form(self):
        """Should parse -P short form"""
        parser = create_parser()
        args = parser.parse_args(["-P", "/tmp", "test prompt"])

        assert args.allowed_paths == ["/tmp"]

    def test_no_allow_path_default(self):
        """Should default to empty list when not provided"""
        parser = create_parser()
        args = parser.parse_args(["test prompt"])

        assert args.allowed_paths == []
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_cli_integration.py::TestAllowPathArgument -v
```

Expected: Tests fail because `allowed_paths` attribute doesn't exist

**Step 3: Add --allow-path argument to parser**

In `wolo/cli/parser.py`, find the argument definitions and add:

```python
# wolo/cli/parser.py (add with other arguments)

    parser.add_argument(
        "-P", "--allow-path",
        dest="allowed_paths",
        action="append",
        default=[],
        metavar="PATH",
        help="Add a path to the write allowlist (can be used multiple times)"
    )
```

**Step 4: Run tests**

```bash
pytest tests/path_safety/test_cli_integration.py::TestAllowPathArgument -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add wolo/cli/parser.py tests/path_safety/test_cli_integration.py
git commit -m "feat: add --allow-path CLI argument"
```

---

## Task 7: Initialize PathGuard in CLI Main

**Files:**
- Modify: `wolo/cli/main.py`

**Step 1: Write test for PathGuard initialization**

```python
# tests/path_safety/test_cli_integration.py (add to existing file)

from unittest.mock import patch, MagicMock
from pathlib import Path


class TestPathGuardInitialization:
    def test_initializes_with_config_paths(self):
        """PathGuard should be initialized with config paths"""
        from wolo.config import Config, PathSafetyConfig
        from wolo.cli.main import _initialize_path_guard

        config = Config(
            api_key="test",
            model="test",
            base_url="https://test.com",
            path_safety=PathSafetyConfig(
                allowed_write_paths=[Path("/workspace")]
            )
        )

        with patch('wolo.cli.main.set_path_guard') as mock_set:
            _initialize_path_guard(config, [])

            mock_set.assert_called_once()
            guard = mock_set.call_args[0][0]
            assert isinstance(guard, type(PathGuard()))  # Is a PathGuard instance

    def test_initializes_with_cli_paths(self):
        """PathGuard should include CLI-provided paths"""
        from wolo.config import Config
        from wolo.cli.main import _initialize_path_guard

        config = Config(
            api_key="test",
            model="test",
            base_url="https://test.com"
        )

        with patch('wolo.cli.main.set_path_guard') as mock_set:
            _initialize_path_guard(config, ["/workspace", "/var/tmp"])

            mock_set.assert_called_once()
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_cli_integration.py::TestPathGuardInitialization -v
```

Expected: `AttributeError: module 'wolo.cli.main' has no attribute '_initialize_path_guard'`

**Step 3: Add _initialize_path_guard function**

```python
# wolo/cli/main.py (add near other initialization functions)

def _initialize_path_guard(config: Config, cli_paths: list[str]) -> None:
    """Initialize PathGuard with config and CLI-provided paths.

    Args:
        config: Configuration object containing path_safety settings
        cli_paths: List of paths provided via --allow-path CLI argument
    """
    from wolo.path_guard import PathGuard, set_path_guard

    config_paths = config.path_safety.allowed_write_paths
    cli_path_objects = [Path(p).resolve() for p in cli_paths]

    guard = PathGuard(
        config_paths=config_paths,
        cli_paths=cli_path_objects,
    )
    set_path_guard(guard)
```

**Step 4: Call _initialize_path_guard in execution paths**

Find where execution starts and add the call. In `wolo/cli/main.py`, find the route_command or main execution flow and add:

```python
# wolo/cli/main.py (in the main execution flow, after config is loaded)

# Initialize PathGuard before running tasks
_initialize_path_guard(config, args.allowed_paths)
```

**Step 5: Run tests**

```bash
pytest tests/path_safety/test_cli_integration.py::TestPathGuardInitialization -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add wolo/cli/main.py tests/path_safety/test_cli_integration.py
git commit -m "feat: initialize PathGuard with config and CLI paths"
```

---

## Task 8: Add Path Confirmation Interaction to CLI

**Files:**
- Modify: `wolo/cli/execution.py`

**Step 1: Write test for confirmation handling**

```python
# tests/path_safety/test_cli_interaction.py
import pytest
from unittest.mock import patch, MagicMock
from wolo.cli.execution import handle_path_confirmation


class TestPathConfirmation:
    @patch('sys.stdin.isatty', return_value=True)
    @patch('wolo.cli.execution.Console.input', return_value='y')
    def test_confirm_allows_operation(self, mock_input, mock_isatty):
        """User confirming 'y' should allow the operation"""
        result = handle_path_confirmation("/workspace/file.py", "write")
        assert result is True

    @patch('sys.stdin.isatty', return_value=True)
    @patch('wolo.cli.execution.Console.input', return_value='n')
    def test_deny_refuses_operation(self, mock_input, mock_isatty):
        """User entering 'n' should refuse the operation"""
        result = handle_path_confirmation("/etc/passwd", "write")
        assert result is False

    @patch('sys.stdin.isatty', return_value=False)
    def test_non_interactive_refuses(self, mock_isatty):
        """Non-interactive mode should refuse without prompting"""
        result = handle_path_confirmation("/workspace/file.py", "write")
        assert result is False

    @patch('sys.stdin.isatty', return_value=True)
    @patch('wolo.cli.execution.Console.input', return_value='a')
    def test_confirm_allows_directory(self, mock_input, mock_isatty):
        """Confirming with 'a' should allow the entire directory"""
        result = handle_path_confirmation("/workspace/project/file.py", "write")
        assert result is True
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_cli_interaction.py -v
```

Expected: `ImportError: cannot import name 'handle_path_confirmation'`

**Step 3: Implement handle_path_confirmation function**

```python
# wolo/cli/execution.py (add to file)

import sys
from pathlib import Path
from rich.console import Console


class SessionCancelled(Exception):
    """Raised when user cancels the session during confirmation."""
    pass


async def handle_path_confirmation(path: str, operation: str) -> bool:
    """Handle path confirmation prompt for user.

    Args:
        path: The path requiring confirmation
        operation: The operation type (write/delete/etc)

    Returns:
        True if user allowed the operation, False if denied

    Raises:
        SessionCancelled: If user enters 'q' to quit
    """
    from wolo.path_guard import get_path_guard

    console = Console()
    console.print(f"\n⚠️  [yellow]Path Confirmation Required[/yellow]")
    console.print(f"Operation: [cyan]{operation}[/cyan]")
    console.print(f"Path: [cyan]{path}[/cyan]")
    console.print("This path is not in the default allowlist (/tmp) or configured whitelist.")

    if not sys.stdin.isatty():
        console.print("[dim]Non-interactive mode, operation denied.[/dim]")
        console.print("Tip: Configure path_safety.allowed_write_paths in ~/.wolo/config.yaml")
        return False

    while True:
        response = console.input("\n[yellow]Allow this operation?[/yellow] [Y/n/a/q] ").strip().lower()

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
            console.print(f"[green]✓[/green] {parent} and subdirectories added to session whitelist")
            return True
        elif response == "q":
            console.print("[red]Session cancelled[/red]")
            raise SessionCancelled()
        else:
            console.print("[dim]Please enter Y/n/a/q[/dim]")
```

**Step 4: Run tests**

```bash
pytest tests/path_safety/test_cli_interaction.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add wolo/cli/execution.py tests/path_safety/test_cli_interaction.py
git commit -m "feat: add path confirmation interaction handler"
```

---

## Task 9: Integrate PathGuard into write_execute Tool

**Files:**
- Modify: `wolo/tools.py`

**Step 1: Write test for write_execute integration**

```python
# tests/path_safety/test_tool_integration.py
import pytest
from pathlib import Path
from wolo.tools import write_execute
from wolo.path_guard import PathGuard, set_path_guard, Operation
from wolo.path_guard_exceptions import PathConfirmationRequired


class TestWriteExecuteIntegration:
    def test_allows_tmp_without_confirmation(self):
        """Writing to /tmp should be allowed without confirmation"""
        guard = PathGuard()
        set_path_guard(guard)

        import asyncio
        result = asyncio.run(write_execute("/tmp/test.txt", "content"))

        assert "Error" not in result["output"]
        assert "Permission denied" not in result["output"]

    def test_raises_confirmation_for_workspace(self):
        """Writing to /workspace should raise PathConfirmationRequired"""
        guard = PathGuard()
        set_path_guard(guard)

        import asyncio
        with pytest.raises(PathConfirmationRequired) as exc_info:
            asyncio.run(write_execute("/workspace/test.txt", "content"))

        assert exc_info.value.path == "/workspace/test.txt"
        assert exc_info.value.operation == "write"

    def test_allows_whitelisted_path(self):
        """Writing to whitelisted path should be allowed"""
        guard = PathGuard(config_paths=[Path("/workspace")])
        set_path_guard(guard)

        import asyncio
        result = asyncio.run(write_execute("/workspace/test.txt", "content"))

        assert "Permission denied" not in result["output"]
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_tool_integration.py -v
```

Expected: Tests fail because write_execute doesn't check PathGuard

**Step 3: Modify write_execute to check PathGuard**

In `wolo/tools.py`, find `write_execute` function and add the guard check at the beginning:

```python
# wolo/tools.py (modify write_execute function)

async def write_execute(file_path: str, content: str) -> dict[str, Any]:
    """Write content to a file with path safety check."""
    from wolo.path_guard import get_path_guard, Operation
    from wolo.path_guard_exceptions import PathConfirmationRequired

    guard = get_path_guard()
    result = guard.check(file_path, Operation.WRITE)

    if result.requires_confirmation:
        raise PathConfirmationRequired(file_path, "write")

    if not result.allowed:
        return {
            "title": f"write: {file_path}",
            "output": f"Permission denied: {result.reason}",
            "metadata": {"error": "path_not_allowed"}
        }

    # Continue with existing write logic...
    # (rest of the function remains unchanged)
```

**Step 4: Run tests**

```bash
pytest tests/path_safety/test_tool_integration.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add wolo/tools.py tests/path_safety/test_tool_integration.py
git commit -m "feat: integrate PathGuard into write_execute tool"
```

---

## Task 10: Handle PathConfirmationRequired in execute_tool

**Files:**
- Modify: `wolo/tools.py` (execute_tool function)

**Step 1: Write test for execute_tool confirmation handling**

```python
# tests/path_safety/test_tool_integration.py (add to existing file)

class TestExecuteToolConfirmation:
    @pytest.mark.asyncio
    async def test_handles_confirmation_required(self):
        """execute_tool should handle PathConfirmationRequired"""
        from wolo.tools import ToolPart
        from wolo.path_guard_exceptions import PathConfirmationRequired
        from unittest.mock import patch, AsyncMock

        tool_part = ToolPart(tool="write", input={"file_path": "/workspace/test.txt", "content": "test"})

        # Mock handle_path_confirmation to return True (user allowed)
        with patch('wolo.tools.handle_path_confirmation', return_value=True):
            with patch('wolo.tools.write_execute', new_callable=AsyncMock) as mock_write:
                mock_write.return_value = {"title": "write: /workspace/test.txt", "output": "Success"}

                # This should not raise an exception
                await execute_tool(tool_part)

                assert tool_part.status != "error"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/path_safety/test_tool_integration.py::TestExecuteToolConfirmation -v
```

Expected: Test fails because execute_tool doesn't handle the exception

**Step 3: Modify execute_tool to catch PathConfirmationRequired**

In `wolo/tools.py`, find the `execute_tool` function and add exception handling for write/edit tools:

```python
# wolo/tools.py (in execute_tool function)

async def execute_tool(
    tool_part: ToolPart, agent_config: Any = None, session_id: str = None, config: Any = None
) -> None:
    """Execute a tool call and update the part with results."""
    from wolo.path_guard_exceptions import PathConfirmationRequired

    # ... existing permission check code ...

    # For write and edit tools, handle PathConfirmationRequired
    if tool_part.tool in ("write", "edit", "multiedit"):
        try:
            # Proceed with tool execution
            if tool_part.tool == "write":
                result = await write_execute(**tool_part.input)
            # ... other tools ...
        except PathConfirmationRequired as e:
            # Import here to avoid circular dependency
            from wolo.cli.execution import handle_path_confirmation

            try:
                allowed = await handle_path_confirmation(e.path, e.operation)
                if allowed:
                    # Retry after confirmation
                    if tool_part.tool == "write":
                        result = await write_execute(**tool_part.input)
                    # ... re-execute the tool ...
                else:
                    tool_part.status = "error"
                    tool_part.output = f"Permission denied by user: {e.path}"
                    return
            except Exception as cancel_error:
                if "SessionCancelled" in type(cancel_error).__name__:
                    raise
                tool_part.status = "error"
                tool_part.output = f"Operation cancelled: {cancel_error}"
                return

    # ... rest of existing code ...
```

**Note:** The exact placement depends on the current structure of execute_tool. The key is to catch `PathConfirmationRequired` for write operations and call `handle_path_confirmation`.

**Step 4: Run tests**

```bash
pytest tests/path_safety/test_tool_integration.py::TestExecuteToolConfirmation -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add wolo/tools.py tests/path_safety/test_tool_integration.py
git commit -m "feat: handle PathConfirmationRequired in execute_tool"
```

---

## Task 11: Add Session Persistence for Path Confirmations

**Files:**
- Modify: `wolo/session.py`

**Step 1: Write test for session persistence**

```python
# tests/path_safety/test_session_persistence.py
import pytest
import json
from pathlib import Path
from datetime import datetime
from wolo.session import save_path_confirmations, load_path_confirmations


class TestPathConfirmationPersistence:
    def test_save_and_load(self, tmp_path, monkeypatch):
        """Should save and load path confirmations"""
        # Create mock session directory
        session_dir = tmp_path / "sessions" / "test_session"
        session_dir.mkdir(parents=True)

        # Mock get_session_dir
        import wolo.session
        monkeypatch.setattr(wolo.session, "get_session_dir", lambda sid: session_dir)

        confirmed_dirs = [Path("/workspace"), Path("/tmp/project")]

        save_path_confirmations("test_session", confirmed_dirs)

        # Verify file was created
        confirmation_file = session_dir / "path_confirmations.json"
        assert confirmation_file.exists()

        # Load and verify
        loaded = load_path_confirmations("test_session")
        assert len(loaded) == 2
        assert any(p == Path("/workspace").resolve() for p in loaded)
        assert any(p == Path("/tmp/project").resolve() for p in loaded)

    def test_file_format(self, tmp_path, monkeypatch):
        """Saved file should have correct format"""
        session_dir = tmp_path / "sessions" / "format_test"
        session_dir.mkdir(parents=True)

        import wolo.session
        monkeypatch.setattr(wolo.session, "get_session_dir", lambda sid: session_dir)

        save_path_confirmations("format_test", [Path("/workspace")])

        confirmation_file = session_dir / "path_confirmations.json"
        data = json.loads(confirmation_file.read_text())

        assert "confirmed_dirs" in data
        assert "confirmation_count" in data
        assert "last_updated" in data
        assert data["confirmation_count"] == 1

    def test_load_nonexistent_returns_empty(self, tmp_path, monkeypatch):
        """Loading non-existent confirmation file should return empty list"""
        session_dir = tmp_path / "sessions" / "nonexistent"
        session_dir.mkdir(parents=True)

        import wolo.session
        monkeypatch.setattr(wolo.session, "get_session_dir", lambda sid: session_dir)

        loaded = load_path_confirmations("nonexistent")
        assert loaded == []
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/path_safety/test_session_persistence.py -v
```

Expected: `AttributeError: module 'wolo.session' has no attribute 'save_path_confirmations'`

**Step 3: Add persistence functions to session.py**

```python
# wolo/session.py (add to file, after existing imports and constants)

def get_session_dir(session_id: str) -> Path:
    """Get the directory for a session."""
    return Path.home() / ".wolo" / "sessions" / session_id


def save_path_confirmations(session_id: str, confirmed_dirs: list[Path]) -> None:
    """Save confirmed paths to session storage.

    Args:
        session_id: The session identifier
        confirmed_dirs: List of confirmed directory paths
    """
    confirmation_file = get_session_dir(session_id) / "path_confirmations.json"

    data = {
        "confirmed_dirs": [str(p) for p in confirmed_dirs],
        "confirmation_count": len(confirmed_dirs),
        "last_updated": datetime.now().isoformat(),
    }

    with open(confirmation_file, "w") as f:
        json.dump(data, f, indent=2)


def load_path_confirmations(session_id: str) -> list[Path]:
    """Load confirmed paths from session storage.

    Args:
        session_id: The session identifier

    Returns:
        List of confirmed directory paths (empty if file doesn't exist)
    """
    confirmation_file = get_session_dir(session_id) / "path_confirmations.json"

    if not confirmation_file.exists():
        return []

    with open(confirmation_file) as f:
        data = json.load(f)

    return [Path(p) for p in data.get("confirmed_dirs", [])]
```

**Step 4: Run tests**

```bash
pytest tests/path_safety/test_session_persistence.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add wolo/session.py tests/path_safety/test_session_persistence.py
git commit -m "feat: add session persistence for path confirmations"
```

---

## Task 12: Load Path Confirmations on Session Resume

**Files:**
- Modify: `wolo/session.py` (or wherever session resume happens)

**Step 1: Write test for resume loading confirmations**

```python
# tests/path_safety/test_session_persistence.py (add to existing file)

class TestSessionResumeWithConfirmations:
    def test_resume_loads_confirmations_to_pathguard(self, tmp_path, monkeypatch):
        """Resuming a session should load confirmations into PathGuard"""
        from wolo.path_guard import PathGuard, set_path_guard, reset_path_guard
        import wolo.session

        # Setup mock session directory
        session_dir = tmp_path / "sessions" / "resume_test"
        session_dir.mkdir(parents=True)
        monkeypatch.setattr(wolo.session, "get_session_dir", lambda sid: session_dir)

        # Create confirmation file
        wolo.session.save_path_confirmations("resume_test", [Path("/workspace")])

        # Reset and load
        reset_path_guard()
        confirmed = wolo.session.load_path_confirmations("resume_test")

        # Create PathGuard with loaded confirmations
        guard = PathGuard(session_confirmed=confirmed)
        set_path_guard(guard)

        # Verify paths are allowed
        from wolo.path_guard import Operation
        result = guard.check("/workspace/file.py", Operation.WRITE)

        assert result.allowed is True
        assert result.requires_confirmation is False
```

**Step 2: Run test**

```bash
pytest tests/path_safety/test_session_persistence.py::TestSessionResumeWithConfirmations -v
```

Expected: PASS

**Step 3: Find session resume code and add PathGuard initialization**

Look for the session resume/initialization code in `wolo/session.py` or `wolo/cli/execution.py`. Add code to load confirmations when resuming:

```python
# In session resume logic (location depends on current code structure)

from wolo.session import load_path_confirmations
from wolo.path_guard import PathGuard, set_path_guard

# When resuming a session:
confirmed_dirs = load_path_confirmations(session_id)
if confirmed_dirs:
    guard = PathGuard(session_confirmed=confirmed_dirs)
    set_path_guard(guard)
```

**Step 4: Run tests**

```bash
pytest tests/path_safety/test_session_persistence.py -v
```

Expected: All tests pass

**Step 5: Commit**

```bash
git add tests/path_safety/test_session_persistence.py
git commit -m "feat: load path confirmations on session resume"
```

---

## Task 13: Save Confirmations on Session Exit

**Files:**
- Modify: `wolo/session.py` or `wolo/cli/execution.py`

**Step 1: Write test for saving confirmations on exit**

```python
# tests/path_safety/test_session_persistence.py (add to existing file)

class TestSaveConfirmationsOnExit:
    def test_saves_on_session_save(self, tmp_path, monkeypatch):
        """Saving session should also save path confirmations"""
        from wolo.path_guard import PathGuard, reset_path_guard
        import wolo.session

        session_dir = tmp_path / "sessions" / "save_test"
        session_dir.mkdir(parents=True)
        monkeypatch.setattr(wolo.session, "get_session_dir", lambda sid: session_dir)

        # Create PathGuard with confirmed directory
        reset_path_guard()
        guard = PathGuard()
        guard.confirm_directory("/workspace")
        set_path_guard(guard)

        # Save confirmations
        from wolo.path_guard import get_path_guard
        confirmed = get_path_guard().get_confirmed_dirs()
        wolo.session.save_path_confirmations("save_test", confirmed)

        # Verify file exists
        confirmation_file = session_dir / "path_confirmations.json"
        assert confirmation_file.exists()

        data = json.loads(confirmation_file.read_text())
        assert len(data["confirmed_dirs"]) == 1
```

**Step 2: Run test**

```bash
pytest tests/path_safety/test_session_persistence.py::TestSaveConfirmationsOnExit -v
```

Expected: PASS

**Step 3: Add save call to session save logic**

Find where `save_session()` is called and add path confirmation saving:

```python
# In session save logic (wolo/session.py or wolo/cli/execution.py)

def save_session_with_confirmations(session_id: str) -> None:
    """Save session including path confirmations."""
    from wolo.path_guard import get_path_guard

    # Save existing session data
    save_session(session_id)

    # Save path confirmations
    guard = get_path_guard()
    confirmed = guard.get_confirmed_dirs()
    if confirmed:
        save_path_confirmations(session_id, confirmed)
```

**Step 4: Run all tests**

```bash
pytest tests/path_safety/ -v
```

Expected: All tests pass

**Step 5: Commit**

```bash
git add wolo/session.py tests/path_safety/test_session_persistence.py
git commit -m "feat: save path confirmations on session save"
```

---

## Task 14: Add Documentation

**Files:**
- Create: `docs/PATH_SAFETY.md`

**Step 1: Write documentation**

```markdown
# Path Safety - PathGuard Documentation

## Overview

PathGuard is a whitelist-based path protection system for file write operations in wolo. It prevents accidental writes to unintended locations by requiring user confirmation for paths outside the configured allowlist.

## Default Behavior

- **Allowed without confirmation**: Only `/tmp`
- **Requires confirmation**: All other paths (including home directory `~`)
- **Confirmation persists**: Confirmed directories are remembered for the session

## Configuration

### Config File

Add to `~/.wolo/config.yaml`:

```yaml
path_safety:
  # Paths where write operations are allowed without confirmation
  allowed_write_paths:
    - /workspace
    - /var/tmp
    - /home/user/projects

  # Maximum number of confirmations per session (prevents confirmation fatigue)
  max_confirmations_per_session: 10

  # Enable audit logging for denied operations
  audit_denied: true

  # Audit log file location
  audit_log_file: ~/.wolo/path_audit.log
```

### Command Line

```bash
# Add a single path to allowlist
wolo --allow-path /workspace "create a file"

# Add multiple paths
wolo -P /workspace -P /var/tmp "run task"
```

## User Interaction

When a write operation requires confirmation:

```
⚠️  Path Confirmation Required
Operation: write
Path: /workspace/project/file.py
This path is not in the default allowlist (/tmp) or configured whitelist.

Allow this operation? [Y/n/a/q]
```

**Options:**
- `Y` or `y` - Allow this specific operation
- `n` - Deny this operation
- `a` - Allow entire directory (and subdirectories)
- `q` - Cancel the entire session

## Session Persistence

Confirmed directories are saved to `~/.wolo/sessions/<session_id>/path_confirmations.json`. When you resume a session, previously confirmed directories remain allowed.

## Examples

### Example 1: First Time Writing to Workspace

```bash
$ wolo "create a file in /workspace/test.txt"

⚠️  Path Confirmation Required
Operation: write
Path: /workspace/test.txt
This path is not in the default allowlist (/tmp) or configured whitelist.

Allow this operation? [Y/n/a/q] a
✓ /workspace and subdirectories added to session whitelist
```

### Example 2: Using Config File Whitelist

```yaml
# ~/.wolo/config.yaml
path_safety:
  allowed_write_paths:
    - /workspace
    - /home/user/myproject
```

```bash
$ wolo "write to /workspace/file.py"
# No confirmation needed - /workspace is in whitelist
```

### Example 3: Temporary Whitelist via CLI

```bash
$ wolo -P /tmp/work -P /var/cache "process files"
# /tmp/work and /var/cache are allowed for this session only
```

## Security Model

PathGuard uses a **whitelist-only approach**:

1. **Default allowlist**: Only `/tmp`
2. **Config file**: Additional paths from `path_safety.allowed_write_paths`
3. **CLI arguments**: Paths from `--allow-path` / `-P`
4. **Session confirmations**: Directories confirmed during the session

All paths are **normalized** (resolving symlinks and relative paths) before checking.

## Troubleshooting

### "Permission denied" when writing to home directory

This is expected behavior. Either:
1. Confirm the directory when prompted
2. Add to config file whitelist
3. Use `--allow-path ~/specific/path`

### Non-interactive mode denial

In scripts or non-interactive terminals, operations are auto-denied. Pre-configure allowlist in config file.

### Session confirmations lost

Confirmations are saved per session. Use `-r <session_id>` to resume and keep confirmations.
```

**Step 2: Commit documentation**

```bash
git add docs/PATH_SAFETY.md
git commit -m "docs: add PathGuard documentation"
```

---

## Task 15: Run Full Test Suite

**Step 1: Run all PathGuard tests**

```bash
pytest tests/path_safety/ -v
```

Expected: All tests pass

**Step 2: Run related existing tests**

```bash
pytest tests/test_tools.py -v
pytest tests/test_config.py -v
pytest wolo/tests/ -v
```

Expected: No regressions

**Step 3: Fix any failures**

If tests fail, fix issues and commit.

**Step 4: Final commit**

```bash
git add .
git commit -m "test: ensure all tests pass for PathGuard feature"
```

---

## Verification Checklist

- [ ] `/tmp` writes work without confirmation
- [ ] Home directory writes require confirmation
- [ ] Config file whitelist works
- [ ] `--allow-path` CLI argument works
- [ ] Confirmations persist to session
- [ ] Session resume loads confirmations
- [ ] `write` tool checks PathGuard
- [ ] `edit` tool checks PathGuard (if implemented)
- [ ] Non-interactive mode denies gracefully
- [ ] All tests pass
- [ ] Documentation is complete

---

## Future Enhancements (Out of Scope)

- Shell command write detection (e.g., `echo "x" > /path`)
- Delete operation special handling
- Audit log implementation
- Per-agent path restrictions
- Path confirmation rate limiting

---

**End of Implementation Plan**
