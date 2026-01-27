"""
Shared formatting utilities for output renderers.

Provides common formatting functions used by multiple renderers.
"""

from typing import Any


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable form.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "123ms" or "1.5s" or "2m 30s"
    """
    if seconds < 0.001:
        return "<1ms"
    elif seconds < 1:
        return f"{int(seconds * 1000)}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        if secs > 0:
            return f"{minutes}m {secs}s"
        return f"{minutes}m"


def truncate(text: str, max_len: int = 60, suffix: str = "...") -> str:
    """
    Truncate text with suffix.

    Args:
        text: Text to truncate
        max_len: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def count_lines(text: str) -> int:
    """Count non-empty lines in text."""
    if not text:
        return 0
    return len([ln for ln in text.split("\n") if ln.strip()])


def format_changes(additions: int, deletions: int) -> str:
    """
    Format file changes summary.

    Args:
        additions: Number of added lines
        deletions: Number of deleted lines

    Returns:
        Formatted string like "+3 -2"
    """
    parts = []
    if additions > 0:
        parts.append(f"+{additions}")
    if deletions > 0:
        parts.append(f"-{deletions}")
    return " ".join(parts) if parts else "no changes"


def get_status_icon(status: str, use_color: bool = True) -> tuple[str, str]:
    """
    Get status icon and color.

    Args:
        status: Status string ('completed', 'error', etc.)
        use_color: Whether to return color codes

    Returns:
        Tuple of (icon, color_code)
    """
    icons = {
        "completed": ("✓", "\033[92m" if use_color else ""),
        "error": ("✗", "\033[91m" if use_color else ""),
        "partial": ("○", "\033[93m" if use_color else ""),
        "running": ("◐", "\033[96m" if use_color else ""),
        "pending": ("~", "\033[90m" if use_color else ""),
        "interrupted": ("⚡", "\033[93m" if use_color else ""),
        "timeout": ("⏱", "\033[93m" if use_color else ""),
    }
    return icons.get(status, ("?", ""))


def get_tool_icon(tool_name: str) -> str:
    """
    Get icon for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Icon string
    """
    icons = {
        "shell": "$",
        "read": "📄",
        "write": "📝",
        "edit": "✏️",
        "multiedit": "✏️",
        "grep": "🔍",
        "glob": "📂",
        "task": "🤖",
        "todowrite": "📋",
        "todoread": "📋",
        "question": "❓",
        "batch": "⚡",
        "skill": "📚",
    }
    return icons.get(tool_name, "▶")


def format_file_path(path: str, max_len: int = 50) -> str:
    """
    Format file path for display, truncating from the start if needed.

    Args:
        path: File path
        max_len: Maximum display length

    Returns:
        Formatted path
    """
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3) :]


def format_diff_stats(metadata: dict[str, Any]) -> str:
    """
    Format diff statistics from metadata.

    Args:
        metadata: Tool metadata containing additions/deletions

    Returns:
        Formatted diff stats string
    """
    additions = metadata.get("additions", 0)
    deletions = metadata.get("deletions", 0)

    if additions == 0 and deletions == 0:
        return "no changes"

    return format_changes(additions, deletions)


def format_search_stats(metadata: dict[str, Any]) -> str:
    """
    Format search result statistics.

    Args:
        metadata: Tool metadata containing matches count

    Returns:
        Formatted search stats string
    """
    matches = metadata.get("matches", 0)
    if matches == 0:
        return "no matches"
    elif matches == 1:
        return "1 match"
    else:
        return f"{matches} matches"


def wrap_text(text: str, width: int, indent: str = "") -> list[str]:
    """
    Wrap text to specified width.

    Args:
        text: Text to wrap
        width: Maximum line width
        indent: Prefix for each line

    Returns:
        List of wrapped lines
    """
    import textwrap

    effective_width = width - len(indent)
    if effective_width <= 10:
        effective_width = 10

    wrapper = textwrap.TextWrapper(
        width=effective_width,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=True,
    )

    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip():
            lines.extend(wrapper.wrap(paragraph))
        else:
            lines.append(indent)

    return lines
