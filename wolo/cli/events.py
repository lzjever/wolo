"""Event handlers for CLI output."""

import asyncio
import logging

from wolo.events import bus

logger = logging.getLogger(__name__)

# ANSI color codes
RESET = "\033[0m"
DIM = "\033[90m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"

# Track tool start info for combining with complete event
_pending_tool_starts: dict[str, dict] = {}

# Watch server management
_current_session_id: str | None = None
_watch_server = None


def _on_text_delta(d: dict) -> None:
    """Handle text delta events."""
    if d.get("reasoning"):
        print(f"{DIM}{d['text']}{RESET}", end="", flush=True)
    else:
        print(d["text"], end="", flush=True)

    # 广播到 watch 服务器（如果存在）
    _broadcast_to_watch_server(
        {"type": "text-delta", "text": d.get("text", ""), "reasoning": d.get("reasoning", False)}
    )


def _on_tool_start(d: dict) -> None:
    """Handle tool start events - store for combining with complete."""
    tool_name = d.get("tool", "")
    _pending_tool_starts[tool_name] = d
    logger.info(f"Tool started: {tool_name}")

    # 广播到 watch 服务器
    _broadcast_to_watch_server(
        {"type": "tool-start", "tool": tool_name, "brief": d.get("brief", tool_name)}
    )


def _on_tool_complete(d: dict) -> None:
    """Handle tool complete events - show combined start+result in one line."""
    tool_name = d.get("tool", "")
    status = d.get("status", "unknown")
    duration = d.get("duration", 0)
    result_brief = d.get("brief", "")

    # Get start info
    start_info = _pending_tool_starts.pop(tool_name, {})
    start_brief = start_info.get("brief", tool_name)

    # Format duration
    if duration >= 1:
        duration_str = f"{duration:.1f}s"
    else:
        duration_str = f"{int(duration * 1000)}ms"

    # Status indicator and color
    if status == "completed":
        status_icon = "✓"
        status_color = GREEN
    elif status == "error":
        status_icon = "✗"
        status_color = RED
    else:
        status_icon = "○"
        status_color = YELLOW

    # Single line output: ▶ $ git status → ✓ 3 lines (120ms)
    # Or for errors: ▶ $ invalid_cmd → ✗ command not found (5ms)
    if result_brief:
        print(
            f"\n{CYAN}▶{RESET} {start_brief} {DIM}→{RESET} {status_color}{status_icon} {result_brief}{RESET} {DIM}({duration_str}){RESET}",
            flush=True,
        )
    else:
        print(
            f"\n{CYAN}▶{RESET} {start_brief} {DIM}→{RESET} {status_color}{status_icon}{RESET} {DIM}({duration_str}){RESET}",
            flush=True,
        )

    # Show output if tool spec says so
    if d.get("show_output") and d.get("output"):
        # Indent output for clarity
        output_lines = d["output"].strip().split("\n")
        for line in output_lines[:10]:  # Limit to 10 lines
            print(f"  {DIM}{line}{RESET}", flush=True)
        if len(output_lines) > 10:
            print(f"  {DIM}... ({len(output_lines) - 10} more lines){RESET}", flush=True)

    logger.info(f"Tool completed: {tool_name} - {status} ({duration_str})")

    # 广播到 watch 服务器
    _broadcast_to_watch_server(
        {
            "type": "tool-complete",
            "tool": tool_name,
            "status": status,
            "duration": duration,
            "brief": result_brief,
        }
    )


def _on_tool_result(d: dict) -> None:
    """Handle tool result events - just log, display handled in tool-complete."""
    output = d.get("output", "")
    logger.debug(f"Tool result for {d.get('tool', '')}: {output[:200] if output else ''}...")


def _on_finish(d: dict) -> None:
    """Handle finish events."""
    # Don't print separator here - it will be printed at program end
    # This avoids duplicate separators when multiple finish events are received
    logger.info(f"Agent finished: {d.get('reason', 'unknown')}")

    # 广播到 watch 服务器
    _broadcast_to_watch_server({"type": "finish", "reason": d.get("reason", "unknown")})


def _broadcast_to_watch_server(event: dict) -> None:
    """向 watch 服务器广播事件（异步调用）。"""
    global _current_session_id, _watch_server

    if _current_session_id is None or _watch_server is None:
        return

    # 异步调用（不阻塞）
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_watch_server.broadcast_event(event))
    except Exception as e:
        logger.debug(f"Failed to broadcast event: {e}")


def setup_event_handlers() -> None:
    """Setup event handlers for CLI output."""
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
