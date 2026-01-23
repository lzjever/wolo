"""Compaction module for managing long session histories.

This module provides a strategy-based architecture for compacting conversation
histories when they exceed context limits. It supports multiple compaction
policies that can be applied in priority order.

Key Components:
    - CompactionManager: Orchestrates compaction policies
    - CompactionPolicy: Abstract base class for compaction strategies
    - SummaryCompactionPolicy: Summarizes old messages using LLM
    - ToolOutputPruningPolicy: Prunes old tool outputs selectively
    - CompactionHistory: Records and retrieves compaction history

Usage:
    ```python
    from wolo.compaction import CompactionManager
    from wolo.compaction.config import get_default_config

    config = get_default_config()
    manager = CompactionManager(config, llm_config)

    decision = manager.should_compact(messages, session_id)
    if decision.should_compact:
        result = await manager.compact(messages, session_id)
    ```
"""

from wolo.compaction.config import (
    CompactionConfig,
    SummaryPolicyConfig,
    ToolPruningPolicyConfig,
    get_default_config,
    load_compaction_config,
)
from wolo.compaction.history import CompactionHistory
from wolo.compaction.manager import CompactionManager
from wolo.compaction.token import TokenEstimator
from wolo.compaction.types import (
    CompactionContext,
    CompactionDecision,
    CompactionRecord,
    CompactionResult,
    CompactionStatus,
    MessageRef,
    PolicyResult,
    PolicyType,
    TokenStats,
)

__all__ = [
    # Types
    "CompactionStatus",
    "PolicyType",
    "TokenStats",
    "MessageRef",
    "CompactionRecord",
    "CompactionContext",
    "PolicyResult",
    "CompactionDecision",
    "CompactionResult",
    # Config
    "CompactionConfig",
    "SummaryPolicyConfig",
    "ToolPruningPolicyConfig",
    "get_default_config",
    "load_compaction_config",
    # Token
    "TokenEstimator",
    # Manager
    "CompactionManager",
    # History
    "CompactionHistory",
]
