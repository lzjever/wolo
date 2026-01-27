"""
Base classes for output rendering.

This module provides the abstract base class and configuration
for all output renderers.
"""

import os
import shutil
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class OutputStyle(Enum):
    """Output style options."""

    MINIMAL = "minimal"  # Script-friendly, no colors
    DEFAULT = "default"  # Standard interactive output
    VERBOSE = "verbose"  # Detailed output with diffs, etc.


@dataclass
class OutputConfig:
    """Configuration for output rendering."""

    style: OutputStyle = OutputStyle.DEFAULT

    # Display options
    use_color: bool = True
    show_reasoning: bool = True
    show_timestamps: bool = False

    # Content limits
    max_output_lines: int = 20  # For verbose mode tool output
    diff_context_lines: int = 3  # Context lines in diffs

    # JSON output (forces minimal + no color)
    json_output: bool = False

    @classmethod
    def from_args_and_config(
        cls,
        output_style: str | None = None,
        no_color: bool = False,
        show_reasoning: bool | None = None,
        json_output: bool = False,
        config_data: dict | None = None,
    ) -> "OutputConfig":
        """
        Create OutputConfig by merging CLI args with config file.

        CLI arguments take precedence over config file values.
        """
        config_data = config_data or {}
        output_section = config_data.get("output", {})

        # JSON mode forces minimal + no color
        if json_output:
            return cls(
                style=OutputStyle.MINIMAL,
                use_color=False,
                show_reasoning=False,
                json_output=True,
            )

        # Determine style: CLI > config > default
        if output_style:
            style = OutputStyle(output_style)
        elif output_section.get("style"):
            style = OutputStyle(output_section["style"])
        else:
            style = OutputStyle.DEFAULT

        # Determine color: --no-color flag or TTY detection
        # minimal mode always has no color (script-friendly)
        if style == OutputStyle.MINIMAL:
            use_color = False
        else:
            use_color = not no_color and _supports_color()

        # Determine show_reasoning: CLI > config > default
        if show_reasoning is not None:
            reasoning = show_reasoning
        else:
            reasoning = output_section.get("show_reasoning", True)

        return cls(
            style=style,
            use_color=use_color,
            show_reasoning=reasoning,
            show_timestamps=output_section.get("show_timestamps", False),
            max_output_lines=output_section.get("max_output_lines", 20),
            diff_context_lines=output_section.get("diff_context_lines", 3),
            json_output=False,
        )


def _supports_color() -> bool:
    """Check if terminal supports color output."""
    # Check NO_COLOR environment variable first (https://no-color.org/)
    if os.environ.get("NO_COLOR"):
        return False

    # Check if stdout is a TTY
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False

    # Check TERM environment
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False

    return True


class OutputRenderer(ABC):
    """
    Abstract base class for output renderers.

    All renderers must implement these methods to handle
    different types of output events from the agent loop.
    """

    def __init__(self, config: OutputConfig):
        self.config = config
        self._setup_colors()

    def _setup_colors(self) -> None:
        """Setup ANSI color codes based on config."""
        if self.config.use_color:
            self.RESET = "\033[0m"
            self.BOLD = "\033[1m"
            self.DIM = "\033[90m"
            self.RED = "\033[91m"
            self.GREEN = "\033[92m"
            self.YELLOW = "\033[93m"
            self.BLUE = "\033[94m"
            self.MAGENTA = "\033[95m"
            self.CYAN = "\033[96m"
            self.WHITE = "\033[97m"
            # Diff colors
            self.DIFF_ADD = "\033[92m"
            self.DIFF_DEL = "\033[91m"
            self.DIFF_HUNK = "\033[96m"
            # Border
            self.BORDER = "\033[90m"
        else:
            # No colors
            self.RESET = ""
            self.BOLD = ""
            self.DIM = ""
            self.RED = ""
            self.GREEN = ""
            self.YELLOW = ""
            self.BLUE = ""
            self.MAGENTA = ""
            self.CYAN = ""
            self.WHITE = ""
            self.DIFF_ADD = ""
            self.DIFF_DEL = ""
            self.DIFF_HUNK = ""
            self.BORDER = ""

    def get_terminal_width(self) -> int:
        """Get terminal width for formatting."""
        try:
            return shutil.get_terminal_size().columns
        except Exception:
            return 80

    # ==================== Abstract Methods ====================

    @abstractmethod
    def on_agent_start(self, agent_name: str) -> None:
        """
        Called when agent starts responding.

        Args:
            agent_name: Display name of the agent
        """
        pass

    @abstractmethod
    def on_text_delta(self, text: str, is_reasoning: bool = False) -> None:
        """
        Called for streaming text output.

        Args:
            text: Text chunk to display
            is_reasoning: True if this is reasoning/thinking output
        """
        pass

    def on_tool_call_streaming(
        self,
        tool_name: str,
        tool_id: str,
        length: int = 0,
    ) -> None:
        """
        Called when LLM starts streaming a tool call.

        This provides early feedback to the user while waiting for the LLM
        to generate tool call arguments (especially useful for write operations).

        Default implementation does nothing. Override to show streaming indicator.

        Args:
            tool_name: Name of the tool being called
            tool_id: Unique identifier for this tool call
            length: Current length of accumulated arguments (in chars)
        """
        pass  # Default: no-op, subclasses can override

    def on_tool_call_progress(
        self,
        index: int,
        length: int,
    ) -> None:
        """
        Called when LLM is generating more tool call arguments.

        This is called repeatedly as arguments are streamed, allowing
        the renderer to update progress display (e.g., "Generating... 456 chars").

        Default implementation does nothing. Override to show progress updates.

        Args:
            index: Index of the tool call (for parallel tool calls)
            length: Current length of accumulated arguments (in chars)
        """
        pass  # Default: no-op, subclasses can override

    @abstractmethod
    def on_tool_start(
        self,
        tool_name: str,
        params: dict[str, Any],
        brief: str,
        icon: str = "▶",
    ) -> None:
        """
        Called when a tool starts executing.

        Args:
            tool_name: Name of the tool
            params: Tool parameters
            brief: Brief description of the tool call
            icon: Icon to display
        """
        pass

    @abstractmethod
    def on_tool_complete(
        self,
        tool_name: str,
        status: str,
        duration: float,
        brief: str = "",
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Called when a tool completes.

        Args:
            tool_name: Name of the tool
            status: Completion status ('completed', 'error', etc.)
            duration: Execution duration in seconds
            brief: Brief description of result
            output: Full output (may be shown in verbose mode)
            metadata: Additional metadata (diff, matches count, etc.)
        """
        pass

    @abstractmethod
    def on_finish(self, reason: str) -> None:
        """
        Called when agent finishes.

        Args:
            reason: Finish reason ('stop', 'max_steps', 'error', etc.)
        """
        pass

    @abstractmethod
    def on_error(self, error: str) -> None:
        """
        Called for error output.

        Args:
            error: Error message
        """
        pass

    # ==================== Optional Methods ====================

    def on_shortcuts_hint(self) -> None:
        """Display keyboard shortcuts hint (optional)."""
        pass

    def on_session_info(self, session_id: str, resumed: bool = False) -> None:
        """Display session information (optional)."""
        pass
