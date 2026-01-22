"""Compaction policies module.

This module provides the policy framework for compaction strategies.
All policies inherit from CompactionPolicy and can be applied
through the CompactionManager.

Available Policies:
    - SummaryCompactionPolicy: Summarizes old messages using LLM
    - ToolOutputPruningPolicy: Selectively prunes old tool outputs
"""

from wolo.compaction.policy.base import CompactionPolicy
from wolo.compaction.policy.summary import SummaryCompactionPolicy
from wolo.compaction.policy.pruning import ToolOutputPruningPolicy

__all__ = [
    "CompactionPolicy",
    "SummaryCompactionPolicy",
    "ToolOutputPruningPolicy",
]
