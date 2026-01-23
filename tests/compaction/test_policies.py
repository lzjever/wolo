"""Tests for compaction policies."""

from unittest.mock import MagicMock

from wolo.compaction.config import CompactionConfig
from wolo.compaction.policy.pruning import ToolOutputPruningPolicy
from wolo.compaction.policy.summary import SummaryCompactionPolicy
from wolo.compaction.types import (
    CompactionContext,
    PolicyType,
)
from wolo.session import Message, TextPart, ToolPart


def create_messages(count: int) -> tuple:
    """Create test messages."""
    messages = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append(Message(role=role, parts=[TextPart(text=f"Message {i}")]))
    return tuple(messages)


def create_context(
    messages: tuple,
    token_count: int = 10000,
    token_limit: int = 8000,
    config: CompactionConfig = None,
) -> CompactionContext:
    """Create test context."""
    return CompactionContext(
        session_id="test-session",
        messages=messages,
        token_count=token_count,
        token_limit=token_limit,
        model="test-model",
        config=config or CompactionConfig(),
    )


class TestSummaryPolicyProperties:
    """Tests for SummaryCompactionPolicy properties."""

    def test_name_is_summary(self):
        """Name should be 'summary'."""
        policy = SummaryCompactionPolicy(MagicMock())
        assert policy.name == "summary"

    def test_policy_type_is_summary(self):
        """Policy type should be SUMMARY."""
        policy = SummaryCompactionPolicy(MagicMock())
        assert policy.policy_type == PolicyType.SUMMARY

    def test_priority_is_100(self):
        """Priority should be 100."""
        policy = SummaryCompactionPolicy(MagicMock())
        assert policy.priority == 100


class TestSummaryPolicyShouldApply:
    """Tests for SummaryCompactionPolicy.should_apply."""

    def test_returns_false_when_disabled(self):
        """Should return False when disabled."""
        policy = SummaryCompactionPolicy(MagicMock())
        config = CompactionConfig()
        config.summary_policy.enabled = False
        context = create_context(create_messages(20), config=config)

        assert policy.should_apply(context) is False

    def test_returns_false_when_not_enough_messages(self):
        """Should return False when not enough messages.

        recent_exchanges_to_keep = 6 means need at least 12 messages.
        """
        policy = SummaryCompactionPolicy(MagicMock())
        context = create_context(create_messages(10))

        assert policy.should_apply(context) is False

    def test_returns_false_when_under_limit(self):
        """Should return False when under token limit."""
        policy = SummaryCompactionPolicy(MagicMock())
        context = create_context(
            create_messages(20),
            token_count=5000,
            token_limit=8000,
        )

        assert policy.should_apply(context) is False

    def test_returns_true_when_all_conditions_met(self):
        """Should return True when all conditions met."""
        policy = SummaryCompactionPolicy(MagicMock())
        context = create_context(
            create_messages(20),
            token_count=10000,
            token_limit=8000,
        )

        assert policy.should_apply(context) is True


class TestSummaryPolicyEstimateSavings:
    """Tests for SummaryCompactionPolicy.estimate_savings."""

    def test_returns_positive_when_can_compact(self):
        """Should return positive value when can compact."""
        policy = SummaryCompactionPolicy(MagicMock())
        context = create_context(
            create_messages(20),
            token_count=10000,
        )

        savings = policy.estimate_savings(context)
        assert savings > 0

    def test_returns_zero_when_cannot_compact(self):
        """Should return 0 when cannot compact."""
        policy = SummaryCompactionPolicy(MagicMock())
        context = create_context(create_messages(10))

        savings = policy.estimate_savings(context)
        assert savings == 0


class TestToolPruningPolicyProperties:
    """Tests for ToolOutputPruningPolicy properties."""

    def test_name_is_tool_pruning(self):
        """Name should be 'tool_pruning'."""
        policy = ToolOutputPruningPolicy()
        assert policy.name == "tool_pruning"

    def test_policy_type_is_tool_pruning(self):
        """Policy type should be TOOL_PRUNING."""
        policy = ToolOutputPruningPolicy()
        assert policy.policy_type == PolicyType.TOOL_PRUNING

    def test_priority_is_50(self):
        """Priority should be 50."""
        policy = ToolOutputPruningPolicy()
        assert policy.priority == 50


class TestToolPruningPolicyShouldApply:
    """Tests for ToolOutputPruningPolicy.should_apply."""

    def test_returns_false_when_disabled(self):
        """Should return False when disabled."""
        policy = ToolOutputPruningPolicy()
        config = CompactionConfig()
        config.tool_pruning_policy.enabled = False

        messages = create_tool_messages(10)
        context = create_context(messages, config=config)

        assert policy.should_apply(context) is False

    def test_returns_false_when_no_tool_calls(self):
        """Should return False when no tool calls."""
        policy = ToolOutputPruningPolicy()
        context = create_context(create_messages(20))

        assert policy.should_apply(context) is False

    def test_returns_false_when_under_limit(self):
        """Should return False when under token limit."""
        policy = ToolOutputPruningPolicy()
        messages = create_tool_messages(5, output_size=100)
        context = create_context(
            messages,
            token_count=5000,
            token_limit=8000,
        )

        assert policy.should_apply(context) is False


def create_tool_messages(count: int, output_size: int = 5000) -> tuple:
    """Create messages with tool calls."""
    messages = []
    for i in range(count):
        messages.append(Message(role="user", parts=[TextPart(text=f"Request {i}")]))
        messages.append(
            Message(
                role="assistant",
                parts=[
                    ToolPart(
                        tool="read",
                        input={"path": f"/test{i}.py"},
                        output="x" * output_size,
                        status="completed",
                    )
                ],
            )
        )
    return tuple(messages)
