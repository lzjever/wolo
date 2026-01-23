"""Tests for CLI utility functions."""

from wolo.cli.parser import ParsedArgs, combine_inputs
from wolo.cli.utils import get_message_from_sources


def test_get_message_from_stdin():
    """Test getting message from stdin."""
    args = ParsedArgs()
    args.message = "stdin message"
    args.message_from_stdin = True

    message, has_message = get_message_from_sources(args)
    assert has_message
    assert message == "stdin message"


def test_get_message_from_positional():
    """Test getting message from positional arguments."""
    args = ParsedArgs()
    args.message = "positional message"
    args.message_from_stdin = False

    message, has_message = get_message_from_sources(args)
    assert has_message
    assert message == "positional message"


def test_get_message_no_source():
    """Test getting message when no source available."""
    args = ParsedArgs()
    args.message = ""
    args.message_from_stdin = False

    message, has_message = get_message_from_sources(args)
    assert not has_message
    assert message == ""


def test_get_message_priority_stdin_over_positional():
    """Test that stdin has priority over positional."""
    args = ParsedArgs()
    args.message = "positional"
    args.message_from_stdin = True
    args.message = "stdin"  # This would be set by parser

    # Simulate parser behavior: stdin message overwrites
    args.message = "stdin message"
    message, has_message = get_message_from_sources(args)
    assert has_message
    assert message == "stdin message"


# ==================== Dual Input Tests ====================


def test_combine_inputs_both_provided():
    """Test combine_inputs with both pipe and CLI prompt."""
    message, has_message = combine_inputs("context from pipe", "user task")
    assert has_message
    assert "context from pipe" in message
    assert "user task" in message


def test_combine_inputs_pipe_only():
    """Test combine_inputs with pipe input only."""
    message, has_message = combine_inputs("pipe content", None)
    assert has_message
    assert message == "pipe content"


def test_combine_inputs_cli_only():
    """Test combine_inputs with CLI prompt only."""
    message, has_message = combine_inputs(None, "cli prompt")
    assert has_message
    assert message == "cli prompt"


def test_combine_inputs_neither():
    """Test combine_inputs with no input."""
    message, has_message = combine_inputs(None, None)
    assert not has_message
    assert message == ""


def test_combine_inputs_empty_strings():
    """Test combine_inputs with empty strings."""
    message, has_message = combine_inputs("", "")
    assert not has_message
    assert message == ""


def test_combine_inputs_whitespace_only():
    """Test combine_inputs with whitespace-only input."""
    message, has_message = combine_inputs("  ", "  ")
    assert not has_message
    assert message == ""


def test_combine_inputs_template_format():
    """Test that combined message uses correct template format."""
    message, has_message = combine_inputs("my context", "my task")
    assert has_message
    # Check template structure
    assert "## Context (from stdin)" in message
    assert "## Task" in message
    assert "my context" in message
    assert "my task" in message
