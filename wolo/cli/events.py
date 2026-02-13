"""
Event handlers for CLI output.

Natural conversation style - tool calls described in natural language,
integrated into the AI's response flow.
"""

import asyncio
import logging

from wolo.cli.output import (
    format_duration,
    print_error,
    print_finish,
    print_shell_preview,
    print_text,
    print_tool_complete,
    print_tool_start,
)
from wolo.events import bus

logger = logging.getLogger(__name__)

# Watch server management
_current_session_id: str | None = None
_watch_server = None


def _on_text_delta(d: dict) -> None:
    """Handle text delta events - streaming AI response."""
    print_text(d.get("text", ""))

    # Broadcast to watch server
    _broadcast_to_watch_server(
        {"type": "text-delta", "text": d.get("text", ""), "reasoning": d.get("reasoning", False)}
    )


def _on_tool_start(d: dict) -> None:
    """Handle tool start events - print natural language description."""
    tool_name = d.get("tool", "")
    brief = d.get("brief", "")

    print_tool_start(tool_name, brief)

    logger.info(f"Tool started: {tool_name}")

    # Broadcast to watch server
    _broadcast_to_watch_server(
        {
            "type": "tool-start",
            "tool": tool_name,
            "brief": brief,
        }
    )


def _on_tool_complete(d: dict) -> None:
    """Handle tool complete events - print completion with details."""
    tool_name = d.get("tool", "")
    status = d.get("status", "unknown")
    duration = d.get("duration", 0)
    brief = d.get("brief", "")
    output = d.get("output", "")
    metadata = d.get("metadata", {})

    # Special handling for shell commands: show output preview
    if tool_name == "shell" and output:
        command = metadata.get("command", brief)
        print_shell_preview(command, output, duration)
    else:
        print_tool_complete(tool_name, status, duration, brief, output, metadata)

    duration_str = format_duration(duration)
    logger.info(f"Tool completed: {tool_name} - {status} ({duration_str})")

    # Broadcast to watch server
    _broadcast_to_watch_server(
        {
            "type": "tool-complete",
            "tool": tool_name,
            "status": status,
            "duration": duration,
            "brief": brief,
            "output": output,
            "metadata": metadata,
        }
    )


def _on_tool_result(d: dict) -> None:
    """Handle tool result events - just log, display handled in tool-complete."""
    output = d.get("output", "")
    logger.debug(f"Tool result for {d.get('tool', '')}: {output[:200] if output else ''}...")


def _on_finish(d: dict) -> None:
    """Handle finish events."""
    print_finish()

    reason = d.get("reason", "unknown")
    logger.info(f"Agent finished: {reason}")

    # Broadcast to watch server
    _broadcast_to_watch_server({"type": "finish", "reason": reason})


def _broadcast_to_watch_server(event: dict) -> None:
    """Broadcast event to watch server (async call)."""
    global _current_session_id, _watch_server

    if _current_session_id is None or _watch_server is None:
        return

    # Async call (non-blocking)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_watch_server.broadcast_event(event))
    except Exception as e:
        logger.debug(f"Failed to broadcast event: {e}")


def setup_event_handlers() -> None:
    """Setup event handlers for CLI output."""
    # Subscribe to events
    bus.subscribe("text-delta", _on_text_delta)
    bus.subscribe("tool-start", _on_tool_start)
    bus.subscribe("tool-complete", _on_tool_complete)
    bus.subscribe("tool-result", _on_tool_result)
    bus.subscribe("finish", _on_finish)


def set_watch_server(session_id: str | None, watch_server) -> None:
    """Set the watch server for event broadcasting."""
    global _current_session_id, _watch_server
    _current_session_id = session_id
    _watch_server = watch_server


def show_error(error: str) -> None:
    """Display error message."""
    print_error(error)
