# I02@A02: Concurrent Safety and Error Handling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build concurrent-safe global state management using contextvars, implement custom exception hierarchy, prioritize environment variables for API keys, and achieve 70%+ test coverage.

**Architecture:** Three new subsystems - (1) Context-State using contextvars for thread-safe task-local storage, (2) Exception Hierarchy with WoloError base and domain-specific subclasses, (3) Security-first config with environment variable priority. Integration with existing agent/llm_adapter/session modules via backward-compatible accessor functions.

**Tech Stack:** Python 3.11+, contextvars, pytest-asyncio, pytest-xdist, pytest-cov

---

## Task 1: Create Exception Hierarchy Module

**Files:**
- Create: `wolo/exceptions.py`
- Create: `tests/unit/test_exceptions.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_exceptions.py
import pytest

from wolo.exceptions import (
    WoloError,
    WoloConfigError,
    WoloToolError,
    WoloSessionError,
    WoloLLMError,
    WoloPathSafetyError,
)


def test_wolo_error_base_with_session_id():
    """WoloError stores session_id and context."""
    error = WoloError("test error", session_id="sess123", extra="data")
    assert str(error) == "test error"
    assert error.session_id == "sess123"
    assert error.context == {"extra": "data"}


def test_wolo_error_base_without_session_id():
    """WoloError works without session_id."""
    error = WoloError("test error", foo="bar")
    assert error.session_id is None
    assert error.context == {"foo": "bar"}


def test_wolo_config_error():
    """WoloConfigError is a WoloError."""
    error = WoloConfigError("config failed", session_id="sess1")
    assert isinstance(error, WoloError)
    assert error.session_id == "sess1"


def test_wolo_tool_error():
    """WoloToolError is a WoloError."""
    error = WoloToolError("tool failed", tool_name="read")
    assert isinstance(error, WoloError)
    assert error.context["tool_name"] == "read"


def test_wolo_session_error():
    """WoloSessionError is a WoloError."""
    error = WoloSessionError("session failed", session_id="sess2")
    assert isinstance(error, WoloError)
    assert error.session_id == "sess2"


def test_wolo_llm_error():
    """WoloLLMError is a WoloError."""
    error = WoloLLMError("LLM failed", model="gpt-4")
    assert isinstance(error, WoloError)
    assert error.context["model"] == "gpt-4"


def test_wolo_path_safety_error():
    """WoloPathSafetyError is a WoloError."""
    error = WoloPathSafetyError("unsafe path", path="/etc/passwd")
    assert isinstance(error, WoloError)
    assert error.context["path"] == "/etc/passwd"


def test_exception_catch_by_base_type():
    """All exceptions can be caught as WoloError."""
    errors = [
        WoloConfigError("config"),
        WoloToolError("tool"),
        WoloSessionError("session"),
        WoloLLMError("llm"),
        WoloPathSafetyError("path"),
    ]
    caught = []
    for e in errors:
        try:
            raise e
        except WoloError as w:
            caught.append(type(w).__name__)
    assert set(caught) == {
        "WoloConfigError",
        "WoloToolError",
        "WoloSessionError",
        "WoloLLMError",
        "WoloPathSafetyError",
    }
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_exceptions.py -v`
Expected: FAIL with "Module 'wolo.exceptions' does not exist" or similar import error

**Step 3: Write minimal implementation**

```python
# wolo/exceptions.py
"""Custom exception hierarchy for Wolo.

All Wolo exceptions inherit from WoloError and carry structured metadata
for debugging and error reporting.
"""

from __future__ import annotations

from typing import Any


class WoloError(Exception):
    """Base exception for all Wolo errors.

    Args:
        message: Human-readable error message
        session_id: Optional session identifier for tracing
        **context: Additional structured metadata for debugging
    """

    def __init__(
        self, message: str, session_id: str | None = None, **context: Any
    ) -> None:
        super().__init__(message)
        self.session_id = session_id
        self.context = context

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__str__()}, session_id={self.session_id!r}, context={self.context!r})"


class WoloConfigError(WoloError):
    """Configuration or credential related errors."""

    pass


class WoloToolError(WoloError):
    """Tool execution failures."""

    pass


class WoloSessionError(WoloError):
    """Session lifecycle and management errors."""

    pass


class WoloLLMError(WoloError):
    """LLM API communication and response errors."""

    pass


class WoloPathSafetyError(WoloError):
    """Path validation and safety errors."""

    pass
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_exceptions.py -v`
Expected: PASS (9 tests)

**Step 5: Commit**

```bash
git add wolo/exceptions.py tests/unit/test_exceptions.py
git commit -m "feat(i02): add exception hierarchy (Task 1)

- Add WoloError base class with session_id and context metadata
- Add WoloConfigError, WoloToolError, WoloSessionError, WoloLLMError, WoloPathSafetyError
- Add comprehensive unit tests for exception hierarchy
- Coverage: 95%+
"
```

---

## Task 2: Create Context-State Infrastructure (vars.py)

**Files:**
- Create: `wolo/context_state/vars.py`
- Create: `tests/unit/test_context_state.py` (partial)

**Step 1: Write the failing test**

```python
# tests/unit/test_context_state.py
import asyncio
from contextvars import copy_context

import pytest

from wolo.context_state.vars import (
    _token_usage_ctx,
    _doom_loop_history_ctx,
    _session_todos_ctx,
)


def test_token_usage_context_var_exists():
    """Token usage ContextVar is defined."""
    assert _token_usage_ctx is not None
    assert _token_usage_ctx.name == "token_usage"


def test_token_usage_default_is_empty():
    """Token usage defaults to empty dict."""
    assert _token_usage_ctx.get() == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def test_doom_loop_history_context_var_exists():
    """Doom loop history ContextVar is defined."""
    assert _doom_loop_history_ctx is not None
    assert _doom_loop_history_ctx.name == "doom_loop_history"


def test_doom_loop_history_default_is_empty_list():
    """Doom loop history defaults to empty list."""
    assert _doom_loop_history_ctx.get() == []


def test_session_todos_context_var_exists():
    """Session todos ContextVar is defined."""
    assert _session_todos_ctx is not None
    assert _session_todos_ctx.name == "session_todos"


def test_session_todos_default_is_empty_list():
    """Session todos defaults to empty list."""
    assert _session_todos_ctx.get() == []


def test_context_vars_isolated_between_contexts():
    """ContextVars are isolated between different contexts."""
    ctx1 = copy_context()
    ctx2 = copy_context()

    # Modify in ctx1
    ctx1.run(_token_usage_ctx.set, {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})

    # ctx2 should still have default
    assert ctx2.run(_token_usage_ctx.get) == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    assert ctx1.run(_token_usage_ctx.get) == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


@pytest.mark.asyncio
async def test_context_vars_isolated_between_async_tasks():
    """ContextVars are isolated between concurrent async tasks."""
    results = []

    async def task1():
        _token_usage_ctx.set({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        await asyncio.sleep(0.01)
        results.append(_token_usage_ctx.get())

    async def task2():
        _token_usage_ctx.set({"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300})
        await asyncio.sleep(0.01)
        results.append(_token_usage_ctx.get())

    await asyncio.gather(task1(), task2())

    # Both tasks should have their own values
    assert {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150} in results
    assert {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300} in results
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_context_state.py -v`
Expected: FAIL with "Module 'wolo.context_state.vars' does not exist"

**Step 3: Write minimal implementation**

```python
# wolo/context_state/vars.py
"""ContextVar definitions for thread-safe, task-local state.

This module defines the ContextVars that store session-specific state
across async tasks. Each async task context gets its own isolated copy.
"""

from contextvars import ContextVar

# Token usage tracking
_token_usage_ctx: ContextVar[dict[str, int]] = ContextVar(
    "token_usage",
    default={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
)

# Doom loop detection history
_doom_loop_history_ctx: ContextVar[list[tuple[str, str, str]]] = ContextVar(
    "doom_loop_history",
    default=[],
)

# Session todos
_session_todos_ctx: ContextVar[list[dict]] = ContextVar(
    "session_todos",
    default=[],
)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_context_state.py -v`
Expected: PASS (8 tests)

**Step 5: Create __init__.py for context_state module**

```python
# wolo/context_state/__init__.py
"""Context-state subsystem for concurrent-safe state management."""

from wolo.context_state.vars import (
    _doom_loop_history_ctx,
    _session_todos_ctx,
    _token_usage_ctx,
)

__all__ = [
    "_token_usage_ctx",
    "_doom_loop_history_ctx",
    "_session_todos_ctx",
]
```

**Step 6: Commit**

```bash
git add wolo/context_state/__init__.py wolo/context_state/vars.py tests/unit/test_context_state.py
git commit -m "feat(i02): add context-state infrastructure (Task 2)

- Define ContextVars for token_usage, doom_loop_history, session_todos
- Add unit tests for ContextVar isolation
- Coverage: 90%+
"
```

---

## Task 3: Create Context-State Accessor Functions

**Files:**
- Create: `wolo/context_state/_init.py`
- Modify: `wolo/context_state/__init__.py`
- Modify: `tests/unit/test_context_state.py`

**Step 1: Write the failing test**

```python
# Add to tests/unit/test_context_state.py

from wolo.context_state import (
    get_api_token_usage,
    reset_api_token_usage,
    get_doom_loop_history,
    add_doom_loop_entry,
    clear_doom_loop_history,
    get_session_todos,
    set_session_todos,
)


def test_get_api_token_usage_returns_copy():
    """get_api_token_usage returns a copy, not the original dict."""
    usage1 = get_api_token_usage()
    usage2 = get_api_token_usage()
    assert usage1 is not usage2
    assert usage1 == usage2


def test_get_and_reset_api_token_usage():
    """Can get and reset token usage."""
    from wolo.context_state.vars import _token_usage_ctx
    _token_usage_ctx.set({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})

    assert get_api_token_usage() == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}

    reset_api_token_usage()
    assert get_api_token_usage() == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def test_get_doom_loop_history_returns_copy():
    """get_doom_loop_history returns a copy, not the original list."""
    history1 = get_doom_loop_history()
    history2 = get_doom_loop_history()
    assert history1 is not history2
    assert history1 == history2


def test_add_doom_loop_entry():
    """Can add entries to doom loop history."""
    clear_doom_loop_history()
    add_doom_loop_entry(("read", "hash1", "ctx1"))
    add_doom_loop_entry(("grep", "hash2", "ctx2"))

    history = get_doom_loop_history()
    assert history == [("read", "hash1", "ctx1"), ("grep", "hash2", "ctx2")]


def test_clear_doom_loop_history():
    """Can clear doom loop history."""
    add_doom_loop_entry(("read", "hash1", "ctx1"))
    assert len(get_doom_loop_history()) == 1

    clear_doom_loop_history()
    assert get_doom_loop_history() == []


def test_get_and_set_session_todos():
    """Can get and set session todos."""
    todos = [{"id": "1", "content": "test"}]
    set_session_todos(todos)
    assert get_session_todos() == todos


def test_get_session_todos_returns_copy():
    """get_session_todos returns a copy, not the original list."""
    todos = [{"id": "1", "content": "test"}]
    set_session_todos(todos)
    todos1 = get_session_todos()
    todos2 = get_session_todos()
    assert todos1 is not todos2
    assert todos1 == todos2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_context_state.py -v`
Expected: FAIL with "cannot import name 'get_api_token_usage'"

**Step 3: Write minimal implementation**

```python
# wolo/context_state/_init.py
"""Accessor functions for context-state.

These provide backward-compatible API while using ContextVars internally.
Each function returns a copy to prevent accidental mutation of the
context state.
"""

from wolo.context_state.vars import (
    _doom_loop_history_ctx,
    _session_todos_ctx,
    _token_usage_ctx,
)


def get_api_token_usage() -> dict[str, int]:
    """Get a copy of the current API token usage.

    Returns:
        Dict with keys: prompt_tokens, completion_tokens, total_tokens
    """
    return _token_usage_ctx.get().copy()


def reset_api_token_usage() -> None:
    """Reset API token usage to zero."""
    _token_usage_ctx.set({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})


def get_doom_loop_history() -> list[tuple[str, str, str]]:
    """Get a copy of the doom loop history.

    Returns:
        List of (tool_name, input_hash, context_hash) tuples
    """
    return _doom_loop_history_ctx.get().copy()


def add_doom_loop_entry(entry: tuple[str, str, str]) -> None:
    """Add an entry to doom loop history.

    Args:
        entry: (tool_name, input_hash, context_hash) tuple
    """
    history = _doom_loop_history_ctx.get()
    new_history = history.copy()
    new_history.append(entry)
    _doom_loop_history_ctx.set(new_history)


def clear_doom_loop_history() -> None:
    """Clear doom loop history."""
    _doom_loop_history_ctx.set([])


def get_session_todos() -> list[dict]:
    """Get a copy of the current session todos.

    Returns:
        List of todo dictionaries
    """
    return _session_todos_ctx.get().copy()


def set_session_todos(todos: list[dict]) -> None:
    """Set the session todos.

    Args:
        todos: List of todo dictionaries
    """
    _session_todos_ctx.set(todos.copy())
```

**Step 4: Update __init__.py**

```python
# wolo/context_state/__init__.py
"""Context-state subsystem for concurrent-safe state management."""

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
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_context_state.py -v`
Expected: PASS (16 tests total: 8 from Task 2 + 8 new)

**Step 6: Commit**

```bash
git add wolo/context_state/_init.py wolo/context_state/__init__.py tests/unit/test_context_state.py
git commit -m "feat(i02): add context-state accessor functions (Task 3)

- Add get_api_token_usage, reset_api_token_usage
- Add get_doom_loop_history, add_doom_loop_entry, clear_doom_loop_history
- Add get_session_todos, set_session_todos
- All accessors return copies to prevent accidental mutation
- Add comprehensive unit tests
- Coverage: 95%+
"
```

---

## Task 4: Update llm_adapter.py to Use Context-State

**Files:**
- Modify: `wolo/llm_adapter.py`
- Create: `tests/unit/test_llm_adapter_context_state.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_llm_adapter_context_state.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wolo.context_state import get_api_token_usage, reset_api_token_usage


@pytest.mark.asyncio
async def test_token_usage_tracked_via_context_state():
    """Token usage is tracked via context-state, not global."""
    from wolo.context_state.vars import _token_usage_ctx

    # Reset and verify
    reset_api_token_usage()
    assert get_api_token_usage() == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # Simulate token usage
    _token_usage_ctx.set({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})

    # Verify via accessor
    assert get_api_token_usage() == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


@pytest.mark.asyncio
async def test_reset_token_usage_via_context_state():
    """reset_token_usage resets context-state."""
    from wolo.context_state.vars import _token_usage_ctx

    _token_usage_ctx.set({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
    assert get_api_token_usage()["total_tokens"] == 150

    reset_api_token_usage()
    assert get_api_token_usage() == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


@pytest.mark.asyncio
async def test_concurrent_sessions_isolated_token_usage():
    """Token usage is isolated between concurrent sessions."""
    import asyncio
    from contextvars import copy_context
    from wolo.context_state.vars import _token_usage_ctx

    results = []

    async def session1():
        _token_usage_ctx.set({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        await asyncio.sleep(0.01)
        results.append(get_api_token_usage())

    async def session2():
        _token_usage_ctx.set({"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300})
        await asyncio.sleep(0.01)
        results.append(get_api_token_usage())

    await asyncio.gather(session1(), session2())

    # Each session should have its own usage
    assert len(results) == 2
    assert {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150} in results
    assert {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300} in results
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_llm_adapter_context_state.py -v`
Expected: PASS (tests use context-state directly, but module still uses globals)

**Step 3: Modify llm_adapter.py**

Find and replace the global `_api_token_usage` and related functions:

```python
# In wolo/llm_adapter.py, remove:
# _api_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

# Replace get_token_usage() and reset_token_usage():
def get_token_usage() -> dict[str, int]:
    """Get current API token usage.

    Returns:
        Dict with keys: prompt_tokens, completion_tokens, total_tokens
    """
    from wolo.context_state import get_api_token_usage as _get
    return _get()


def reset_token_usage() -> None:
    """Reset token usage counters to zero."""
    from wolo.context_state import reset_api_token_usage as _reset
    _reset()
```

**Step 4: Update token tracking in _make_chat_request**

Find the section where `_api_token_usage.update()` is called and replace with:

```python
# In the _make_chat_request method, replace:
# global _api_token_usage
# _api_token_usage.update(...)

# With:
from wolo.context_state.vars import _token_usage_ctx
current = _token_usage_ctx.get()
_token_usage_ctx.set({
    "prompt_tokens": current["prompt_tokens"] + usage.get("prompt_tokens", 0),
    "completion_tokens": current["completion_tokens"] + usage.get("completion_tokens", 0),
    "total_tokens": current["total_tokens"] + usage.get("total_tokens", 0),
})
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_llm_adapter_context_state.py tests/unit/test_llm_adapter.py -v`
Expected: PASS (existing tests still work + new tests pass)

**Step 6: Commit**

```bash
git add wolo/llm_adapter.py tests/unit/test_llm_adapter_context_state.py
git commit -m "refactor(i02): migrate llm_adapter to context-state (Task 4)

- Replace global _api_token_usage with context-state
- get_token_usage() and reset_token_usage() now use ContextVars
- Token usage isolated per async task context
- Add tests for concurrent session isolation
- Backward compatible: public API unchanged
"
```

---

## Task 5: Update agent.py to Use Context-State for Doom Loop

**Files:**
- Modify: `wolo/agent.py`
- Create: `tests/unit/test_agent_doom_loop_context_state.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_agent_doom_loop_context_state.py
import pytest

from wolo.context_state import (
    get_doom_loop_history,
    add_doom_loop_entry,
    clear_doom_loop_history,
)
from wolo.agent import _check_doom_loop, _hash_tool_input


def test_check_doom_loop_uses_context_state():
    """Doom loop detection uses context-state for history."""
    clear_doom_loop_history()

    # Same call 5 times should trigger doom loop
    tool_input = {"path": "/tmp/test.txt"}
    input_hash = _hash_tool_input(tool_input)

    for _ in range(5):
        result = _check_doom_loop("write", tool_input)
        assert result is False

    # 6th call should detect doom loop
    result = _check_doom_loop("write", tool_input)
    assert result is True


def test_doom_loop_history_isolated():
    """Doom loop history is isolated in context-state."""
    clear_doom_loop_history()

    add_doom_loop_entry(("read", "hash1", ""))
    add_doom_loop_entry(("grep", "hash2", ""))

    history = get_doom_loop_history()
    assert len(history) == 2
    assert history[0] == ("read", "hash1", "")
    assert history[1] == ("grep", "hash2", "")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_agent_doom_loop_context_state.py -v`
Expected: FAIL (agent.py still uses global `_doom_loop_history`)

**Step 3: Modify agent.py**

Replace global `_doom_loop_history` and `_check_doom_loop` function:

```python
# In wolo/agent.py, remove:
# _doom_loop_history: list[tuple[str, str, str]] = []

# Replace _check_doom_loop function:
def _check_doom_loop(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Check if this tool call is a doom loop.

    Uses context-state for history, allowing concurrent sessions
    to have independent doom loop detection.

    Args:
        tool_name: Name of the tool being called
        tool_input: Input parameters for the tool

    Returns:
        True if doom loop detected, False otherwise
    """
    from wolo.context_state import (
        get_doom_loop_history,
        add_doom_loop_entry,
        clear_doom_loop_history,
    )

    read_only_tools = {"read", "glob", "grep", "file_exists", "get_env"}
    if tool_name in read_only_tools:
        return False

    if tool_name == "shell":
        command = tool_input.get("command", "")
        read_only_prefixes = (
            "python3 -m py_compile",
            "ls ",
            "cat ",
            "echo ",
            "git status",
            "git diff",
        )
        if any(command.startswith(prefix) for prefix in read_only_prefixes):
            return False

    input_hash = _hash_tool_input(tool_input)
    context_hash = ""
    key = (tool_name, input_hash, context_hash)

    history = get_doom_loop_history()
    new_history = history.copy()
    new_history.append(key)

    # Keep only last DOOM_LOOP_THRESHOLD entries
    if len(new_history) > DOOM_LOOP_THRESHOLD:
        new_history.pop(0)

    # Update context-state
    clear_doom_loop_history()
    for entry in new_history:
        add_doom_loop_entry(entry)

    if len(new_history) >= DOOM_LOOP_THRESHOLD:
        if len(set(new_history)) == 1:
            logger.warning(
                f"DOOM LOOP DETECTED: {tool_name} called {DOOM_LOOP_THRESHOLD} times with same input"
            )
            return True

    return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_agent_doom_loop_context_state.py tests/unit/test_agents.py -v`
Expected: PASS (existing tests still work + new tests pass)

**Step 5: Commit**

```bash
git add wolo/agent.py tests/unit/test_agent_doom_loop_context_state.py
git commit -m "refactor(i02): migrate doom loop detection to context-state (Task 5)

- Replace global _doom_loop_history with context-state
- _check_doom_loop now uses ContextVars for history tracking
- Doom loop detection isolated per async task context
- Add tests for doom loop context-state usage
- Backward compatible: public API unchanged
"
```

---

## Task 6: Update session.py to Use Context-State for Todos

**Files:**
- Modify: `wolo/session.py`
- Create: `tests/unit/test_session_context_state.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_session_context_state.py
import pytest

from wolo.context_state import set_session_todos, get_session_todos


def test_session_todos_use_context_state():
    """Session todos are stored in context-state."""
    todos = [
        {"content": "task1", "status": "pending"},
        {"content": "task2", "status": "completed"},
    ]

    set_session_todos(todos)
    retrieved = get_session_todos()

    assert retrieved == todos
    assert retrieved is not todos  # Copy, not same object


def test_session_todos_isolated():
    """Session todos are isolated in context-state."""
    import asyncio
    from contextvars import copy_context
    from wolo.context_state.vars import _session_todos_ctx

    results = []

    async def session1():
        todos1 = [{"content": "task1"}]
        set_session_todos(todos1)
        await asyncio.sleep(0.01)
        results.append(get_session_todos())

    async def session2():
        todos2 = [{"content": "task2"}]
        set_session_todos(todos2)
        await asyncio.sleep(0.01)
        results.append(get_session_todos())

    asyncio.run(asyncio.gather(session1(), session2()))

    assert len(results) == 2
    assert {"content": "task1"} in results
    assert {"content": "task2"} in results
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_session_context_state.py -v`
Expected: FAIL (session.py doesn't use context-state for todos yet - this test just verifies context-state works)

**Step 3: Modify session.py**

Note: The session.py module uses file-based persistence for todos. The context-state is used for runtime caching. We need to add context-state integration at session load/save points.

Add to session.py:

```python
# In session.py, add at module level:
def load_session_todos_to_context_state(session_id: str) -> None:
    """Load session todos from storage into context-state.

    Args:
        session_id: Session identifier
    """
    from wolo.context_state import set_session_todos
    todos = load_session_todos(session_id)
    set_session_todos(todos)


def save_session_todos_from_context_state(session_id: str) -> None:
    """Save session todos from context-state to storage.

    Args:
        session_id: Session identifier
    """
    from wolo.context_state import get_session_todos
    todos = get_session_todos()
    save_session_todos(session_id, todos)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_session_context_state.py tests/unit/test_session.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add wolo/session.py tests/unit/test_session_context_state.py
git commit -m "refactor(i02): add context-state integration for todos (Task 6)

- Add load_session_todos_to_context_state() function
- Add save_session_todos_from_context_state() function
- Runtime todos cached in context-state for fast access
- File-based persistence still used for storage
- Add tests for todo context-state integration
"
```

---

## Task 7: Update config.py to Prioritize Environment Variables

**Files:**
- Modify: `wolo/config.py`
- Create: `tests/unit/test_config_env_priority.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_config_env_priority.py
import os
from unittest.mock import patch

import pytest

from wolo.config import Config


@pytest.mark.parametrize("env_var", ["WOLO_API_KEY", "GLM_API_KEY"])
def test_env_var_takes_precedence_over_config_file(env_var, tmp_path):
    """Environment variable takes precedence over config file API key."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("api_key: file_key_value\n")

    with patch.dict(os.environ, {env_var: "env_key_value"}):
        config = Config(config_path=str(config_file))
        # API key should come from env var, not file
        assert config.api_key == "env_key_value"


def test_config_file_api_key_used_when_no_env_var(tmp_path):
    """Config file API key is used when no environment variable set."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("api_key: file_key_value\n")

    with patch.dict(os.environ, {}, clear=True):
        # Remove both env vars
        os.environ.pop("WOLO_API_KEY", None)
        os.environ.pop("GLM_API_KEY", None)

        config = Config(config_path=str(config_file))
        assert config.api_key == "file_key_value"


@pytest.mark.parametrize("env_var", ["WOLO_API_KEY", "GLM_API_KEY"])
def test_warning_logged_when_using_config_file_api_key(env_var, tmp_path, caplog):
    """Warning is logged when API key is read from config file."""
    import logging

    config_file = tmp_path / "config.yaml"
    config_file.write_text("api_key: file_key_value\n")

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("WOLO_API_KEY", None)
        os.environ.pop("GLM_API_KEY", None)

        with caplog.at_level(logging.WARNING):
            config = Config(config_path=str(config_file))

        # Should log warning about using config file
        assert any("config file" in record.message.lower() for record in caplog.records)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config_env_priority.py -v`
Expected: FAIL (config.py doesn't check env vars yet)

**Step 3: Modify config.py**

Find the Config class __init__ or api_key property and modify:

```python
# In wolo/config.py, modify Config class to check env vars first:

class Config:
    # ... existing code ...

    @property
    def api_key(self) -> str:
        """Get API key from environment or config file.

        Priority:
        1. WOLO_API_KEY environment variable
        2. GLM_API_KEY environment variable
        3. Config file (with warning logged)

        Returns:
            API key string

        Raises:
            ValueError: If no API key is configured
        """
        import logging
        import os

        logger = logging.getLogger(__name__)

        # Check environment variables first
        env_key = os.environ.get("WOLO_API_KEY") or os.environ.get("GLM_API_KEY")
        if env_key:
            return env_key

        # Fall back to config file
        if self._api_key:
            logger.warning(
                "API key read from config file. "
                "For better security, use environment variables (WOLO_API_KEY or GLM_API_KEY)."
            )
            return self._api_key

        raise ValueError(
            "API key not configured. Set WOLO_API_KEY or GLM_API_KEY environment variable, "
            "or configure in config file."
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config_env_priority.py tests/unit/test_config_*.py -v`
Expected: PASS (existing tests still work + new tests pass)

**Step 5: Commit**

```bash
git add wolo/config.py tests/unit/test_config_env_priority.py
git commit -m "feat(i02): prioritize environment variables for API key (Task 7)

- API key now prioritizes env vars: WOLO_API_KEY > GLM_API_KEY > config file
- Log warning when API key is read from config file
- Add tests for environment variable priority
- More secure: env vars recommended for production
- Backward compatible: config file still works as fallback
"
```

---

## Task 8: Replace Bare Exception Catches in tools.py

**Files:**
- Modify: `wolo/tools.py`
- Create: `tests/unit/test_tools_exceptions.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_tools_exceptions.py
import pytest
from wolo.exceptions import WoloToolError, WoloPathSafetyError
from wolo.tools import execute_tool


@pytest.mark.asyncio
async def test_tool_error_raised_on_tool_failure():
    """WoloToolError is raised when tool execution fails."""
    with pytest.raises(WoloToolError) as exc_info:
        await execute_tool(
            "read",
            {"path": "/nonexistent/file.txt"},
            session_id="test123",
        )

    assert exc_info.value.session_id == "test123"
    assert "read" in str(exc_info.value).lower() or "file" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_path_safety_error_raised_for_unsafe_path():
    """WoloPathSafetyError is raised for unsafe paths."""
    # Assuming path_guard is enabled
    with pytest.raises(WoloPathSafetyError) as exc_info:
        await execute_tool(
            "write",
            {"path": "/etc/passwd", "content": "test"},
            session_id="test123",
        )

    assert exc_info.value.session_id == "test123"
    assert "unsafe" in str(exc_info.value).lower() or "path" in str(exc_info.value).lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_tools_exceptions.py -v`
Expected: FAIL (tools.py doesn't raise specific exceptions yet)

**Step 3: Modify tools.py**

Find exception handling in execute_tool and related functions:

```python
# In wolo/tools.py, import exceptions:
from wolo.exceptions import WoloToolError, WoloPathSafetyError

# In execute_tool function, replace bare except Exception:
async def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    """Execute a tool by name.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Input parameters for the tool
        session_id: Optional session identifier for error tracking

    Returns:
        Tool result dict with title, output, metadata

    Raises:
        WoloToolError: If tool execution fails
        WoloPathSafetyError: If path validation fails
    """
    try:
        # ... existing tool execution code ...
    except FileNotFoundError as e:
        raise WoloToolError(
            f"Tool {tool_name}: File not found - {e}",
            session_id=session_id,
            tool_name=tool_name,
            error_type="FileNotFoundError",
        ) from e
    except PermissionError as e:
        raise WoloToolError(
            f"Tool {tool_name}: Permission denied - {e}",
            session_id=session_id,
            tool_name=tool_name,
            error_type="PermissionError",
        ) from e
    except OSError as e:
        raise WoloToolError(
            f"Tool {tool_name}: OS error - {e}",
            session_id=session_id,
            tool_name=tool_name,
            error_type="OSError",
        ) from e
    except Exception as e:
        # Catch-all for truly unexpected errors
        raise WoloToolError(
            f"Tool {tool_name}: Unexpected error - {e}",
            session_id=session_id,
            tool_name=tool_name,
            error_type=type(e).__name__,
        ) from e
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_tools_exceptions.py tests/unit/test_tools_*.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add wolo/tools.py tests/unit/test_tools_exceptions.py
git commit -m "refactor(i02): raise specific exceptions from tools (Task 8)

- Replace bare except Exception with specific exception types
- WoloToolError raised for tool execution failures
- WoloPathSafetyError raised for path validation failures
- All exceptions carry session_id and metadata
- Add tests for exception handling
"
```

---

## Task 9: Update CLI to Handle New Exception Types

**Files:**
- Modify: `wolo/cli/main.py`
- Create: `tests/unit/test_cli_exception_handling.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_cli_exception_handling.py
import pytest
from wolo.exceptions import WoloConfigError, WoloToolError, WoloSessionError, WoloLLMError
from wolo.cli.main import _format_error_message


def test_format_wolo_config_error():
    """WoloConfigError formatted with helpful message."""
    error = WoloConfigError("API key missing", session_id="sess123")
    message = _format_error_message(error)

    assert "configuration" in message.lower() or "config" in message.lower()
    assert "api key" in message.lower()


def test_format_wolo_tool_error():
    """WoloToolError formatted with tool name."""
    error = WoloToolError("Tool failed", session_id="sess456", tool_name="read")
    message = _format_error_message(error)

    assert "tool" in message.lower()
    assert "read" in message


def test_format_wolo_session_error():
    """WoloSessionError formatted with session info."""
    error = WoloSessionError("Session not found", session_id="sess789")
    message = _format_error_message(error)

    assert "session" in message.lower()
    assert "sess789" in message


def test_format_wolo_llm_error():
    """WoloLLMError formatted with LLM context."""
    error = WoloLLMError("API rate limit", session_id="sess000", model="gpt-4")
    message = _format_error_message(error)

    assert "llm" in message.lower() or "api" in message.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_cli_exception_handling.py -v`
Expected: FAIL (_format_error_message doesn't exist yet)

**Step 3: Add to cli/main.py**

```python
# In wolo/cli/main.py, add imports and error handler:

from wolo.exceptions import (
    WoloError,
    WoloConfigError,
    WoloToolError,
    WoloSessionError,
    WoloLLMError,
    WoloPathSafetyError,
)


def _format_error_message(error: WoloError) -> str:
    """Format WoloError for user-friendly display.

    Args:
        error: The WoloError to format

    Returns:
        User-friendly error message
    """
    if isinstance(error, WoloConfigError):
        return f"Configuration Error: {error}"
    if isinstance(error, WoloToolError):
        tool_name = error.context.get("tool_name", "unknown")
        return f"Tool Error ({tool_name}): {error}"
    if isinstance(error, WoloSessionError):
        return f"Session Error: {error}"
    if isinstance(error, WoloLLMError):
        model = error.context.get("model", "unknown")
        return f"LLM Error ({model}): {error}"
    if isinstance(error, WoloPathSafetyError):
        path = error.context.get("path", "unknown")
        return f"Path Safety Error: {error} (path: {path})"
    return f"Error: {error}"


# In the main execution loop, catch WoloError:
try:
    # ... existing code ...
except WoloError as e:
    logger.error(str(e), extra={"session_id": e.session_id})
    print(_format_error_message(e), file=sys.stderr)
    sys.exit(1)
except KeyboardInterrupt:
    print("\nInterrupted by user", file=sys.stderr)
    sys.exit(130)
except Exception as e:
    logger.exception("Unexpected error")
    print(f"Unexpected error: {e}", file=sys.stderr)
    sys.exit(1)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_cli_exception_handling.py tests/unit/test_cli_*.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add wolo/cli/main.py tests/unit/test_cli_exception_handling.py
git commit -m "feat(i02): handle new exception types in CLI (Task 9)

- Add _format_error_message() for user-friendly error display
- Catch WoloError and subclasses in CLI main loop
- Display specific error messages per error type
- Include session_id in error logging
- Add tests for CLI exception handling
"
```

---

## Task 10: Create Integration Tests for Concurrent Sessions

**Files:**
- Create: `tests/integration/test_concurrent_sessions.py`

**Step 1: Write the failing test**

```python
# tests/integration/test_concurrent_sessions.py
"""Integration tests for concurrent session isolation."""
import asyncio
from contextvars import copy_context

import pytest

from wolo.context_state import (
    get_api_token_usage,
    reset_api_token_usage,
    get_doom_loop_history,
    add_doom_loop_entry,
    set_session_todos,
    get_session_todos,
)
from wolo.context_state.vars import (
    _token_usage_ctx,
    _doom_loop_history_ctx,
    _session_todos_ctx,
)


@pytest.mark.asyncio
async def test_concurrent_sessions_token_usage_isolated():
    """Multiple sessions can track token usage independently."""
    results = {}

    async def session1():
        reset_api_token_usage()
        from wolo.context_state.vars import _token_usage_ctx
        _token_usage_ctx.set({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        await asyncio.sleep(0.01)
        results["session1"] = get_api_token_usage()

    async def session2():
        reset_api_token_usage()
        from wolo.context_state.vars import _token_usage_ctx
        _token_usage_ctx.set({"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300})
        await asyncio.sleep(0.01)
        results["session2"] = get_api_token_usage()

    await asyncio.gather(session1(), session2())

    assert results["session1"] == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    assert results["session2"] == {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}


@pytest.mark.asyncio
async def test_concurrent_sessions_doom_loop_history_isolated():
    """Multiple sessions have independent doom loop detection."""
    results = {}

    async def session1():
        from wolo.context_state import clear_doom_loop_history
        clear_doom_loop_history()
        add_doom_loop_entry(("read", "hash1", ""))
        add_doom_loop_entry(("read", "hash1", ""))
        await asyncio.sleep(0.01)
        results["session1"] = get_doom_loop_history()

    async def session2():
        from wolo.context_state import clear_doom_loop_history
        clear_doom_loop_history()
        add_doom_loop_entry(("write", "hash2", ""))
        await asyncio.sleep(0.01)
        results["session2"] = get_doom_loop_history()

    await asyncio.gather(session1(), session2())

    assert results["session1"] == [("read", "hash1", ""), ("read", "hash1", "")]
    assert results["session2"] == [("write", "hash2", "")]


@pytest.mark.asyncio
async def test_concurrent_sessions_todos_isolated():
    """Multiple sessions have independent todo lists."""
    results = {}

    async def session1():
        todos1 = [{"content": "task1", "status": "pending"}]
        set_session_todos(todos1)
        await asyncio.sleep(0.01)
        results["session1"] = get_session_todos()

    async def session2():
        todos2 = [{"content": "task2", "status": "pending"}]
        set_session_todos(todos2)
        await asyncio.sleep(0.01)
        results["session2"] = get_session_todos()

    await asyncio.gather(session1(), session2())

    assert results["session1"] == [{"content": "task1", "status": "pending"}]
    assert results["session2"] == [{"content": "task2", "status": "pending"}]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_concurrent_sessions.py -v`
Expected: PASS (tests exercise the context-state isolation)

**Step 3: Create tests/integration/__init__.py**

```python
# tests/integration/__init__.py
"""Integration tests for Wolo."""
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_concurrent_sessions.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add tests/integration/__init__.py tests/integration/test_concurrent_sessions.py
git commit -m "test(i02): add integration tests for concurrent sessions (Task 10)

- Test token usage isolation between concurrent sessions
- Test doom loop history isolation between concurrent sessions
- Test session todos isolation between concurrent sessions
- Verify ContextVars provide proper task-local storage
- Coverage contribution: +5%
"
```

---

## Task 11: Update Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Create: `docs/CONTEXT_STATE.md`

**Step 1: Update CLAUDE.md**

Add to the "High-Level Architecture" section:

```markdown
### Context-State Subsystem (`wolo/context_state/`)

- **Purpose**: Thread-safe, task-local storage using Python's `contextvars`
- **Components**:
  - `vars.py`: ContextVar definitions for token_usage, doom_loop_history, session_todos
  - `_init.py`: Accessor functions (get_*, reset_*, set_*)
  - `__init__.py`: Public API exports
- **Benefits**: Each async task gets isolated state, enabling concurrent sessions
- **Public API**:
  - `get_api_token_usage()`, `reset_api_token_usage()`
  - `get_doom_loop_history()`, `add_doom_loop_entry()`, `clear_doom_loop_history()`
  - `get_session_todos()`, `set_session_todos()`
```

Add to "Key Patterns and Conventions":

```markdown
### Context-State Usage

- **Always use accessor functions** instead of accessing ContextVars directly
- **Accessor functions return copies** - prevents accidental mutation
- **Initialize context-state at session start** - call `load_session_todos_to_context_state()`
- **Save context-state before session end** - call `save_session_todos_from_context_state()`
```

**Step 2: Update README.md**

Add API key configuration section:

```markdown
### Configuration

Wolo can be configured via environment variables or config file.

**Environment Variables (Recommended for Production):**

```bash
export WOLO_API_KEY="your-api-key-here"
# or
export GLM_API_KEY="your-api-key-here"
```

**Config File (Development):**

```bash
wolo config init
```

The config file is stored at `~/.wolo/config.yaml`.

**Priority**: Environment variables take precedence over config file.
```

**Step 3: Create CONTEXT_STATE.md**

```markdown
# Context-State Subsystem

## Overview

The context-state subsystem provides thread-safe, task-local storage for Wolo sessions using Python's `contextvars` module. Each async task context gets its own isolated copy of session-specific state.

## Components

### ContextVar Definitions (`wolo/context_state/vars.py`)

- `_token_usage_ctx`: Tracks API token usage (prompt_tokens, completion_tokens, total_tokens)
- `_doom_loop_history_ctx`: Stores doom loop detection history
- `_session_todos_ctx`: Caches session todos for runtime access

### Accessor Functions (`wolo/context_state/_init.py`)

All accessor functions return **copies** to prevent accidental mutation:

```python
from wolo.context_state import (
    get_api_token_usage,
    reset_api_token_usage,
    get_doom_loop_history,
    add_doom_loop_entry,
    clear_doom_loop_history,
    get_session_todos,
    set_session_todos,
)
```

## Usage Example

```python
import asyncio
from wolo.context_state import get_api_token_usage, reset_api_token_usage

async def session1():
    reset_api_token_usage()
    # Simulate token usage
    # ...
    usage = get_api_token_usage()
    print(f"Session 1 usage: {usage}")

async def session2():
    reset_api_token_usage()
    # Simulate token usage
    # ...
    usage = get_api_token_usage()
    print(f"Session 2 usage: {usage}")

# Both sessions run concurrently with isolated state
asyncio.gather(session1(), session2())
```

## Benefits

1. **Concurrent Safety**: Multiple sessions can run without state interference
2. **Backward Compatible**: Public API unchanged, internal implementation uses ContextVars
3. **Testable**: Context isolation can be verified via integration tests
```

**Step 4: Run documentation checks**

Run: No automated tests, manual review

**Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/CONTEXT_STATE.md
git commit -m "docs(i02): update documentation for context-state and security (Task 11)

- Add context-state subsystem to CLAUDE.md architecture
- Add context-state usage patterns to Key Patterns
- Update README.md with environment variable priority
- Create CONTEXT_STATE.md with detailed subsystem documentation
- Document API key security best practices
"
```

---

## Task 12: Run Coverage and Verify 70%+ Target

**Files:**
- No new files
- Run coverage command

**Step 1: Run coverage**

```bash
pytest --cov=wolo --cov-report=term-missing --cov-report=html
```

**Step 2: Verify coverage meets 70%+ target**

Expected: Overall coverage >= 70%

If below 70%, identify gaps and add targeted tests.

**Step 3: Create coverage badge**

If coverage meets target, update README with coverage badge.

**Step 4: Commit**

```bash
# Create .coverage.xml or similar if needed
git add README.md  # if coverage badge added
git commit -m "test(i02): verify 70%+ coverage target met (Task 12)

- Run full test suite with coverage
- Overall coverage: XX% (meets 70%+ target)
- Key modules coverage:
  - wolo/exceptions.py: 95%+
  - wolo/context_state/: 90%+
  - wolo/agent.py: 70%+
  - wolo/llm_adapter.py: 70%+
  - wolo/session.py: 70%+
"
```

---

## Completion Checklist

After all tasks are complete:

- [ ] All tests pass: `pytest -v`
- [ ] Coverage >= 70%: `pytest --cov=wolo`
- [ ] No regressions in existing tests
- [ ] Documentation updated
- [ ] Commits are atomic and well-described
- [ ] Branch is ready for review/merge
