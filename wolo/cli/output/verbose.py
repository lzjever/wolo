"""
Verbose output renderer.

Provides detailed output with diffs, full command output, etc.
Useful for debugging and learning.

Output format:
    🤖 AgentName: [streaming text...]

    ┌─ 📄 Read src/file.py ✓ (32ms)
    │  lines: 45, offset: 0
    └──────────────────────────────────

    ┌─ ✏️  Edit src/file.py ✓ (28ms)
    │  @@ -21,7 +21,9 @@
    │  -def process(data: str) -> dict:
    │  +def process(data: Optional[str]) -> dict:
    │  +    if data is None:
    │  +        return {}
    │
    │  Changes: +3 -2 lines
    └──────────────────────────────────
"""

import time
from typing import Any

from wolo.cli.output.base import OutputConfig, OutputRenderer
from wolo.cli.output.formatters import (
    format_duration,
    get_status_icon,
)


class VerboseRenderer(OutputRenderer):
    """Verbose output renderer with detailed tool output."""

    # Box drawing characters
    BOX_TOP_LEFT = "┌"
    BOX_BOTTOM_LEFT = "└"
    BOX_VERTICAL = "│"
    BOX_HORIZONTAL = "─"

    def __init__(self, config: OutputConfig):
        super().__init__(config)
        self._pending_tools: dict[str, dict] = {}
        self._agent_name: str = ""
        self._current_tool: dict | None = None
        self._in_reasoning: bool = False  # Track reasoning state for <think> tags

    def _close_reasoning_tag(self) -> None:
        """Close <think> tag if currently in reasoning mode (only when no color)."""
        if self._in_reasoning and not self.config.use_color:
            print("</think>", flush=True)
            self._in_reasoning = False

    def on_agent_start(self, agent_name: str) -> None:
        """Display agent name prompt."""
        self._agent_name = agent_name
        print(f"\n{self.BLUE}{agent_name}{self.RESET}: ", end="", flush=True)

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

        # Build display string
        tool_icons = {
            "write": "📝",
            "edit": "✏️",
            "read": "📄",
            "shell": "$",
            "grep": "🔍",
            "glob": "📂",
            "task": "🤖",
            "todowrite": "📋",
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
            "glob": "📂",
            "task": "🤖",
            "todowrite": "📋",
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
        """Show tool as pending."""
        self._current_tool = {
            "name": tool_name,
            "brief": brief,
            "params": params,
            "start_time": time.time(),
        }
        # Clear any streaming progress line before showing new line
        if hasattr(self, "_streaming_tool") and self._streaming_tool:
            print("\r" + " " * 100 + "\r", end="")
            self._streaming_tool = None
        # Show pending indicator
        print(f"\n{self.DIM}~ {brief}...{self.RESET}", end="", flush=True)

    def on_tool_complete(
        self,
        tool_name: str,
        status: str,
        duration: float,
        brief: str = "",
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Render tool output in a bordered block."""
        metadata = metadata or {}

        # Clear pending line
        print("\r" + " " * 80 + "\r", end="")

        # Get tool info
        start_info = self._current_tool or {}
        start_brief = start_info.get("brief", tool_name)
        self._current_tool = None

        # Render based on tool type
        self._render_tool_block(tool_name, start_brief, status, duration, output, metadata)

    def _render_tool_block(
        self,
        tool_name: str,
        start_brief: str,
        status: str,
        duration: float,
        output: str | None,
        metadata: dict[str, Any],
    ) -> None:
        """Render a tool output block with border."""
        # Note: start_brief already contains icon from tool_registry.format_brief()
        status_icon, status_color = get_status_icon(status, self.config.use_color)
        if not self.config.use_color:
            status_color = ""
        dur_str = format_duration(duration)

        # Header line (no extra icon - brief already has it)
        print(
            f"{self.BORDER}{self.BOX_TOP_LEFT}{self.BOX_HORIZONTAL} "
            f"{start_brief} "
            f"{status_color}{status_icon}{self.RESET} "
            f"{self.DIM}({dur_str}){self.RESET}"
        )

        # Content based on tool type
        if status == "error":
            self._render_error_content(output)
        elif tool_name in ("edit", "write") and metadata.get("diff"):
            self._render_diff_content(metadata["diff"], metadata)
        elif tool_name == "shell":
            self._render_shell_content(output, metadata)
        elif tool_name in ("grep", "glob"):
            self._render_search_content(output, metadata)
        elif tool_name == "read":
            self._render_read_content(output, metadata)
        elif tool_name in ("todowrite", "todoread"):
            self._render_todo_content(output, metadata)
        elif output:
            self._render_generic_content(output)

        # Footer line
        width = min(40, self.get_terminal_width() - 4)
        print(f"{self.BORDER}{self.BOX_BOTTOM_LEFT}{self.BOX_HORIZONTAL * width}{self.RESET}\n")

    def _render_line(self, text: str, color: str = "") -> None:
        """Render a single line with border prefix."""
        print(f"{self.BORDER}{self.BOX_VERTICAL}{self.RESET}  {color}{text}{self.RESET}")

    def _render_error_content(self, output: str | None) -> None:
        """Render error output."""
        if output:
            lines = output.strip().split("\n")
            for line in lines[:10]:
                self._render_line(line, self.RED)
            if len(lines) > 10:
                self._render_line(f"... ({len(lines) - 10} more lines)", self.DIM)

    def _render_diff_content(self, diff_text: str, metadata: dict[str, Any]) -> None:
        """Render diff output with syntax highlighting."""
        lines = diff_text.strip().split("\n")

        # Show diff lines with color
        shown = 0
        max_lines = self.config.max_output_lines
        for line in lines:
            if shown >= max_lines:
                self._render_line(f"... ({len(lines) - shown} more lines)", self.DIM)
                break

            if line.startswith("+") and not line.startswith("+++"):
                self._render_line(line, self.DIFF_ADD)
            elif line.startswith("-") and not line.startswith("---"):
                self._render_line(line, self.DIFF_DEL)
            elif line.startswith("@@"):
                self._render_line(line, self.DIFF_HUNK)
            else:
                self._render_line(line, self.DIM)
            shown += 1

        # Summary
        additions = metadata.get("additions", 0)
        deletions = metadata.get("deletions", 0)
        self._render_line("")
        self._render_line(
            f"Changes: {self.DIFF_ADD}+{additions}{self.RESET} "
            f"{self.DIFF_DEL}-{deletions}{self.RESET}",
            "",
        )

    def _render_shell_content(self, output: str | None, metadata: dict[str, Any]) -> None:
        """Render shell command output."""
        command = metadata.get("command", "")
        exit_code = metadata.get("exit_code", 0)

        # Show command
        self._render_line(f"$ {command}", self.YELLOW)
        self._render_line("")

        # Show output
        if output:
            lines = output.strip().split("\n")
            max_lines = self.config.max_output_lines
            for i, line in enumerate(lines):
                if i >= max_lines:
                    self._render_line(f"... ({len(lines) - i} more lines)", self.DIM)
                    break
                self._render_line(line)
        else:
            self._render_line("(no output)", self.DIM)

        # Show exit code if non-zero
        if exit_code != 0:
            self._render_line("")
            self._render_line(f"Exit code: {exit_code}", self.YELLOW)

    def _render_search_content(self, output: str | None, metadata: dict[str, Any]) -> None:
        """Render grep/glob results."""
        matches = metadata.get("matches", 0)

        if output:
            lines = output.strip().split("\n")
            max_lines = self.config.max_output_lines
            for i, line in enumerate(lines):
                if i >= max_lines:
                    self._render_line(f"... ({len(lines) - i} more results)", self.DIM)
                    break
                # Highlight file paths
                if ":" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 2:
                        self._render_line(
                            f"{self.CYAN}{parts[0]}{self.RESET}:{':'.join(parts[1:])}"
                        )
                        continue
                self._render_line(line)

        self._render_line("")
        self._render_line(f"Total: {matches} match{'es' if matches != 1 else ''}", self.DIM)

    def _render_read_content(self, output: str | None, metadata: dict[str, Any]) -> None:
        """Render read file info."""
        total_lines = metadata.get("total_lines", 0)
        offset = metadata.get("offset", 0)
        showing = metadata.get("showing_lines", 0)

        self._render_line(f"Total lines: {total_lines}")
        if offset > 0:
            self._render_line(f"Offset: {offset}")
        if showing and showing < total_lines:
            self._render_line(f"Showing: {showing} lines")

    def _render_todo_content(self, output: str | None, metadata: dict[str, Any]) -> None:
        """Render todo list."""
        todos = metadata.get("todos", [])
        if not todos and output:
            # Parse from output
            for line in output.strip().split("\n"):
                self._render_line(line)
            return

        for todo in todos:
            status = todo.get("status", "pending")
            content = todo.get("content", "")
            icons = {"pending": "○", "in_progress": "◐", "completed": "●"}
            colors = {
                "pending": self.DIM,
                "in_progress": self.YELLOW,
                "completed": self.GREEN,
            }
            icon = icons.get(status, "○")
            color = colors.get(status, "")
            self._render_line(f"{color}{icon} {content}{self.RESET}")

    def _render_generic_content(self, output: str) -> None:
        """Render generic output."""
        lines = output.strip().split("\n")
        max_lines = self.config.max_output_lines
        for i, line in enumerate(lines):
            if i >= max_lines:
                self._render_line(f"... ({len(lines) - i} more lines)", self.DIM)
                break
            self._render_line(line)

    def on_finish(self, reason: str) -> None:
        """Handle agent finish."""
        # Close any open reasoning tag
        self._close_reasoning_tag()
        print()
        if reason != "stop":
            print(f"{self.DIM}Finished: {reason}{self.RESET}")

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
            print(f"{self.DIM}Resumed session: {session_id}{self.RESET}")
        else:
            print(f"{self.DIM}Session: {session_id}{self.RESET}")
