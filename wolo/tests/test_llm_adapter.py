"""Tests for lexilux LLM adapter."""

from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if lexilux is not available
pytest.importorskip("lexilux", reason="lexilux not installed")

from wolo.config import Config
from wolo.llm_adapter import WoloLLMClient, get_token_usage, reset_token_usage


@pytest.fixture
def mock_config():
    """Create mock config."""
    config = MagicMock(spec=Config)
    config.base_url = "https://api.test.com/v1"
    config.api_key = "test-key"
    config.model = "test-model"  # Can be any OpenAI-compatible model
    config.temperature = 0.7
    config.max_tokens = 1000
    config.enable_think = True  # Reasoning mode
    config.debug_llm_file = None
    config.debug_full_dir = None
    return config


@pytest.mark.asyncio
async def test_wolo_llm_client_initialization(mock_config):
    """Test WoloLLMClient initialization."""
    client = WoloLLMClient(
        config=mock_config, session_id="test-session", agent_display_name="TestAgent"
    )

    assert client.enable_think is True
    assert client._session_id == "test-session"
    assert client.model == "test-model"
    assert client.temperature == 0.7


@pytest.mark.asyncio
async def test_opencode_headers_building(mock_config):
    """Test opencode headers construction."""
    client = WoloLLMClient(config=mock_config, session_id="test-session")

    headers = client._build_opencode_headers("test-session", "TestAgent")

    assert "x-opencode-session" in headers
    assert headers["x-opencode-session"] == "test-session"
    assert "x-opencode-client" in headers
    assert headers["x-opencode-client"] == "cli"
    assert "User-Agent" in headers
    assert "opencode/1.0.0" in headers["User-Agent"]


@pytest.mark.asyncio
async def test_message_format_conversion(mock_config):
    """Test wolo → lexilux message format conversion."""
    client = WoloLLMClient(config=mock_config)

    wolo_messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": ["text part"]},  # Multi-modal content
    ]

    lexilux_messages = client._to_lexilux_messages(wolo_messages)

    assert len(lexilux_messages) == 3
    assert lexilux_messages[0]["role"] == "user"
    assert lexilux_messages[0]["content"] == "Hello"
    assert lexilux_messages[1]["role"] == "assistant"
    assert lexilux_messages[1]["content"] == "Hi there!"
    # Multi-modal content should be converted to string
    assert lexilux_messages[2]["content"] == "text part"  # String list handled correctly


@pytest.mark.asyncio
async def test_tool_format_conversion(mock_config):
    """Test tool format conversion from dict to FunctionTool objects."""
    client = WoloLLMClient(config=mock_config)

    wolo_tools = [
        {"type": "function", "function": {"name": "test_tool", "description": "A test tool"}}
    ]

    lexilux_tools = client._convert_tools(wolo_tools)

    # Should convert to FunctionTool objects
    assert len(lexilux_tools) == 1
    tool = lexilux_tools[0]
    assert tool.name == "test_tool"
    assert tool.description == "A test tool"
    assert tool.type == "function"

    # Test None case
    assert client._convert_tools(None) is None


def test_token_usage_functions():
    """Test token usage compatibility functions."""
    # Reset should work
    reset_token_usage()
    usage = get_token_usage()

    assert usage["prompt_tokens"] == 0
    assert usage["completion_tokens"] == 0
    assert usage["total_tokens"] == 0


@pytest.mark.asyncio
async def test_compatibility_methods(mock_config):
    """Test compatibility methods with original GLMClient."""
    client = WoloLLMClient(config=mock_config)

    # Test property access (compatibility with original)
    assert hasattr(client, "finish_reason")
    assert hasattr(client, "api_key")
    assert hasattr(client, "base_url")
    assert hasattr(client, "model")
    assert hasattr(client, "temperature")
    assert hasattr(client, "max_tokens")
    assert hasattr(client, "enable_think")

    # Test class methods
    await WoloLLMClient.close_all_sessions()  # Should not raise


@pytest.mark.asyncio
@patch("wolo.llm_adapter.Chat")
async def test_chat_completion_basic_flow(mock_chat_class, mock_config):
    """Test basic chat completion flow with mocked lexilux."""
    # Setup mock
    mock_chat_instance = MagicMock()
    mock_chat_class.return_value = mock_chat_instance

    # Mock the stream response
    mock_chunk = MagicMock()
    mock_chunk.delta = "Hello"
    mock_chunk.reasoning_content = None
    mock_chunk.tool_calls = []
    mock_chunk.done = False
    mock_chunk.finish_reason = None
    mock_chunk.usage = MagicMock()
    mock_chunk.usage.input_tokens = 10
    mock_chunk.usage.output_tokens = 5
    mock_chunk.usage.total_tokens = 15

    mock_done_chunk = MagicMock()
    mock_done_chunk.delta = ""
    mock_done_chunk.reasoning_content = None
    mock_done_chunk.tool_calls = []
    mock_done_chunk.done = True
    mock_done_chunk.finish_reason = "stop"
    mock_done_chunk.usage = mock_chunk.usage

    # Create proper async iterator and async function
    async def mock_aiter():
        for chunk in [mock_chunk, mock_done_chunk]:
            yield chunk

    # astream should return a coroutine that resolves to an async iterator
    async def mock_astream(*args, **kwargs):
        return mock_aiter()

    mock_chat_instance.astream = mock_astream

    # Create client and test
    client = WoloLLMClient(config=mock_config)

    messages = [{"role": "user", "content": "Hello"}]
    events = []

    async for event in client.chat_completion(messages):
        events.append(event)

    # Verify events
    assert len(events) == 2
    assert events[0]["type"] == "text-delta"
    assert events[0]["text"] == "Hello"
    assert events[1]["type"] == "finish"
    assert events[1]["reason"] == "stop"

    # Verify that events were generated (indicates successful call)
    # Note: We can't verify exact call args since we replaced the mock method
    # but the successful event generation indicates the call worked


if __name__ == "__main__":
    pytest.main([__file__])
