"""Tests for session context-state integration."""

# Check if lexilux is available (required for session.py imports)
try:
    import lexilux  # noqa: F401

    LEXILUX_AVAILABLE = True
except ImportError:
    LEXILUX_AVAILABLE = False

if not LEXILUX_AVAILABLE:
    import pytest

    pytest.skip("lexilux not installed - requires local path dependency", allow_module_level=True)

from pathlib import Path

import pytest

from wolo.context_state import get_session_todos, set_session_todos


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


@pytest.mark.asyncio
async def test_session_todos_isolated():
    """Session todos are stored in context-state and can be updated."""
    import asyncio

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

    await asyncio.gather(session1(), session2())

    # With asyncio.gather in the same task, the second set_session_todos
    # overwrites the first. Both will return the last set value.
    assert len(results) == 2
    assert [{"content": "task1"}] in results
    assert [{"content": "task2"}] in results


def test_load_session_todos_to_context_state(tmp_path, monkeypatch):
    """load_session_todos_to_context_state loads todos into context-state."""
    from wolo.session import (
        create_session,
        load_session_todos_to_context_state,
        save_session_todos,
    )

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Create a test session
    session_id = create_session(agent_name="test_agent")

    # Save some todos to disk
    todos = [{"content": "task1", "status": "pending"}, {"content": "task2", "status": "completed"}]
    save_session_todos(session_id, todos)

    # Load into context-state
    load_session_todos_to_context_state(session_id)

    # Verify todos are in context-state
    retrieved = get_session_todos()
    assert retrieved == todos


def test_save_session_todos_from_context_state(tmp_path, monkeypatch):
    """save_session_todos_from_context_state saves todos from context-state."""
    from wolo.session import (
        create_session,
        load_session_todos,
        save_session_todos_from_context_state,
    )

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Create a test session
    session_id = create_session(agent_name="test_agent")

    # Set todos in context-state
    todos = [{"content": "task1", "status": "pending"}, {"content": "task2", "status": "completed"}]
    set_session_todos(todos)

    # Save from context-state to disk
    save_session_todos_from_context_state(session_id)

    # Load from disk to verify
    loaded = load_session_todos(session_id)
    assert loaded == todos
