"""Compaction manager.

Orchestrates compaction policies and manages the overall compaction process.
"""

import logging
from typing import TYPE_CHECKING

from wolo.compaction.history import CompactionHistory
from wolo.compaction.policy.base import CompactionPolicy
from wolo.compaction.policy.pruning import ToolOutputPruningPolicy
from wolo.compaction.policy.summary import SummaryCompactionPolicy
from wolo.compaction.token import TokenEstimator
from wolo.compaction.types import (
    CompactionContext,
    CompactionDecision,
    CompactionRecord,
    CompactionResult,
    CompactionStatus,
    PolicyType,
)

if TYPE_CHECKING:
    from wolo.compaction.config import CompactionConfig
    from wolo.config import Config
    from wolo.session import Message

logger = logging.getLogger(__name__)


class CompactionManager:
    """Orchestrates compaction policies for session management.

    The CompactionManager coordinates multiple compaction policies,
    applying them in priority order until the session is within
    the token limit or all policies have been tried.

    Usage:
        ```python
        config = CompactionConfig()
        manager = CompactionManager(config, llm_config)

        # Check if compaction is needed
        decision = manager.should_compact(messages, session_id)

        if decision.should_compact:
            result = await manager.compact(messages, session_id)
            if result.status == CompactionStatus.APPLIED:
                messages = list(result.result_messages)
        ```

    Thread Safety:
        This class is not thread-safe. Use separate instances for
        concurrent sessions or implement external synchronization.
    """

    def __init__(
        self,
        config: "CompactionConfig",
        llm_config: "Config",
    ) -> None:
        """Initialize the compaction manager.

        Args:
            config: Compaction configuration
            llm_config: LLM configuration for summary generation
        """
        from wolo.session import get_storage

        self._config = config
        self._llm_config = llm_config

        # Initialize history
        self._history = CompactionHistory(get_storage())

        # Initialize policies (sorted by priority, descending)
        self._policies: list[CompactionPolicy] = []
        self._init_policies()

    def _init_policies(self) -> None:
        """Initialize and sort policies by priority."""
        policies: list[CompactionPolicy] = []

        # Add tool pruning policy
        if self._config.tool_pruning_policy.enabled:
            pruning = ToolOutputPruningPolicy()
            policies.append(pruning)

        # Add summary policy
        if self._config.summary_policy.enabled:
            summary = SummaryCompactionPolicy(self._llm_config)
            policies.append(summary)

        # Sort by priority (descending - higher priority first)
        # Use config priority if available, otherwise use policy default
        def get_priority(policy: CompactionPolicy) -> int:
            config_priority = self._config.policy_priority.get(policy.name)
            return config_priority if config_priority is not None else policy.priority

        policies.sort(key=get_priority, reverse=True)
        self._policies = policies

    @property
    def config(self) -> "CompactionConfig":
        """Get the compaction configuration."""
        return self._config

    def should_compact(
        self,
        messages: list["Message"],
        session_id: str,
    ) -> CompactionDecision:
        """Determine if compaction is needed.

        Args:
            messages: Current message list
            session_id: Session identifier

        Returns:
            CompactionDecision with recommendation and details
        """
        # Check if compaction is enabled
        if not self._config.enabled:
            return CompactionDecision(
                should_compact=False,
                reason="Compaction is disabled",
                current_tokens=0,
                limit_tokens=0,
                overflow_ratio=0.0,
                applicable_policies=(),
            )

        # Calculate token usage
        current_tokens = TokenEstimator.estimate_messages(messages)
        limit_tokens = (
            getattr(self._llm_config, "context_window", 128000) - self._config.reserved_tokens
        )

        if limit_tokens <= 0:
            limit_tokens = getattr(self._llm_config, "context_window", 128000)

        overflow_ratio = current_tokens / limit_tokens if limit_tokens > 0 else 0.0

        # Check if over threshold
        should_compact = overflow_ratio > self._config.overflow_threshold

        if not should_compact:
            return CompactionDecision(
                should_compact=False,
                reason=f"Token usage ({overflow_ratio:.1%}) below threshold ({self._config.overflow_threshold:.1%})",
                current_tokens=current_tokens,
                limit_tokens=limit_tokens,
                overflow_ratio=overflow_ratio,
                applicable_policies=(),
            )

        # Find applicable policies
        context = CompactionContext(
            session_id=session_id,
            messages=tuple(messages),
            token_count=current_tokens,
            token_limit=limit_tokens,
            model=self._llm_config.model,
            config=self._config,
        )

        applicable = []
        for policy in self._policies:
            if policy.should_apply(context):
                applicable.append(policy.policy_type)

        return CompactionDecision(
            should_compact=True,
            reason=f"Token usage ({overflow_ratio:.1%}) exceeds threshold ({self._config.overflow_threshold:.1%})",
            current_tokens=current_tokens,
            limit_tokens=limit_tokens,
            overflow_ratio=overflow_ratio,
            applicable_policies=tuple(applicable),
        )

    async def compact(
        self,
        messages: list["Message"],
        session_id: str,
    ) -> CompactionResult:
        """Execute compaction on messages.

        Applies policies in priority order until within token limit
        or all policies have been tried.

        Args:
            messages: Current message list
            session_id: Session identifier

        Returns:
            CompactionResult with outcome and records
        """
        if not self._config.enabled:
            return CompactionResult(
                status=CompactionStatus.SKIPPED,
                original_messages=tuple(messages),
                result_messages=tuple(messages),
                error="Compaction is disabled",
            )

        # Calculate initial state
        original_tokens = TokenEstimator.estimate_messages(messages)
        limit_tokens = (
            getattr(self._llm_config, "context_window", 128000) - self._config.reserved_tokens
        )

        if limit_tokens <= 0:
            limit_tokens = getattr(self._llm_config, "context_window", 128000)

        # Check if compaction is actually needed
        if original_tokens <= limit_tokens:
            return CompactionResult(
                status=CompactionStatus.NOT_NEEDED,
                original_messages=tuple(messages),
                result_messages=tuple(messages),
            )

        # Track results
        current_messages = tuple(messages)
        records: list[CompactionRecord] = []
        policies_applied: list[PolicyType] = []
        last_error: str | None = None

        # Apply policies in order
        for policy in self._policies:
            # Build context with current state
            current_tokens = TokenEstimator.estimate_messages(list(current_messages))

            # Check if still over limit
            if current_tokens <= limit_tokens:
                break

            context = CompactionContext(
                session_id=session_id,
                messages=current_messages,
                token_count=current_tokens,
                token_limit=limit_tokens,
                model=self._llm_config.model,
                config=self._config,
            )

            # Check if policy should apply
            if not policy.should_apply(context):
                continue

            logger.info(f"Applying compaction policy: {policy.name}")

            # Apply policy
            result = await policy.apply(context)

            if result.status == CompactionStatus.APPLIED:
                # Update current state
                current_messages = result.messages
                if result.record:
                    records.append(result.record)
                    # Save to history
                    self._history.add_record(session_id, result.record)
                policies_applied.append(policy.policy_type)

            elif result.status == CompactionStatus.FAILED:
                logger.warning(f"Policy {policy.name} failed: {result.error}")
                last_error = result.error
                # Continue to next policy

        # Calculate final state
        final_tokens = TokenEstimator.estimate_messages(list(current_messages))
        tokens_saved = original_tokens - final_tokens

        # Determine final status
        if records:
            status = CompactionStatus.APPLIED
        elif last_error:
            status = CompactionStatus.FAILED
        else:
            status = CompactionStatus.SKIPPED

        logger.info(
            f"Compaction completed: {status.name}, "
            f"saved {tokens_saved} tokens ({len(records)} policies applied)"
        )

        return CompactionResult(
            status=status,
            original_messages=tuple(messages),
            result_messages=current_messages,
            records=tuple(records),
            total_tokens_saved=tokens_saved,
            policies_applied=tuple(policies_applied),
            error=last_error,
        )

    def get_history(
        self,
        session_id: str,
    ) -> list[CompactionRecord]:
        """Get compaction history for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of compaction records (newest first)
        """
        return self._history.get_records(session_id)

    def get_original_messages(
        self,
        session_id: str,
        record_id: str,
    ) -> list["Message"]:
        """Get original messages from a compaction record.

        Args:
            session_id: Session identifier
            record_id: Compaction record identifier

        Returns:
            List of original messages
        """
        return self._history.get_original_messages(session_id, record_id)
