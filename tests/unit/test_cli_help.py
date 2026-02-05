"""Tests for cli/help.py - Help system for Wolo CLI."""

from unittest.mock import MagicMock

from wolo.cli.exit_codes import ExitCode
from wolo.cli.help import show_command_help, show_help, show_main_help, show_subcommand_help


class TestShowHelp:
    """Tests for show_help function."""

    def test_main_help_with_no_args(self, capsys):
        """Test that show_help shows main help when no args provided."""
        args = MagicMock()
        args.positional_args = []

        result = show_help(args)

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        assert "Wolo - AI Agent CLI" in captured.out
        assert "USAGE:" in captured.out

    def test_main_help_with_main_context(self, capsys):
        """Test that show_help shows main help with 'main' context."""
        args = MagicMock()
        args.positional_args = ["main"]

        result = show_help(args)

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        assert "Wolo - AI Agent CLI" in captured.out

    def test_session_help(self, capsys):
        """Test that show_help shows session help."""
        args = MagicMock()
        args.positional_args = ["session"]

        result = show_help(args)

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        assert "Session Management" in captured.out
        assert "SUBCOMMANDS:" in captured.out

    def test_session_subcommand_help(self, capsys):
        """Test that show_help shows session subcommand help."""
        args = MagicMock()
        args.positional_args = ["session", "list"]

        result = show_help(args)

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        assert "wolo session list" in captured.out

    def test_config_help(self, capsys):
        """Test that show_help shows config help."""
        args = MagicMock()
        args.positional_args = ["config"]

        result = show_help(args)

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        assert "Configuration Management" in captured.out

    def test_config_subcommand_help(self, capsys):
        """Test that show_help shows config subcommand help."""
        args = MagicMock()
        args.positional_args = ["config", "init"]

        result = show_help(args)

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        assert "wolo config init" in captured.out

    def test_chat_help(self, capsys):
        """Test that show_help shows chat help."""
        args = MagicMock()
        args.positional_args = ["chat"]

        result = show_help(args)

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        assert "Wolo Chat - Interactive Conversation Mode" in captured.out

    def test_unknown_context_shows_main_help(self, capsys):
        """Test that unknown context falls back to main help."""
        args = MagicMock()
        args.positional_args = ["unknown_command"]

        result = show_help(args)

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        assert "Wolo - AI Agent CLI" in captured.out


class TestShowMainHelp:
    """Tests for show_main_help function."""

    def test_contains_usage_section(self, capsys):
        """Test main help contains USAGE section."""
        show_main_help()
        captured = capsys.readouterr()
        assert "USAGE:" in captured.out

    def test_contains_basic_usage(self, capsys):
        """Test main help contains BASIC USAGE section."""
        show_main_help()
        captured = capsys.readouterr()
        assert "BASIC USAGE:" in captured.out

    def test_contains_execution_modes(self, capsys):
        """Test main help contains EXECUTION MODES section."""
        show_main_help()
        captured = capsys.readouterr()
        assert "EXECUTION MODES:" in captured.out
        assert "--solo" in captured.out
        assert "--coop" in captured.out

    def test_contains_session_options(self, capsys):
        """Test main help contains SESSION OPTIONS section."""
        show_main_help()
        captured = capsys.readouterr()
        assert "SESSION OPTIONS:" in captured.out

    def test_contains_examples(self, capsys):
        """Test main help contains EXAMPLES section."""
        show_main_help()
        captured = capsys.readouterr()
        assert "EXAMPLES:" in captured.out


class TestShowCommandHelp:
    """Tests for show_command_help function."""

    def test_session_command_help(self, capsys):
        """Test session command help."""
        show_command_help("session")
        captured = capsys.readouterr()
        assert "Session Management" in captured.out
        assert "list" in captured.out
        assert "show" in captured.out
        assert "resume" in captured.out
        assert "create" in captured.out
        assert "watch" in captured.out
        assert "delete" in captured.out
        assert "clean" in captured.out

    def test_config_command_help(self, capsys):
        """Test config command help."""
        show_command_help("config")
        captured = capsys.readouterr()
        assert "Configuration Management" in captured.out
        assert "init" in captured.out
        assert "list-endpoints" in captured.out
        assert "show" in captured.out

    def test_chat_command_help(self, capsys):
        """Test chat command help."""
        show_command_help("chat")
        captured = capsys.readouterr()
        assert "Wolo Chat" in captured.out
        assert "REPL COMMANDS:" in captured.out

    def test_unknown_command_shows_main_help(self, capsys):
        """Test unknown command shows main help."""
        show_command_help("unknown")
        captured = capsys.readouterr()
        assert "Wolo - AI Agent CLI" in captured.out


class TestShowSubcommandHelp:
    """Tests for show_subcommand_help function."""

    def test_session_create_help(self, capsys):
        """Test session create subcommand help."""
        show_subcommand_help("session", "create")
        captured = capsys.readouterr()
        assert "wolo session create" in captured.out

    def test_session_list_help(self, capsys):
        """Test session list subcommand help."""
        show_subcommand_help("session", "list")
        captured = capsys.readouterr()
        assert "wolo session list" in captured.out
        assert "wolo -l" in captured.out

    def test_session_show_help(self, capsys):
        """Test session show subcommand help."""
        show_subcommand_help("session", "show")
        captured = capsys.readouterr()
        assert "wolo session show" in captured.out

    def test_session_resume_help(self, capsys):
        """Test session resume subcommand help."""
        show_subcommand_help("session", "resume")
        captured = capsys.readouterr()
        assert "wolo session resume" in captured.out
        assert "REPL" in captured.out

    def test_session_watch_help(self, capsys):
        """Test session watch subcommand help."""
        show_subcommand_help("session", "watch")
        captured = capsys.readouterr()
        assert "wolo session watch" in captured.out
        assert "wolo -w" in captured.out

    def test_session_delete_help(self, capsys):
        """Test session delete subcommand help."""
        show_subcommand_help("session", "delete")
        captured = capsys.readouterr()
        assert "wolo session delete" in captured.out

    def test_session_clean_help(self, capsys):
        """Test session clean subcommand help."""
        show_subcommand_help("session", "clean")
        captured = capsys.readouterr()
        assert "wolo session clean" in captured.out
        assert "30 days" in captured.out

    def test_session_unknown_subcommand(self, capsys):
        """Test session unknown subcommand shows session help."""
        show_subcommand_help("session", "unknown")
        captured = capsys.readouterr()
        assert "Session Management" in captured.out

    def test_config_init_help(self, capsys):
        """Test config init subcommand help."""
        show_subcommand_help("config", "init")
        captured = capsys.readouterr()
        assert "wolo config init" in captured.out

    def test_config_list_endpoints_help(self, capsys):
        """Test config list-endpoints subcommand help."""
        show_subcommand_help("config", "list-endpoints")
        captured = capsys.readouterr()
        assert "wolo config list-endpoints" in captured.out

    def test_config_show_help(self, capsys):
        """Test config show subcommand help."""
        show_subcommand_help("config", "show")
        captured = capsys.readouterr()
        assert "wolo config show" in captured.out

    def test_config_docs_help(self, capsys):
        """Test config docs subcommand help."""
        show_subcommand_help("config", "docs")
        captured = capsys.readouterr()
        assert "wolo config docs" in captured.out

    def test_config_example_help(self, capsys):
        """Test config example subcommand help."""
        show_subcommand_help("config", "example")
        captured = capsys.readouterr()
        assert "wolo config example" in captured.out

    def test_config_unknown_subcommand(self, capsys):
        """Test config unknown subcommand shows config help."""
        show_subcommand_help("config", "unknown")
        captured = capsys.readouterr()
        assert "Configuration Management" in captured.out

    def test_unknown_command_shows_main_help(self, capsys):
        """Test unknown command shows main help."""
        show_subcommand_help("unknown", "something")
        captured = capsys.readouterr()
        assert "Wolo - AI Agent CLI" in captured.out
