"""Tests for llm_adapter context-state migration.

Tests that token usage tracking is properly isolated per async context
using the context-state infrastructure.
"""

from unittest.mock import MagicMock, patch

import pytest

# Check if lexilux is available
try:
    import lexilux  # noqa: F401

    LEXILUX_AVAILABLE = True
except ImportError:
    LEXILUX_AVAILABLE = False

if not LEXILUX_AVAILABLE:
    pytest.skip("lexilux not installed - requires local path dependency", allow_module_level=True)

from wolo.config import Config
from wolo.context_state import _token_usage_ctx

try:
    from wolo.llm_adapter import WoloLLMClient, get_token_usage, reset_token_usage
except ImportError:
    pytest.skip("lexilux not installed - requires local path dependency", allow_module_level=True)


@pytest.fixture
def mock_config():
    """Create mock config."""
    config = MagicMock(spec=Config)
    config.base_url = "https://api.test.com/v1"
    config.api_key = "test-key"
    config.model = "test-model"
    config.temperature = 0.7
    config.max_tokens = 1000
    config.enable_think = False
    config.debug_llm_file = None
    config.debug_full_dir = None
    return config


@pytest.mark.asyncio
async def test_token_usage_tracked_via_context_state(mock_config):
    """Test that token usage is tracked via context-state."""
    # Reset to ensure clean state
    reset_token_usage()

    # Mock the lexilux Chat to return token usage
    with patch("wolo.llm_adapter.Chat") as mock_chat_class:
        mock_chat_instance = MagicMock()
        mock_chat_class.return_value = mock_chat_instance

        # Mock chunk with token usage
        mock_chunk = MagicMock()
        mock_chunk.delta = "Hello"
        mock_chunk.reasoning_content = None
        mock_chunk.streaming_tool_calls = []
        mock_chunk.done = True
        mock_chunk.finish_reason = "stop"
        mock_chunk.usage = MagicMock()
        mock_chunk.usage.input_tokens = 100
        mock_chunk.usage.output_tokens = 50
        mock_chunk.usage.total_tokens = 150

        async def mock_aiter():
            yield mock_chunk

        async def mock_astream(*args, **kwargs):
            return mock_aiter()

        mock_chat_instance.astream = mock_astream

        # Create client and make a call
        client = WoloLLMClient(config=mock_config)
        messages = [{"role": "user", "content": "Hello"}]

        async for _ in client.chat_completion(messages):
            pass

        # Verify token usage was tracked via context-state
        usage = get_token_usage()
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150

        # Verify it's in the context-state ContextVar
        ctx_usage = _token_usage_ctx.get()
        assert ctx_usage["prompt_tokens"] == 100
        assert ctx_usage["completion_tokens"] == 50
        assert ctx_usage["total_tokens"] == 150


@pytest.mark.asyncio
async def test_reset_token_usage_via_context_state(mock_config):
    """Test that reset_token_usage resets context-state."""
    # Mock the lexilux Chat to return token usage
    with patch("wolo.llm_adapter.Chat") as mock_chat_class:
        mock_chat_instance = MagicMock()
        mock_chat_class.return_value = mock_chat_instance

        # Mock chunk with token usage
        mock_chunk = MagicMock()
        mock_chunk.delta = "Hello"
        mock_chunk.reasoning_content = None
        mock_chunk.streaming_tool_calls = []
        mock_chunk.done = True
        mock_chunk.finish_reason = "stop"
        mock_chunk.usage = MagicMock()
        mock_chunk.usage.input_tokens = 100
        mock_chunk.usage.output_tokens = 50
        mock_chunk.usage.total_tokens = 150

        async def mock_aiter():
            yield mock_chunk

        async def mock_astream(*args, **kwargs):
            return mock_aiter()

        mock_chat_instance.astream = mock_astream

        # Create client and make a call
        client = WoloLLMClient(config=mock_config)
        messages = [{"role": "user", "content": "Hello"}]

        async for _ in client.chat_completion(messages):
            pass

        # Verify token usage was tracked
        usage = get_token_usage()
        assert usage["total_tokens"] == 150

        # Reset and verify context-state is cleared
        reset_token_usage()
        usage = get_token_usage()
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0

        # Verify the ContextVar was reset
        ctx_usage = _token_usage_ctx.get()
        assert ctx_usage["prompt_tokens"] == 0
        assert ctx_usage["completion_tokens"] == 0
        assert ctx_usage["total_tokens"] == 0


@pytest.mark.asyncio
async def test_concurrent_sessions_isolated_token_usage(mock_config):
    """Test that token usage is isolated between concurrent async contexts."""
    import asyncio

    results = {}

    async def session_a():
        """First async context with its own token usage."""

        async def inner_a():
            # Mock the lexilux Chat
            with patch("wolo.llm_adapter.Chat") as mock_chat_class:
                mock_chat_instance = MagicMock()
                mock_chat_class.return_value = mock_chat_instance

                # Mock chunk with token usage
                mock_chunk = MagicMock()
                mock_chunk.delta = "Response A"
                mock_chunk.reasoning_content = None
                mock_chunk.streaming_tool_calls = []
                mock_chunk.done = True
                mock_chunk.finish_reason = "stop"
                mock_chunk.usage = MagicMock()
                mock_chunk.usage.input_tokens = 100
                mock_chunk.usage.output_tokens = 50
                mock_chunk.usage.total_tokens = 150

                async def mock_aiter():
                    yield mock_chunk

                async def mock_astream(*args, **kwargs):
                    return mock_aiter()

                mock_chat_instance.astream = mock_astream

                # Create client and make a call
                client = WoloLLMClient(config=mock_config)
                messages = [{"role": "user", "content": "Hello A"}]

                async for _ in client.chat_completion(messages):
                    pass

                # Get token usage for this context
                usage = get_token_usage()
                results["session_a"] = usage

        await inner_a()

    async def session_b():
        """Second async context with its own token usage."""

        async def inner_b():
            # Mock the lexilux Chat
            with patch("wolo.llm_adapter.Chat") as mock_chat_class:
                mock_chat_instance = MagicMock()
                mock_chat_class.return_value = mock_chat_instance

                # Mock chunk with different token usage
                mock_chunk = MagicMock()
                mock_chunk.delta = "Response B"
                mock_chunk.reasoning_content = None
                mock_chunk.streaming_tool_calls = []
                mock_chunk.done = True
                mock_chunk.finish_reason = "stop"
                mock_chunk.usage = MagicMock()
                mock_chunk.usage.input_tokens = 200
                mock_chunk.usage.output_tokens = 100
                mock_chunk.usage.total_tokens = 300

                async def mock_aiter():
                    yield mock_chunk

                async def mock_astream(*args, **kwargs):
                    return mock_aiter()

                mock_chat_instance.astream = mock_astream

                # Create client and make a call
                client = WoloLLMClient(config=mock_config)
                messages = [{"role": "user", "content": "Hello B"}]

                async for _ in client.chat_completion(messages):
                    pass

                # Get token usage for this context
                usage = get_token_usage()
                results["session_b"] = usage

        await inner_b()

    # Run both sessions concurrently
    await asyncio.gather(session_a(), session_b())

    # Verify each session has its own isolated token usage
    assert "session_a" in results
    assert "session_b" in results

    assert results["session_a"]["prompt_tokens"] == 100
    assert results["session_a"]["completion_tokens"] == 50
    assert results["session_a"]["total_tokens"] == 150

    assert results["session_b"]["prompt_tokens"] == 200
    assert results["session_b"]["completion_tokens"] == 100
    assert results["session_b"]["total_tokens"] == 300


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
