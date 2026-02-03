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
