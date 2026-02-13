"""
Execution modes for Wolo (simplified - no keyboard shortcuts, no UI state).

Defines three operation modes:
- SOLO: Autonomous execution, AI works independently without asking questions
- COOP: Cooperative execution, AI may ask clarifying questions
- REPL: Continuous conversation mode, loops for continuous input
"""

from dataclasses import dataclass
from enum import Enum


class ExecutionMode(Enum):
    """
    Execution mode enumeration (simplified).

    SOLO: Autonomous execution, no questions asked.
          - Question tool: DISABLED
          - Best for: Scripting, automation, batch processing

    COOP: Cooperative execution, AI may ask clarifying questions.
          - Question tool: ENABLED
          - Best for: Complex tasks requiring user guidance

    REPL: Continuous conversation mode.
          - Question tool: ENABLED
          - Loops for continuous input
          - Best for: Interactive exploration, debugging
    """

    SOLO = "solo"
    COOP = "coop"
    REPL = "repl"


@dataclass
class ModeConfig:
    """
    Configuration for an execution mode (simplified).

    Determines which features are enabled and how the agent behaves.
    """

    mode: ExecutionMode
    enable_question_tool: bool
    exit_after_task: bool

    @classmethod
    def for_mode(cls, mode: ExecutionMode) -> "ModeConfig":
        """
        Create configuration for a specific mode.

        Args:
            mode: The execution mode

        Returns:
            ModeConfig with appropriate settings for the mode

        Mode Configuration Matrix:
            | Feature              | SOLO  | COOP  | REPL  |
            |----------------------|-------|-------|-------|
            | enable_question_tool | False | True  | True  |
            | exit_after_task      | True  | True  | False |
        """
        if mode == ExecutionMode.SOLO:
            return cls(
                mode=mode,
                enable_question_tool=False,  # SOLO: no questions
                exit_after_task=True,
            )
        elif mode == ExecutionMode.COOP:
            return cls(
                mode=mode,
                enable_question_tool=True,  # COOP: questions allowed
                exit_after_task=True,
            )
        elif mode == ExecutionMode.REPL:
            return cls(
                mode=mode,
                enable_question_tool=True,  # REPL: questions allowed
                exit_after_task=False,  # REPL: loops continuously
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

        return False
