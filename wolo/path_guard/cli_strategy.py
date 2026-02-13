# wolo/path_guard/cli_strategy.py
"""CLI-based confirmation strategy (simplified - no rich, no UI)."""

import json
import sys
from datetime import datetime
from pathlib import Path

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

        print()
        print("Path Confirmation Required")
        print(f"Operation: {operation}")
        print(f"Path: {path}")
        if resolved_path != path:
            print(f"Resolved Path: {resolved_path}")
        print("This path is not in the default allowlist (/tmp) or configured whitelist.")

        if (
            self._max_confirmations_per_session is not None
            and self._confirmation_count >= self._max_confirmations_per_session
        ):
            print("Confirmation limit reached, operation denied.")
            self._audit_denial(path, operation, "max_confirmations_exceeded")
            return False

        # Non-interactive mode: auto-deny
        if not sys.stdin.isatty():
            print("Non-interactive mode, operation denied.")
            self._audit_denial(path, operation, "non_interactive_auto_deny")
            return False

        # Interactive prompt
        while True:
            response = self._read_confirmation_input()

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
                print(f"Added {parent} and subdirectories to session whitelist")
                return True
            elif response == "q":
                # Cancel the entire session
                raise SessionCancelled()

    def _read_confirmation_input(self) -> str:
        """Read confirmation input using simple input()."""
        try:
            value = input("\nAllow this operation? [Y/n/a/q] ")
            return value.strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "n"
