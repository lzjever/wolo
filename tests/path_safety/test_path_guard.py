# tests/path_safety/test_path_guard.py

"""Tests for the new modular PathGuard API.

These tests verify the path checking functionality after the refactor.
The old monolithic PathGuard class has been replaced with:
- PathChecker: Core checking logic
- PathWhitelist: Whitelist management
- PathGuardConfig: Configuration
"""

from pathlib import Path

from wolo.path_guard import (
    Operation,
    PathChecker,
    PathGuardConfig,
    PathWhitelist,
)


class TestPathGuardBasics:
    def test_default_only_allows_tmp(self):
        """By default, only /tmp should be allowed without confirmation"""
        whitelist = PathWhitelist()
        checker = PathChecker(whitelist)

        # /tmp should be allowed
        result = checker.check("/tmp/test.txt", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

    def test_home_directory_requires_confirmation(self):
        """Home directory should require confirmation by default"""
        whitelist = PathWhitelist()
        checker = PathChecker(whitelist)

        result = checker.check("~/test.txt", Operation.WRITE)
        assert result.allowed is False
        assert result.requires_confirmation is True
        assert "requires confirmation" in result.reason.lower()

    def test_workspace_requires_confirmation_without_whitelist(self):
        """Random paths like /workspace require confirmation"""
        whitelist = PathWhitelist()
        checker = PathChecker(whitelist)

        result = checker.check("/workspace/file.py", Operation.WRITE)
        assert result.requires_confirmation is True

    def test_workdir_allows_all_paths_within_it(self):
        """Working directory should allow all paths within it without confirmation"""
        workdir = Path("/workspace/test_project")
        config = PathGuardConfig(workdir=workdir)
        whitelist = config.create_whitelist(confirmed_dirs=set())
        checker = PathChecker(whitelist)

        # Paths within workdir should be allowed
        result = checker.check("/workspace/test_project/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        # Nested paths should be allowed
        result = checker.check("/workspace/test_project/src/module.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        # Paths outside workdir should require confirmation
        result = checker.check("/other/path/file.py", Operation.WRITE)
        assert result.requires_confirmation is True

    def test_workdir_has_highest_priority(self):
        """Working directory should have highest priority among whitelist sources"""
        workdir = Path("/custom/workdir")
        config = PathGuardConfig(
            config_paths=[Path("/config/path")],
            cli_paths=[Path("/cli/path")],
            workdir=workdir,
        )
        whitelist = config.create_whitelist(confirmed_dirs=set([Path("/confirmed/path")]))
        checker = PathChecker(whitelist)

        # Workdir paths should be allowed
        result = checker.check("/custom/workdir/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        # Other whitelist sources should still work
        result = checker.check("/config/path/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        result = checker.check("/cli/path/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        result = checker.check("/confirmed/path/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        # Non-whitelisted paths require confirmation
        result = checker.check("/random/path/file.py", Operation.WRITE)
        assert result.requires_confirmation is True


class TestPathConfirmationRequired:
    def test_exception_attributes(self):
        """Exception should store path and operation"""
        from wolo.path_guard import PathConfirmationRequired

        exc = PathConfirmationRequired("/workspace/test.txt", "write")

        assert exc.path == "/workspace/test.txt"
        assert exc.operation == "write"
        assert "write" in str(exc)
        assert "/workspace/test.txt" in str(exc)


class TestPathGuardExecutor:
    def test_middleware_initialization(self):
        """Test that the middleware can be initialized properly"""
        from wolo.tools_pkg.path_guard_executor import initialize_path_guard_middleware

        # Initialize middleware
        initialize_path_guard_middleware(
            config_paths=[],
            cli_paths=[],
            workdir=None,
            confirmed_dirs=[],
        )

        # Verify we can get the middleware
        from wolo.tools_pkg.path_guard_executor import get_path_guard_middleware

        middleware = get_path_guard_middleware()
        assert middleware is not None

    def test_get_confirmed_dirs(self):
        """Test getting confirmed directories"""
        from wolo.tools_pkg.path_guard_executor import (
            get_confirmed_dirs,
            initialize_path_guard_middleware,
        )

        # Initialize middleware
        initialize_path_guard_middleware(
            config_paths=[],
            cli_paths=[],
            workdir=None,
            confirmed_dirs=[],
        )

        # Get confirmed dirs (should be empty initially)
        confirmed = get_confirmed_dirs()
        assert confirmed == []
