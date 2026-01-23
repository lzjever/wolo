"""Event bus tests."""

import asyncio

import pytest

from wolo.events import EventBus


class TestEventBus:
    """EventBus class tests."""

    @pytest.mark.asyncio
    async def test_async_subscribe_publish(self):
        """Test asynchronous subscribe and publish."""
        test_bus = EventBus()
        received = []

        async def async_callback(data):
            await asyncio.sleep(0.01)  # Simulate async work
            received.append(data)

        test_bus.subscribe("test_event", async_callback)
        await test_bus.publish("test_event", {"key": "value"})

        assert len(received) == 1
        assert received[0] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_mixed_subscribers(self):
        """Test mixed sync and async subscribers."""
        test_bus = EventBus()
        sync_received = []
        async_received = []

        def sync_callback(data):
            sync_received.append(data)

        async def async_callback(data):
            await asyncio.sleep(0.01)
            async_received.append(data)

        test_bus.subscribe("test_event", sync_callback)
        test_bus.subscribe("test_event", async_callback)

        await test_bus.publish("test_event", {"key": "value"})

        assert len(sync_received) == 1
        assert len(async_received) == 1
        assert sync_received[0] == {"key": "value"}
        assert async_received[0] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_sync_callback_support(self):
        """Test that publish works with sync callbacks."""
        test_bus = EventBus()
        received = []

        def sync_callback(data):
            received.append(data)

        test_bus.subscribe("test_event", sync_callback)
        await test_bus.publish("test_event", {"key": "value"})

        assert len(received) == 1
        assert received[0] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """Test multiple subscribers for same event."""
        test_bus = EventBus()
        received1 = []
        received2 = []

        def callback1(data):
            received1.append(data)

        def callback2(data):
            received2.append(data)

        test_bus.subscribe("test_event", callback1)
        test_bus.subscribe("test_event", callback2)
        await test_bus.publish("test_event", {"key": "value"})

        assert len(received1) == 1
        assert len(received2) == 1
