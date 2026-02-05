"""Shell execution tools."""

import asyncio
import time
import uuid
from typing import Any

from wolo.tools_pkg.constants import MAX_OUTPUT_LINES, MAX_SHELL_HISTORY
from wolo.truncate import truncate_output

# Track running shell processes for Ctrl+S viewing (session-scoped)
# Structure: {session_id: {shell_id: shell_info}}
_running_shells: dict[str, dict[str, dict]] = {}
# Structure: {session_id: [shell_info, ...]}
_shell_history: dict[str, list[dict]] = {}


async def shell_execute(
    command: str, timeout: int = 30000, session_id: str | None = None
) -> dict[str, Any]:
    """Execute a shell command and return the result."""
    from wolo.subprocess_manager import managed_subprocess

    shell_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # Track this shell process (session-scoped)
    shell_info = {
        "id": shell_id,
        "command": command,
        "start_time": start_time,
        "output_lines": [],
        "status": "running",
        "exit_code": None,
    }

    # Use session_id for scoping, fallback to "_global" for backward compatibility
    scope_id = session_id or "_global"
    if scope_id not in _running_shells:
        _running_shells[scope_id] = {}
    _running_shells[scope_id][shell_id] = shell_info

    async with managed_subprocess(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, shell=True
    ) as process:
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout / 1000)

            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            if error:
                output = output + "\n" + error if output else error

            # Store output (limited lines)
            lines = output.split("\n")
            shell_info["output_lines"] = (
                lines[-MAX_OUTPUT_LINES:] if len(lines) > MAX_OUTPUT_LINES else lines
            )
            shell_info["status"] = "completed"
            shell_info["exit_code"] = process.returncode
            shell_info["end_time"] = time.time()
            shell_info["duration"] = shell_info["end_time"] - start_time

            # Move to history (session-scoped)
            if scope_id in _running_shells and shell_id in _running_shells[scope_id]:
                del _running_shells[scope_id][shell_id]
            if scope_id not in _shell_history:
                _shell_history[scope_id] = []
            _shell_history[scope_id].insert(0, shell_info)
            if len(_shell_history[scope_id]) > MAX_SHELL_HISTORY:
                _shell_history[scope_id].pop()

            # Truncate output if too large
            truncated = truncate_output(output)

            return {
                "title": command,
                "output": truncated.content,
                "metadata": {
                    "exit_code": process.returncode,
                    "shell_id": shell_id,
                    "truncated": truncated.truncated,
                    "saved_path": truncated.saved_path,
                },
            }
        except TimeoutError:
            process.kill()
            await process.wait()

            shell_info["status"] = "timeout"
            shell_info["exit_code"] = -1
            shell_info["end_time"] = time.time()
            shell_info["duration"] = shell_info["end_time"] - start_time

            # Move to history (session-scoped)
            if scope_id in _running_shells and shell_id in _running_shells[scope_id]:
                del _running_shells[scope_id][shell_id]
            if scope_id not in _shell_history:
                _shell_history[scope_id] = []
            _shell_history[scope_id].insert(0, shell_info)
            if len(_shell_history[scope_id]) > MAX_SHELL_HISTORY:
                _shell_history[scope_id].pop()

            return {
                "title": command,
                "output": f"Command timed out after {timeout}ms",
                "metadata": {"exit_code": -1, "shell_id": shell_id},
            }


def get_shell_status(session_id: str | None = None) -> dict:
    """Get current shell status for Ctrl+S display (session-scoped)."""
    scope_id = session_id or "_global"
    running = _running_shells.get(scope_id, {})
    history = _shell_history.get(scope_id, [])
    return {
        "running": list(running.values()),
        "history": history[:5],  # Last 5 completed
    }


def clear_shell_state(session_id: str) -> None:
    """Clear shell state for a session (call on session cleanup)."""
    if session_id in _running_shells:
        del _running_shells[session_id]
    if session_id in _shell_history:
        del _shell_history[session_id]
