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
class Config:
    api_key: str
    model: str
    base_url: str
    temperature: float
    max_tokens: int
    mcp_servers: list[str] = field(default_factory=list)
    debug_llm_file: str | None = None  # File to write LLM requests/responses for debugging
    debug_full_dir: str | None = None  # Directory to save full request/response logs
    enable_think: bool = False  # Enable GLM thinking mode

    # Claude compatibility
    claude: ClaudeCompatConfig = field(default_factory=ClaudeCompatConfig)

    # MCP configuration
    mcp: MCPConfig = field(default_factory=MCPConfig)

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
                )
            )
        return endpoints

    @classmethod
    def list_endpoints(cls) -> list[str]:
        """List available endpoint names."""
        endpoints = cls._get_endpoints()
        return [ep.name for ep in endpoints]

    @classmethod
    def from_env(cls, api_key: str | None = None, endpoint_name: str | None = None) -> "Config":
        # Try to load from config file first
        endpoints = cls._get_endpoints()
        config_data = cls._load_config_file()

        # Determine which endpoint to use
        selected_endpoint: EndpointConfig | None = None

        if endpoint_name:
            # User specified endpoint via --endpoint
            for ep in endpoints:
                if ep.name == endpoint_name:
                    selected_endpoint = ep
                    break
            if not selected_endpoint:
                raise ValueError(
                    f"Endpoint '{endpoint_name}' not found in config file. Available: {', '.join(ep.name for ep in endpoints)}"
                )
        elif endpoints:
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
            model = selected_endpoint.model
            base_url = selected_endpoint.api_base
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
            model = os.getenv("WOLO_MODEL", "glm-4")
            base_url = os.getenv("WOLO_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
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

        # Load enable_think from config or env
        enable_think = config_data.get("enable_think", False)
        if not enable_think:
            enable_think = os.getenv("WOLO_ENABLE_THINK", "").lower() in ("true", "1", "yes")

        # Load compaction config
        from wolo.compaction.config import load_compaction_config

        compaction_data = config_data.get("compaction", {})
        compaction_config = load_compaction_config(compaction_data)

        return cls(
            api_key=key,
            model=model,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            mcp_servers=mcp_servers,
            enable_think=enable_think,
            claude=claude_config,
            mcp=mcp_config,
            compaction=compaction_config,
        )
