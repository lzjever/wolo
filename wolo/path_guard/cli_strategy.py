# wolo/path_guard/cli_strategy.py
"""CLI-based confirmation strategy."""

import json
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console

from wolo.path_guard.exceptions import SessionCancelled
from wolo.path_guard.strategy import ConfirmationStrategy


class CLIConfirmationStrategy(ConfirmationStrategy):
    """Interactive confirmation strategy for CLI usage.

    This strategy prompts the user via the console for path confirmation
    requests. It supports both interactive (TTY) and non-interactive modes.

    In non-interactive mode (e.g., piped input), confirmation requests
    are automatically denied.
    """

    def __init__(
        self,
        max_confirmations_per_session: int | None = None,
        audit_denied: bool = True,
        audit_log_file: Path | None = None,
    ) -> None:
        """Initialize the CLI confirmation strategy."""
        self._console = Console()
        self._max_confirmations_per_session = max_confirmations_per_session
        self._confirmation_count = 0
        self._audit_denied = audit_denied
        self._audit_log_file = audit_log_file

    def _audit_denial(self, path: str, operation: str, reason: str) -> None:
        """Append a denial audit entry."""
        if not self._audit_denied or self._audit_log_file is None:
            return
        try:
            self._audit_log_file.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": datetime.now().isoformat(),
                "path": path,
                "operation": operation,
                "reason": reason,
            }
            with open(self._audit_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=True) + "\n")
        except Exception:
            # Auditing should never break tool execution.
            pass

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

        try:
            resolved_path = str(Path(path).resolve())
        except (OSError, RuntimeError):
            resolved_path = path

        self._console.print("\n[yellow]Path Confirmation Required[/yellow]")
        self._console.print(f"Operation: [cyan]{operation}[/cyan]")
        self._console.print(f"Path: [cyan]{path}[/cyan]")
        if resolved_path != path:
            self._console.print(f"Resolved Path: [cyan]{resolved_path}[/cyan]")
        self._console.print(
            "This path is not in the default allowlist (/tmp) or configured whitelist."
        )

        if (
            self._max_confirmations_per_session is not None
            and self._confirmation_count >= self._max_confirmations_per_session
        ):
            self._console.print("[dim]Confirmation limit reached, operation denied.[/dim]")
            self._audit_denial(path, operation, "max_confirmations_exceeded")
            return False

        # Non-interactive mode: auto-deny
        if not sys.stdin.isatty():
            self._console.print("[dim]Non-interactive mode, operation denied.[/dim]")
            self._audit_denial(path, operation, "non_interactive_auto_deny")
            return False

        # Interactive prompt
        while True:
            response = await self._read_confirmation_input()

            if response in ("", "y", "yes"):
                # Allow this specific path
                guard = get_path_guard()
                guard.confirm_directory(resolved_path)
                self._confirmation_count += 1
                return True
            elif response in ("n", "no"):
                # Deny this operation
                self._audit_denial(path, operation, "user_denied")
                return False
            elif response == "a":
                # Allow parent directory and all subdirectories
                guard = get_path_guard()
                parent = Path(resolved_path).parent
                guard.confirm_directory(parent)
                self._confirmation_count += 1
                self._console.print(
                    f"[green]Add[/green] {parent} and subdirectories to session whitelist"
                )
                return True
            elif response == "q":
                # Cancel the entire session
                raise SessionCancelled()

    async def _read_confirmation_input(self) -> str:
        """Read confirmation input with UI-aware terminal handling."""
        # Prefer the unified prompt_toolkit input path when UI is available.
        # It correctly handles terminal mode transitions and key echo.
        try:
            from wolo.ui import get_current_ui

            ui = get_current_ui()
        except Exception:
            ui = None

        if ui and hasattr(ui, "prompt_for_input"):
            control = getattr(ui, "manager", None)
            old_state = None
            if control is not None:
                try:
                    from wolo.control import ControlState

                    old_state = control.state
                    control._set_state(ControlState.WAIT_INPUT)
                except Exception:
                    old_state = None

            try:
                value = await ui.prompt_for_input("Allow this operation? [Y/n/a/q]")
                return (value or "").strip().lower()
            finally:
                if control is not None and old_state is not None:
                    try:
                        control._set_state(old_state)
                    except Exception:
                        pass

        # Fallback: force NORMAL mode before plain console input.
        terminal = None
        previous_mode = None
        try:
            from wolo.terminal import TerminalMode, get_terminal_manager

            terminal = get_terminal_manager()
            if terminal.available:
                previous_mode = terminal.current_mode
                await terminal.set_mode(TerminalMode.NORMAL, force=True)
        except Exception:
            terminal = None
            previous_mode = None

        try:
            return (
                self._console.input("\n[yellow]Allow this operation?[/yellow] [Y/n/a/q] ")
                .strip()
                .lower()
            )
        finally:
            if terminal and terminal.available and previous_mode is not None:
                try:
                    await terminal.set_mode(previous_mode, force=True)
                except Exception:
                    pass
