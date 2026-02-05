"""Path confirmation interaction handler.

This module provides user interaction for path confirmation prompts
when the PathGuard requires user approval.
"""

import sys
from pathlib import Path

from rich.console import Console


class SessionCancelledError(Exception):
    """Raised when user cancels the session during confirmation."""

    pass


# Backward compatibility alias (deprecated)
SessionCancelled = SessionCancelledError


async def handle_path_confirmation(path: str, operation: str) -> bool:
    """Handle path confirmation prompt for user.

    Args:
        path: The path requiring confirmation
        operation: The operation type (write/delete/etc)

    Returns:
        True if user allowed the operation, False if denied

    Raises:
        SessionCancelledError: If user enters 'q' to quit
    """
    from wolo.path_guard import get_path_guard

    console = Console()
    console.print("\n⚠️  [yellow]Path Confirmation Required[/yellow]")
    console.print(f"Operation: [cyan]{operation}[/cyan]")
    console.print(f"Path: [cyan]{path}[/cyan]")
    console.print("This path is not in the default allowlist (/tmp) or configured whitelist.")

    if not sys.stdin.isatty():
        console.print("[dim]Non-interactive mode, operation denied.[/dim]")
        console.print("Tip: Configure path_safety.allowed_write_paths in ~/.wolo/config.yaml")
        return False

    while True:
        response = (
            console.input("\n[yellow]Allow this operation?[/yellow] [Y/n/a/q] ").strip().lower()
        )

        if response in ("", "y", "yes"):
            guard = get_path_guard()
            guard.confirm_directory(path)
            return True
        elif response in ("n", "no"):
            return False
        elif response == "a":
            guard = get_path_guard()
            parent = Path(path).parent
            guard.confirm_directory(parent)
            console.print(
                f"[green]✓[/green] {parent} and subdirectories added to session whitelist"
            )
            return True
        elif response == "q":
            console.print("[red]Session cancelled[/red]")
            raise SessionCancelledError()
        else:
            console.print("[dim]Please enter Y/n/a/q[/dim]")
