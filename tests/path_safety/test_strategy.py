# tests/path_safety/test_strategy.py
"""Tests for ConfirmationStrategy module."""

import pytest

from wolo.path_guard.strategy import (
    ConfirmationStrategy,
    AutoDenyConfirmationStrategy,
    AutoAllowConfirmationStrategy,
)


class TestAutoDenyConfirmationStrategy:
    def test_always_denies(self):
        """Should always return False."""
        strategy = AutoDenyConfirmationStrategy()
        result = await_or_sync(strategy.confirm("/any/path", "write"))
        assert result is False

    def test_denies_for_any_operation(self):
        """Should deny for any operation type."""
        strategy = AutoDenyConfirmationStrategy()
        assert await_or_sync(strategy.confirm("/path", "write")) is False
        assert await_or_sync(strategy.confirm("/path", "edit")) is False
        assert await_or_sync(strategy.confirm("/path", "read")) is False


class TestAutoAllowConfirmationStrategy:
    def test_always_allows(self):
        """Should always return True."""
        strategy = AutoAllowConfirmationStrategy()
        result = await_or_sync(strategy.confirm("/any/path", "write"))
        assert result is True

    def test_allows_for_any_operation(self):
        """Should allow for any operation type."""
        strategy = AutoAllowConfirmationStrategy()
        assert await_or_sync(strategy.confirm("/path", "write")) is True
        assert await_or_sync(strategy.confirm("/path", "edit")) is True
        assert await_or_sync(strategy.confirm("/path", "read")) is True


class TestConfirmationStrategyABC:
    def test_cannot_instantiate_abc(self):
        """Should not be able to instantiate abstract base class."""
        with pytest.raises(TypeError):
            ConfirmationStrategy()


# Helper function to handle both sync and async calls
def await_or_sync(coroutine_or_value):
    """Helper to await coroutine or return value directly."""
    import asyncio

    if asyncio.iscoroutine(coroutine_or_value):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, create task and return it
                # For test purposes, we'll use a simple approach
                import asyncio

                async def run():
                    return await coroutine_or_value

                return asyncio.run(run())
        except RuntimeError:
            pass
        return asyncio.run(coroutine_or_value)
    return coroutine_or_value


# Override tests to use async properly
@pytest.mark.asyncio
class TestAutoDenyConfirmationStrategyAsync:
    async def test_always_denies(self):
        """Should always return False."""
        strategy = AutoDenyConfirmationStrategy()
        result = await strategy.confirm("/any/path", "write")
        assert result is False

    async def test_denies_for_any_operation(self):
        """Should deny for any operation type."""
        strategy = AutoDenyConfirmationStrategy()
        assert await strategy.confirm("/path", "write") is False
        assert await strategy.confirm("/path", "edit") is False
        assert await strategy.confirm("/path", "read") is False


@pytest.mark.asyncio
class TestAutoAllowConfirmationStrategyAsync:
    async def test_always_allows(self):
        """Should always return True."""
        strategy = AutoAllowConfirmationStrategy()
        result = await strategy.confirm("/any/path", "write")
        assert result is True

    async def test_allows_for_any_operation(self):
        """Should allow for any operation type."""
        strategy = AutoAllowConfirmationStrategy()
        assert await strategy.confirm("/path", "write") is True
        assert await strategy.confirm("/path", "edit") is True
        assert await strategy.confirm("/path", "read") is True
