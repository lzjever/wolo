"""
CLI utility functions for Wolo.
"""

from datetime import datetime
from wolo.cli.parser import ParsedArgs, combine_inputs
from wolo.cli.exit_codes import ExitCode


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


def print_session_info(session_id: str, show_resume_hints: bool = True) -> None:
    """
    Print session information in a formatted display.
    
    Args:
        session_id: Session ID
        show_resume_hints: Whether to show resume command hints
    """
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
    is_running = status.get("is_running", False)
    pid = status.get("pid")
    
    # Format created time
    if created_at:
        created_dt = datetime.fromtimestamp(created_at)
        created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")
        # Calculate relative time
        now = datetime.now()
        delta = now - created_dt
        if delta.days > 0:
            relative_str = f"{delta.days} day(s) ago"
        elif delta.seconds >= 3600:
            relative_str = f"{delta.seconds // 3600} hour(s) ago"
        elif delta.seconds >= 60:
            relative_str = f"{delta.seconds // 60} minute(s) ago"
        else:
            relative_str = "just now"
    else:
        created_str = "Unknown"
        relative_str = "Unknown"
    
    # Print formatted output
    print(f"Session: {session_id}")
    print("━" * 60)
    print(f"  Agent:     {agent_name}")
    print(f"  Created:   {created_str}")
    print(f"  Messages:  {message_count}")
    
    if is_running and pid:
        print(f"  Status:    \033[92mRunning (PID: {pid})\033[0m")
    else:
        print(f"  Status:    \033[90mStopped\033[0m")
    
    print()
    print(f"  Last activity: {relative_str}")
    
    if show_resume_hints and not is_running:
        print()
        print(f"  Resume: wolo session resume {session_id}")
        print(f"  Or:     wolo -r {session_id} \"your prompt\"")
    
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
