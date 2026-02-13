"""
Simplified control module for Wolo.

Only supports Ctrl+C interrupt. No complex state machine.
KISS principle: Keep It Simple, Stupid.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ControlManager:
    """
    Simplified control manager.

    Only tracks:
    - Whether we've been interrupted (Ctrl+C)
    - Current step info
    """

    interrupted: bool = False
    step: int = 0
    max_steps: int = 100

    def should_interrupt(self) -> bool:
        """Check if we should interrupt."""
        return self.interrupted

    def request_interrupt(self) -> None:
        """Request an interrupt (called by signal handler)."""
        self.interrupted = True
        logger.info("Interrupt requested")

    def start_running(self) -> None:
        """Start running (reset state)."""
        self.interrupted = False
        self.step = 0
        logger.debug("Control started")

    def set_step(self, step: int, max_steps: int | None = None) -> None:
        """Update step info."""
        self.step = step
        if max_steps is not None:
            self.max_steps = max_steps

    def check_step_boundary(self) -> str | None:
        """Check at step boundary - always returns None (no interject support)."""
        return None

    def finish(self) -> None:
        """Finish running."""
        self.interrupted = False
        logger.debug("Control finished")

    def reset(self) -> None:
        """Reset state."""
        self.interrupted = False
        self.step = 0


# Global manager storage (one per session)
_managers: dict[str, ControlManager] = {}


def get_manager(session_id: str) -> ControlManager:
    """Get or create control manager for session."""
    if session_id not in _managers:
        _managers[session_id] = ControlManager()
        logger.debug(f"Created control manager for session {session_id[:8]}...")
    return _managers[session_id]


def remove_manager(session_id: str) -> None:
    """Remove control manager for session."""
    if session_id in _managers:
        _managers[session_id].finish()
        del _managers[session_id]
        logger.debug(f"Removed control manager for session {session_id[:8]}...")


def get_all_managers() -> dict[str, ControlManager]:
    """Get all managers (for debugging)."""
    return _managers.copy()
