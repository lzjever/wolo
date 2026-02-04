"""Event bus for UI updates and agent events."""

import inspect
from collections.abc import Callable
from typing import Any


class EventBus:
    _subscribers: dict[str, list[Callable[[dict[str, Any]], None]]]

    def __init__(self) -> None:
        self._subscribers = {}

    def subscribe(self, event_type: str, callback: Callable[[dict[str, Any]], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """异步发布事件，支持异步订阅者"""
        for callback in self._subscribers.get(event_type, []):
            if inspect.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)


# Global event bus instance
bus = EventBus()
