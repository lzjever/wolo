"""Configuration for the compaction module.

This module defines all configuration options for compaction policies
and provides functions to load configuration from dictionaries.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SummaryPolicyConfig:
    """Configuration for the summary compaction policy.

    Attributes:
        enabled: Whether this policy is enabled
        recent_exchanges_to_keep: Number of recent user-assistant exchanges to preserve
        summary_max_tokens: Maximum tokens for the summary (None = no limit)
        summary_prompt_template: Custom prompt template (empty = use default)
        include_tool_calls_in_summary: Whether to include tool call info in summary
    """

    enabled: bool = True
    recent_exchanges_to_keep: int = 6
    summary_max_tokens: int | None = None
    summary_prompt_template: str = ""
    include_tool_calls_in_summary: bool = True


@dataclass
class ToolPruningPolicyConfig:
    """Configuration for the tool output pruning policy.

    Attributes:
        enabled: Whether this policy is enabled
        protect_recent_turns: Number of recent turns to protect from pruning
        protect_token_threshold: Token threshold before starting to prune
        minimum_prune_tokens: Minimum tokens to prune (skip if less)
        protected_tools: Tool names that should never be pruned
        replacement_text: Text to replace pruned outputs with
    """

    enabled: bool = True
    protect_recent_turns: int = 2
    protect_token_threshold: int = 40000
    minimum_prune_tokens: int = 20000
    protected_tools: tuple[str, ...] = ()
    replacement_text: str = "[Output pruned to save context space]"


@dataclass
class CompactionConfig:
    """Main configuration for the compaction module.

    Attributes:
        enabled: Master switch for compaction functionality
        auto_compact: Whether to automatically trigger compaction
        check_interval_steps: Steps between automatic checks
        overflow_threshold: Ratio threshold to trigger compaction (0.0-1.0)
        reserved_tokens: Tokens to reserve for system prompt and responses

        summary_policy: Configuration for summary policy
        tool_pruning_policy: Configuration for tool pruning policy

        policy_priority: Priority values for each policy (higher = execute first)
    """

    enabled: bool = True
    auto_compact: bool = True
    check_interval_steps: int = 3
    overflow_threshold: float = 0.9
    reserved_tokens: int = 2000

    summary_policy: SummaryPolicyConfig = field(default_factory=SummaryPolicyConfig)
    tool_pruning_policy: ToolPruningPolicyConfig = field(default_factory=ToolPruningPolicyConfig)

    policy_priority: dict[str, int] = field(
        default_factory=lambda: {
            "tool_pruning": 50,
            "summary": 100,
        }
    )


# Default summary prompt template (structured for consistent AI output)
DEFAULT_SUMMARY_PROMPT_TEMPLATE = """Summarize the conversation history using this exact structure for context continuity.

## Goal
[What the user is trying to accomplish - be specific about the main objective]

## Completed
[Work that has been finished successfully - list concrete achievements]

## In Progress
[Current work and pending tasks - what was being worked on when the summary was created]

## Key Files
[List of relevant files with brief notes about what they contain or their purpose]

## Next Steps
[What should be done next - recommended actions for continuing the work]

## Important Context
[Critical information for continuation - decisions made, constraints, preferences, or gotchas to remember]

---

## Conversation History

{conversation}

---

Generate the summary now, following the structure above exactly.
"""


def get_default_config() -> CompactionConfig:
    """Get the default compaction configuration.

    Returns:
        CompactionConfig with default values
    """
    return CompactionConfig()


def load_compaction_config(config_data: dict[str, Any] | None) -> CompactionConfig:
    """Load compaction configuration from a dictionary.

    Args:
        config_data: Configuration dictionary (from config.yaml compaction section)

    Returns:
        CompactionConfig instance with values from config_data,
        falling back to defaults for missing values
    """
    if not config_data:
        return get_default_config()

    # Load summary policy config
    summary_data = config_data.get("summary_policy", {})
    summary_config = SummaryPolicyConfig(
        enabled=summary_data.get("enabled", True),
        recent_exchanges_to_keep=summary_data.get("recent_exchanges_to_keep", 6),
        summary_max_tokens=summary_data.get("summary_max_tokens"),
        summary_prompt_template=summary_data.get("summary_prompt_template", ""),
        include_tool_calls_in_summary=summary_data.get("include_tool_calls_in_summary", True),
    )

    # Load tool pruning policy config
    pruning_data = config_data.get("tool_pruning_policy", {})
    pruning_config = ToolPruningPolicyConfig(
        enabled=pruning_data.get("enabled", True),
        protect_recent_turns=pruning_data.get("protect_recent_turns", 2),
        protect_token_threshold=pruning_data.get("protect_token_threshold", 40000),
        minimum_prune_tokens=pruning_data.get("minimum_prune_tokens", 20000),
        protected_tools=tuple(pruning_data.get("protected_tools", [])),
        replacement_text=pruning_data.get(
            "replacement_text", "[Output pruned to save context space]"
        ),
    )

    # Load policy priority
    default_priority = {"tool_pruning": 50, "summary": 100}
    policy_priority = config_data.get("policy_priority", default_priority)

    return CompactionConfig(
        enabled=config_data.get("enabled", True),
        auto_compact=config_data.get("auto_compact", True),
        check_interval_steps=config_data.get("check_interval_steps", 3),
        overflow_threshold=config_data.get("overflow_threshold", 0.9),
        reserved_tokens=config_data.get("reserved_tokens", 2000),
        summary_policy=summary_config,
        tool_pruning_policy=pruning_config,
        policy_priority=policy_priority,
    )
