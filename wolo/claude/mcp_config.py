"""
Claude MCP configuration reader.

Reads MCP server configuration from Claude Desktop's config file:
- Linux: ~/.config/claude/claude_desktop_config.json
- macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
- Windows: %APPDATA%/Claude/claude_desktop_config.json
"""

import json
import logging
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """
    Configuration for a single MCP server.
    
    Supports two types:
    - local: Stdio transport with command/args
    - remote: HTTP/SSE transport with URL
    """
    
    name: str
    
    # Type: "local" or "remote"
    type: str = "local"
    
    # Local server config
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    
    # Remote server config
    url: Optional[str] = None
    headers: dict[str, str] = field(default_factory=dict)
    auth_token: Optional[str] = None
    
    # Common
    enabled: bool = True
    timeout: int = 60000  # ms
    
    def requires_node(self) -> bool:
        """Check if this server requires Node.js."""
        if self.type == "remote":
            return False
        return self.command in ("node", "npx", "npm")
    
    def is_remote(self) -> bool:
        """Check if this is a remote server."""
        return self.type == "remote"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "timeout": self.timeout,
        }
        
        if self.type == "local":
            result.update({
                "command": self.command,
                "args": self.args,
                "env": self.env,
            })
        else:  # remote
            result.update({
                "url": self.url,
                "headers": self.headers,
            })
            if self.auth_token:
                result["auth_token"] = "***"  # Don't expose token
        
        return result


def get_claude_desktop_config_paths() -> list[Path]:
    """Get possible paths for Claude Desktop config file."""
    paths = []
    
    system = platform.system()
    
    if system == "Linux":
        paths.append(Path.home() / ".config" / "claude" / "claude_desktop_config.json")
    elif system == "Darwin":  # macOS
        paths.append(Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            paths.append(Path(appdata) / "Claude" / "claude_desktop_config.json")
    
    # Also check common alternative locations
    paths.append(Path.home() / ".claude" / "claude_desktop_config.json")
    
    return paths


def load_claude_mcp_servers(config_path: Optional[Path] = None) -> dict[str, MCPServerConfig]:
    """
    Load MCP server configurations from Claude Desktop config.
    
    Args:
        config_path: Optional explicit path to config file
    
    Returns:
        Dictionary mapping server name to MCPServerConfig
    """
    # Find config file
    if config_path:
        paths = [config_path]
    else:
        paths = get_claude_desktop_config_paths()
    
    config_data = None
    used_path = None
    
    for path in paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                used_path = path
                break
            except Exception as e:
                logger.warning(f"Failed to read {path}: {e}")
    
    if config_data is None:
        logger.debug("No Claude Desktop config found")
        return {}
    
    logger.debug(f"Loading MCP config from {used_path}")
    
    # Parse mcpServers section
    servers_data = config_data.get("mcpServers", {})
    servers = {}
    
    for name, server_config in servers_data.items():
        try:
            servers[name] = MCPServerConfig(
                name=name,
                command=server_config.get("command", ""),
                args=server_config.get("args", []),
                env=server_config.get("env", {}),
                enabled=True,
            )
            logger.debug(f"Loaded MCP server config: {name}")
        except Exception as e:
            logger.warning(f"Failed to parse MCP server {name}: {e}")
    
    logger.info(f"Loaded {len(servers)} MCP server configs from Claude Desktop")
    return servers


def merge_mcp_configs(
    claude_servers: dict[str, MCPServerConfig],
    wolo_servers: dict[str, MCPServerConfig],
) -> dict[str, MCPServerConfig]:
    """
    Merge MCP server configurations.
    
    Wolo configs take precedence over Claude configs.
    
    Args:
        claude_servers: Servers from Claude Desktop config
        wolo_servers: Servers from Wolo config
    
    Returns:
        Merged server configurations
    """
    merged = dict(claude_servers)
    merged.update(wolo_servers)  # Wolo configs override
    return merged
