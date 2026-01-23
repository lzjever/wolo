"""Tests for CLI argument parser."""

from wolo.cli.parser import FlexibleArgumentParser
from wolo.modes import ExecutionMode


def test_parse_simple_message():
    parser = FlexibleArgumentParser()
    args = parser.parse(["hello", "world"])
    assert args.message == "hello world"
    assert args.command_type == "default"


def test_parse_options_before_message():
    """Test --solo option parsing."""
    parser = FlexibleArgumentParser()
    args = parser.parse(["--solo", "message"])
    assert args.execution_options.mode == ExecutionMode.SOLO
    assert args.message == "message"


def test_parse_options_after_message():
    """Test --solo option after message."""
    parser = FlexibleArgumentParser()
    args = parser.parse(["message", "--solo"])
    assert args.execution_options.mode == ExecutionMode.SOLO
    assert args.message == "message"


def test_parse_coop_mode():
    """Test --coop option parsing."""
    parser = FlexibleArgumentParser()
    args = parser.parse(["--coop", "message"])
    assert args.execution_options.mode == ExecutionMode.COOP
    assert args.message == "message"


def test_parse_short_options():
    parser = FlexibleArgumentParser()
    args = parser.parse(["-s", "mytask", "message"])
    assert args.session_options.session_name == "mytask"
    assert args.message == "message"


def test_parse_equals_syntax():
    parser = FlexibleArgumentParser()
    args = parser.parse(["--agent=plan", "message"])
    assert args.execution_options.agent_type == "plan"
    assert args.message == "message"


def test_parse_separator():
    parser = FlexibleArgumentParser()
    args = parser.parse(["--solo", "--", "message", "with", "dashes"])
    assert args.execution_options.mode == ExecutionMode.SOLO
    assert args.message == "message with dashes"


def test_parse_subcommand():
    parser = FlexibleArgumentParser()
    args = parser.parse(["session", "list"])
    # Note: command_type and subcommand are set by router, not parser
    assert args.positional_args == ["session", "list"]


def test_default_mode_is_solo():
    """Test that default execution mode is SOLO."""
    parser = FlexibleArgumentParser()
    args = parser.parse(["message"])
    assert args.execution_options.mode == ExecutionMode.SOLO


def test_dual_input_cli_only():
    """Test that CLI-only input works."""
    parser = FlexibleArgumentParser()
    args = parser.parse(["my prompt"], check_stdin=False)
    assert args.message == "my prompt"
    assert args.cli_prompt == "my prompt"
    assert args.pipe_input is None


def test_parse_resume_option():
    """Test -r/--resume option parsing."""
    parser = FlexibleArgumentParser()
    args = parser.parse(["-r", "session_id", "message"])
    assert args.session_options.resume_id == "session_id"
    assert args.message == "message"


def test_parse_session_option():
    """Test -s/--session option parsing."""
    parser = FlexibleArgumentParser()
    args = parser.parse(["-s", "myproject", "message"])
    assert args.session_options.session_name == "myproject"
    assert args.message == "message"
