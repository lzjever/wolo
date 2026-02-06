"""Shell execution tools."""

import asyncio
import re
import sys
import time
import uuid
from typing import Any

from rich.console import Console

from wolo.tools_pkg.constants import MAX_OUTPUT_LINES, MAX_SHELL_HISTORY
from wolo.truncate import truncate_output

# Track running shell processes for Ctrl+S viewing (session-scoped)
# Structure: {session_id: {shell_id: shell_info}}
_running_shells: dict[str, dict[str, dict]] = {}
# Structure: {session_id: [shell_info, ...]}
_shell_history: dict[str, list[dict]] = {}
# Structure: {session_id: {risk_pattern_id, ...}}
_shell_risk_approvals: dict[str, set[str]] = {}


SHELL_HIGH_RISK_PATTERNS: list[dict[str, str]] = [
    {
        "id": "rm_root_like",
        "regex": r"\brm\s+-rf?\s+(/(\s|$)|--no-preserve-root\b)",
        "description": "Destructive recursive delete near root",
    },
    {
        "id": "mkfs_disk",
        "regex": r"\bmkfs(\.\w+)?\b",
        "description": "Disk formatting command",
    },
    {
        "id": "dd_to_block_device",
        "regex": r"\bdd\b[^\\n]*\bof=/dev/",
        "description": "Raw write to block device",
    },
    {
        "id": "shutdown_or_reboot",
        "regex": r"\b(shutdown|reboot|halt|poweroff)\b",
        "description": "System shutdown/reboot command",
    },
    {
        "id": "curl_pipe_shell",
        "regex": r"\b(curl|wget)\b[^\\n]*\|\s*(sh|bash|zsh)\b",
        "description": "Remote script piped to shell",
    },
    {
        "id": "git_reset_hard",
        "regex": r"\bgit\s+reset\s+--hard\b",
        "description": "Destructive git reset",
    },
]


def detect_shell_high_risk_patterns(command: str) -> list[dict[str, str]]:
    """Return matched high-risk command patterns."""
    matched: list[dict[str, str]] = []
    for pattern in SHELL_HIGH_RISK_PATTERNS:
        if re.search(pattern["regex"], command, flags=re.IGNORECASE):
            matched.append(pattern)
    return matched


def should_allow_shell_command(
    command: str, session_id: str | None = None
) -> tuple[bool, str | None]:
    """Check high-risk shell command and ask for confirmation if needed."""
    scope_id = session_id or "_global"
    matched = detect_shell_high_risk_patterns(command)
    if not matched:
        return True, None

    approved = _shell_risk_approvals.setdefault(scope_id, set())
    for pattern in matched:
        if pattern["id"] in approved:
            continue

        console = Console()
        console.print("\n[yellow]High-Risk Shell Command Detected[/yellow]")
        console.print(f"Pattern: [cyan]{pattern['description']}[/cyan]")
        console.print(f"Command: [cyan]{command}[/cyan]")

        if not sys.stdin.isatty():
            return False, (
                "Denied high-risk shell command in non-interactive mode. "
                f"Pattern: {pattern['description']}"
            )

        while True:
            response = (
                console.input("\n[yellow]Allow?[/yellow] [y=once / a=session / n=deny] ")
                .strip()
                .lower()
            )
            if response == "y":
                break
            if response == "a":
                approved.add(pattern["id"])
                break
            if response in ("", "n", "no"):
                return False, f"Denied high-risk shell command: {pattern['description']}"

    return True, None


async def shell_execute(
    command: str,
    timeout: int = 30000,
    session_id: str | None = None,
    wild_mode: bool = False,
) -> dict[str, Any]:
    """Execute a shell command and return the result."""
    from wolo.subprocess_manager import managed_subprocess

    if not wild_mode:
        allowed, denial_message = should_allow_shell_command(command, session_id=session_id)
        if not allowed:
            return {
                "title": command,
                "output": denial_message or "Denied high-risk shell command",
                "metadata": {"exit_code": -2, "error": "high_risk_shell_denied"},
            }

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
    if session_id in _shell_risk_approvals:
        del _shell_risk_approvals[session_id]
