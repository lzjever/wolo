# tests/path_safety/test_config.py
"""Tests for PathGuardConfig module."""

from pathlib import Path

from wolo.path_guard.checker import PathWhitelist
from wolo.path_guard.config import PathGuardConfig


class TestPathGuardConfig:
    def test_default_config(self):
        """Default config should have empty paths."""
        config = PathGuardConfig()
        assert config.config_paths == []
        assert config.cli_paths == []
        assert config.workdir is None

    def test_config_with_paths(self):
        """Config should store provided paths."""
        config = PathGuardConfig(
            config_paths=[Path("/project")],
            cli_paths=[Path("/allowed")],
            workdir=Path("/workspace"),
        )
        assert len(config.config_paths) == 1
        assert config.config_paths[0] == Path("/project")
        assert len(config.cli_paths) == 1
        assert config.cli_paths[0] == Path("/allowed")
        assert config.workdir == Path("/workspace")

    def test_create_whitelist(self):
        """Should create PathWhitelist from config."""
        config = PathGuardConfig(
            config_paths=[Path("/project")],
            cli_paths=[Path("/allowed")],
            workdir=Path("/workspace"),
        )
        confirmed_dirs = {Path("/home/user/project")}

        whitelist = config.create_whitelist(confirmed_dirs)

        assert isinstance(whitelist, PathWhitelist)
        # Check that workdir is in whitelist
        assert whitelist.is_whitelisted(Path("/workspace/file.txt"))
        # Check that config paths are in whitelist
        assert whitelist.is_whitelisted(Path("/project/file.txt"))
        # Check that CLI paths are in whitelist
        assert whitelist.is_whitelisted(Path("/allowed/file.txt"))
        # Check that confirmed dirs are in whitelist
        assert whitelist.is_whitelisted(Path("/home/user/project/file.txt"))

    def test_create_checker(self):
        """Should create PathChecker from config."""
        config = PathGuardConfig(
            config_paths=[Path("/project")],
        )

        checker = config.create_checker()

        # Should allow paths from config
        result = checker.check("/project/file.txt", "write")
        assert result.allowed

    def test_create_checker_with_confirmed_dirs(self):
        """Should create PathChecker with confirmed directories."""
        config = PathGuardConfig()
        confirmed_dirs = {Path("/tmp/confirmed")}

        checker = config.create_checker(confirmed_dirs)

        # Should allow confirmed paths
        result = checker.check("/tmp/confirmed/file.txt", "write")
        assert result.allowed

    def test_from_dict(self):
        """Should create config from dictionary."""
        data = {
            "config_paths": ["/project", "~/workspace"],
            "cli_paths": ["/allowed"],
            "workdir": "/workspace",
        }

        config = PathGuardConfig.from_dict(data)

        assert len(config.config_paths) == 2
        assert config.cli_paths[0] == Path("/allowed")
        assert config.workdir == Path("/workspace")

    def test_from_dict_expand_user(self):
        """Should expand ~ in paths."""
        data = {"config_paths": ["~/project"], "cli_paths": [], "workdir": None}

        config = PathGuardConfig.from_dict(data)

        # ~ should be expanded to actual home directory
        assert str(config.config_paths[0]).startswith("/")
        assert not str(config.config_paths[0]).startswith("~")

    def test_from_dict_empty(self):
        """Should handle empty dictionary."""
        config = PathGuardConfig.from_dict({})
        assert config.config_paths == []
        assert config.cli_paths == []
        assert config.workdir is None

    def test_from_dict_none_values(self):
        """Should handle None values in dictionary."""
        data = {"config_paths": None, "cli_paths": None, "workdir": None}
        config = PathGuardConfig.from_dict(data)
        assert config.config_paths == []
        assert config.cli_paths == []

    def test_to_dict(self):
        """Should convert config to dictionary."""
        config = PathGuardConfig(
            config_paths=[Path("/project")],
            cli_paths=[Path("/allowed")],
            workdir=Path("/workspace"),
        )

        data = config.to_dict()

        assert data["config_paths"] == ["/project"]
        assert data["cli_paths"] == ["/allowed"]
        assert data["workdir"] == "/workspace"
