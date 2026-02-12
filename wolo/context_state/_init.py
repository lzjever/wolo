"""Context-state accessor functions.

This module provides the public API for accessing and modifying context state
stored in ContextVars. All accessor functions return copies to prevent
accidental mutation of the underlying context state.
"""

from wolo.context_state.vars import (
    _doom_loop_history_ctx,
    _session_todos_ctx,
    _token_usage_ctx,
)


def _default_token_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def get_api_token_usage() -> dict[str, int]:
    """Get a copy of the current API token usage.

    Returns:
        A dictionary with keys: prompt_tokens, completion_tokens, total_tokens.
        The returned dict is a copy; modifying it won't affect the context state.
    """
    try:
        return _token_usage_ctx.get().copy()
    except LookupError:
        val = _default_token_usage()
        _token_usage_ctx.set(val)
        return val.copy()


def reset_api_token_usage() -> None:
    """Reset API token usage to zero."""
    _token_usage_ctx.set(_default_token_usage())


def get_doom_loop_history() -> list[tuple[str, str, str]]:
    """Get a copy of the doom loop history.

    Returns:
        A list of tuples (tool_name, tool_input, tool_output).
        The returned list is a copy; modifying it won't affect the context state.
    """
    try:
        return _doom_loop_history_ctx.get().copy()
    except LookupError:
        _doom_loop_history_ctx.set([])
        return []


def add_doom_loop_entry(entry: tuple[str, str, str]) -> None:
    """Add an entry to doom loop history.

    Args:
        entry: A tuple (tool_name, tool_input, tool_output) representing
               a tool call that may be part of a doom loop.
    """
    try:
        history = _doom_loop_history_ctx.get()
    except LookupError:
        history = []
    new_history = history.copy()
    new_history.append(entry)
    _doom_loop_history_ctx.set(new_history)


def clear_doom_loop_history() -> None:
    """Clear doom loop history."""
    _doom_loop_history_ctx.set([])


def get_session_todos() -> list[dict]:
    """Get a copy of the current session todos.

    Returns:
        A list of todo dictionaries.
        The returned list is a copy; modifying it won't affect the context state.
    """
    try:
        return _session_todos_ctx.get().copy()
    except LookupError:
        _session_todos_ctx.set([])
        return []


def set_session_todos(todos: list[dict]) -> None:
    """Set the session todos.

    Args:
        todos: A list of todo dictionaries to set as the current todos.
               The input list will be copied before storage.
    """
    _session_todos_ctx.set(todos.copy())
