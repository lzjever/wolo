"""Context-state infrastructure for Wolo.

This module provides a thread-safe, task-local state management system using
Python's ContextVar mechanism. It's designed for concurrent environments where
different tasks or sessions need isolated state.

Public API:
    - Token usage tracking: get_api_token_usage(), reset_api_token_usage()
    - Doom loop detection: get_doom_loop_history(), add_doom_loop_entry(), clear_doom_loop_history()
    - Session todos: get_session_todos(), set_session_todos()

All accessor functions return copies of the underlying state to prevent
accidental mutation. This ensures that the context state remains consistent
and predictable across concurrent operations.

The ContextVar instances (_token_usage_ctx, _doom_loop_history_ctx,
_session_todos_ctx) are exported for testing purposes but should not be
accessed directly in production code.
"""

from wolo.context_state._init import (
    add_doom_loop_entry,
    clear_doom_loop_history,
    get_api_token_usage,
    get_doom_loop_history,
    get_session_todos,
    reset_api_token_usage,
    set_session_todos,
)
from wolo.context_state.vars import (
    _doom_loop_history_ctx,
    _session_todos_ctx,
    _token_usage_ctx,
)

__all__ = [
    # Public API
    "get_api_token_usage",
    "reset_api_token_usage",
    "get_doom_loop_history",
    "add_doom_loop_entry",
    "clear_doom_loop_history",
    "get_session_todos",
    "set_session_todos",
    # Internal (for testing)
    "_token_usage_ctx",
    "_doom_loop_history_ctx",
    "_session_todos_ctx",
]
