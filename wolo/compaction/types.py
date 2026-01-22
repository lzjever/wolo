"""Type definitions for the compaction module.

This module defines all data structures used in compaction operations.
All data classes are immutable (frozen) to ensure thread safety and
prevent accidental modifications.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from wolo.compaction.config import CompactionConfig


class CompactionStatus(Enum):
    """Status of a compaction operation.
    
    Attributes:
        NOT_NEEDED: No compaction was necessary (under threshold)
        APPLIED: Compaction was successfully applied
        FAILED: Compaction failed with an error
        SKIPPED: Compaction was skipped (e.g., disabled or no applicable policy)
    """
    NOT_NEEDED = auto()
    APPLIED = auto()
    FAILED = auto()
    SKIPPED = auto()


class PolicyType(Enum):
    """Types of compaction policies.
    
    Attributes:
        SUMMARY: Summarizes old messages into a single context message
        TOOL_PRUNING: Selectively removes old tool outputs
    
    Note:
        Future policies (e.g., EMBEDDING, IMPORTANCE) can be added here
        without modifying existing code.
    """
    SUMMARY = "summary"
    TOOL_PRUNING = "tool_pruning"


@dataclass(frozen=True)
class TokenStats:
    """Token statistics for a message or session.
    
    Attributes:
        estimated: Estimated token count using character-based heuristics
        actual: Actual token count from API response (None if unavailable)
        model: Model name used for estimation
    """
    estimated: int
    actual: int | None = None
    model: str = "default"


@dataclass(frozen=True)
class MessageRef:
    """Reference to a message without full content.
    
    Used in compaction records to reference original messages without
    duplicating their content.
    
    Attributes:
        id: Unique message identifier
        role: Message role ("user" or "assistant")
        timestamp: Unix timestamp when message was created
        token_count: Estimated token count for this message
    """
    id: str
    role: str
    timestamp: float
    token_count: int


@dataclass(frozen=True)
class CompactionRecord:
    """Record of a single compaction operation.
    
    Stores complete information about a compaction for auditing,
    debugging, and potential recovery of original messages.
    
    Attributes:
        id: Unique record identifier (UUID)
        session_id: Session this compaction belongs to
        policy: Type of policy that was applied
        created_at: Unix timestamp when compaction occurred
        
        original_token_count: Token count before compaction
        result_token_count: Token count after compaction
        original_message_count: Number of messages before compaction
        result_message_count: Number of messages after compaction
        
        compacted_message_ids: IDs of messages that were compacted
        preserved_message_ids: IDs of messages that were kept
        summary_message_id: ID of the summary message (if created)
        
        summary_text: Generated summary content
        
        config_snapshot: Configuration at time of compaction
    """
    id: str
    session_id: str
    policy: PolicyType
    created_at: float
    
    original_token_count: int
    result_token_count: int
    original_message_count: int
    result_message_count: int
    
    compacted_message_ids: tuple[str, ...]
    preserved_message_ids: tuple[str, ...]
    summary_message_id: str | None
    
    summary_text: str
    
    config_snapshot: dict[str, Any]


@dataclass(frozen=True)
class CompactionContext:
    """Context passed to compaction policies.
    
    Contains all information a policy needs to make decisions
    and perform compaction.
    
    Attributes:
        session_id: Session identifier
        messages: Tuple of messages (immutable view)
        token_count: Current total token count
        token_limit: Maximum allowed tokens
        model: Model name for token estimation
        config: Compaction configuration
    """
    session_id: str
    messages: tuple  # tuple[Message, ...]
    token_count: int
    token_limit: int
    model: str
    config: "CompactionConfig"


@dataclass(frozen=True)
class PolicyResult:
    """Result from applying a compaction policy.
    
    Attributes:
        status: Execution status
        messages: Processed messages (if successful)
        record: Compaction record (if successful)
        error: Error message (if failed)
    """
    status: CompactionStatus
    messages: tuple | None = None  # tuple[Message, ...] | None
    record: CompactionRecord | None = None
    error: str | None = None


@dataclass(frozen=True)
class CompactionDecision:
    """Decision from should_compact check.
    
    Attributes:
        should_compact: Whether compaction is needed
        reason: Human-readable explanation of the decision
        current_tokens: Current token usage
        limit_tokens: Token limit (after reserving space)
        overflow_ratio: Ratio of current to limit (1.0 = at limit)
        applicable_policies: Policies that can be applied
    """
    should_compact: bool
    reason: str
    current_tokens: int
    limit_tokens: int
    overflow_ratio: float
    applicable_policies: tuple[PolicyType, ...]


@dataclass(frozen=True)
class CompactionResult:
    """Final result of a compaction operation.
    
    Attributes:
        status: Final status of the operation
        original_messages: Original messages (for reference)
        result_messages: Messages after compaction
        records: All compaction records created
        total_tokens_saved: Total tokens reduced
        policies_applied: List of policies that were applied
        error: Error message if operation failed
    """
    status: CompactionStatus
    original_messages: tuple  # tuple[Message, ...]
    result_messages: tuple    # tuple[Message, ...]
    records: tuple[CompactionRecord, ...] = field(default_factory=tuple)
    total_tokens_saved: int = 0
    policies_applied: tuple[PolicyType, ...] = field(default_factory=tuple)
    error: str | None = None
