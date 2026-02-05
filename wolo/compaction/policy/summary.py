"""Summary compaction policy.

Compacts conversation history by generating an LLM summary of older
messages while preserving recent exchanges.
"""

import logging
import time
import uuid
from typing import TYPE_CHECKING

from wolo.compaction.config import DEFAULT_SUMMARY_PROMPT_TEMPLATE
from wolo.compaction.policy.base import CompactionPolicy
from wolo.compaction.token import TokenEstimator
from wolo.compaction.types import (
    CompactionRecord,
    CompactionStatus,
    PolicyResult,
    PolicyType,
)

if TYPE_CHECKING:
    from wolo.compaction.types import CompactionContext
    from wolo.config import Config

logger = logging.getLogger(__name__)


class SummaryCompactionPolicy(CompactionPolicy):
    """Compaction policy that summarizes old messages.

    This policy keeps the most recent N exchanges and summarizes
    older messages into a single context message using the LLM.

    Behavior:
        1. Determines which messages to keep (recent N exchanges)
        2. Determines which messages to summarize (everything else)
        3. Generates a summary using the configured LLM
        4. Creates a new message list: [summary_message] + [recent_messages]
        5. Records the compaction for history/recovery

    Attributes:
        llm_config: Configuration for the LLM used for summarization
    """

    def __init__(self, llm_config: "Config") -> None:
        """Initialize the summary policy.

        Args:
            llm_config: LLM configuration for summary generation
        """
        self._llm_config = llm_config

    @property
    def name(self) -> str:
        return "summary"

    @property
    def policy_type(self) -> PolicyType:
        return PolicyType.SUMMARY

    @property
    def priority(self) -> int:
        return 100

    def should_apply(self, context: "CompactionContext") -> bool:
        """Check if summary compaction should be applied.

        Conditions for application:
        1. Policy is enabled in config
        2. There are enough messages to compact (more than keep threshold)
        3. Current token count exceeds the limit
        """
        if not context.config.summary_policy.enabled:
            return False

        # Need at least (keep_exchanges * 2) messages to have something to compact
        min_messages = context.config.summary_policy.recent_exchanges_to_keep * 2
        if len(context.messages) <= min_messages:
            return False

        return context.token_count > context.token_limit

    async def apply(self, context: "CompactionContext") -> PolicyResult:
        """Apply summary compaction.

        Algorithm:
        1. Split messages into to_compact and to_keep
        2. If nothing to compact, return SKIPPED
        3. Generate summary using LLM
        4. Create summary message with metadata
        5. Combine summary + kept messages
        6. Create compaction record
        7. Return result
        """
        from wolo.session import Message, TextPart

        try:
            # Split messages
            keep_exchanges = context.config.summary_policy.recent_exchanges_to_keep
            to_compact, to_keep = self._split_messages(context.messages, keep_exchanges)

            if not to_compact:
                return PolicyResult(status=CompactionStatus.SKIPPED, error="No messages to compact")

            # Generate summary
            summary_text = await self._generate_summary(to_compact, context)

            # Create summary message
            summary_msg_id = str(uuid.uuid4())
            summary_msg = Message(
                id=summary_msg_id,
                role="user",
            )
            summary_msg.parts.append(
                TextPart(text=f"[Conversation History Summary]\n\n{summary_text}")
            )

            # Add metadata to summary message
            record_id = str(uuid.uuid4())
            summary_msg.metadata = {
                "compaction": {
                    "is_summary": True,
                    "record_id": record_id,
                    "compacted_message_ids": [msg.id for msg in to_compact],
                    "created_at": time.time(),
                }
            }

            # Build result messages
            result_messages = (summary_msg,) + tuple(to_keep)

            # Calculate token counts
            original_tokens = TokenEstimator.estimate_messages(list(context.messages))
            result_tokens = TokenEstimator.estimate_messages(list(result_messages))

            # Create compaction record
            record = CompactionRecord(
                id=record_id,
                session_id=context.session_id,
                policy=PolicyType.SUMMARY,
                created_at=time.time(),
                original_token_count=original_tokens,
                result_token_count=result_tokens,
                original_message_count=len(context.messages),
                result_message_count=len(result_messages),
                compacted_message_ids=tuple(msg.id for msg in to_compact),
                preserved_message_ids=tuple(msg.id for msg in to_keep),
                summary_message_id=summary_msg_id,
                summary_text=summary_text,
                config_snapshot={
                    "recent_exchanges_to_keep": keep_exchanges,
                    "summary_max_tokens": context.config.summary_policy.summary_max_tokens,
                },
            )

            logger.info(
                f"Summary compaction applied: {len(context.messages)} -> {len(result_messages)} messages, "
                f"{original_tokens} -> {result_tokens} tokens"
            )

            return PolicyResult(
                status=CompactionStatus.APPLIED,
                messages=result_messages,
                record=record,
            )

        except Exception as e:
            logger.error(f"Summary compaction failed: {e}")
            return PolicyResult(status=CompactionStatus.FAILED, error=str(e))

    def estimate_savings(self, context: "CompactionContext") -> int:
        """Estimate token savings from summary compaction.

        Assumes summary will be about 20% of the original compacted content.
        """
        if not self.should_apply(context):
            return 0

        keep_exchanges = context.config.summary_policy.recent_exchanges_to_keep
        to_compact, _ = self._split_messages(context.messages, keep_exchanges)

        if not to_compact:
            return 0

        compact_tokens = TokenEstimator.estimate_messages(list(to_compact))
        # Assume summary is ~20% of original
        estimated_summary_tokens = int(compact_tokens * 0.2)

        return max(0, compact_tokens - estimated_summary_tokens)

    def _split_messages(
        self,
        messages: tuple,
        keep_exchanges: int,
    ) -> tuple[tuple, tuple]:
        """Split messages into compact and keep portions.

        Args:
            messages: All messages
            keep_exchanges: Number of exchanges to keep

        Returns:
            Tuple of (to_compact, to_keep)
        """
        if not messages:
            return ((), ())

        # Count user messages from the end
        to_keep = []
        user_count = 0

        for msg in reversed(messages):
            to_keep.insert(0, msg)
            if msg.role == "user":
                user_count += 1
            if user_count >= keep_exchanges:
                break

        # Everything else is to compact
        keep_count = len(to_keep)
        to_compact = messages[:-keep_count] if keep_count < len(messages) else ()

        return (tuple(to_compact), tuple(to_keep))

    async def _generate_summary(
        self,
        messages: tuple,
        context: "CompactionContext",
    ) -> str:
        """Generate summary using LLM.

        Args:
            messages: Messages to summarize
            context: Compaction context

        Returns:
            Generated summary text
        """
        from wolo.llm_adapter import WoloLLMClient
        from wolo.session import TextPart, ToolPart

        # Build conversation text
        conversation_lines = []
        for msg in messages:
            prefix = "User:" if msg.role == "user" else "Assistant:"

            for part in msg.parts:
                if isinstance(part, TextPart) and part.text.strip():
                    conversation_lines.append(f"{prefix} {part.text}")
                elif isinstance(part, ToolPart):
                    if context.config.summary_policy.include_tool_calls_in_summary:
                        conversation_lines.append(f"{prefix} [Used tool: {part.tool}]")

        if not conversation_lines:
            return "(Empty conversation history)"

        conversation_text = "\n\n".join(conversation_lines)

        # Build prompt
        template = (
            context.config.summary_policy.summary_prompt_template or DEFAULT_SUMMARY_PROMPT_TEMPLATE
        )
        prompt = template.format(conversation=conversation_text)

        # Call LLM
        client = WoloLLMClient(self._llm_config, None, None)

        try:
            llm_messages = [{"role": "user", "content": prompt}]
            summary_parts = []

            async for event in client.chat_completion(llm_messages, tools=None, stream=True):
                if event.get("type") == "text-delta":
                    summary_parts.append(event["text"])
                elif event.get("type") == "finish":
                    break

            summary = "".join(summary_parts).strip()

            # Apply max tokens limit if configured
            max_tokens = context.config.summary_policy.summary_max_tokens
            if max_tokens:
                # Rough character limit (4 chars per token)
                max_chars = max_tokens * 4
                if len(summary) > max_chars:
                    summary = summary[:max_chars] + "..."

            return summary

        except Exception as e:
            logger.warning(f"LLM summary generation failed: {e}, using fallback")
            # Fallback summary
            user_count = sum(1 for m in messages if m.role == "user")
            assistant_count = sum(1 for m in messages if m.role == "assistant")
            return (
                f"Previous conversation containing {user_count} user messages "
                f"and {assistant_count} assistant responses."
            )
