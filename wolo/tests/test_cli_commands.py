"""Tests for CLI commands."""

from wolo.cli.commands.config import ConfigCommandGroup
from wolo.cli.commands.repl import ReplCommand
from wolo.cli.commands.run import RunCommand
from wolo.cli.commands.session import SessionCommandGroup
from wolo.cli.parser import ParsedArgs
from wolo.modes import ExecutionMode


def test_run_command_name():
    """Test RunCommand name property."""
    cmd = RunCommand()
    assert cmd.name == "run"


def test_run_command_description():
    """Test RunCommand description property."""
    cmd = RunCommand()
    assert "task" in cmd.description.lower()


def test_run_command_validate_missing_message():
    """Test RunCommand validation with missing message."""
    cmd = RunCommand()
    args = ParsedArgs()
    args.execution_options.mode = ExecutionMode.COOP
    args.message = ""
    args.message_from_stdin = False

    is_valid, error_msg = cmd.validate_args(args)
    assert not is_valid
    assert "prompt" in error_msg.lower() or "message" in error_msg.lower()


def test_run_command_validate_resume_without_message():
    """Test RunCommand validation with -r but no message."""
    cmd = RunCommand()
    args = ParsedArgs()
    args.session_options.resume_id = "test_session"
    args.message = ""
    args.message_from_stdin = False

    is_valid, error_msg = cmd.validate_args(args)
    assert not is_valid
    assert "-r" in error_msg or "--resume" in error_msg


def test_run_command_validate_watch_error():
    """Test RunCommand validation with -w (should error)."""
    cmd = RunCommand()
    args = ParsedArgs()
    args.session_options.watch_id = "test_session"

    is_valid, error_msg = cmd.validate_args(args)
    assert not is_valid
    assert "-w" in error_msg or "--watch" in error_msg


def test_repl_command_name():
    """Test ReplCommand name property."""
    cmd = ReplCommand()
    assert cmd.name == "repl"


def test_repl_command_validation():
    """Test ReplCommand validation (should always pass)."""
    cmd = ReplCommand()
    args = ParsedArgs()
    is_valid, error_msg = cmd.validate_args(args)
    assert is_valid


def test_session_command_group_name():
    """Test SessionCommandGroup name property."""
    cmd = SessionCommandGroup()
    assert cmd.name == "session"


def test_config_command_group_name():
    """Test ConfigCommandGroup name property."""
    cmd = ConfigCommandGroup()
    assert cmd.name == "config"


def test_run_command_validate_solo_mode():
    """Test RunCommand validation with SOLO mode."""
    cmd = RunCommand()
    args = ParsedArgs()
    args.execution_options.mode = ExecutionMode.SOLO
    args.message = "test"

    is_valid, error_msg = cmd.validate_args(args)
    assert is_valid


def test_run_command_validate_coop_mode():
    """Test RunCommand validation with COOP mode."""
    cmd = RunCommand()
    args = ParsedArgs()
    args.execution_options.mode = ExecutionMode.COOP
    args.message = "test"

    is_valid, error_msg = cmd.validate_args(args)
    assert is_valid
