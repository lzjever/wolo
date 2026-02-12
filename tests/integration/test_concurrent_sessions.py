"""Integration tests for concurrent session isolation."""

import asyncio

import pytest

from wolo.context_state import (
    add_doom_loop_entry,
    clear_doom_loop_history,
    get_api_token_usage,
    get_doom_loop_history,
    get_session_todos,
    reset_api_token_usage,
    set_session_todos,
)
from wolo.context_state.vars import (
    _token_usage_ctx,
)


@pytest.mark.asyncio
async def test_concurrent_sessions_token_usage_isolated():
    """Multiple sessions can track token usage independently."""
    results = {}

    async def session1():
        reset_api_token_usage()
        _token_usage_ctx.set({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        await asyncio.sleep(0.01)
        results["session1"] = get_api_token_usage()

    async def session2():
        reset_api_token_usage()
        _token_usage_ctx.set({"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300})
        await asyncio.sleep(0.01)
        results["session2"] = get_api_token_usage()

    await asyncio.gather(session1(), session2())

    assert results["session1"] == {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
    }
    assert results["session2"] == {
        "prompt_tokens": 200,
        "completion_tokens": 100,
        "total_tokens": 300,
    }


@pytest.mark.asyncio
async def test_concurrent_sessions_doom_loop_history_isolated():
    """Multiple sessions have independent doom loop detection."""
    results = {}

    async def session1():
        clear_doom_loop_history()
        add_doom_loop_entry(("read", "hash1", ""))
        add_doom_loop_entry(("read", "hash1", ""))
        await asyncio.sleep(0.01)
        results["session1"] = get_doom_loop_history()

    async def session2():
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


@pytest.mark.asyncio
async def test_context_var_isolation_with_copy_context():
    """ContextVars are isolated when using copy_context."""
    from contextvars import copy_context

    # Initialize the context var before copying, so both contexts start with the same value
    reset_api_token_usage()

    ctx1 = copy_context()
    ctx2 = copy_context()

    # Modify in ctx1
    ctx1.run(
        _token_usage_ctx.set, {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    )

    # ctx2 should still have the initial (zero) value
    assert ctx2.run(_token_usage_ctx.get) == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    assert ctx1.run(_token_usage_ctx.get) == {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
    }


@pytest.mark.asyncio
async def test_multiple_concurrent_sessions():
    """Test with many concurrent sessions."""
    results = {}

    async def session(session_id: int):
        reset_api_token_usage()
        tokens = session_id * 100
        _token_usage_ctx.set(
            {
                "prompt_tokens": tokens,
                "completion_tokens": tokens // 2,
                "total_tokens": tokens * 3 // 2,
            }
        )
        add_doom_loop_entry((f"tool_{session_id}", f"hash_{session_id}", ""))
        set_session_todos([{"content": f"task_{session_id}"}])
        await asyncio.sleep(0.001)
        results[session_id] = {
            "tokens": get_api_token_usage(),
            "history": get_doom_loop_history(),
            "todos": get_session_todos(),
        }

    # Run 10 sessions concurrently
    tasks = [session(i) for i in range(10)]
    await asyncio.gather(*tasks)

    # Verify each session has its own state
    for i in range(10):
        assert results[i]["tokens"]["total_tokens"] == i * 150
        assert results[i]["history"] == [(f"tool_{i}", f"hash_{i}", "")]
        assert results[i]["todos"] == [{"content": f"task_{i}"}]
