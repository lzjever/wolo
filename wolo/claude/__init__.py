"""
Claude compatibility layer for Wolo.

This module provides compatibility with Claude's configuration format,
allowing Wolo to read and use:
- Skills from ~/.wolo/skills/ (native) and ~/.claude/skills/ (compat)
- Claude MCP configuration from claude_desktop_config.json
- Claude settings from ~/.claude/settings.json
"""

from .config import ClaudeConfig, load_claude_config
from .skill_loader import ClaudeSkill, load_claude_skills, load_all_skills
from .mcp_config import load_claude_mcp_servers

__all__ = [
    "ClaudeConfig",
    "load_claude_config",
    "ClaudeSkill",
    "load_claude_skills",
    "load_all_skills",
    "load_claude_mcp_servers",
]
