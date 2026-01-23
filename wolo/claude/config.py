"""
Claude configuration reader.

Reads Claude's configuration files:
- ~/.claude/settings.json - Global settings (env vars, enabled plugins)
- ~/.claude/projects/<hash>/ - Project-specific settings
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ClaudeConfig:
    """Claude configuration data."""

    # Environment variables from settings.json
    env: dict[str, str] = field(default_factory=dict)

    # Enabled plugins (plugin_id -> enabled)
    enabled_plugins: dict[str, bool] = field(default_factory=dict)

    # Paths
    config_dir: Path = field(default_factory=lambda: Path.home() / ".claude")
    skills_dir: Path = field(default_factory=lambda: Path.home() / ".claude" / "skills")

    @property
    def exists(self) -> bool:
        """Check if Claude config directory exists."""
        return self.config_dir.exists()


def get_claude_config_dir() -> Path:
    """Get the Claude configuration directory."""
    return Path.home() / ".claude"


def load_claude_config(config_dir: Path | None = None) -> ClaudeConfig:
    """
    Load Claude configuration from ~/.claude/settings.json.

    Args:
        config_dir: Optional custom config directory (default: ~/.claude)

    Returns:
        ClaudeConfig with loaded settings
    """
    if config_dir is None:
        config_dir = get_claude_config_dir()

    config = ClaudeConfig(
        config_dir=config_dir,
        skills_dir=config_dir / "skills",
    )

    if not config_dir.exists():
        logger.debug(f"Claude config directory not found: {config_dir}")
        return config

    # Load settings.json
    settings_path = config_dir / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, encoding="utf-8") as f:
                settings = json.load(f)

            config.env = settings.get("env", {})
            config.enabled_plugins = settings.get("enabledPlugins", {})

            logger.debug(
                f"Loaded Claude settings: {len(config.env)} env vars, "
                f"{len(config.enabled_plugins)} plugins"
            )
        except Exception as e:
            logger.warning(f"Failed to load Claude settings: {e}")

    return config


def apply_claude_env(config: ClaudeConfig) -> None:
    """
    Apply Claude environment variables to the current process.

    This is useful for inheriting API keys and other settings from Claude.

    Args:
        config: ClaudeConfig with env vars to apply
    """
    import os

    for key, value in config.env.items():
        if key not in os.environ:
            os.environ[key] = value
            logger.debug(f"Applied Claude env: {key}")
