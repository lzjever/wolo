"""Tool output pruning policy.

Selectively removes old tool outputs while preserving tool call metadata.
This is a lighter-weight compaction strategy than full summarization.
"""

import copy
import logging
import time
import uuid
from typing import TYPE_CHECKING

from wolo.compaction.policy.base import CompactionPolicy
from wolo.compaction.token import TokenEstimator
from wolo.compaction.types import (
    CompactionRecord,
    CompactionStatus,
    PolicyResult,
    PolicyType,
)

if TYPE_CHECKING:
    from wolo.compaction.config import ToolPruningPolicyConfig
    from wolo.compaction.types import CompactionContext
    from wolo.session import Message, ToolPart

logger = logging.getLogger(__name__)


class ToolOutputPruningPolicy(CompactionPolicy):
    """Compaction policy that prunes old tool outputs.

    This policy selectively removes the output content of old tool calls
    while preserving the tool call metadata (name, input). This is less
    aggressive than full summarization and is tried first.

    Behavior:
        1. Scans messages from newest to oldest
        2. Protects recent N turns from pruning
        3. Accumulates tool output tokens until threshold
        4. Prunes outputs beyond the threshold
        5. Replaces pruned outputs with placeholder text

    Protected Tools:
        Certain tools can be protected from pruning (configured via
        protected_tools). These tools' outputs are never removed.
    """

    @property
    def name(self) -> str:
        return "tool_pruning"

    @property
    def policy_type(self) -> PolicyType:
        return PolicyType.TOOL_PRUNING

    @property
    def priority(self) -> int:
        return 50

    def should_apply(self, context: "CompactionContext") -> bool:
        """Check if tool pruning should be applied.

        Conditions for application:
        1. Policy is enabled in config
        2. There are completed tool calls in messages
        3. Tool output tokens exceed protection threshold
        4. Current token count exceeds the limit
        """
        if not context.config.tool_pruning_policy.enabled:
            return False

        if context.token_count <= context.token_limit:
            return False

        # Check if there are any completed tool calls
        has_tools = self._has_completed_tools(context.messages)
        if not has_tools:
            return False

        # Check if pruning would help
        prunable = self._find_prunable_outputs(
            context.messages,
            context.config.tool_pruning_policy,
        )

        total_prunable = sum(tokens for _, _, tokens in prunable)
        return total_prunable >= context.config.tool_pruning_policy.minimum_prune_tokens

    async def apply(self, context: "CompactionContext") -> PolicyResult:
        """Apply tool output pruning.

        Algorithm:
        1. Find all prunable tool outputs
        2. If below minimum threshold, skip
        3. Create deep copies of affected messages
        4. Replace tool outputs with placeholder
        5. Build result with modified messages
        6. Create compaction record
        """
        from wolo.session import ToolPart

        try:
            config = context.config.tool_pruning_policy

            # Find prunable outputs
            prunable = self._find_prunable_outputs(context.messages, config)

            total_prunable_tokens = sum(tokens for _, _, tokens in prunable)
            if total_prunable_tokens < config.minimum_prune_tokens:
                return PolicyResult(
                    status=CompactionStatus.SKIPPED,
                    error=f"Prunable tokens ({total_prunable_tokens}) below minimum ({config.minimum_prune_tokens})",
                )

            # Create message copies and apply pruning
            messages_list = list(context.messages)
            pruned_message_ids = set()
            pruned_count = 0

            # Build a map of message_id -> message_index for quick lookup
            msg_id_to_idx = {msg.id: idx for idx, msg in enumerate(messages_list)}

            for msg, tool_part, _ in prunable:
                msg_idx = msg_id_to_idx.get(msg.id)
                if msg_idx is None:
                    continue

                # Deep copy the message if not already copied
                if msg.id not in pruned_message_ids:
                    messages_list[msg_idx] = self._deep_copy_message(messages_list[msg_idx])
                    pruned_message_ids.add(msg.id)

                # Find and prune the tool part
                copied_msg = messages_list[msg_idx]
                for i, part in enumerate(copied_msg.parts):
                    if isinstance(part, ToolPart) and part.id == tool_part.id:
                        # Create a new ToolPart with pruned output
                        pruned_part = self._prune_tool_part(part, config)
                        copied_msg.parts[i] = pruned_part
                        pruned_count += 1
                        break

            result_messages = tuple(messages_list)

            # Calculate token counts
            original_tokens = TokenEstimator.estimate_messages(list(context.messages))
            result_tokens = TokenEstimator.estimate_messages(list(result_messages))

            # Create compaction record
            record_id = str(uuid.uuid4())
            record = CompactionRecord(
                id=record_id,
                session_id=context.session_id,
                policy=PolicyType.TOOL_PRUNING,
                created_at=time.time(),
                original_token_count=original_tokens,
                result_token_count=result_tokens,
                original_message_count=len(context.messages),
                result_message_count=len(result_messages),
                compacted_message_ids=tuple(pruned_message_ids),
                preserved_message_ids=tuple(
                    msg.id for msg in context.messages if msg.id not in pruned_message_ids
                ),
                summary_message_id=None,
                summary_text=f"Pruned {pruned_count} tool outputs",
                config_snapshot={
                    "protect_recent_turns": config.protect_recent_turns,
                    "protect_token_threshold": config.protect_token_threshold,
                    "minimum_prune_tokens": config.minimum_prune_tokens,
                },
            )

            logger.info(
                f"Tool pruning applied: {pruned_count} outputs pruned, "
                f"{original_tokens} -> {result_tokens} tokens"
            )

            return PolicyResult(
                status=CompactionStatus.APPLIED,
                messages=result_messages,
                record=record,
            )

        except Exception as e:
            logger.error(f"Tool pruning failed: {e}")
            return PolicyResult(status=CompactionStatus.FAILED, error=str(e))

    def estimate_savings(self, context: "CompactionContext") -> int:
        """Estimate token savings from pruning."""
        if not context.config.tool_pruning_policy.enabled:
            return 0

        prunable = self._find_prunable_outputs(
            context.messages,
            context.config.tool_pruning_policy,
        )

        total = sum(tokens for _, _, tokens in prunable)
        # Account for replacement text (about 10 tokens each)
        replacement_tokens = len(prunable) * 10

        return max(0, total - replacement_tokens)

    def _has_completed_tools(self, messages: tuple) -> bool:
        """Check if there are any completed tool calls."""
        from wolo.session import ToolPart

        for msg in messages:
            for part in msg.parts:
                if isinstance(part, ToolPart) and part.status == "completed":
                    return True
        return False

    def _find_prunable_outputs(
        self,
        messages: tuple,
        config: "ToolPruningPolicyConfig",
    ) -> list[tuple["Message", "ToolPart", int]]:
        """Find tool outputs that can be pruned.

        Args:
            messages: Message tuple
            config: Pruning configuration

        Returns:
            List of (message, tool_part, token_count) tuples for prunable outputs
        """
        from wolo.session import ToolPart

        prunable = []
        accumulated_tokens = 0
        turns = 0

        # Scan from newest to oldest
        for msg in reversed(messages):
            # Count turns (user messages mark turn boundaries)
            if msg.role == "user":
                turns += 1

            # Skip recent turns
            if turns <= config.protect_recent_turns:
                continue

            # Check for summary message (stop scanning)
            if hasattr(msg, "metadata") and msg.metadata.get("compaction", {}).get("is_summary"):
                break

            # Find completed tool calls
            for part in msg.parts:
                if not isinstance(part, ToolPart):
                    continue
                if part.status != "completed":
                    continue
                if not part.output:
                    continue

                # Skip protected tools
                if part.tool in config.protected_tools:
                    continue

                # Skip already pruned outputs
                if hasattr(part, "metadata") and part.metadata.get("pruned"):
                    break  # Stop at already-pruned content

                # Estimate tokens for this output
                output_tokens = TokenEstimator.estimate_text(part.output)
                accumulated_tokens += output_tokens

                # Only prune after exceeding protection threshold
                if accumulated_tokens > config.protect_token_threshold:
                    prunable.append((msg, part, output_tokens))

        return prunable

    def _deep_copy_message(self, message: "Message") -> "Message":
        """Create a deep copy of a message."""
        from wolo.session import Message, TextPart, ToolPart

        # Copy parts
        new_parts = []
        for part in message.parts:
            if isinstance(part, TextPart):
                new_part = TextPart(id=part.id, text=part.text)
                new_parts.append(new_part)
            elif isinstance(part, ToolPart):
                new_part = ToolPart(
                    id=part.id,
                    tool=part.tool,
                    input=copy.deepcopy(part.input),
                    output=part.output,
                    status=part.status,
                )
                new_part.start_time = part.start_time
                new_part.end_time = part.end_time
                new_parts.append(new_part)

        # Create new message
        new_msg = Message(
            id=message.id,
            role=message.role,
            parts=new_parts,
        )
        new_msg.timestamp = message.timestamp
        new_msg.finished = message.finished
        new_msg.finish_reason = message.finish_reason
        new_msg.reasoning_content = message.reasoning_content

        # Copy metadata
        if hasattr(message, "metadata"):
            new_msg.metadata = copy.deepcopy(message.metadata)

        return new_msg

    def _prune_tool_part(
        self,
        part: "ToolPart",
        config: "ToolPruningPolicyConfig",
    ) -> "ToolPart":
        """Create a pruned copy of a tool part."""
        from wolo.session import ToolPart

        original_tokens = TokenEstimator.estimate_text(part.output)

        new_part = ToolPart(
            id=part.id,
            tool=part.tool,
            input=copy.deepcopy(part.input),
            output=config.replacement_text,
            status=part.status,
        )
        new_part.start_time = part.start_time
        new_part.end_time = part.end_time

        # Add pruning metadata
        if not hasattr(new_part, "metadata"):
            new_part.metadata = {}
        new_part.metadata = {
            "pruned": True,
            "pruned_at": time.time(),
            "original_output_tokens": original_tokens,
        }

        return new_part
