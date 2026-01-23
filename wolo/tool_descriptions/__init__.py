"""Tool descriptions loader for Wolo.

Tool descriptions are stored in .txt files in this directory,
similar to OpenCode's approach.
"""

from pathlib import Path

_DESCRIPTIONS_DIR = Path(__file__).parent


def load_tool_description(tool_name: str) -> str:
    """
    Load tool description from .txt file.

    Args:
        tool_name: Name of the tool (e.g., "shell", "read")

    Returns:
        Tool description string, or a fallback if file not found
    """
    desc_file = _DESCRIPTIONS_DIR / f"{tool_name}.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    # Fallback to short description
    return f"Tool: {tool_name}"


def get_description_path(tool_name: str) -> Path:
    """Get the path to a tool's description file."""
    return _DESCRIPTIONS_DIR / f"{tool_name}.txt"
