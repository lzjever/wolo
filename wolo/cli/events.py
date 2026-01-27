"""Event handlers for CLI output.

This module provides event handlers that connect the agent loop events
to the output rendering system. It supports different output styles
(minimal, default, verbose) through the OutputRenderer abstraction.
"""

import asyncio
import logging
from typing import Any

from wolo.events import bus

logger = logging.getLogger(__name__)

# Import output module (late import to avoid circular dependency)
_renderer = None
_output_config = None

# Legacy ANSI color codes (for backward compatibility with watch mode)
RESET = "\033[0m"
DIM = "\033[90m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"

# Watch server management
_current_session_id: str | None = None
_watch_server = None


def _get_renderer():
    """Get the current renderer, creating default if needed."""
    global _renderer
    if _renderer is None:
        from wolo.cli.output import OutputConfig, get_renderer

        _renderer = get_renderer(OutputConfig())
    return _renderer


def _on_text_delta(d: dict) -> None:
    """Handle text delta events."""
    renderer = _get_renderer()
    renderer.on_text_delta(d.get("text", ""), d.get("reasoning", False))

    # Broadcast to watch server
    _broadcast_to_watch_server(
        {"type": "text-delta", "text": d.get("text", ""), "reasoning": d.get("reasoning", False)}
    )


def _on_tool_call_streaming(d: dict) -> None:
    """Handle tool call streaming events (LLM started generating tool arguments)."""
    renderer = _get_renderer()
    renderer.on_tool_call_streaming(
        tool_name=d.get("tool", ""),
        tool_id=d.get("id", ""),
        length=d.get("length", 0),
    )

    # Broadcast to watch server
    _broadcast_to_watch_server(
        {
            "type": "tool-call-streaming",
            "tool": d.get("tool", ""),
            "id": d.get("id", ""),
            "length": d.get("length", 0),
        }
    )


def _on_tool_call_progress(d: dict) -> None:
    """Handle tool call progress events (LLM is generating more arguments)."""
    renderer = _get_renderer()
    renderer.on_tool_call_progress(
        index=d.get("index", 0),
        length=d.get("length", 0),
    )

    # Broadcast to watch server
    _broadcast_to_watch_server(
        {
            "type": "tool-call-progress",
            "index": d.get("index", 0),
            "length": d.get("length", 0),
        }
    )


def _on_tool_start(d: dict) -> None:
    """Handle tool start events."""
    renderer = _get_renderer()
    renderer.on_tool_start(
        tool_name=d.get("tool", ""),
        params=d.get("params", {}),
        brief=d.get("brief", d.get("tool", "")),
        icon=d.get("icon", "▶"),
    )

    logger.info(f"Tool started: {d.get('tool', '')}")

    # Broadcast to watch server
    _broadcast_to_watch_server(
        {
            "type": "tool-start",
            "tool": d.get("tool", ""),
            "brief": d.get("brief", d.get("tool", "")),
        }
    )


def _on_tool_complete(d: dict) -> None:
    """Handle tool complete events."""
    renderer = _get_renderer()
    renderer.on_tool_complete(
        tool_name=d.get("tool", ""),
        status=d.get("status", "unknown"),
        duration=d.get("duration", 0),
        brief=d.get("brief", ""),
        output=d.get("output"),
        metadata=d.get("metadata", {}),
    )

    tool_name = d.get("tool", "")
    status = d.get("status", "unknown")
    duration = d.get("duration", 0)
    duration_str = f"{duration:.1f}s" if duration >= 1 else f"{int(duration * 1000)}ms"
    logger.info(f"Tool completed: {tool_name} - {status} ({duration_str})")

    # Broadcast to watch server
    _broadcast_to_watch_server(
        {
            "type": "tool-complete",
            "tool": tool_name,
            "status": status,
            "duration": duration,
            "brief": d.get("brief", ""),
        }
    )


def _on_tool_result(d: dict) -> None:
    """Handle tool result events - just log, display handled in tool-complete."""
    output = d.get("output", "")
    logger.debug(f"Tool result for {d.get('tool', '')}: {output[:200] if output else ''}...")


def _on_finish(d: dict) -> None:
    """Handle finish events."""
    renderer = _get_renderer()
    renderer.on_finish(d.get("reason", "unknown"))

    logger.info(f"Agent finished: {d.get('reason', 'unknown')}")

    # Broadcast to watch server
    _broadcast_to_watch_server({"type": "finish", "reason": d.get("reason", "unknown")})


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


def setup_event_handlers(output_config: Any = None) -> None:
    """
    Setup event handlers for CLI output.

    Args:
        output_config: OutputConfig instance for output rendering.
                      If None, uses default configuration.
    """
    global _renderer, _output_config

    # Create renderer with config
    if output_config is not None:
        from wolo.cli.output import get_renderer

        _output_config = output_config
        _renderer = get_renderer(output_config)
    else:
        # Use default config
        from wolo.cli.output import OutputConfig, get_renderer

        _output_config = OutputConfig()
        _renderer = get_renderer(_output_config)

    # Subscribe to events
    bus.subscribe("text-delta", _on_text_delta)
    bus.subscribe("tool-call-streaming", _on_tool_call_streaming)
    bus.subscribe("tool-call-progress", _on_tool_call_progress)
    bus.subscribe("tool-start", _on_tool_start)
    bus.subscribe("tool-complete", _on_tool_complete)
    bus.subscribe("tool-result", _on_tool_result)
    bus.subscribe("finish", _on_finish)


def set_watch_server(session_id: str | None, watch_server) -> None:
    """Set the watch server for event broadcasting."""
    global _current_session_id, _watch_server
    _current_session_id = session_id
    _watch_server = watch_server


def get_current_renderer():
    """Get the current output renderer."""
    return _get_renderer()


def show_shortcuts_hint() -> None:
    """Display keyboard shortcuts hint using current renderer."""
    renderer = _get_renderer()
    renderer.on_shortcuts_hint()


def show_session_info(session_id: str, resumed: bool = False) -> None:
    """Display session information using current renderer."""
    renderer = _get_renderer()
    renderer.on_session_info(session_id, resumed)


def show_agent_start(agent_name: str) -> None:
    """Display agent start prompt using current renderer."""
    renderer = _get_renderer()
    renderer.on_agent_start(agent_name)


def show_error(error: str) -> None:
    """Display error message using current renderer."""
    renderer = _get_renderer()
    renderer.on_error(error)
