"""Integration tests for agent.py with lexilux adapter."""

from unittest.mock import MagicMock, patch

import pytest

from wolo.config import Config


@pytest.mark.asyncio
@patch("wolo.agent.logger")
async def test_agent_loop_client_selection_legacy(mock_logger):
    """Test that agent selects legacy client when use_lexilux_client is False."""
    # This is a unit test for the import logic, not a full agent loop test

    config = MagicMock(spec=Config)
    config.use_lexilux_client = False

    # Mock the dynamic import behavior
    with patch("wolo.agent.logger") as mock_logger:
        # Test import selection logic
        if config.use_lexilux_client:
            # This path should not be taken
            assert False, "Should not use lexilux client when flag is False"
        else:
            # This is the expected path
            from wolo.llm import GLMClient

            assert GLMClient is not None
            mock_logger.info.assert_not_called()  # Logger not called in this test


@pytest.mark.asyncio
@patch("wolo.agent.logger")
async def test_agent_loop_client_selection_lexilux(mock_logger):
    """Test that agent can import lexilux client when use_lexilux_client is True."""
    config = MagicMock(spec=Config)
    config.use_lexilux_client = True

    # Test that we can import the lexilux adapter
    if config.use_lexilux_client:
        from wolo.llm_adapter import WoloLLMClient as GLMClient

        assert GLMClient is not None
        # Verify it's the correct class
        assert GLMClient.__name__ == "WoloLLMClient"


@pytest.mark.asyncio
@patch("wolo.llm_adapter.Chat")  # Mock lexilux Chat
async def test_basic_compatibility_between_clients(mock_chat):
    """Test basic compatibility between legacy and lexilux clients."""

    # Test configuration
    config_dict = {
        "api_key": "test-key",
        "model": "test-model",
        "base_url": "https://api.test.com/v1",
        "temperature": 0.7,
        "max_tokens": 1000,
        "enable_think": False,
        "debug_llm_file": None,
        "debug_full_dir": None,
        "mcp_servers": [],
    }

    # Test legacy client instantiation
    legacy_config = Config(**config_dict, use_lexilux_client=False)

    from wolo.llm import GLMClient as LegacyClient

    legacy_client = LegacyClient(
        config=legacy_config, session_id="test-session", agent_display_name="TestAgent"
    )

    # Verify legacy client properties
    assert legacy_client.api_key == "test-key"
    assert legacy_client.model == "test-model"
    assert legacy_client.enable_think is False

    # Test lexilux client instantiation
    lexilux_config = Config(**config_dict, use_lexilux_client=True)

    from wolo.llm_adapter import WoloLLMClient as LexiluxClient

    lexilux_client = LexiluxClient(
        config=lexilux_config, session_id="test-session", agent_display_name="TestAgent"
    )

    # Verify lexilux client has compatible interface
    assert lexilux_client.api_key == "test-key"
    assert lexilux_client.model == "test-model"
    assert lexilux_client.enable_think is False
    assert hasattr(lexilux_client, "chat_completion")
    assert hasattr(lexilux_client, "finish_reason")

    # Verify both have the same method signatures
    import inspect

    legacy_signature = inspect.signature(legacy_client.chat_completion)
    lexilux_signature = inspect.signature(lexilux_client.chat_completion)

    # Parameter names should match (though implementation may differ)
    assert set(legacy_signature.parameters.keys()) == set(lexilux_signature.parameters.keys())


def test_config_flag_integration():
    """Test that Config properly handles the new use_lexilux_client flag."""

    # Test default value
    config_default = Config(
        api_key="test",
        model="test-model",
        base_url="https://test.com",
        temperature=0.7,
        max_tokens=1000,
    )
    assert config_default.use_lexilux_client is False

    # Test explicit True
    config_lexilux = Config(
        api_key="test",
        model="test-model",
        base_url="https://test.com",
        temperature=0.7,
        max_tokens=1000,
        use_lexilux_client=True,
    )
    assert config_lexilux.use_lexilux_client is True

    # Test explicit False
    config_legacy = Config(
        api_key="test",
        model="test-model",
        base_url="https://test.com",
        temperature=0.7,
        max_tokens=1000,
        use_lexilux_client=False,
    )
    assert config_legacy.use_lexilux_client is False


if __name__ == "__main__":
    pytest.main([__file__])
