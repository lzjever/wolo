"""Tests for CLI command routing."""

from wolo.cli.main import _route_command


def test_route_empty_args():
    """Test routing with empty arguments shows brief help."""
    command_type, remaining = _route_command([], False)
    assert command_type == "default_help"  # Changed: no args shows help
    assert remaining == []


def test_route_help():
    """Test routing help command."""
    command_type, remaining = _route_command(["--help"], False)
    assert command_type == "help"
    assert remaining == ["main"]


def test_route_quick_list():
    """Test routing quick list command."""
    command_type, remaining = _route_command(["-l"], False)
    assert command_type == "session_list"
    assert remaining == []


def test_route_quick_watch():
    """Test routing quick watch command."""
    command_type, remaining = _route_command(["-w", "session_id"], False)
    assert command_type == "session_watch"
    assert remaining == ["session_id"]


def test_route_watch_missing_id():
    """Test routing watch without ID."""
    command_type, remaining = _route_command(["-w"], False)
    assert command_type == "error"
    assert "watch requires" in remaining[0]


def test_route_subcommand_session():
    """Test routing session subcommand."""
    command_type, remaining = _route_command(["session", "list"], False)
    assert command_type == "session"
    assert remaining == ["list"]


def test_route_subcommand_config():
    """Test routing config subcommand."""
    command_type, remaining = _route_command(["config", "list-endpoints"], False)
    assert command_type == "config"
    assert remaining == ["list-endpoints"]


def test_route_subcommand_debug():
    """Test routing debug subcommand."""
    command_type, remaining = _route_command(["debug", "llm"], False)
    assert command_type == "debug"
    assert remaining == ["llm"]


def test_route_subcommand_run_deprecated():
    """Test routing run subcommand (deprecated, now routes to execute)."""
    command_type, remaining = _route_command(["run", "message"], False)
    assert command_type == "execute"  # Changed: run is deprecated
    assert remaining == ["message"]


def test_route_subcommand_repl():
    """Test routing repl subcommand."""
    command_type, remaining = _route_command(["repl"], False)
    assert command_type == "repl"
    assert remaining == []


def test_route_subcommand_chat():
    """Test routing chat subcommand (synonym for repl)."""
    command_type, remaining = _route_command(["chat"], False)
    assert command_type == "repl"  # chat routes to repl
    assert remaining == []


def test_route_default_execution():
    """Test routing default execution with a prompt."""
    command_type, remaining = _route_command(["message"], False)
    assert command_type == "execute"  # Changed: prompt routes to execute
    assert remaining == ["message"]


def test_route_with_stdin():
    """Test routing with stdin input."""
    # With stdin and no args, should route to execute
    command_type, remaining = _route_command([], True)
    assert command_type == "execute"
    assert remaining == []

    # With stdin and args (not help), should route to execute
    command_type, remaining = _route_command(["message"], True)
    assert command_type == "execute"
    assert remaining == ["message"]


def test_route_help_with_subcommand():
    """Test routing help with subcommand."""
    command_type, remaining = _route_command(["session", "--help"], False)
    assert command_type == "help"
    assert remaining == ["session"]


def test_route_chat_with_options():
    """Test routing chat with options."""
    command_type, remaining = _route_command(["chat", "--coop"], False)
    assert command_type == "repl"
    assert remaining == ["--coop"]


def test_route_multiple_args_with_options():
    """Test routing with multiple args and options."""
    command_type, remaining = _route_command(["--solo", "fix", "the", "bug"], False)
    assert command_type == "execute"
    assert remaining == ["--solo", "fix", "the", "bug"]
