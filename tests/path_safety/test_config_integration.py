# tests/path_safety/test_config_integration.py
from pathlib import Path

from wolo.config import PathSafetyConfig


class TestPathSafetyConfig:
    def test_default_values(self):
        """PathSafetyConfig should have sensible defaults"""
        config = PathSafetyConfig()

        assert config.allowed_write_paths == []
        assert config.max_confirmations_per_session == 10
        assert config.audit_denied is True
        assert config.audit_log_file == Path.home() / ".wolo" / "path_audit.log"

    def test_custom_values(self):
        """Should accept custom configuration values"""
        custom_path = Path("/custom/audit.log")
        config = PathSafetyConfig(
            allowed_write_paths=[Path("/workspace"), Path("/tmp")],
            max_confirmations_per_session=20,
            audit_denied=False,
            audit_log_file=custom_path,
        )

        assert len(config.allowed_write_paths) == 2
        assert config.max_confirmations_per_session == 20
        assert config.audit_denied is False
        assert config.audit_log_file == custom_path

    def test_to_path_guard_config_basic(self):
        """Should convert to PathGuardConfig with basic config"""
        config = PathSafetyConfig(allowed_write_paths=[Path("/workspace"), Path("/tmp")])

        guard_config = config.to_path_guard_config()

        assert guard_config.config_paths == [Path("/workspace"), Path("/tmp")]
        assert guard_config.cli_paths == []
        assert guard_config.workdir is None

    def test_to_path_guard_config_with_cli_paths(self):
        """Should include CLI paths in converted config"""
        config = PathSafetyConfig(allowed_write_paths=[Path("/workspace")])

        cli_paths = [Path("/var/tmp"), Path("/cache")]
        guard_config = config.to_path_guard_config(cli_paths=cli_paths)

        assert guard_config.config_paths == [Path("/workspace")]
        assert guard_config.cli_paths == cli_paths
        assert guard_config.workdir is None

    def test_to_path_guard_config_with_workdir(self):
        """Should include workdir in converted config"""
        config = PathSafetyConfig(allowed_write_paths=[Path("/workspace")])

        workdir = Path("/home/user/project")
        guard_config = config.to_path_guard_config(workdir=workdir)

        assert guard_config.config_paths == [Path("/workspace")]
        assert guard_config.cli_paths == []
        assert guard_config.workdir == workdir

    def test_to_path_guard_config_full(self):
        """Should convert with all parameters"""
        config = PathSafetyConfig(allowed_write_paths=[Path("/workspace"), Path("/tmp")])

        cli_paths = [Path("/var/tmp")]
        workdir = Path("/home/user/project")
        guard_config = config.to_path_guard_config(cli_paths=cli_paths, workdir=workdir)

        assert guard_config.config_paths == [Path("/workspace"), Path("/tmp")]
        assert guard_config.cli_paths == cli_paths
        assert guard_config.workdir == workdir

    def test_to_path_guard_config_does_not_modify_original(self):
        """Conversion should not modify original config"""
        original_paths = [Path("/workspace")]
        config = PathSafetyConfig(allowed_write_paths=original_paths)

        config.to_path_guard_config(cli_paths=[Path("/tmp")], workdir=Path("/work"))

        # Original should be unchanged
        assert config.allowed_write_paths == original_paths
        assert config.max_confirmations_per_session == 10
