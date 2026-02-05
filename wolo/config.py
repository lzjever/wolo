"""Configuration management for Wolo."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class EndpointConfig:
    """Configuration for a single API endpoint."""

    name: str
    model: str
    api_base: str
    api_key: str
    temperature: float = 0.7
    max_tokens: int = 16384
    source_model: str | None = None
    enable_think: bool = False  # Enable reasoning mode for this endpoint


@dataclass
class ClaudeCompatConfig:
    """Configuration for Claude compatibility mode."""

    enabled: bool = False
    config_dir: Path | None = None  # Default: ~/.claude

    # What to load from Claude
    load_skills: bool = True
    load_mcp: bool = True

    # MCP settings
    node_strategy: str = "auto"  # auto, require, skip, python_fallback


@dataclass
class MCPConfig:
    """MCP configuration."""

    enabled: bool = True
    node_strategy: str = "auto"  # auto, require, skip, python_fallback
    servers: dict = field(default_factory=dict)  # name -> MCPServerConfig dict


@dataclass
class PathSafetyConfig:
    """Configuration for path safety protection.

    This is a compatibility layer that bridges the legacy config format
    with the new PathGuard modular architecture.

    Attributes:
        allowed_write_paths: List of paths where write operations are allowed without confirmation
        max_confirmations_per_session: Maximum number of path confirmations per session
        audit_denied: Whether to audit denied operations
        audit_log_file: Path to audit log file
    """

    allowed_write_paths: list[Path] = field(default_factory=list)
    max_confirmations_per_session: int = 10
    audit_denied: bool = True
    audit_log_file: Path = field(default_factory=lambda: Path.home() / ".wolo" / "path_audit.log")

    def to_path_guard_config(self, cli_paths: list[Path] | None = None, workdir: Path | None = None) -> "PathGuardConfig":
        """Convert to PathGuardConfig for use with the new PathGuard architecture.

        Args:
            cli_paths: Additional paths from CLI arguments (--allow-path/-P)
            workdir: Working directory from -C/--workdir

        Returns:
            PathGuardConfig instance for use with PathGuard modules
        """
        from wolo.path_guard.config import PathGuardConfig

        return PathGuardConfig(
            config_paths=self.allowed_write_paths.copy(),
            cli_paths=cli_paths or [],
            workdir=workdir,
        )


@dataclass
class Config:
    api_key: str
    model: str
    base_url: str
    temperature: float
    max_tokens: int
    mcp_servers: list[str] = field(default_factory=list)
    debug_llm_file: str | None = None  # File to write LLM requests/responses for debugging
    debug_full_dir: str | None = None  # Directory to save full request/response logs
    enable_think: bool = (
        False  # Enable reasoning mode for compatible models (OpenAI o1, DeepSeek-R1, etc.)
    )

    # Claude compatibility
    claude: ClaudeCompatConfig = field(default_factory=ClaudeCompatConfig)

    # MCP configuration
    mcp: MCPConfig = field(default_factory=MCPConfig)

    # Path safety configuration
    path_safety: PathSafetyConfig = field(default_factory=PathSafetyConfig)

    # Compaction configuration (lazy import to avoid circular dependency)
    compaction: Any = None  # Type: CompactionConfig | None

    @classmethod
    def _load_config_file(cls) -> dict[str, Any]:
        """Load configuration from ~/.wolo/config.yaml."""
        config_path = Path.home() / ".wolo" / "config.yaml"
        if not config_path.exists():
            return {}

        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Failed to load config file: {e}")
            return {}

    @classmethod
    def is_first_run(cls) -> bool:
        """
        Check if this is the first run of Wolo (no config file exists).

        Returns:
            True if ~/.wolo/config.yaml does not exist or is empty/invalid
            False if valid config file exists
        """
        config_path = Path.home() / ".wolo" / "config.yaml"

        # Check file existence
        if not config_path.exists() or not config_path.is_file():
            return True

        # Check file is not empty
        try:
            if config_path.stat().st_size == 0:
                return True
        except OSError:
            # Can't stat file, treat as first run
            return True

        # Check file is valid YAML and has endpoints
        try:
            config_data = cls._load_config_file()
            # If load returns empty dict, treat as first run
            if not config_data:
                return True

            # Check if endpoints exist and is not empty
            endpoints = config_data.get("endpoints", [])
            if not endpoints or not isinstance(endpoints, list) or len(endpoints) == 0:
                return True

            # Valid config with endpoints exists
            return False
        except Exception:
            # Any exception means invalid config, treat as first run
            return True

    @classmethod
    def _get_endpoints(cls) -> list[EndpointConfig]:
        """Get all configured endpoints from config file."""
        config_data = cls._load_config_file()
        endpoints_data = config_data.get("endpoints", [])

        endpoints = []
        for ep in endpoints_data:
            endpoints.append(
                EndpointConfig(
                    name=ep["name"],
                    model=ep["model"],
                    api_base=ep["api_base"],
                    api_key=ep["api_key"],
                    temperature=ep.get("temperature", 0.7),
                    max_tokens=ep.get("max_tokens", 16384),
                    source_model=ep.get("source_model"),
                    enable_think=ep.get("enable_think", False),  # Load from endpoint
                )
            )
        return endpoints

    @classmethod
    def list_endpoints(cls) -> list[str]:
        """List available endpoint names."""
        endpoints = cls._get_endpoints()
        return [ep.name for ep in endpoints]

    @classmethod
    def from_env(
        cls,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> "Config":
        """
        Load configuration from environment and CLI arguments.

        Args:
            api_key: API key from CLI (overrides config)
            base_url: Base URL from CLI (if provided, bypasses config file)
            model: Model name from CLI (overrides config)

        Returns:
            Config instance

        Behavior:
            - If base_url is provided, all three (base_url, api_key, model) are required.
              This bypasses the config file completely.
            - Otherwise, uses endpoints from config file or environment variables.
        """
        config_data = cls._load_config_file()

        # Direct mode: if base_url is provided, bypass config file
        if base_url:
            if not api_key:
                raise ValueError(
                    "When using --baseurl, --api-key is required. "
                    "Please provide both --baseurl and --api-key, or use config file."
                )
            if not model:
                raise ValueError(
                    "When using --baseurl, --model is required. "
                    "Please provide --baseurl, --api-key, and --model, or use config file."
                )

            # Use direct CLI parameters, load other settings from config or defaults
            # Load MCP servers from config file or environment variable
            mcp_servers = config_data.get("mcp_servers", [])
            if not mcp_servers:
                mcp_env = os.getenv("WOLO_MCP_SERVERS", "")
                mcp_servers = [s.strip() for s in mcp_env.split(",") if s.strip()]

            # Load Claude compatibility config
            claude_data = config_data.get("claude", {})
            claude_config = ClaudeCompatConfig(
                enabled=claude_data.get("enabled", False),
                config_dir=Path(claude_data["config_dir"])
                if claude_data.get("config_dir")
                else None,
                load_skills=claude_data.get("skills", {}).get("enabled", True)
                if isinstance(claude_data.get("skills"), dict)
                else claude_data.get("load_skills", True),
                load_mcp=claude_data.get("mcp", {}).get("enabled", True)
                if isinstance(claude_data.get("mcp"), dict)
                else claude_data.get("load_mcp", True),
                node_strategy=claude_data.get("node_strategy", "auto"),
            )

            # Load MCP config
            mcp_data = config_data.get("mcp", {})
            mcp_config = MCPConfig(
                enabled=mcp_data.get("enabled", True),
                node_strategy=mcp_data.get("node_strategy", "auto"),
                servers=mcp_data.get("servers", {}),
            )

            # Load enable_think from config or env
            enable_think = config_data.get("enable_think", False)
            if not enable_think:
                enable_think = os.getenv("WOLO_ENABLE_THINK", "").lower() in ("true", "1", "yes")

            # Load compaction config
            from wolo.compaction.config import load_compaction_config

            compaction_data = config_data.get("compaction", {})
            compaction_config = load_compaction_config(compaction_data)

            # Load path safety config
            path_safety_data = config_data.get("path_safety", {})
            path_safety_config = PathSafetyConfig(
                allowed_write_paths=[
                    Path(p) for p in path_safety_data.get("allowed_write_paths", [])
                ],
                max_confirmations_per_session=path_safety_data.get(
                    "max_confirmations_per_session", 10
                ),
                audit_denied=path_safety_data.get("audit_denied", True),
                audit_log_file=Path(path_safety_data.get("audit_log_file"))
                if path_safety_data.get("audit_log_file")
                else Path.home() / ".wolo" / "path_audit.log",
            )

            return cls(
                api_key=api_key,
                model=model,
                base_url=base_url,
                temperature=0.7,  # Default
                max_tokens=16384,  # Default
                mcp_servers=mcp_servers,
                enable_think=enable_think,
                claude=claude_config,
                mcp=mcp_config,
                compaction=compaction_config,
                path_safety=path_safety_config,
            )

        # Config file mode: use endpoints from config file
        endpoints = cls._get_endpoints()

        # Determine which endpoint to use
        selected_endpoint: EndpointConfig | None = None

        if endpoints:
            # Use default endpoint from config, or first endpoint
            default_name = config_data.get("default_endpoint")
            if default_name:
                for ep in endpoints:
                    if ep.name == default_name:
                        selected_endpoint = ep
                        break
            if not selected_endpoint:
                selected_endpoint = endpoints[0]

        # Build config from selected endpoint or fallback to env vars
        if selected_endpoint:
            key = api_key or selected_endpoint.api_key
            model_name = model or selected_endpoint.model
            base_url_from_config = selected_endpoint.api_base
            temperature = selected_endpoint.temperature
            max_tokens = selected_endpoint.max_tokens
        else:
            # No config file - use environment variables only (no defaults)
            key = api_key or os.getenv("GLM_API_KEY")
            if not key:
                raise ValueError(
                    "No API key configured. Please set GLM_API_KEY environment variable "
                    "or configure endpoints in ~/.wolo/config.yaml"
                )
            model_name = model or os.getenv("WOLO_MODEL", "glm-4")
            base_url_from_config = os.getenv(
                "WOLO_API_BASE", "https://open.bigmodel.cn/api/paas/v4"
            )
            temperature = float(os.getenv("WOLO_TEMPERATURE", "0.7"))
            max_tokens = int(os.getenv("WOLO_MAX_TOKENS", "16384"))

        # Load MCP servers from config file or environment variable
        mcp_servers = config_data.get("mcp_servers", [])
        if not mcp_servers:
            mcp_env = os.getenv("WOLO_MCP_SERVERS", "")
            mcp_servers = [s.strip() for s in mcp_env.split(",") if s.strip()]

        # Load Claude compatibility config
        claude_data = config_data.get("claude", {})
        claude_config = ClaudeCompatConfig(
            enabled=claude_data.get("enabled", False),
            config_dir=Path(claude_data["config_dir"]) if claude_data.get("config_dir") else None,
            load_skills=claude_data.get("skills", {}).get("enabled", True)
            if isinstance(claude_data.get("skills"), dict)
            else claude_data.get("load_skills", True),
            load_mcp=claude_data.get("mcp", {}).get("enabled", True)
            if isinstance(claude_data.get("mcp"), dict)
            else claude_data.get("load_mcp", True),
            node_strategy=claude_data.get("node_strategy", "auto"),
        )

        # Load MCP config
        mcp_data = config_data.get("mcp", {})
        mcp_config = MCPConfig(
            enabled=mcp_data.get("enabled", True),
            node_strategy=mcp_data.get("node_strategy", "auto"),
            servers=mcp_data.get("servers", {}),
        )

        # Load enable_think: endpoint > global config > env
        if selected_endpoint:
            enable_think = selected_endpoint.enable_think
        else:
            enable_think = config_data.get("enable_think", False)
        if not enable_think:
            enable_think = os.getenv("WOLO_ENABLE_THINK", "").lower() in ("true", "1", "yes")

        # Load compaction config
        from wolo.compaction.config import load_compaction_config

        compaction_data = config_data.get("compaction", {})
        compaction_config = load_compaction_config(compaction_data)

        # Load path safety config
        path_safety_data = config_data.get("path_safety", {})
        path_safety_config = PathSafetyConfig(
            allowed_write_paths=[Path(p) for p in path_safety_data.get("allowed_write_paths", [])],
            max_confirmations_per_session=path_safety_data.get("max_confirmations_per_session", 10),
            audit_denied=path_safety_data.get("audit_denied", True),
            audit_log_file=Path(path_safety_data.get("audit_log_file"))
            if path_safety_data.get("audit_log_file")
            else Path.home() / ".wolo" / "path_audit.log",
        )

        return cls(
            api_key=key,
            model=model_name,
            base_url=base_url_from_config,
            temperature=temperature,
            max_tokens=max_tokens,
            mcp_servers=mcp_servers,
            enable_think=enable_think,
            claude=claude_config,
            mcp=mcp_config,
            compaction=compaction_config,
            path_safety=path_safety_config,
        )
