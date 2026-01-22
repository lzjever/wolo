"""Abstract base class for compaction policies.

Defines the interface that all compaction policies must implement.
Uses the Strategy pattern to allow interchangeable algorithms.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wolo.compaction.types import CompactionContext, PolicyResult, PolicyType


class CompactionPolicy(ABC):
    """Abstract base class for compaction policies.
    
    All concrete policies must inherit from this class and implement
    all abstract methods. Policies are applied in priority order
    by the CompactionManager.
    
    Design Contract:
        - name must be unique across all policies
        - priority determines execution order (higher = first)
        - should_apply must be idempotent with no side effects
        - apply must not modify the original messages
    
    Example:
        ```python
        class MyPolicy(CompactionPolicy):
            @property
            def name(self) -> str:
                return "my_policy"
            
            @property
            def policy_type(self) -> PolicyType:
                return PolicyType.SUMMARY  # or define new type
            
            @property
            def priority(self) -> int:
                return 75
            
            def should_apply(self, context: CompactionContext) -> bool:
                return context.token_count > context.token_limit
            
            async def apply(self, context: CompactionContext) -> PolicyResult:
                # Implementation here
                ...
            
            def estimate_savings(self, context: CompactionContext) -> int:
                return context.token_count // 2
        ```
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this policy.
        
        Returns:
            Non-empty string that uniquely identifies this policy
            
        Postconditions:
            - Return value is a non-empty string
            - Return value is consistent across calls
        """
        ...
    
    @property
    @abstractmethod
    def policy_type(self) -> "PolicyType":
        """Type enumeration for this policy.
        
        Returns:
            PolicyType enum value representing this policy's category
        """
        ...
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """Execution priority for this policy.
        
        Higher values mean the policy is tried earlier. Recommended ranges:
        - 10-49: Lightweight preprocessing
        - 50-99: Selective pruning
        - 100-199: Full compaction
        - 200+: Post-processing
        
        Returns:
            Positive integer representing priority
        """
        ...
    
    @abstractmethod
    def should_apply(self, context: "CompactionContext") -> bool:
        """Determine whether this policy should be applied.
        
        This method must be idempotent and have no side effects.
        It should only examine the context to make a decision.
        
        Args:
            context: Current compaction context with messages and config
            
        Returns:
            True if the policy should be applied, False otherwise
            
        Preconditions:
            - context is not None
            - context.messages is not empty
            
        Postconditions:
            - No state is modified
            - Return value is deterministic for same input
        """
        ...
    
    @abstractmethod
    async def apply(self, context: "CompactionContext") -> "PolicyResult":
        """Apply this compaction policy.
        
        Performs the actual compaction operation. May call external
        services (e.g., LLM for summarization). Must not modify the
        original messages in the context.
        
        Args:
            context: Current compaction context
            
        Returns:
            PolicyResult containing:
            - status: CompactionStatus indicating success/failure
            - messages: New message tuple if successful
            - record: CompactionRecord if successful
            - error: Error message if failed
            
        Preconditions:
            - should_apply(context) returned True
            - context is not None
            
        Postconditions:
            - Original context.messages is not modified
            - If successful, result.messages is a new tuple
            - If successful, result.record contains valid data
            
        Error Handling:
            This method should not raise exceptions. Errors should be
            returned via PolicyResult.error with status=FAILED.
        """
        ...
    
    @abstractmethod
    def estimate_savings(self, context: "CompactionContext") -> int:
        """Estimate token savings if this policy is applied.
        
        Used for planning and decision-making. Does not perform
        any actual compaction.
        
        Args:
            context: Current compaction context
            
        Returns:
            Estimated number of tokens that would be saved.
            Returns 0 if unable to estimate or policy not applicable.
            
        Preconditions:
            - context is not None
            
        Postconditions:
            - Return value >= 0
            - No state is modified
        """
        ...
