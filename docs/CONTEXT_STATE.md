# Context-State Subsystem

## Overview

The context-state subsystem provides thread-safe, task-local storage for Wolo sessions using Python's `contextvars` module. Each async task context gets its own isolated copy of session-specific state.

## Motivation

Prior to this subsystem, Wolo used global variables for tracking state like token usage and doom loop history. This caused issues in concurrent scenarios where multiple sessions might run simultaneously:

```python
# Old approach (problematic)
_api_token_usage = {"prompt_tokens": 0, ...}  # Shared across all sessions!
_doom_loop_history = []  # Shared across all sessions!
```

With `contextvars`, each async task gets its own isolated state:

```python
# New approach (concurrent-safe)
_token_usage_ctx = ContextVar("token_usage", default={...})  # Isolated per task
```

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

## Integration Points

### Agent Loop (`wolo/agent.py`)

- Doom loop history is cleared at session start: `clear_doom_loop_history()`
- Each tool call checks doom loop via context-state: `get_doom_loop_history()`

### Session Management (`wolo/session.py`)

- Load todos into context-state: `load_session_todos_to_context_state(session_id)`
- Save todos from context-state: `save_session_todos_from_context_state(session_id)`

### LLM Adapter (`wolo/llm_adapter.py`)

- Token tracking via context-state: `get_api_token_usage()`, `reset_api_token_usage()`

## Best Practices

1. **Always use accessor functions** instead of accessing ContextVars directly
2. **Accessor functions return copies** - prevents accidental mutation
3. **Initialize context-state at session start** - call `load_session_todos_to_context_state()`
4. **Save context-state before session end** - call `save_session_todos_from_context_state()`

## Benefits

1. **Concurrent Safety**: Multiple sessions can run without state interference
2. **Backward Compatible**: Public API unchanged, internal implementation uses ContextVars
3. **Testable**: Context isolation can be verified via integration tests

## Testing

Integration tests in `tests/integration/test_concurrent_sessions.py` verify:
- Token usage isolation between concurrent sessions
- Doom loop history isolation between concurrent sessions
- Session todos isolation between concurrent sessions
