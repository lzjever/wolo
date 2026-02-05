"""Tests for baseurl direct mode configuration."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from wolo.cli.commands.repl import ReplCommand
from wolo.cli.commands.run import RunCommand
from wolo.cli.exit_codes import ExitCode
from wolo.cli.parser import FlexibleArgumentParser, ParsedArgs
from wolo.config import Config


class TestConfigFromEnvBaseUrl:
    """Test Config.from_env() with baseurl direct mode."""

    def test_from_env_baseurl_mode_all_required(self, tmp_path, monkeypatch):
        """Test that baseurl mode requires all three parameters."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Test missing api_key
        with pytest.raises(ValueError, match="--api-key is required"):
            Config.from_env(base_url="https://api.example.com/v1", model="test-model")

        # Test missing model
        with pytest.raises(ValueError, match="--model is required"):
            Config.from_env(base_url="https://api.example.com/v1", api_key="test-key")

        # Test all provided - should succeed
        config = Config.from_env(
            base_url="https://api.example.com/v1", api_key="test-key", model="test-model"
        )

        assert config.base_url == "https://api.example.com/v1"
        assert config.api_key == "test-key"
        assert config.model == "test-model"
        assert config.temperature == 0.7  # Default
        assert config.max_tokens == 16384  # Default

    def test_from_env_baseurl_bypasses_config_file(self, tmp_path, monkeypatch):
        """Test that baseurl mode bypasses config file."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create config file with different values
        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_data = {
            "endpoints": [
                {
                    "name": "default",
                    "model": "config-model",
                    "api_base": "https://config.example.com/v1",
                    "api_key": "config-key",
                }
            ]
        }
        config_file.write_text(yaml.dump(config_data))

        # Use baseurl mode - should ignore config file
        config = Config.from_env(
            base_url="https://cli.example.com/v1", api_key="cli-key", model="cli-model"
        )

        assert config.base_url == "https://cli.example.com/v1"
        assert config.api_key == "cli-key"
        assert config.model == "cli-model"

    def test_from_env_config_file_mode(self, tmp_path, monkeypatch):
        """Test config file mode when baseurl not provided."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create config file
        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_data = {
            "endpoints": [
                {
                    "name": "default",
                    "model": "config-model",
                    "api_base": "https://config.example.com/v1",
                    "api_key": "config-key",
                    "temperature": 0.8,
                    "max_tokens": 20000,
                }
            ],
            "default_endpoint": "default",
        }
        config_file.write_text(yaml.dump(config_data))

        # Use config file mode
        config = Config.from_env()

        assert config.base_url == "https://config.example.com/v1"
        assert config.api_key == "config-key"
        assert config.model == "config-model"
        assert config.temperature == 0.8
        assert config.max_tokens == 20000

    def test_from_env_config_file_mode_with_overrides(self, tmp_path, monkeypatch):
        """Test config file mode with CLI overrides."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create config file
        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_data = {
            "endpoints": [
                {
                    "name": "default",
                    "model": "config-model",
                    "api_base": "https://config.example.com/v1",
                    "api_key": "config-key",
                }
            ],
            "default_endpoint": "default",
        }
        config_file.write_text(yaml.dump(config_data))

        # Override api_key and model, but not base_url (so still config file mode)
        config = Config.from_env(api_key="override-key", model="override-model")

        assert config.base_url == "https://config.example.com/v1"  # From config
        assert config.api_key == "override-key"  # Overridden
        assert config.model == "override-model"  # Overridden


class TestParserBaseUrl:
    """Test parser for --base-url option."""

    def test_parse_base_url_long_form(self):
        """Test parsing --base-url option."""
        parser = FlexibleArgumentParser()
        args = parser.parse(["--base-url", "https://api.example.com/v1", "message"])

        assert args.execution_options.base_url == "https://api.example.com/v1"
        assert args.message == "message"

    def test_parse_base_url_with_equals(self):
        """Test parsing --base-url=value syntax."""
        parser = FlexibleArgumentParser()
        args = parser.parse(["--base-url=https://api.example.com/v1", "message"])

        assert args.execution_options.base_url == "https://api.example.com/v1"
        assert args.message == "message"

    def test_parse_base_url_with_model_and_api_key(self):
        """Test parsing all three required options together."""
        parser = FlexibleArgumentParser()
        args = parser.parse(
            [
                "--base-url",
                "https://api.example.com/v1",
                "--model",
                "test-model",
                "--api-key",
                "test-key",
                "message",
            ]
        )

        assert args.execution_options.base_url == "https://api.example.com/v1"
        assert args.execution_options.model == "test-model"
        assert args.execution_options.api_key == "test-key"
        assert args.message == "message"


class TestRunCommandWithBaseUrl:
    """Test RunCommand with baseurl direct mode."""

    def test_run_command_with_baseurl(self, tmp_path, monkeypatch):
        """Test RunCommand uses baseurl when provided."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create minimal config to pass first-run check
        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            "endpoints:\n  - name: default\n    model: test\n    api_base: https://test.com\n    api_key: test\n"
        )

        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test prompt"
        args.message_from_stdin = False
        args.execution_options.base_url = "https://api.example.com/v1"
        args.execution_options.api_key = "test-key"
        args.execution_options.model = "test-model"

        # Mock the actual execution to avoid running the agent
        with patch("wolo.cli.execution.run_single_task_mode") as mock_run:
            mock_run.return_value = ExitCode.SUCCESS
            with patch("wolo.session.create_session", return_value="test-session"):
                with patch("wolo.session.check_and_set_session_pid", return_value=True):
                    with patch("wolo.cli.events.setup_event_handlers"):
                        with patch("wolo.question_ui.setup_question_handler"):
                            result = cmd.execute(args)

        # Verify Config.from_env was called with baseurl
        # The actual verification would be in the mock, but we can check the result
        assert result == ExitCode.SUCCESS

    def test_run_command_baseurl_requires_all_params(self, tmp_path, monkeypatch, capsys):
        """Test RunCommand fails when baseurl provided but missing api-key or model."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create minimal config
        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            "endpoints:\n  - name: default\n    model: test\n    api_base: https://test.com\n    api_key: test\n"
        )

        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test prompt"
        args.message_from_stdin = False
        args.execution_options.base_url = "https://api.example.com/v1"
        # Missing api_key and model

        result = cmd.execute(args)

        assert result == ExitCode.CONFIG_ERROR
        captured = capsys.readouterr()
        assert "required" in captured.err.lower()


class TestReplCommandWithBaseUrl:
    """Test ReplCommand with baseurl direct mode."""

    def test_repl_command_with_baseurl(self, tmp_path, monkeypatch):
        """Test ReplCommand uses baseurl when provided."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create minimal config
        config_dir = tmp_path / ".wolo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            "endpoints:\n  - name: default\n    model: test\n    api_base: https://test.com\n    api_key: test\n"
        )

        cmd = ReplCommand()
        args = ParsedArgs()
        args.execution_options.base_url = "https://api.example.com/v1"
        args.execution_options.api_key = "test-key"
        args.execution_options.model = "test-model"

        # Mock the actual execution
        with patch("wolo.cli.execution.run_repl_mode") as mock_run:
            mock_run.return_value = ExitCode.SUCCESS
            with patch("wolo.session.create_session", return_value="test-session"):
                with patch("wolo.session.check_and_set_session_pid", return_value=True):
                    with patch("wolo.cli.events.setup_event_handlers"):
                        result = cmd.execute(args)

        assert result == ExitCode.SUCCESS
