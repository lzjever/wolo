# wolo/path_guard/cli_strategy.py
"""CLI-based confirmation strategy."""

import sys
from pathlib import Path

from rich.console import Console

from wolo.path_guard.strategy import ConfirmationStrategy
from wolo.path_guard.exceptions import SessionCancelled


class CLIConfirmationStrategy(ConfirmationStrategy):
    """Interactive confirmation strategy for CLI usage.

    This strategy prompts the user via the console for path confirmation
    requests. It supports both interactive (TTY) and non-interactive modes.

    In non-interactive mode (e.g., piped input), confirmation requests
    are automatically denied.
    """

    def __init__(self) -> None:
        """Initialize the CLI confirmation strategy."""
        self._console = Console()

    async def confirm(self, path: str, operation: str) -> bool:
        """Request user confirmation via CLI prompt.

        Args:
            path: The path that requires confirmation
            operation: The operation type (e.g., "write", "edit")

        Returns:
            True if allowed, False if denied

        Raises:
            SessionCancelled: If user enters 'q' to cancel the session
        """
        # Import here to avoid circular dependency during refactor
        from wolo.path_guard import get_path_guard

        self._console.print("\n[yellow]Path Confirmation Required[/yellow]")
        self._console.print(f"Operation: [cyan]{operation}[/cyan]")
        self._console.print(f"Path: [cyan]{path}[/cyan]")
        self._console.print(
            "This path is not in the default allowlist (/tmp) or configured whitelist."
        )

        # Non-interactive mode: auto-deny
        if not sys.stdin.isatty():
            self._console.print("[dim]Non-interactive mode, operation denied.[/dim]")
            return False

        # Interactive prompt
        while True:
            response = (
                self._console.input(
                    "\n[yellow]Allow this operation?[/yellow] [Y/n/a/q] "
                )
                .strip()
                .lower()
            )

            if response in ("", "y", "yes"):
                # Allow this specific path
                guard = get_path_guard()
                guard.confirm_directory(path)
                return True
            elif response in ("n", "no"):
                # Deny this operation
                return False
            elif response == "a":
                # Allow parent directory and all subdirectories
                guard = get_path_guard()
                parent = Path(path).parent
                guard.confirm_directory(parent)
                self._console.print(
                    f"[green]Add[/green] {parent} and subdirectories to session whitelist"
                )
                return True
            elif response == "q":
                # Cancel the entire session
                raise SessionCancelled()
