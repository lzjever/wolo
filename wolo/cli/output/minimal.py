"""
Minimal output renderer.

Provides script-friendly output with structured summary.
Defaults to no colors (can be overridden with FORCE_COLOR=1 env var).
Useful for CI/CD, log processing, and scripting.

Output format (text mode):
    Agent: [final response text]

    Modified files:
      - src/file.py (+3, -2)

    Done.

Output format (JSON mode):
    {
      "response": "...",
      "tool_calls": [...],
      "files_modified": [...],
      "status": "completed"
    }
"""

import json
from typing import Any

from wolo.cli.output.base import OutputConfig, OutputRenderer


class MinimalRenderer(OutputRenderer):
    """Minimal output renderer for scripting."""

    def __init__(self, config: OutputConfig):
        super().__init__(config)
        self._text_buffer: list[str] = []
        self._tool_calls: list[dict] = []
        self._files_modified: list[str] = []
        self._agent_name: str = ""
        self._finish_reason: str = ""
        self._finished: bool = False  # Track if finish has been called to prevent duplicates
        self._in_reasoning: bool = False  # Track reasoning state for <think> tags

    def on_agent_start(self, agent_name: str) -> None:
        """
        Store agent name.

        In minimal mode, we don't print the agent name prompt
        (script-friendly, no interactive prompts).
        """
        self._agent_name = agent_name
        # Don't print anything in minimal mode

    def _close_reasoning_tag(self) -> None:
        """Close <think> tag if currently in reasoning mode."""
        if self._in_reasoning:
            print("</think>", flush=True)
            self._in_reasoning = False

    def on_text_delta(self, text: str, is_reasoning: bool = False) -> None:
        """
        Handle streaming text output.

        In minimal mode, we still stream output for better UX,
        but also collect it for final summary.
        Reasoning content is wrapped in <think></think> tags.
        """
        if is_reasoning:
            # Reasoning output: only show if show_reasoning is enabled
            if self.config.show_reasoning:
                # Open <think> tag if not already in reasoning
                if not self._in_reasoning:
                    print("<think>", flush=True)
                    self._in_reasoning = True
                print(text, end="", flush=True)
        else:
            # Close reasoning tag if transitioning from reasoning to regular text
            self._close_reasoning_tag()
            # Regular text output: stream in real-time (better UX)
            print(text, end="", flush=True)
            # Also collect for final summary (if needed)
            self._text_buffer.append(text)

    def on_tool_start(
        self,
        tool_name: str,
        params: dict[str, Any],
        brief: str,
        icon: str = "▶",
    ) -> None:
        """Silent - wait for complete."""
        pass

    def on_tool_complete(
        self,
        tool_name: str,
        status: str,
        duration: float,
        brief: str = "",
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Collect tool call info and show brief inline hint."""
        metadata = metadata or {}

        tool_info = {
            "tool": tool_name,
            "status": status,
            "duration_ms": int(duration * 1000),
        }

        # Add tool-specific info and show inline hint
        if tool_name in ("edit", "write"):
            file_path = (
                metadata.get("file_path") or brief.replace("✏️ ", "").replace("📝 ", "").strip()
            )
            additions = metadata.get("additions", 0)
            deletions = metadata.get("deletions", 0)
            tool_info["file"] = file_path
            tool_info["changes"] = {"additions": additions, "deletions": deletions}

            if status == "completed" and file_path:
                self._files_modified.append(file_path)
                # Show inline hint
                action = "wrote" if tool_name == "write" else "edited"
                print(f"\n[{action}: {file_path}]", flush=True)

        elif tool_name == "read":
            file_path = metadata.get("file_path") or brief.replace("📄 ", "").strip()
            tool_info["file"] = file_path
            tool_info["lines"] = metadata.get("total_lines", 0)
            # Show inline hint
            if status == "completed":
                lines = metadata.get("total_lines", 0)
                print(f"\n[read: {file_path} ({lines} lines)]", flush=True)

        elif tool_name == "shell":
            tool_info["command"] = metadata.get("command", "")
            tool_info["exit_code"] = metadata.get("exit_code", 0)
            # Show inline hint
            if status == "completed":
                cmd = metadata.get("command", "")[:40]
                exit_code = metadata.get("exit_code", 0)
                hint = (
                    f"[shell: {cmd}"
                    + ("..." if len(metadata.get("command", "")) > 40 else "")
                    + f" → {exit_code}]"
                )
                print(f"\n{hint}", flush=True)

        elif tool_name in ("grep", "glob"):
            tool_info["matches"] = metadata.get("matches", 0)
            # Show inline hint
            if status == "completed":
                matches = metadata.get("matches", 0)
                print(f"\n[{tool_name}: {matches} matches]", flush=True)

        self._tool_calls.append(tool_info)

    def on_finish(self, reason: str) -> None:
        """Output final result."""
        # Prevent duplicate finish output (finish event may be triggered multiple times)
        if self._finished:
            return

        # Close any open reasoning tag
        self._close_reasoning_tag()

        self._finished = True
        self._finish_reason = reason

        if self.config.json_output:
            self._output_json()
        else:
            self._output_text()

    def _output_json(self) -> None:
        """Output JSON format."""
        response_text = "".join(self._text_buffer).strip()

        result = {
            "agent": self._agent_name,
            "response": response_text,
            "tool_calls": self._tool_calls,
            "files_modified": self._files_modified,
            "status": self._finish_reason,
        }

        print(json.dumps(result, ensure_ascii=False, indent=2))

    def _output_text(self) -> None:
        """Output minimal text format - silent exit."""
        response_text = "".join(self._text_buffer).strip()

        # In minimal mode, text is already streamed via on_text_delta,
        # so we don't print it again here to avoid duplication.
        # Just add a newline if we streamed content
        if response_text:
            print()  # Final newline after streamed content

        # Silent exit - no "Done." message (tool actions already shown inline)

    def on_error(self, error: str) -> None:
        """Output error."""
        if self.config.json_output:
            result = {
                "error": error,
                "status": "error",
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Error: {error}")

    def on_shortcuts_hint(self) -> None:
        """No shortcuts hint in minimal mode."""
        pass

    def on_session_info(self, session_id: str, resumed: bool = False) -> None:
        """No session info in minimal mode."""
        pass
