"""
Default output renderer.

Provides the standard interactive output with colors and icons.
This is similar to the current wolo behavior but with improvements.

Output format:
    🤖 AgentName: [streaming text...]

    ▶ $ git status → ✓ 3 lines (120ms)
    ▶ 📄 src/file.py → ✓ 45 lines (32ms)
    ▶ ✏️  src/file.py → ✓ +3 -2 (28ms)
"""

from typing import Any

from wolo.cli.output.base import OutputConfig, OutputRenderer
from wolo.cli.output.formatters import (
    format_diff_stats,
    format_duration,
    format_search_stats,
    get_status_icon,
    truncate,
)


class DefaultRenderer(OutputRenderer):
    """Default output renderer with colors and single-line tool output."""

    def __init__(self, config: OutputConfig):
        super().__init__(config)
        self._pending_tools: dict[str, dict] = {}
        self._agent_name: str = ""
        self._in_reasoning: bool = False  # Track reasoning state for <think> tags

    def _close_reasoning_tag(self) -> None:
        """Close <think> tag if currently in reasoning mode (only when no color)."""
        if self._in_reasoning and not self.config.use_color:
            print("</think>", flush=True)
            self._in_reasoning = False

    def on_agent_start(self, agent_name: str) -> None:
        """Display agent name prompt."""
        self._agent_name = agent_name
        print(f"{self.BLUE}{agent_name}{self.RESET}: ", end="", flush=True)

    def on_text_delta(self, text: str, is_reasoning: bool = False) -> None:
        """Stream text output."""
        if is_reasoning:
            if self.config.show_reasoning:
                if self.config.use_color:
                    # Use dim color for reasoning
                    print(f"{self.DIM}{text}{self.RESET}", end="", flush=True)
                else:
                    # Use <think> tags when no color
                    if not self._in_reasoning:
                        print("<think>", flush=True)
                        self._in_reasoning = True
                    print(text, end="", flush=True)
        else:
            # Close reasoning tag if transitioning from reasoning to regular text
            self._close_reasoning_tag()
            print(text, end="", flush=True)

    def on_tool_call_streaming(
        self,
        tool_name: str,
        tool_id: str,
        length: int = 0,
    ) -> None:
        """Show streaming indicator when LLM starts generating tool call arguments."""
        # Store current tool info for progress updates
        self._streaming_tool = {
            "name": tool_name,
            "id": tool_id,
        }

        # Clear any previous streaming line
        print("\r" + " " * 100 + "\r", end="")

        # Build concise display string
        tool_icons = {
            "write": "📝",
            "edit": "✏️",
            "read": "📄",
            "shell": "$",
            "grep": "🔍",
        }
        icon = tool_icons.get(tool_name, "▶")

        print(
            f"{self.DIM}~ {icon} {tool_name} ({length} chars)...{self.RESET}",
            end="",
            flush=True,
        )

    def on_tool_call_progress(
        self,
        index: int,
        length: int,
    ) -> None:
        """Update progress display as more arguments are generated."""
        if not hasattr(self, "_streaming_tool") or not self._streaming_tool:
            return

        tool_name = self._streaming_tool.get("name", "")
        tool_icons = {
            "write": "📝",
            "edit": "✏️",
            "read": "📄",
            "shell": "$",
            "grep": "🔍",
        }
        icon = tool_icons.get(tool_name, "▶")

        # Clear and update
        print("\r" + " " * 100 + "\r", end="")
        print(
            f"{self.DIM}~ {icon} {tool_name} ({length} chars)...{self.RESET}",
            end="",
            flush=True,
        )

    def on_tool_start(
        self,
        tool_name: str,
        params: dict[str, Any],
        brief: str,
        icon: str = "▶",
    ) -> None:
        """Store tool start info for combining with complete event."""
        self._pending_tools[tool_name] = {
            "brief": brief,
            "icon": icon,
            "params": params,
        }

    def on_tool_complete(
        self,
        tool_name: str,
        status: str,
        duration: float,
        brief: str = "",
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Display combined tool start + result on single line."""
        metadata = metadata or {}

        # Clear any streaming progress line first
        if hasattr(self, "_streaming_tool") and self._streaming_tool:
            print("\r" + " " * 100 + "\r", end="")
            self._streaming_tool = None

        # Get start info (brief already contains icon from tool_registry.format_brief())
        start_info = self._pending_tools.pop(tool_name, {})
        start_brief = start_info.get("brief", tool_name)

        # Format duration
        duration_str = format_duration(duration)

        # Get status icon and color
        status_icon, status_color = get_status_icon(status, self.config.use_color)
        if not self.config.use_color:
            status_color = ""

        # Format result brief based on tool type
        result_brief = self._format_result_brief(tool_name, status, brief, output, metadata)

        # Build output line
        # Format: ▶ $ git status → ✓ 3 lines (120ms)
        if result_brief:
            print(
                f"\n{self.CYAN}▶{self.RESET} {start_brief} "
                f"{self.DIM}→{self.RESET} "
                f"{status_color}{status_icon} {result_brief}{self.RESET} "
                f"{self.DIM}({duration_str}){self.RESET}",
                flush=True,
            )
        else:
            print(
                f"\n{self.CYAN}▶{self.RESET} {start_brief} "
                f"{self.DIM}→{self.RESET} "
                f"{status_color}{status_icon}{self.RESET} "
                f"{self.DIM}({duration_str}){self.RESET}",
                flush=True,
            )

    def _format_result_brief(
        self,
        tool_name: str,
        status: str,
        brief: str,
        output: str | None,
        metadata: dict[str, Any],
    ) -> str:
        """Format brief result description based on tool type."""
        if status == "error":
            # For errors, show truncated error message
            if output:
                lines = output.strip().split("\n")
                return truncate(lines[-1] if lines else output, 50)
            return "failed"

        # Tool-specific result formatting
        if tool_name in ("edit", "write", "multiedit"):
            return format_diff_stats(metadata)

        if tool_name in ("grep", "glob"):
            return format_search_stats(metadata)

        if tool_name == "read":
            total_lines = metadata.get("total_lines", 0)
            if total_lines:
                return f"{total_lines} lines"
            return "done"

        if tool_name == "shell":
            # For shell, show line count or brief output
            if output:
                lines = [ln for ln in output.strip().split("\n") if ln.strip()]
                if not lines:
                    return "(no output)"
                elif len(lines) == 1:
                    return truncate(lines[0], 50)
                else:
                    return f"{len(lines)} lines"
            return "done"

        if tool_name == "todowrite":
            todos = metadata.get("todos", [])
            if todos:
                completed = len([t for t in todos if t.get("status") == "completed"])
                return f"{completed}/{len(todos)} done"
            return "updated"

        if tool_name == "task":
            return metadata.get("finish_reason", "done")

        # Default
        return brief if brief else "done"

    def on_finish(self, reason: str) -> None:
        """Handle agent finish."""
        # Close any open reasoning tag
        self._close_reasoning_tag()
        # Add final newline
        print()

    def on_error(self, error: str) -> None:
        """Display error message."""
        print(f"\n{self.RED}Error: {error}{self.RESET}", flush=True)

    def on_shortcuts_hint(self) -> None:
        """Display keyboard shortcuts hint."""
        print(
            f"{self.DIM}[快捷键: ^A:插话 ^B:打断 ^P:暂停 ^S:Shell ^L:MCP ^H:帮助 ^C:退出]{self.RESET}",
            flush=True,
        )
        print()

    def on_session_info(self, session_id: str, resumed: bool = False) -> None:
        """Display session information."""
        if resumed:
            print(f"{self.DIM}Resumed session: {session_id[:8]}...{self.RESET}")
        else:
            print(f"{self.DIM}Session: {session_id[:8]}...{self.RESET}")
