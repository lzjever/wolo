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

    def test_workdir_allows_all_paths_within_it(self):
        """Working directory should allow all paths within it without confirmation"""
        workdir = Path("/workspace/test_project")
        guard = PathGuard(workdir=workdir)

        # Paths within workdir should be allowed
        result = guard.check("/workspace/test_project/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        # Nested paths should be allowed
        result = guard.check("/workspace/test_project/src/module.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        # Paths outside workdir should require confirmation
        result = guard.check("/other/path/file.py", Operation.WRITE)
        assert result.requires_confirmation is True

    def test_workdir_has_highest_priority(self):
        """Working directory should have highest priority among whitelist sources"""
        workdir = Path("/custom/workdir")
        config_paths = [Path("/config/path")]
        cli_paths = [Path("/cli/path")]
        session_confirmed = [Path("/confirmed/path")]

        guard = PathGuard(
            config_paths=config_paths,
            cli_paths=cli_paths,
            session_confirmed=session_confirmed,
            workdir=workdir,
        )

        # Workdir paths should be allowed
        result = guard.check("/custom/workdir/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        # Other whitelist sources should still work
        result = guard.check("/config/path/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        result = guard.check("/cli/path/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        result = guard.check("/confirmed/path/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

        # Non-whitelisted paths require confirmation
        result = guard.check("/random/path/file.py", Operation.WRITE)
        assert result.requires_confirmation is True


class TestPathConfirmationRequired:
    def test_exception_attributes(self):
        """Exception should store path and operation"""
        from wolo.path_guard_exceptions import PathConfirmationRequired

        exc = PathConfirmationRequired("/workspace/test.txt", "write")

        assert exc.path == "/workspace/test.txt"
        assert exc.operation == "write"
        assert "write" in str(exc)
        assert "/workspace/test.txt" in str(exc)
