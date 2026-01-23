"""
Execution modes for Wolo.

Defines three operation modes:
- SOLO: Autonomous execution, AI works independently without asking questions
- COOP: Cooperative execution, AI may ask clarifying questions
- REPL: Continuous conversation mode, loops for continuous input
"""

from dataclasses import dataclass
from enum import Enum


class ExecutionMode(Enum):
    """
    Execution mode enumeration.

    SOLO: Autonomous execution, no questions asked.
          - Keyboard shortcuts: ENABLED (pause, stop)
          - Question tool: DISABLED
          - UI state display: ENABLED
          - Best for: Scripting, automation, batch processing

    COOP: Cooperative execution, AI may ask clarifying questions.
          - Keyboard shortcuts: ENABLED
          - Question tool: ENABLED
          - UI state display: ENABLED
          - Best for: Complex tasks requiring user guidance

    REPL: Continuous conversation mode.
          - Keyboard shortcuts: ENABLED
          - Question tool: ENABLED
          - UI state display: ENABLED
          - Loops for continuous input
          - Best for: Interactive exploration, debugging
    """

    SOLO = "solo"
    COOP = "coop"
    REPL = "repl"


@dataclass
class ModeConfig:
    """
    Configuration for an execution mode.

    Determines which features are enabled and how the agent behaves.
    """

    mode: ExecutionMode
    enable_keyboard_shortcuts: bool
    enable_question_tool: bool
    enable_ui_state: bool
    exit_after_task: bool
    wait_for_input_before_start: bool

    @classmethod
    def for_mode(cls, mode: ExecutionMode) -> "ModeConfig":
        """
        Create configuration for a specific mode.

        Args:
            mode: The execution mode

        Returns:
            ModeConfig with appropriate settings for the mode

        Mode Configuration Matrix:
            | Feature                    | SOLO  | COOP  | REPL  |
            |----------------------------|-------|-------|-------|
            | enable_keyboard_shortcuts  | True  | True  | True  |
            | enable_question_tool       | False | True  | True  |
            | enable_ui_state            | True  | True  | True  |
            | exit_after_task            | True  | True  | False |
        """
        if mode == ExecutionMode.SOLO:
            return cls(
                mode=mode,
                enable_keyboard_shortcuts=True,
                enable_question_tool=False,  # SOLO: no questions
                enable_ui_state=True,
                exit_after_task=True,
                wait_for_input_before_start=False,
            )
        elif mode == ExecutionMode.COOP:
            return cls(
                mode=mode,
                enable_keyboard_shortcuts=True,
                enable_question_tool=True,  # COOP: questions allowed
                enable_ui_state=True,
                exit_after_task=True,
                wait_for_input_before_start=False,
            )
        elif mode == ExecutionMode.REPL:
            return cls(
                mode=mode,
                enable_keyboard_shortcuts=True,
                enable_question_tool=True,  # REPL: questions allowed
                enable_ui_state=True,
                exit_after_task=False,  # REPL: loops continuously
                wait_for_input_before_start=False,
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")


@dataclass
class QuotaConfig:
    """
    Quota configuration for agent execution.

    Currently only max_steps is implemented. Future quotas:
    - max_tokens: Maximum total tokens (prompt + completion)
    - max_time_seconds: Maximum execution time
    """

    max_steps: int = 100
    max_tokens: int | None = None  # Future: token limit
    max_time_seconds: int | None = None  # Future: time limit

    def check_quota_exceeded(self, current_steps: int, current_tokens: int | None = None) -> bool:
        """
        Check if quota has been exceeded.

        Args:
            current_steps: Current step count
            current_tokens: Current token count (optional, for future use)

        Returns:
            True if quota exceeded, False otherwise
        """
        if current_steps >= self.max_steps:
            return True

        # Future: check token and time limits
        # if self.max_tokens and current_tokens and current_tokens >= self.max_tokens:
        #     return True

        return False
