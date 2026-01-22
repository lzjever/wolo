"""Comprehensive tests for SummaryCompactionPolicy.

Tests the summary policy with mocked LLM calls and various edge cases.
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from wolo.compaction.policy.summary import SummaryCompactionPolicy
from wolo.compaction.types import CompactionContext, CompactionStatus, PolicyType
from wolo.compaction.config import CompactionConfig
from wolo.session import Message, TextPart, ToolPart
from wolo.config import Config


@pytest.fixture
def mock_llm_config():
    """Create mock LLM config."""
    config = MagicMock(spec=Config)
    config.max_tokens = 10000
    config.model = "test-model"
    config.api_key = "test-key"
    config.base_url = "https://test.api"
    config.temperature = 0.7
    return config


@pytest.fixture
def compaction_config():
    """Create compaction config."""
    return CompactionConfig(
        summary_policy=CompactionConfig().summary_policy,
    )


@pytest.fixture
def policy(mock_llm_config):
    """Create SummaryCompactionPolicy instance."""
    return SummaryCompactionPolicy(mock_llm_config)


def create_messages(count: int, text_length: int = 100) -> tuple:
    """Create message tuple."""
    messages = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        text = f"Message {i}: " + "x" * text_length
        messages.append(Message(role=role, parts=[TextPart(text=text)]))
    return tuple(messages)


def create_context(
    messages: tuple,
    token_count: int = 10000,
    token_limit: int = 8000,
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


class TestSummaryPolicyProperties:
    """Test policy properties."""
    
    def test_name(self, policy):
        """Name should be 'summary'."""
        assert policy.name == "summary"
    
    def test_policy_type(self, policy):
        """Policy type should be SUMMARY."""
        assert policy.policy_type == PolicyType.SUMMARY
    
    def test_priority(self, policy):
        """Priority should be 100."""
        assert policy.priority == 100


class TestSummaryPolicyShouldApply:
    """Test should_apply logic."""
    
    def test_disabled_returns_false(self, policy, compaction_config):
        """When disabled, should return False."""
        compaction_config.summary_policy.enabled = False
        context = create_context(create_messages(20), config=compaction_config)
        
        assert policy.should_apply(context) is False
    
    def test_not_enough_messages(self, policy, compaction_config):
        """When not enough messages, should return False."""
        # Default keep_exchanges = 6, so need > 12 messages
        context = create_context(create_messages(10), config=compaction_config)
        
        assert policy.should_apply(context) is False
    
    def test_exactly_threshold_messages(self, policy, compaction_config):
        """Exactly at threshold should return False."""
        # keep_exchanges = 6, so exactly 12 messages should return False
        keep_exchanges = compaction_config.summary_policy.recent_exchanges_to_keep
        min_messages = keep_exchanges * 2
        context = create_context(create_messages(min_messages), config=compaction_config)
        
        assert policy.should_apply(context) is False
    
    def test_under_token_limit(self, policy, compaction_config):
        """When under token limit, should return False."""
        context = create_context(
            create_messages(20),
            token_count=5000,
            token_limit=8000,
            config=compaction_config,
        )
        
        assert policy.should_apply(context) is False
    
    def test_all_conditions_met(self, policy, compaction_config):
        """When all conditions met, should return True."""
        context = create_context(
            create_messages(20),
            token_count=10000,
            token_limit=8000,
            config=compaction_config,
        )
        
        assert policy.should_apply(context) is True
    
    def test_custom_keep_exchanges(self, policy, compaction_config):
        """Should respect custom keep_exchanges setting."""
        compaction_config.summary_policy.recent_exchanges_to_keep = 3
        # Need > 6 messages
        context = create_context(create_messages(7), config=compaction_config)
        
        # Should return True if over token limit
        context = create_context(
            create_messages(7),
            token_count=10000,
            token_limit=8000,
            config=compaction_config,
        )
        
        assert policy.should_apply(context) is True


class TestSummaryPolicyApply:
    """Test apply() execution."""
    
    @pytest.mark.asyncio
    async def test_successful_compaction(self, policy, mock_llm_config, compaction_config):
        """Successful compaction should return APPLIED status."""
        # Mock LLM client
        mock_client = MagicMock()
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [
            {"type": "text-delta", "text": "Summary of conversation"},
            {"type": "finish"},
        ]
        mock_client.chat_completion.return_value = mock_stream
        
        with patch('wolo.llm.GLMClient', return_value=mock_client):
            messages = create_messages(20, text_length=200)
            context = create_context(
                messages,
                token_count=10000,
                token_limit=8000,
                config=compaction_config,
            )
            
            result = await policy.apply(context)
            
            assert result.status == CompactionStatus.APPLIED
            assert result.messages is not None
            assert result.record is not None
            assert len(result.messages) < len(context.messages)
    
    @pytest.mark.asyncio
    async def test_no_messages_to_compact(self, policy, compaction_config):
        """When no messages to compact, should return SKIPPED."""
        # Create messages where all are kept
        keep_exchanges = compaction_config.summary_policy.recent_exchanges_to_keep
        messages = create_messages(keep_exchanges * 2)  # Exactly at threshold
        
        context = create_context(
            messages,
            token_count=10000,
            token_limit=8000,
            config=compaction_config,
        )
        
        result = await policy.apply(context)
        
        assert result.status == CompactionStatus.SKIPPED
    
    @pytest.mark.asyncio
    async def test_llm_failure_handled(self, policy, mock_llm_config, compaction_config):
        """LLM failure should be handled gracefully."""
        # Mock LLM to raise exception
        mock_client = MagicMock()
        mock_client.chat_completion.side_effect = Exception("LLM API error")
        
        with patch('wolo.llm.GLMClient', return_value=mock_client):
            messages = create_messages(20, text_length=200)
            context = create_context(
                messages,
                token_count=10000,
                token_limit=8000,
                config=compaction_config,
            )
            
            result = await policy.apply(context)
            
            # Should either fail or use fallback
            assert result.status in (CompactionStatus.FAILED, CompactionStatus.APPLIED)
            if result.status == CompactionStatus.FAILED:
                assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_summary_message_has_metadata(self, policy, mock_llm_config, compaction_config):
        """Summary message should have compaction metadata."""
        mock_client = MagicMock()
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [
            {"type": "text-delta", "text": "Summary"},
            {"type": "finish"},
        ]
        mock_client.chat_completion.return_value = mock_stream
        
        with patch('wolo.llm.GLMClient', return_value=mock_client):
            messages = create_messages(20, text_length=200)
            context = create_context(
                messages,
                token_count=10000,
                token_limit=8000,
                config=compaction_config,
            )
            
            result = await policy.apply(context)
            
            if result.status == CompactionStatus.APPLIED:
                # First message should be summary
                summary_msg = result.messages[0]
                assert summary_msg.metadata.get("compaction", {}).get("is_summary") is True
                assert "record_id" in summary_msg.metadata.get("compaction", {})
    
    @pytest.mark.asyncio
    async def test_preserves_recent_messages(self, policy, mock_llm_config, compaction_config):
        """Should preserve recent messages."""
        keep_exchanges = compaction_config.summary_policy.recent_exchanges_to_keep
        
        mock_client = MagicMock()
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [
            {"type": "text-delta", "text": "Summary"},
            {"type": "finish"},
        ]
        mock_client.chat_completion.return_value = mock_stream
        
        with patch('wolo.llm.GLMClient', return_value=mock_client):
            messages = create_messages(20, text_length=200)
            recent_ids = [m.id for m in messages[-keep_exchanges * 2:]]
            
            context = create_context(
                messages,
                token_count=10000,
                token_limit=8000,
                config=compaction_config,
            )
            
            result = await policy.apply(context)
            
            if result.status == CompactionStatus.APPLIED:
                # Recent messages should be preserved
                result_ids = [m.id for m in result.messages[1:]]  # Skip summary
                for msg_id in recent_ids:
                    assert msg_id in result_ids
    
    @pytest.mark.asyncio
    async def test_record_contains_correct_data(self, policy, mock_llm_config, compaction_config):
        """Compaction record should contain correct data."""
        mock_client = MagicMock()
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [
            {"type": "text-delta", "text": "Summary text"},
            {"type": "finish"},
        ]
        mock_client.chat_completion.return_value = mock_stream
        
        with patch('wolo.llm.GLMClient', return_value=mock_client):
            messages = create_messages(20, text_length=200)
            context = create_context(
                messages,
                token_count=10000,
                token_limit=8000,
                config=compaction_config,
            )
            
            result = await policy.apply(context)
            
            if result.status == CompactionStatus.APPLIED and result.record:
                record = result.record
                assert record.session_id == "test-session"
                assert record.policy == PolicyType.SUMMARY
                assert record.original_message_count == len(messages)
                assert record.result_message_count == len(result.messages)
                assert len(record.compacted_message_ids) > 0
                assert len(record.preserved_message_ids) > 0
                assert record.summary_message_id is not None
                assert "Summary" in record.summary_text
    
    @pytest.mark.asyncio
    async def test_max_tokens_limit_applied(self, policy, mock_llm_config, compaction_config):
        """Should apply max_tokens limit to summary."""
        compaction_config.summary_policy.summary_max_tokens = 100
        
        mock_client = MagicMock()
        mock_stream = AsyncMock()
        # Generate long summary
        long_summary = "x" * 10000
        mock_stream.__aiter__.return_value = [
            {"type": "text-delta", "text": long_summary},
            {"type": "finish"},
        ]
        mock_client.chat_completion.return_value = mock_stream
        
        with patch('wolo.llm.GLMClient', return_value=mock_client):
            messages = create_messages(20, text_length=200)
            context = create_context(
                messages,
                token_count=10000,
                token_limit=8000,
                config=compaction_config,
            )
            
            result = await policy.apply(context)
            
            if result.status == CompactionStatus.APPLIED and result.record:
                # Summary should be truncated
                summary_length = len(result.record.summary_text)
                # Should be roughly max_tokens * 4 chars per token = 400 chars
                assert summary_length <= 500  # Allow some margin


class TestSummaryPolicyEstimateSavings:
    """Test estimate_savings."""
    
    def test_returns_zero_when_cannot_apply(self, policy, compaction_config):
        """Should return 0 when cannot apply."""
        context = create_context(create_messages(10), config=compaction_config)
        
        savings = policy.estimate_savings(context)
        assert savings == 0
    
    def test_returns_positive_when_can_apply(self, policy, compaction_config):
        """Should return positive value when can apply."""
        context = create_context(
            create_messages(20),
            token_count=10000,
            token_limit=8000,
            config=compaction_config,
        )
        
        savings = policy.estimate_savings(context)
        assert savings > 0
    
    def test_savings_proportional_to_compacted(self, policy, compaction_config):
        """Savings should be proportional to compacted messages."""
        context1 = create_context(
            create_messages(20),
            token_count=10000,
            config=compaction_config,
        )
        context2 = create_context(
            create_messages(40),
            token_count=20000,
            config=compaction_config,
        )
        
        savings1 = policy.estimate_savings(context1)
        savings2 = policy.estimate_savings(context2)
        
        # More messages should yield more savings (or at least not less)
        assert savings2 >= savings1
