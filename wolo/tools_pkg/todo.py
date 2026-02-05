"""Todo management tools."""

from typing import Any

# Simple in-memory todo storage (per session)
_todos: dict[str, list[dict]] = {}


def get_todos(session_id: str) -> list[dict]:
    """Get todos for a session."""
    return _todos.get(session_id, [])


def set_todos(session_id: str, todos: list[dict]) -> None:
    """Set todos for a session."""
    _todos[session_id] = todos


async def todowrite_execute(todos: list[dict], session_id: str) -> dict[str, Any]:
    """Write/update todos for a session."""
    from wolo.session import save_session_todos

    if not session_id:
        return {
            "title": "todowrite",
            "output": "TodoWrite requires session_id",
            "metadata": {"error": "missing_session_id"},
        }

    # Store todos in memory
    _todos[session_id] = todos

    # Persist todos to disk
    save_session_todos(session_id, todos)

    # Format output
    completed = [t for t in todos if t.get("status") == "completed"]

    output_lines = ["Todo list updated:"]
    for t in todos:
        status_sym = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
        content = t.get("content", "")
        status = t.get("status", "pending")
        output_lines.append(f"  {status_sym.get(status, '[?]')} {content}")

    if completed:
        output_lines.append(f"\nCompleted: {len(completed)}/{len(todos)}")

    return {
        "title": "todowrite",
        "output": "\n".join(output_lines),
        "metadata": {
            "todos": todos,
            "total": len(todos),
            "completed": len(completed),
        },
    }


async def todoread_execute(session_id: str) -> dict[str, Any]:
    """Read todos for a session."""
    from wolo.session import load_session_todos

    if not session_id:
        return {
            "title": "todoread",
            "output": "TodoRead requires session_id",
            "metadata": {"error": "missing_session_id"},
        }

    # Read from memory
    todos = _todos.get(session_id, [])

    # If not in memory, try loading from disk
    if not todos:
        todos = load_session_todos(session_id)
        if todos:
            _todos[session_id] = todos

    if not todos:
        return {
            "title": "todoread",
            "output": "No todos found for this session.",
            "metadata": {"total": 0},
        }

    # Format output
    output_lines = [f"Current todo list ({len(todos)} items):"]
    for t in todos:
        status_sym = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
        content = t.get("content", "")
        status = t.get("status", "pending")
        output_lines.append(f"  {status_sym.get(status, '[?]')} {content}")

    completed = len([t for t in todos if t.get("status") == "completed"])
    output_lines.append(f"\nProgress: {completed}/{len(todos)} completed")

    return {
        "title": "todoread",
        "output": "\n".join(output_lines),
        "metadata": {
            "todos": todos,
            "total": len(todos),
            "completed": completed,
        },
    }
