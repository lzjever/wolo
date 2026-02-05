"""Tests for config init command and first-run detection."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from wolo.cli.commands.config import ConfigInitCommand
from wolo.cli.commands.repl import ReplCommand
from wolo.cli.commands.run import RunCommand
from wolo.cli.exit_codes import ExitCode
from wolo.cli.parser import ParsedArgs
from wolo.cli.utils import show_first_run_message
from wolo.config import Config


class TestConfigIsFirstRun:
    """Test Config.is_first_run() method."""

    def test_is_first_run_no_file(self, tmp_path, monkeypatch):
        """Test when config file doesn't exist."""
        # Mock Path.home() to return tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        assert Config.is_first_run() is True

    def test_is_first_run_empty_file(self, tmp_path, monkeypatch):
        """Test when config file exists but is empty."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("")

        assert Config.is_first_run() is True

    def test_is_first_run_invalid_yaml(self, tmp_path, monkeypatch):
        """Test when config file has invalid YAML."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("invalid: yaml: content: [")

        assert Config.is_first_run() is True

    def test_is_first_run_no_endpoints(self, tmp_path, monkeypatch):
        """Test when config file has no endpoints key."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("some_other_key: value\n")

        assert Config.is_first_run() is True

    def test_is_first_run_empty_endpoints(self, tmp_path, monkeypatch):
        """Test when config file has empty endpoints list."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("endpoints: []\n")

        assert Config.is_first_run() is True

    def test_is_first_run_valid_config(self, tmp_path, monkeypatch):
        """Test when valid config file exists."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_data = {
            "endpoints": [
                {
                    "name": "default",
                    "model": "glm-4",
                    "api_base": "https://api.example.com/v1",
                    "api_key": "test-key",
                }
            ]
        }
        config_file.write_text(yaml.dump(config_data))

        assert Config.is_first_run() is False


class TestConfigInitCommand:
    """Test ConfigInitCommand."""

    def test_config_init_command_name(self):
        """Test command name."""
        cmd = ConfigInitCommand()
        assert cmd.name == "config init"

    def test_config_init_command_description(self):
        """Test command description."""
        cmd = ConfigInitCommand()
        assert "initialize" in cmd.description.lower()

    def test_config_init_config_exists(self, tmp_path, monkeypatch):
        """Test init fails when config already exists."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create existing config
        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("endpoints:\n  - name: default\n    model: test\n")

        cmd = ConfigInitCommand()
        args = ParsedArgs()

        result = cmd.execute(args)

        assert result == ExitCode.ERROR

    def test_config_init_success(self, tmp_path, monkeypatch):
        """Test successful config initialization."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        cmd = ConfigInitCommand()
        args = ParsedArgs()

        # Mock user input
        with patch("builtins.input", side_effect=["https://api.example.com/v1", "test-model"]):
            with patch("getpass.getpass", return_value="test-api-key"):
                result = cmd.execute(args)

        assert result == ExitCode.SUCCESS

        # Verify config file was created
        config_file = tmp_path / ".wolo" / "config.yaml"
        assert config_file.exists()

        # Verify config content
        with open(config_file) as f:
            config_data = yaml.safe_load(f)

        assert "endpoints" in config_data
        assert len(config_data["endpoints"]) == 1
        assert config_data["endpoints"][0]["name"] == "default"
        assert config_data["endpoints"][0]["model"] == "test-model"
        assert config_data["endpoints"][0]["api_base"] == "https://api.example.com/v1"
        assert config_data["endpoints"][0]["api_key"] == "test-api-key"
        assert config_data["default_endpoint"] == "default"

    def test_config_init_empty_api_base(self, tmp_path, monkeypatch):
        """Test init fails with empty API base URL."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        cmd = ConfigInitCommand()
        args = ParsedArgs()

        with patch("builtins.input", return_value=""):
            result = cmd.execute(args)

        assert result == ExitCode.ERROR

    def test_config_init_invalid_url(self, tmp_path, monkeypatch):
        """Test init fails with invalid URL format."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        cmd = ConfigInitCommand()
        args = ParsedArgs()

        with patch("builtins.input", return_value="invalid-url"):
            result = cmd.execute(args)

        assert result == ExitCode.ERROR

    def test_config_init_empty_api_key(self, tmp_path, monkeypatch):
        """Test init fails with empty API key."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        cmd = ConfigInitCommand()
        args = ParsedArgs()

        with patch("builtins.input", side_effect=["https://api.example.com/v1", "test-model"]):
            with patch("getpass.getpass", return_value=""):
                result = cmd.execute(args)

        assert result == ExitCode.ERROR

    def test_config_init_empty_model(self, tmp_path, monkeypatch):
        """Test init fails with empty model name."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        cmd = ConfigInitCommand()
        args = ParsedArgs()

        with patch("builtins.input", side_effect=["https://api.example.com/v1", ""]):
            with patch("getpass.getpass", return_value="test-api-key"):
                result = cmd.execute(args)

        assert result == ExitCode.ERROR

    def test_config_init_permission_error(self, tmp_path, monkeypatch):
        """Test init handles permission errors."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        cmd = ConfigInitCommand()
        args = ParsedArgs()

        # Mock mkdir to raise PermissionError
        with patch("pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")):
            with patch("builtins.input", side_effect=["https://api.example.com/v1", "test-model"]):
                with patch("getpass.getpass", return_value="test-api-key"):
                    result = cmd.execute(args)

        assert result == ExitCode.CONFIG_ERROR


class TestFirstRunDetection:
    """Test first-run detection in commands."""

    def test_run_command_first_run(self, tmp_path, monkeypatch, capsys):
        """Test RunCommand shows first-run message when no config."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test prompt"
        args.message_from_stdin = False

        with patch("sys.exit", side_effect=SystemExit) as _:
            try:
                cmd.execute(args)
            except SystemExit:
                pass

        # Check that first-run message was printed
        captured = capsys.readouterr()
        assert "not configured" in captured.err.lower() or "config init" in captured.err.lower()

    def test_repl_command_first_run(self, tmp_path, monkeypatch, capsys):
        """Test ReplCommand shows first-run message when no config."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        cmd = ReplCommand()
        args = ParsedArgs()

        with patch("sys.exit", side_effect=SystemExit) as _:
            try:
                cmd.execute(args)
            except SystemExit:
                pass

        # Check that first-run message was printed
        captured = capsys.readouterr()
        assert "not configured" in captured.err.lower() or "config init" in captured.err.lower()

    def test_first_run_message_exits_with_config_error(self, tmp_path, monkeypatch):
        """Test show_first_run_message exits with CONFIG_ERROR."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            show_first_run_message()

        assert exc_info.value.code == ExitCode.CONFIG_ERROR
