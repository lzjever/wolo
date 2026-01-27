"""Pytest configuration for wolo tests."""

import pytest


def pytest_collection_modifyitems(config, items):
    """Modify collected test items to skip lexilux-dependent tests if unavailable."""
    try:
        import lexilux.chat.tools  # noqa: F401
        lexilux_available = True
    except ImportError:
        lexilux_available = False

    if not lexilux_available:
        for item in items:
            if "test_llm_adapter" in item.nodeid or "test_integration_agent_llm_adapter" in item.nodeid:
                item.add_marker(
                    pytest.mark.skip(reason="lexilux not installed - requires local path dependency")
                )
