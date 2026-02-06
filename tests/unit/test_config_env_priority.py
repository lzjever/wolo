"""Tests for environment variable priority in config."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from wolo.config import Config


@pytest.mark.parametrize("env_var", ["WOLO_API_KEY"])
def test_env_var_takes_precedence_over_config_file(env_var, tmp_path, monkeypatch):
    """Environment variable takes precedence over config file API key."""
    # Mock Path.home() to return tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    config_dir = tmp_path / ".wolo"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_data = {
        "endpoints": [
            {
                "name": "test",
                "model": "test-model",
                "api_base": "https://api.test.com",
                "api_key": "file_key_value",
            }
        ]
    }
    config_file.write_text(yaml.dump(config_data))

    with patch.dict(os.environ, {env_var: "env_key_value"}):
        # Use from_env to load config
        config = Config.from_env()
        # API key should come from env var, not file
        assert config.api_key == "env_key_value"


def test_config_file_api_key_used_when_no_env_var(tmp_path, monkeypatch, caplog):
    """Config file API key is used when no environment variable set."""
    # Mock Path.home() to return tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    config_dir = tmp_path / ".wolo"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_data = {
        "endpoints": [
            {
                "name": "test",
                "model": "test-model",
                "api_base": "https://api.test.com",
                "api_key": "file_key_value",
            }
        ]
    }
    config_file.write_text(yaml.dump(config_data))

    with patch.dict(os.environ, {}, clear=True):
        # Remove env var
        os.environ.pop("WOLO_API_KEY", None)

        import logging

        with caplog.at_level(logging.WARNING):
            config = Config.from_env()

        # API key should come from config file
        assert config.api_key == "file_key_value"
        # Should log warning about using config file
        assert any("config file" in record.message.lower() for record in caplog.records)


def test_error_when_no_api_key_configured(tmp_path, monkeypatch):
    """Error is raised when no API key is configured."""
    # Mock Path.home() to return tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    config_dir = tmp_path / ".wolo"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("endpoints: []\n")

    with patch.dict(os.environ, {}, clear=True):
        # Remove env var
        os.environ.pop("WOLO_API_KEY", None)

        with pytest.raises(ValueError) as exc_info:
            Config.from_env()

        assert "API key" in str(exc_info.value)
