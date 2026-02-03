# tests/path_safety/test_cli_integration.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from wolo.cli.parser import FlexibleArgumentParser
from wolo.path_guard import PathGuard


class TestAllowPathArgument:
    def test_single_allow_path(self):
        """Should parse single --allow-path argument"""
        parser = FlexibleArgumentParser()
        args = parser.parse(["--allow-path", "/workspace", "test prompt"])

        assert args.execution_options.allowed_paths == ["/workspace"]

    def test_multiple_allow_paths(self):
        """Should parse multiple --allow-path arguments"""
        parser = FlexibleArgumentParser()
        args = parser.parse([
            "--allow-path", "/workspace",
            "--allow-path", "/var/tmp",
            "test prompt"
        ])

        assert len(args.execution_options.allowed_paths) == 2
        assert "/workspace" in args.execution_options.allowed_paths
        assert "/var/tmp" in args.execution_options.allowed_paths

    def test_short_form(self):
        """Should parse -P short form"""
        parser = FlexibleArgumentParser()
        args = parser.parse(["-P", "/tmp", "test prompt"])

        assert args.execution_options.allowed_paths == ["/tmp"]

    def test_no_allow_path_default(self):
        """Should default to empty list when not provided"""
        parser = FlexibleArgumentParser()
        args = parser.parse(["test prompt"])

        assert args.execution_options.allowed_paths == []


class TestPathGuardInitialization:
    def test_initializes_with_config_paths(self):
        """PathGuard should be initialized with config paths"""
        from wolo.config import Config, PathSafetyConfig
        from wolo.cli.main import _initialize_path_guard

        config = Config(
            api_key="test",
            model="test",
            base_url="https://test.com",
            path_safety=PathSafetyConfig(
                allowed_write_paths=[Path("/workspace")]
            )
        )

        with patch('wolo.cli.main.set_path_guard') as mock_set:
            _initialize_path_guard(config, [])

            mock_set.assert_called_once()
            guard = mock_set.call_args[0][0]
            assert isinstance(guard, type(PathGuard()))  # Is a PathGuard instance

    def test_initializes_with_cli_paths(self):
        """PathGuard should include CLI-provided paths"""
        from wolo.config import Config
        from wolo.cli.main import _initialize_path_guard

        config = Config(
            api_key="test",
            model="test",
            base_url="https://test.com"
        )

        with patch('wolo.cli.main.set_path_guard') as mock_set:
            _initialize_path_guard(config, ["/workspace", "/var/tmp"])

            mock_set.assert_called_once()
