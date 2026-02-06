"""Tests for context-state infrastructure using ContextVars."""

import asyncio
from contextvars import ContextVar, copy_context

import pytest

from wolo.context_state import (
    _doom_loop_history_ctx,
    _session_todos_ctx,
    _token_usage_ctx,
)


@pytest.fixture(autouse=True)
def reset_context_state():
    """Reset all context state before and after each test."""
    # Reset before test
    _token_usage_ctx.set({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    _doom_loop_history_ctx.set([])
    _session_todos_ctx.set([])

    yield

    # Reset after test
    _token_usage_ctx.set({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    _doom_loop_history_ctx.set([])
    _session_todos_ctx.set([])


class TestTokenUsageContextVar:
    """Tests for _token_usage_ctx ContextVar."""

    def test_token_usage_context_var_exists(self):
        """Test that token usage ContextVar is defined."""
        assert _token_usage_ctx is not None
        assert isinstance(_token_usage_ctx, ContextVar)

    def test_token_usage_default_is_empty(self):
        """Test that token usage defaults to empty dict with zero values."""
        ctx = copy_context()
        result = ctx.run(_token_usage_ctx.get)
        assert result == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }


class TestDoomLoopHistoryContextVar:
    """Tests for _doom_loop_history_ctx ContextVar."""

    def test_doom_loop_history_context_var_exists(self):
        """Test that doom loop history ContextVar is defined."""
        assert _doom_loop_history_ctx is not None
        assert isinstance(_doom_loop_history_ctx, ContextVar)

    def test_doom_loop_history_default_is_empty_list(self):
        """Test that doom loop history defaults to empty list."""
        ctx = copy_context()
        result = ctx.run(_doom_loop_history_ctx.get)
        assert result == []


class TestSessionTodosContextVar:
    """Tests for _session_todos_ctx ContextVar."""

    def test_session_todos_context_var_exists(self):
        """Test that session todos ContextVar is defined."""
        assert _session_todos_ctx is not None
        assert isinstance(_session_todos_ctx, ContextVar)

    def test_session_todos_default_is_empty_list(self):
        """Test that session todos defaults to empty list."""
        ctx = copy_context()
        result = ctx.run(_session_todos_ctx.get)
        assert result == []


class TestContextVarIsolation:
    """Tests for ContextVar isolation between contexts."""

    def test_context_vars_isolated_between_contexts(self):
        """Test that ContextVars are isolated between different contexts."""
        ctx1 = copy_context()
        ctx2 = copy_context()

        # Set values in ctx1
        def set_ctx1_values():
            _token_usage_ctx.set(
                {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
            )
            _doom_loop_history_ctx.set([("tool1", "input1", "output1")])
            _session_todos_ctx.set([{"id": "1"}])
            return (
                _token_usage_ctx.get(),
                _doom_loop_history_ctx.get(),
                _session_todos_ctx.get(),
            )

        token_usage_1, doom_loop_1, todos_1 = ctx1.run(set_ctx1_values)

        # Verify ctx1 has the set values
        assert token_usage_1["prompt_tokens"] == 100
        assert doom_loop_1 == [("tool1", "input1", "output1")]
        assert todos_1 == [{"id": "1"}]

        # Verify ctx2 gets default values (using default parameter)
        def get_ctx2_defaults():
            return (
                _token_usage_ctx.get(),
                _doom_loop_history_ctx.get(),
                _session_todos_ctx.get(),
            )

        token_usage_2, doom_loop_2, todos_2 = ctx2.run(get_ctx2_defaults)

        assert token_usage_2 == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        assert doom_loop_2 == []
        assert todos_2 == []

    async def test_context_vars_isolated_between_async_tasks(self):
        """Test that ContextVars are isolated between concurrent async tasks."""
        results = {}

        async def task1():
            # Set values in task1
            _token_usage_ctx.set(
                {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
            )
            await asyncio.sleep(0.01)  # Yield to allow task2 to run
            results["task1"] = _token_usage_ctx.get()

        async def task2():
            await asyncio.sleep(0.005)  # Let task1 set first
            # Task2 should have its own context (default value before set)
            results["task2_before_set"] = _token_usage_ctx.get()
            _token_usage_ctx.set(
                {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}
            )
            results["task2_after_set"] = _token_usage_ctx.get()

        # Run tasks concurrently
        await asyncio.gather(task1(), task2())

        # Verify isolation
        assert results["task1"]["prompt_tokens"] == 100
        assert results["task2_before_set"] == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        assert results["task2_after_set"]["prompt_tokens"] == 200


class TestTokenUsageAccessors:
    """Tests for token usage accessor functions."""

    def test_get_api_token_usage_returns_copy(self):
        """Test that get_api_token_usage returns a copy, not the original."""
        from wolo.context_state import _token_usage_ctx, get_api_token_usage

        # Set initial value
        _token_usage_ctx.set({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})

        # Get the value
        result = get_api_token_usage()

        # Modify the returned dict
        result["prompt_tokens"] = 999

        # Verify original wasn't modified
        original = _token_usage_ctx.get()
        assert original["prompt_tokens"] == 100
        assert original["completion_tokens"] == 50
        assert original["total_tokens"] == 150

    def test_get_and_reset_api_token_usage(self):
        """Test that we can get and reset token usage."""
        from wolo.context_state import _token_usage_ctx, get_api_token_usage, reset_api_token_usage

        # Set initial value
        _token_usage_ctx.set({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})

        # Get the value
        usage = get_api_token_usage()
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150

        # Reset
        reset_api_token_usage()

        # Verify reset
        usage_after = get_api_token_usage()
        assert usage_after == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


class TestDoomLoopHistoryAccessors:
    """Tests for doom loop history accessor functions."""

    def test_get_doom_loop_history_returns_copy(self):
        """Test that get_doom_loop_history returns a copy, not the original."""
        from wolo.context_state import _doom_loop_history_ctx, get_doom_loop_history

        # Set initial value
        _doom_loop_history_ctx.set([("tool1", "input1", "output1")])

        # Get the value
        result = get_doom_loop_history()

        # Modify the returned list
        result.append(("tool2", "input2", "output2"))

        # Verify original wasn't modified
        original = _doom_loop_history_ctx.get()
        assert original == [("tool1", "input1", "output1")]

    def test_add_doom_loop_entry(self):
        """Test that we can add entries to doom loop history."""
        from wolo.context_state import add_doom_loop_entry, get_doom_loop_history

        # Start with empty history
        assert get_doom_loop_history() == []

        # Add an entry
        add_doom_loop_entry(("tool1", "input1", "output1"))

        # Verify it was added
        history = get_doom_loop_history()
        assert history == [("tool1", "input1", "output1")]

        # Add another entry
        add_doom_loop_entry(("tool2", "input2", "output2"))

        # Verify both entries are there
        history = get_doom_loop_history()
        assert len(history) == 2
        assert history[0] == ("tool1", "input1", "output1")
        assert history[1] == ("tool2", "input2", "output2")

    def test_clear_doom_loop_history(self):
        """Test that we can clear doom loop history."""
        from wolo.context_state import (
            add_doom_loop_entry,
            clear_doom_loop_history,
            get_doom_loop_history,
        )

        # Add some entries
        add_doom_loop_entry(("tool1", "input1", "output1"))
        add_doom_loop_entry(("tool2", "input2", "output2"))
        assert len(get_doom_loop_history()) == 2

        # Clear
        clear_doom_loop_history()

        # Verify empty
        assert get_doom_loop_history() == []


class TestSessionTodosAccessors:
    """Tests for session todos accessor functions."""

    def test_get_session_todos_returns_copy(self):
        """Test that get_session_todos returns a copy, not the original."""
        from wolo.context_state import _session_todos_ctx, get_session_todos

        # Set initial value
        _session_todos_ctx.set([{"id": "1", "task": "first"}])

        # Get the value
        result = get_session_todos()

        # Modify the returned list
        result.append({"id": "2", "task": "second"})

        # Verify original wasn't modified
        original = _session_todos_ctx.get()
        assert original == [{"id": "1", "task": "first"}]

    def test_get_and_set_session_todos(self):
        """Test that we can get and set session todos."""
        from wolo.context_state import get_session_todos, set_session_todos

        # Start with empty
        assert get_session_todos() == []

        # Set some todos
        todos = [
            {"id": "1", "task": "first", "status": "pending"},
            {"id": "2", "task": "second", "status": "completed"},
        ]
        set_session_todos(todos)

        # Verify they were set
        result = get_session_todos()
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "2"

    def test_set_session_todos_creates_copy(self):
        """Test that set_session_todos creates a copy, not a reference."""
        from wolo.context_state import get_session_todos, set_session_todos

        # Create todos list
        todos = [{"id": "1", "task": "first"}]
        set_session_todos(todos)

        # Modify original list
        todos.append({"id": "2", "task": "second"})

        # Verify context wasn't modified
        result = get_session_todos()
        assert len(result) == 1
        assert result[0]["id"] == "1"
