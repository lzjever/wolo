"""Plan mode workflow for Wolo."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PlanStage(str, Enum):
    """Plan workflow stages."""
    UNDERSTAND = "understand"      # Understand requirements
    DESIGN = "design"              # Design approach
    REVIEW = "review"              # Review with user
    FINAL_PLAN = "final_plan"      # Create final plan
    EXIT = "exit"                  # Exit plan mode


@dataclass
class PlanState:
    """State for plan mode workflow."""
    stage: PlanStage = PlanStage.UNDERSTAND
    plan_file: Path | None = None
    user_goal: str = ""
    findings: list[str] = field(default_factory=list)
    design_decisions: list[str] = field(default_factory=list)
    remaining_work: list[str] = field(default_factory=list)

    def advance_stage(self) -> PlanStage:
        """Advance to the next stage."""
        stages = list(PlanStage)
        current_index = stages.index(self.stage)
        if current_index < len(stages) - 1:
            self.stage = stages[current_index + 1]
        return self.stage


def get_plan_prompt(stage: PlanStage, state: PlanState) -> str:
    """
    Get the system prompt for a given plan stage.

    Args:
        stage: Current plan stage
        state: Current plan state

    Returns:
        System prompt for the stage
    """
    base_prompt = """You are a planning agent helping users design and plan software changes.

## Plan Mode

You are in a structured planning workflow. Current stage: {stage}

## Stage Instructions

{stage_instructions}

## Your Task

{task}

Remember: You are in READ-ONLY mode for planning. Use read, grep, glob to explore.
"""

    stage_instructions = {
        PlanStage.UNDERSTAND: """**Understand Stage**: Your goal is to understand what the user wants.

1. Ask clarifying questions about:
   - What problem are they trying to solve?
   - What are the constraints/requirements?
   - What's the expected outcome?
2. Explore the codebase to understand context
3. Summarize your understanding

When ready, output: "STAGE_COMPLETE: I understand the requirements." """,

        PlanStage.DESIGN: """**Design Stage**: Design the implementation approach.

1. Identify key files that need modification
2. Propose specific changes (file by file)
3. Consider edge cases and dependencies
4. Estimate complexity

When ready, output: "STAGE_COMPLETE: Design is ready for review." """,

        PlanStage.REVIEW: """**Review Stage**: Review the plan with the user.

1. Present the design clearly
2. Highlight potential issues
3. Ask if user wants modifications
4. Wait for user approval

When approved, output: "STAGE_COMPLETE: Plan approved." """,

        PlanStage.FINAL_PLAN: """**Final Plan Stage**: Create the final implementation plan.

1. Create a detailed, step-by-step plan
2. Include file paths and specific changes
3. Organize by priority/dependency
4. Save the plan to a file

Output: "STAGE_COMPLETE: Final plan created." """,

        PlanStage.EXIT: """**Exit Stage**: Planning complete.

The user can now use the general agent to implement the plan.
Provide a summary of what was planned.""",
    }

    return base_prompt.format(
        stage=stage.value.upper(),
        stage_instructions=stage_instructions.get(stage, ""),
        task=f"Current goal: {state.user_goal}" if state.user_goal else "Help the user plan their changes."
    )


def should_restrict_tool(stage: PlanStage, tool: str) -> bool:
    """
    Check if a tool should be restricted in plan mode.

    In plan mode, only allow editing the plan file itself.
    """
    if stage == PlanStage.UNDERSTAND:
        # Understand stage: fully read-only
        return tool in ("write", "edit", "multiedit", "shell")
    elif stage == PlanStage.DESIGN:
        # Design stage: read-only
        return tool in ("write", "edit", "multiedit", "shell")
    elif stage == PlanStage.REVIEW:
        # Review stage: read-only
        return tool in ("write", "edit", "multiedit", "shell")
    elif stage == PlanStage.FINAL_PLAN:
        # Final plan stage: can write plan file
        return tool in ("multiedit", "shell")
    elif stage == PlanStage.EXIT:
        # Exit stage: fully read-only
        return True
    return False
