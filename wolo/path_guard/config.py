# wolo/path_guard/config.py
"""Configuration management for PathGuard."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wolo.path_guard.checker import PathChecker, PathWhitelist


@dataclass
class PathGuardConfig:
    """Configuration for PathGuard path protection.

    Attributes:
        config_paths: Paths from config file (path_safety.allowed_write_paths)
        cli_paths: Paths from --allow-path/-P CLI arguments
        workdir: Working directory from -C/--workdir
    """

    config_paths: list[Path] = field(default_factory=list)
    cli_paths: list[Path] = field(default_factory=list)
    workdir: Path | None = None

    def create_whitelist(self, confirmed_dirs: set[Path]) -> PathWhitelist:
        """Create a PathWhitelist from this configuration.

        Args:
            confirmed_dirs: Set of directories confirmed by user during session

        Returns:
            PathWhitelist configured with all path sources
        """
        return PathWhitelist(
            config_paths=set(p.resolve() for p in self.config_paths),
            cli_paths=set(p.resolve() for p in self.cli_paths),
            workdir=Path(self.workdir).resolve() if self.workdir else None,
            confirmed_dirs=confirmed_dirs,
        )

    def create_checker(self, confirmed_dirs: set[Path] | None = None) -> PathChecker:
        """Create a PathChecker from this configuration.

        Args:
            confirmed_dirs: Set of directories confirmed by user during session

        Returns:
            PathChecker configured with all path sources
        """
        if confirmed_dirs is None:
            confirmed_dirs = set()
        whitelist = self.create_whitelist(confirmed_dirs)
        return PathChecker(whitelist)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PathGuardConfig":
        """Create config from dictionary (for YAML loading).

        Args:
            data: Dictionary with config_paths, cli_paths, workdir keys

        Returns:
            PathGuardConfig instance
        """
        config_paths = data.get("config_paths") or []
        cli_paths = data.get("cli_paths") or []
        workdir = data.get("workdir")

        return cls(
            config_paths=[Path(p).expanduser() for p in config_paths],
            cli_paths=[Path(p).expanduser() for p in cli_paths],
            workdir=Path(workdir).expanduser().resolve() if workdir else None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary (for YAML serialization).

        Returns:
            Dictionary representation of the config
        """
        return {
            "config_paths": [str(p) for p in self.config_paths],
            "cli_paths": [str(p) for p in self.cli_paths],
            "workdir": str(self.workdir) if self.workdir else None,
        }
