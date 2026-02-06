"""Tests for CLI exception handling."""

from wolo.cli.main import _format_error_message
from wolo.exceptions import (
    WoloConfigError,
    WoloError,
    WoloLLMError,
    WoloPathSafetyError,
    WoloSessionError,
    WoloToolError,
)


def test_format_wolo_config_error():
    """WoloConfigError formatted with helpful message."""
    error = WoloConfigError("API key missing", session_id="sess123")
    message = _format_error_message(error)

    assert "configuration" in message.lower() or "config" in message.lower()
    assert "api key" in message.lower()


def test_format_wolo_tool_error():
    """WoloToolError formatted with tool name."""
    error = WoloToolError("Tool failed", session_id="sess456", tool_name="read")
    message = _format_error_message(error)

    assert "tool" in message.lower()
    assert "read" in message


def test_format_wolo_session_error():
    """WoloSessionError formatted with session info."""
    error = WoloSessionError("Session not found", session_id="sess789")
    message = _format_error_message(error)

    assert "session" in message.lower()
    assert "sess789" in message


def test_format_wolo_llm_error():
    """WoloLLMError formatted with LLM context."""
    error = WoloLLMError("API rate limit", session_id="sess000", model="gpt-4")
    message = _format_error_message(error)

    assert "llm" in message.lower() or "api" in message.lower()


def test_format_wolo_path_safety_error():
    """WoloPathSafetyError formatted with path info."""
    error = WoloPathSafetyError("Unsafe path", session_id="sess111", path="/etc/passwd")
    message = _format_error_message(error)

    assert "path" in message.lower()
    assert "/etc/passwd" in message


def test_format_generic_wolo_error():
    """Generic WoloError formatted without specific type."""
    error = WoloError("Generic error", session_id="sess222")
    message = _format_error_message(error)

    assert "generic error" in message.lower()


def test_format_error_without_session_id():
    """Error formatted without session_id."""
    error = WoloToolError("Tool failed", tool_name="write")
    message = _format_error_message(error)

    assert "tool" in message.lower()
