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
        result = CheckResult.needs_confirmation(path, Operation.WRITE)
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
