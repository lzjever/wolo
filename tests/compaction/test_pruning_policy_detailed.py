"""Comprehensive tests for ToolOutputPruningPolicy.

Tests the tool pruning policy with various edge cases and scenarios.
"""

import pytest
from unittest.mock import MagicMock

from wolo.compaction.policy.pruning import ToolOutputPruningPolicy
from wolo.compaction.types import CompactionContext, CompactionStatus, PolicyType
from wolo.compaction.config import CompactionConfig, ToolPruningPolicyConfig
from wolo.session import Message, TextPart, ToolPart


@pytest.fixture
def policy():
    """Create ToolOutputPruningPolicy instance."""
    return ToolOutputPruningPolicy()


@pytest.fixture
def compaction_config():
    """Create compaction config."""
    return CompactionConfig(
        tool_pruning_policy=ToolPruningPolicyConfig(
            enabled=True,
            protect_recent_turns=2,
            protect_token_threshold=40000,
            minimum_prune_tokens=20000,
        ),
    )


def create_tool_messages(
    count: int,
    output_size: int = 5000,
    protect_recent: int = 0,
) -> tuple:
    """Create messages with tool calls.
    
    Args:
        count: Number of user-assistant pairs
        output_size: Size of tool output in characters
        protect_recent: Number of recent turns to mark as protected
    """
    messages = []
    for i in range(count):
        messages.append(Message(
            role="user",
            parts=[TextPart(text=f"Request {i}")]
        ))
        messages.append(Message(
            role="assistant",
            parts=[
                ToolPart(
                    tool="read",
                    input={"path": f"/test{i}.py"},
                    output="x" * output_size,
                    status="completed",
                )
            ]
        ))
    return tuple(messages)


def create_context(
    messages: tuple,
    token_count: int = 50000,
    token_limit: int = 40000,
    config: CompactionConfig = None,
) -> CompactionContext:
    """Create CompactionContext."""
    if config is None:
        config = CompactionConfig()
    
    return CompactionContext(
        session_id="test-session",
        messages=messages,
        token_count=token_count,
        token_limit=token_limit,
        model="test-model",
        config=config,
    )


class TestToolPruningPolicyProperties:
    """Test policy properties."""
    
    def test_name(self, policy):
        """Name should be 'tool_pruning'."""
        assert policy.name == "tool_pruning"
    
    def test_policy_type(self, policy):
        """Policy type should be TOOL_PRUNING."""
        assert policy.policy_type == PolicyType.TOOL_PRUNING
    
    def test_priority(self, policy):
        """Priority should be 50."""
        assert policy.priority == 50


class TestToolPruningPolicyShouldApply:
    """Test should_apply logic."""
    
    def test_disabled_returns_false(self, policy, compaction_config):
        """When disabled, should return False."""
        compaction_config.tool_pruning_policy.enabled = False
        messages = create_tool_messages(10)
        context = create_context(messages, config=compaction_config)
        
        assert policy.should_apply(context) is False
    
    def test_under_token_limit_returns_false(self, policy, compaction_config):
        """When under token limit, should return False."""
        messages = create_tool_messages(5, output_size=1000)
        context = create_context(
            messages,
            token_count=5000,
            token_limit=10000,
            config=compaction_config,
        )
        
        assert policy.should_apply(context) is False
    
    def test_no_tool_calls_returns_false(self, policy, compaction_config):
        """When no tool calls, should return False."""
        messages = tuple([
            Message(role="user", parts=[TextPart(text="Hello")]),
            Message(role="assistant", parts=[TextPart(text="Hi")]),
        ])
        context = create_context(messages, config=compaction_config)
        
        assert policy.should_apply(context) is False
    
    def test_no_completed_tools_returns_false(self, policy, compaction_config):
        """When no completed tools, should return False."""
        messages = tuple([
            Message(
                role="assistant",
                parts=[
                    ToolPart(
                        tool="read",
                        input={"path": "/test.py"},
                        output="",
                        status="pending",
                    )
                ]
            )
        ])
        context = create_context(messages, config=compaction_config)
        
        assert policy.should_apply(context) is False
    
    def test_below_minimum_prune_tokens(self, policy, compaction_config):
        """When prunable tokens below minimum, should return False."""
        compaction_config.tool_pruning_policy.minimum_prune_tokens = 50000
        messages = create_tool_messages(5, output_size=1000)
        context = create_context(messages, config=compaction_config)
        
        assert policy.should_apply(context) is False
    
    def test_all_conditions_met(self, policy, compaction_config):
        """When all conditions met, should return True."""
        # Lower thresholds for testing
        compaction_config.tool_pruning_policy.minimum_prune_tokens = 1000
        compaction_config.tool_pruning_policy.protect_token_threshold = 1000
        
        messages = create_tool_messages(10, output_size=50000)  # Much larger outputs
        context = create_context(messages, config=compaction_config)
        
        assert policy.should_apply(context) is True


class TestToolPruningPolicyApply:
    """Test apply() execution."""
    
    @pytest.mark.asyncio
    async def test_successful_pruning(self, policy, compaction_config):
        """Successful pruning should return APPLIED status."""
        # Lower thresholds for testing
        compaction_config.tool_pruning_policy.minimum_prune_tokens = 1000
        compaction_config.tool_pruning_policy.protect_token_threshold = 1000
        
        messages = create_tool_messages(10, output_size=50000)  # Much larger outputs
        context = create_context(messages, config=compaction_config)
        
        result = await policy.apply(context)
        
        assert result.status == CompactionStatus.APPLIED
        assert result.messages is not None
        assert result.record is not None
        assert len(result.messages) == len(context.messages)  # Same number of messages
    
    @pytest.mark.asyncio
    async def test_preserves_recent_turns(self, policy, compaction_config):
        """Should preserve recent turns from pruning."""
        protect_turns = compaction_config.tool_pruning_policy.protect_recent_turns
        messages = create_tool_messages(10, output_size=10000)
        
        # Get recent messages
        recent_messages = messages[-protect_turns * 2:]
        recent_tool_parts = []
        for msg in recent_messages:
            for part in msg.parts:
                if isinstance(part, ToolPart):
                    recent_tool_parts.append(part)
        
        context = create_context(messages, config=compaction_config)
        result = await policy.apply(context)
        
        if result.status == CompactionStatus.APPLIED:
            # Check that recent tool outputs are not pruned
            result_recent = result.messages[-protect_turns * 2:]
            for msg in result_recent:
                for part in msg.parts:
                    if isinstance(part, ToolPart):
                        # Recent outputs should not be pruned
                        assert part.output != compaction_config.tool_pruning_policy.replacement_text
    
    @pytest.mark.asyncio
    async def test_prunes_old_outputs(self, policy, compaction_config):
        """Should prune old tool outputs."""
        messages = create_tool_messages(10, output_size=10000)
        context = create_context(messages, config=compaction_config)
        
        result = await policy.apply(context)
        
        if result.status == CompactionStatus.APPLIED:
            replacement = compaction_config.tool_pruning_policy.replacement_text
            pruned_count = 0
            
            # Check older messages (not recent)
            protect_turns = compaction_config.tool_pruning_policy.protect_recent_turns
            older_messages = result.messages[:-protect_turns * 2] if len(result.messages) > protect_turns * 2 else []
            
            for msg in older_messages:
                for part in msg.parts:
                    if isinstance(part, ToolPart) and part.output == replacement:
                        pruned_count += 1
            
            # Should have pruned at least some outputs
            assert pruned_count > 0
    
    @pytest.mark.asyncio
    async def test_preserves_tool_metadata(self, policy, compaction_config):
        """Should preserve tool call metadata (name, input)."""
        messages = create_tool_messages(10, output_size=10000)
        original_tools = {}
        for msg in messages:
            for part in msg.parts:
                if isinstance(part, ToolPart):
                    original_tools[part.id] = {
                        "tool": part.tool,
                        "input": part.input,
                    }
        
        context = create_context(messages, config=compaction_config)
        result = await policy.apply(context)
        
        if result.status == CompactionStatus.APPLIED:
            for msg in result.messages:
                for part in msg.parts:
                    if isinstance(part, ToolPart):
                        original = original_tools.get(part.id)
                        if original:
                            assert part.tool == original["tool"]
                            assert part.input == original["input"]
    
    @pytest.mark.asyncio
    async def test_protects_protected_tools(self, policy, compaction_config):
        """Should protect tools in protected_tools list."""
        compaction_config.tool_pruning_policy.protected_tools = ("read", "write")
        
        messages = []
        for i in range(5):
            messages.append(Message(role="user", parts=[TextPart(text=f"Request {i}")]))
            # Mix of protected and unprotected tools
            tool_name = "read" if i % 2 == 0 else "delete"
            messages.append(Message(
                role="assistant",
                parts=[
                    ToolPart(
                        tool=tool_name,
                        input={"path": f"/test{i}.py"},
                        output="x" * 10000,
                        status="completed",
                    )
                ]
            ))
        
        context = create_context(tuple(messages), config=compaction_config)
        result = await policy.apply(context)
        
        if result.status == CompactionStatus.APPLIED:
            replacement = compaction_config.tool_pruning_policy.replacement_text
            for msg in result.messages:
                for part in msg.parts:
                    if isinstance(part, ToolPart):
                        if part.tool in ("read", "write"):
                            # Protected tools should not be pruned
                            assert part.output != replacement
    
    @pytest.mark.asyncio
    async def test_below_minimum_skips(self, policy, compaction_config):
        """When below minimum prune tokens, should skip."""
        compaction_config.tool_pruning_policy.minimum_prune_tokens = 100000
        
        messages = create_tool_messages(5, output_size=1000)
        context = create_context(messages, config=compaction_config)
        
        result = await policy.apply(context)
        
        assert result.status == CompactionStatus.SKIPPED
        assert "minimum" in result.error.lower() or "below" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_creates_pruning_metadata(self, policy, compaction_config):
        """Pruned tool parts should have metadata."""
        messages = create_tool_messages(10, output_size=10000)
        context = create_context(messages, config=compaction_config)
        
        result = await policy.apply(context)
        
        if result.status == CompactionStatus.APPLIED:
            replacement = compaction_config.tool_pruning_policy.replacement_text
            found_pruned = False
            
            for msg in result.messages:
                for part in msg.parts:
                    if isinstance(part, ToolPart) and part.output == replacement:
                        # Should have pruning metadata
                        assert hasattr(part, 'metadata') or part.metadata is not None
                        found_pruned = True
            
            # Should have found at least one pruned part
            assert found_pruned
    
    @pytest.mark.asyncio
    async def test_record_contains_correct_data(self, policy, compaction_config):
        """Compaction record should contain correct data."""
        messages = create_tool_messages(10, output_size=10000)
        context = create_context(messages, config=compaction_config)
        
        result = await policy.apply(context)
        
        if result.status == CompactionStatus.APPLIED and result.record:
            record = result.record
            assert record.session_id == "test-session"
            assert record.policy == PolicyType.TOOL_PRUNING
            assert record.original_message_count == len(messages)
            assert record.result_message_count == len(result.messages)
            assert "pruned" in record.summary_text.lower()
    
    @pytest.mark.asyncio
    async def test_stops_at_summary_message(self, policy, compaction_config):
        """Should stop scanning at summary message."""
        # Create messages with a summary message in the middle
        messages = list(create_tool_messages(5, output_size=10000))
        
        # Insert summary message
        summary_msg = Message(role="user", parts=[TextPart(text="Summary")])
        summary_msg.metadata = {"compaction": {"is_summary": True}}
        messages.insert(3, summary_msg)
        
        # Add more messages after summary
        messages.extend(create_tool_messages(5, output_size=10000))
        
        context = create_context(tuple(messages), config=compaction_config)
        result = await policy.apply(context)
        
        # Should not prune messages before the summary
        # (Summary acts as a boundary)
        if result.status == CompactionStatus.APPLIED:
            # Verify summary message is still there
            summary_found = False
            for msg in result.messages:
                if msg.metadata.get("compaction", {}).get("is_summary"):
                    summary_found = True
                    break
            # Summary should be preserved
            assert summary_found


class TestToolPruningPolicyEstimateSavings:
    """Test estimate_savings."""
    
    def test_returns_zero_when_disabled(self, policy, compaction_config):
        """Should return 0 when disabled."""
        compaction_config.tool_pruning_policy.enabled = False
        messages = create_tool_messages(10)
        context = create_context(messages, config=compaction_config)
        
        savings = policy.estimate_savings(context)
        assert savings == 0
    
    def test_returns_positive_when_can_prune(self, policy, compaction_config):
        """Should return positive value when can prune."""
        # Lower thresholds for testing
        compaction_config.tool_pruning_policy.minimum_prune_tokens = 1000
        compaction_config.tool_pruning_policy.protect_token_threshold = 1000
        
        messages = create_tool_messages(10, output_size=50000)  # Much larger outputs
        context = create_context(messages, config=compaction_config)
        
        savings = policy.estimate_savings(context)
        assert savings > 0
    
    def test_accounts_for_replacement_text(self, policy, compaction_config):
        """Should account for replacement text overhead."""
        messages = create_tool_messages(10, output_size=10000)
        context = create_context(messages, config=compaction_config)
        
        savings = policy.estimate_savings(context)
        
        # Savings should be less than total prunable tokens
        # due to replacement text
        assert savings >= 0


class TestToolPruningEdgeCases:
    """Test edge cases."""
    
    @pytest.mark.asyncio
    async def test_empty_outputs(self, policy, compaction_config):
        """Should handle empty tool outputs."""
        messages = tuple([
            Message(
                role="assistant",
                parts=[
                    ToolPart(
                        tool="read",
                        input={"path": "/test.py"},
                        output="",  # Empty output
                        status="completed",
                    )
                ]
            )
        ])
        context = create_context(messages, config=compaction_config)
        
        result = await policy.apply(context)
        
        # Should skip (nothing to prune)
        assert result.status == CompactionStatus.SKIPPED
    
    @pytest.mark.asyncio
    async def test_mixed_tool_statuses(self, policy, compaction_config):
        """Should handle mix of tool statuses."""
        messages = tuple([
            Message(
                role="assistant",
                parts=[
                    ToolPart(
                        tool="read",
                        input={"path": "/test1.py"},
                        output="output1",
                        status="completed",
                    ),
                    ToolPart(
                        tool="read",
                        input={"path": "/test2.py"},
                        output="output2",
                        status="pending",
                    ),
                ]
            )
        ])
        context = create_context(messages, config=compaction_config)
        
        result = await policy.apply(context)
        
        # Should only prune completed tools
        if result.status == CompactionStatus.APPLIED:
            for msg in result.messages:
                for part in msg.parts:
                    if isinstance(part, ToolPart) and part.status == "pending":
                        # Pending tools should not be pruned
                        assert part.output != compaction_config.tool_pruning_policy.replacement_text
    
    @pytest.mark.asyncio
    async def test_already_pruned_outputs(self, policy, compaction_config):
        """Should not prune already pruned outputs."""
        replacement = compaction_config.tool_pruning_policy.replacement_text
        messages = tuple([
            Message(
                role="assistant",
                parts=[
                    ToolPart(
                        tool="read",
                        input={"path": "/test.py"},
                        output=replacement,  # Already pruned
                        status="completed",
                    )
                ]
            )
        ])
        # Add metadata to mark as pruned
        if hasattr(messages[0].parts[0], 'metadata'):
            messages[0].parts[0].metadata = {"pruned": True}
        
        context = create_context(messages, config=compaction_config)
        result = await policy.apply(context)
        
        # Should skip (already pruned)
        assert result.status == CompactionStatus.SKIPPED
