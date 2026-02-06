"""Unit tests for wolo.exceptions module."""

from wolo.exceptions import (
    WoloConfigError,
    WoloError,
    WoloLLMError,
    WoloPathSafetyError,
    WoloSessionError,
    WoloToolError,
)


class TestWoloErrorBase:
    """Tests for the base WoloError class."""

    def test_wolo_error_base_with_session_id(self) -> None:
        """WoloError stores session_id and context."""
        error = WoloError(
            message="Something went wrong",
            session_id="test_session_123",
            code="TEST_ERROR",
            detail="Additional context",
        )

        assert str(error) == "Something went wrong"
        assert error.session_id == "test_session_123"
        assert error.context == {"code": "TEST_ERROR", "detail": "Additional context"}
        assert "test_session_123" in repr(error)
        assert "TEST_ERROR" in repr(error)

    def test_wolo_error_base_without_session_id(self) -> None:
        """WoloError works without session_id."""
        error = WoloError(
            message="Simple error",
        )

        assert str(error) == "Simple error"
        assert error.session_id is None
        assert error.context == {}

    def test_exception_catch_by_base_type(self) -> None:
        """All exceptions can be caught as WoloError."""
        errors: list[WoloError] = [
            WoloConfigError("Config error", session_id="sess1"),
            WoloToolError("Tool error", session_id="sess2"),
            WoloSessionError("Session error", session_id="sess3"),
            WoloLLMError("LLM error", session_id="sess4"),
            WoloPathSafetyError("Path safety error", session_id="sess5"),
        ]

        for error in errors:
            assert isinstance(error, WoloError)
            assert error.session_id is not None


class TestWoloConfigError:
    """Tests for WoloConfigError."""

    def test_wolo_config_error(self) -> None:
        """WoloConfigError is a WoloError."""
        error = WoloConfigError(
            "Invalid configuration",
            session_id="config_sess",
            config_key="api_key",
        )

        assert isinstance(error, WoloError)
        assert isinstance(error, WoloConfigError)
        assert str(error) == "Invalid configuration"
        assert error.session_id == "config_sess"
        assert error.context == {"config_key": "api_key"}


class TestWoloToolError:
    """Tests for WoloToolError."""

    def test_wolo_tool_error(self) -> None:
        """WoloToolError is a WoloError."""
        error = WoloToolError(
            "Tool execution failed",
            session_id="tool_sess",
            tool_name="read_file",
            original_error="File not found",
        )

        assert isinstance(error, WoloError)
        assert isinstance(error, WoloToolError)
        assert str(error) == "Tool execution failed"
        assert error.session_id == "tool_sess"
        assert error.context == {
            "tool_name": "read_file",
            "original_error": "File not found",
        }


class TestWoloSessionError:
    """Tests for WoloSessionError."""

    def test_wolo_session_error(self) -> None:
        """WoloSessionError is a WoloError."""
        error = WoloSessionError(
            "Session load failed",
            session_id="session_sess",
            session_path="/path/to/session",
        )

        assert isinstance(error, WoloError)
        assert isinstance(error, WoloSessionError)
        assert str(error) == "Session load failed"
        assert error.session_id == "session_sess"
        assert error.context == {"session_path": "/path/to/session"}


class TestWoloLLMError:
    """Tests for WoloLLMError."""

    def test_wolo_llm_error(self) -> None:
        """WoloLLMError is a WoloError."""
        error = WoloLLMError(
            "LLM API call failed",
            session_id="llm_sess",
            model="gpt-4",
            status_code=500,
        )

        assert isinstance(error, WoloError)
        assert isinstance(error, WoloLLMError)
        assert str(error) == "LLM API call failed"
        assert error.session_id == "llm_sess"
        assert error.context == {"model": "gpt-4", "status_code": 500}


class TestWoloPathSafetyError:
    """Tests for WoloPathSafetyError."""

    def test_wolo_path_safety_error(self) -> None:
        """WoloPathSafetyError is a WoloError."""
        error = WoloPathSafetyError(
            "Path validation failed",
            session_id="path_sess",
            path="/etc/passwd",
            reason="protected system path",
        )

        assert isinstance(error, WoloError)
        assert isinstance(error, WoloPathSafetyError)
        assert str(error) == "Path validation failed"
        assert error.session_id == "path_sess"
        assert error.context == {"path": "/etc/passwd", "reason": "protected system path"}
