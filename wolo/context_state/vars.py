"""Context-state infrastructure using ContextVars for thread-safe, task-local storage."""

from contextvars import ContextVar

# Token usage tracking for the current agent session
# Format: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
_token_usage_ctx: ContextVar[dict[str, int]] = ContextVar(
    "token_usage",
    default={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
)


# Doom loop history for detecting repeated tool calls
# Format: list of tuples (tool_name, tool_input, tool_output)
_doom_loop_history_ctx: ContextVar[list[tuple[str, str, str]]] = ContextVar(
    "doom_loop_history",
    default=[],
)


# Session todos for task tracking
# Format: list of todo dicts
_session_todos_ctx: ContextVar[list[dict]] = ContextVar(
    "session_todos",
    default=[],
)
