"""
Natural output module for Wolo CLI.

Design philosophy:
- No echoing user input (user knows what they said)
- No AI headers (all output is from AI's perspective)
- Tool calls show meaningful content (todos, file changes, etc.)
- Input prompt only in REPL mode
- KISS: Keep It Simple, Stupid
"""

import logging
import re

logger = logging.getLogger(__name__)


def print_text(text: str) -> None:
    """Print streaming text from AI."""
    print(text, end="", flush=True)


def print_tool_start(tool: str, brief: str) -> None:
    """Print tool start indicator."""
    print("\n", end="", flush=True)


def print_tool_complete(
    tool: str,
    status: str,
    duration: float,
    brief: str = "",
    output: str = "",
    metadata: dict = None,
) -> None:
    """Print tool completion with details."""
    metadata = metadata or {}

    if status in ("completed", "success"):
        symbol = "✓"
    elif status == "error":
        symbol = "✗"
    else:
        symbol = "·"

    ms = int(duration * 1000)
    time_str = f"{ms}ms" if ms < 1000 else f"{ms / 1000:.1f}s"

    # Format output based on tool type
    if tool == "todowrite" or tool == "todoread":
        _print_todo_result(tool, output, metadata, symbol, time_str)
    elif tool == "write":
        _print_write_result(brief, output, metadata, symbol, time_str)
    elif tool == "edit":
        _print_edit_result(brief, output, metadata, symbol, time_str)
    elif tool == "read":
        _print_read_result(brief, output, metadata, symbol, time_str)
    elif tool == "glob" or tool == "grep":
        _print_search_result(tool, brief, output, metadata, symbol, time_str)
    else:
        # Default format
        clean_brief = _clean_brief(brief)
        if clean_brief:
            print(f"  {symbol} {clean_brief} ({time_str})")
        else:
            print(f"  {symbol} {tool} ({time_str})")


def _print_todo_result(tool: str, output: str, metadata: dict, symbol: str, time_str: str):
    """Print todo tool result with todo items."""
    todos = metadata.get("todos", [])

    if todos:
        print(f"  {symbol} Todo ({len(todos)} items, {time_str}):")
        for t in todos[:5]:  # Show max 5 items
            status_sym = {"pending": "○", "in_progress": "◐", "completed": "●"}
            content = t.get("content", "")[:60]
            status = t.get("status", "pending")
            sym = status_sym.get(status, "○")
            print(f"    {sym} {content}")
        if len(todos) > 5:
            print(f"    ... and {len(todos) - 5} more")
    else:
        print(f"  {symbol} Todo updated ({time_str})")


def _print_write_result(brief: str, output: str, metadata: dict, symbol: str, time_str: str):
    """Print write tool result."""
    # Extract file path from brief or output
    file_path = brief or ""
    size = metadata.get("size", 0)

    if size > 0:
        size_str = _format_size(size)
        print(f"  {symbol} Wrote {file_path} ({size_str}, {time_str})")
    else:
        print(f"  {symbol} Wrote {file_path} ({time_str})")


def _print_edit_result(brief: str, output: str, metadata: dict, symbol: str, time_str: str):
    """Print edit tool result with diff info."""
    file_path = brief or ""
    diff_lines = metadata.get("diff_lines", 0)
    additions = metadata.get("additions", 0)
    deletions = metadata.get("deletions", 0)

    if diff_lines or additions or deletions:
        changes = []
        if additions:
            changes.append(f"+{additions}")
        if deletions:
            changes.append(f"-{deletions}")
        change_str = ", ".join(changes)
        print(f"  {symbol} Edited {file_path} ({change_str}, {time_str})")
    else:
        print(f"  {symbol} Edited {file_path} ({time_str})")


def _print_read_result(brief: str, output: str, metadata: dict, symbol: str, time_str: str):
    """Print read tool result."""
    file_path = brief or ""
    lines = metadata.get("total_lines", 0) or metadata.get("showing_lines", 0)

    if lines:
        print(f"  {symbol} Read {file_path} ({lines} lines, {time_str})")
    else:
        print(f"  {symbol} Read {file_path} ({time_str})")


def _print_search_result(
    tool: str, brief: str, output: str, metadata: dict, symbol: str, time_str: str
):
    """Print search (glob/grep) result."""
    matches = metadata.get("matches", [])
    count = metadata.get("count", len(matches))

    if tool == "glob":
        if count:
            print(f"  {symbol} Found {count} files ({time_str}):")
            for m in matches[:5]:
                print(f"    {m}")
            if count > 5:
                print(f"    ... and {count - 5} more")
        else:
            print(f"  {symbol} No files found ({time_str})")
    else:  # grep
        if count:
            print(f"  {symbol} Found {count} matches ({time_str})")
        else:
            print(f"  {symbol} No matches found ({time_str})")


def print_shell_preview(command: str, output: str, duration: float) -> None:
    """Print shell command with output preview."""
    ms = int(duration * 1000)
    time_str = f"{ms}ms" if ms < 1000 else f"{ms / 1000:.1f}s"

    # Truncate long commands
    display_cmd = command if len(command) <= 50 else command[:47] + "..."
    print(f"  $ {display_cmd}")

    # Show output preview (up to 3 lines)
    lines = [ln for ln in output.strip().split("\n") if ln.strip()]
    display_lines = lines[:3]

    for line in display_lines:
        if len(line) > 70:
            line = line[:67] + "..."
        print(f"    {line}")

    if len(lines) > 3:
        print(f"    ... ({len(lines) - 3} more lines)")

    print(f"  ✓ ({time_str})")


def print_error(error: str) -> None:
    """Print error message in natural style."""
    print(f"\n  ✗ Error: {error}")


def print_finish() -> None:
    """Print final newline after AI finishes speaking."""
    print()


def print_repl_prompt() -> None:
    """Print REPL input prompt."""
    print()
    print("> ", end="", flush=True)


# --- Helpers ---


def _clean_brief(brief: str) -> str:
    """Clean up brief description - remove emojis, trim whitespace."""
    brief = re.sub(r"[\U0001F300-\U0001F9FF]", "", brief)
    brief = re.sub(r"[📋📝📄📁🔍💡🎯⚡🔄📦]", "", brief)
    brief = " ".join(brief.split())
    return brief.strip()


def _format_size(size: int) -> str:
    """Format file size in human readable format."""
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    else:
        return f"{size / 1024 / 1024:.1f}MB"


def _get_tool_display(tool: str) -> str:
    """Get short, clean display name for a tool."""
    names = {
        "read": "read",
        "write": "write",
        "edit": "edit",
        "glob": "find",
        "grep": "search",
        "shell": "$",
        "web_fetch": "fetch",
        "web_search": "search",
        "task": "task",
        "todowrite": "todo",
        "todoread": "todo",
        "memory_save": "save",
        "memory_load": "load",
        "question": "ask",
        "batch": "batch",
    }
    return names.get(tool, tool)


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds >= 1:
        return f"{seconds:.1f}s"
    else:
        return f"{int(seconds * 1000)}ms"
