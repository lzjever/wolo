"""
CLI utility functions for Wolo.
"""

import sys
from typing import TYPE_CHECKING

from wolo.cli.exit_codes import ExitCode
from wolo.cli.parser import ParsedArgs

if TYPE_CHECKING:
    from wolo.cli.output.base import OutputConfig


def show_first_run_message() -> None:
    """
    Display first-run message to user.

    Prints message to stderr and exits with CONFIG_ERROR code.
    This function does NOT return - it calls sys.exit().
    """
    print(
        "Wolo is not configured. Please run 'wolo config init' to set up your configuration.",
        file=sys.stderr,
    )
    sys.exit(ExitCode.CONFIG_ERROR)


def get_message_from_sources(args: ParsedArgs) -> tuple[str, bool]:
    """
    Get message from parsed arguments.

    The parser now handles dual input (pipe + CLI) concatenation,
    so this function simply returns the combined message.

    Args:
        args: Parsed arguments

    Returns:
        (message, has_message) tuple
    """
    # Message is already combined by parser using combine_inputs()
    if args.message:
        return (args.message, True)

    return ("", False)


def print_session_info(
    session_id: str,
    show_resume_hints: bool = True,
    output_config: "OutputConfig | None" = None,
) -> None:
    """
    Print session information.

    Args:
        session_id: Session ID
        show_resume_hints: Whether to show resume command hints
        output_config: Output configuration for style-specific formatting.
    """
    from datetime import datetime

    from wolo.session import get_session_status, get_storage

    status = get_session_status(session_id)
    if not status.get("exists"):
        print(f"Session {session_id} not found")
        return

    metadata = get_storage().get_session_metadata(session_id)
    if not metadata:
        return

    # Basic info
    agent_name = status.get("agent_name") or "Unknown"
    created_at = status.get("created_at")
    message_count = status.get("message_count", 0)

    # Format created time
    if created_at:
        created_dt = datetime.fromtimestamp(created_at)
        created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        created_str = "Unknown"

    # Get workdir
    workdir = metadata.get("workdir")

    # Truncate workdir for display
    if workdir:
        display_workdir = workdir if len(workdir) <= 45 else "..." + workdir[-42:]
    else:
        display_workdir = None

    # Unified banner format for all modes
    print("━" * 60)
    print(f"  Session:   {session_id}")
    print(f"  Agent:     {agent_name}")
    print(f"  Created:   {created_str}")
    print(f"  Messages:  {message_count}")
    if display_workdir:
        print(f"  Workdir:   {display_workdir}")
    if show_resume_hints:
        print(f'  Resume:    wolo -r {session_id} "your prompt"')
    print("━" * 60)
    print()


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable form.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1.5s", "150ms")
    """
    if seconds >= 1:
        return f"{seconds:.1f}s"
    else:
        return f"{int(seconds * 1000)}ms"


def check_workdir_match(session_id: str) -> tuple[bool, str | None, str]:
    """
    Check if current directory matches session's working directory.

    Args:
        session_id: Session ID to check

    Returns:
        (matches, session_workdir, current_workdir)
        - matches: True if directories match (or session has no workdir)
        - session_workdir: The session's stored workdir (may be None)
        - current_workdir: Current working directory
    """
    import os

    from wolo.session import get_storage

    storage = get_storage()
    metadata = storage.get_session_metadata(session_id)

    current_workdir = os.getcwd()

    if not metadata:
        return (True, None, current_workdir)

    session_workdir = metadata.get("workdir")

    # If no workdir stored, consider it a match (backward compatibility)
    if session_workdir is None:
        return (True, None, current_workdir)

    # Normalize paths for comparison
    session_workdir_norm = os.path.normpath(os.path.abspath(session_workdir))
    current_workdir_norm = os.path.normpath(os.path.abspath(current_workdir))

    matches = session_workdir_norm == current_workdir_norm
    return (matches, session_workdir, current_workdir)


def handle_keyboard_interrupt(session_id: str) -> int:
    """
    Handle KeyboardInterrupt gracefully by saving session.

    Args:
        session_id: Session ID to save

    Returns:
        ExitCode.INTERRUPTED
    """
    print("\nInterrupted. Saving session...", file=sys.stderr)
    try:
        from wolo.session import save_session

        save_session(session_id)
        print(f"Session saved: {session_id}", file=sys.stderr)
        print(f'Resume with: wolo -r {session_id} "your prompt"', file=sys.stderr)
    except Exception as e:
        print(f"Warning: Failed to save session: {e}", file=sys.stderr)
    return ExitCode.INTERRUPTED


def print_workdir_warning(session_workdir: str, current_workdir: str) -> None:
    """
    Print a warning about workdir mismatch.

    Args:
        session_workdir: Session's stored working directory
        current_workdir: Current working directory
    """
    # ANSI colors
    yellow = "\033[93m"
    dim = "\033[90m"
    reset = "\033[0m"

    print(f"{yellow}⚠️  Directory mismatch{reset}")
    print(f"   Session was created in: {session_workdir}")
    print(f"   Current directory:      {current_workdir}")
    print(f"{dim}   (Use -C/--workdir to override, or cd to the original directory){reset}")
    print()
