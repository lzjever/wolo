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
