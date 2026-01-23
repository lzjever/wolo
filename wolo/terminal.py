"""
Terminal state management module.

Provides unified terminal state management to avoid conflicts between
different components (KeyboardListener, prompt_toolkit, etc.).
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from enum import Enum

logger = logging.getLogger(__name__)


class TerminalMode(Enum):
    """Terminal input modes."""

    NORMAL = "normal"  # Cooked mode (line buffered, canonical)
    CBREAK = "cbreak"  # Cbreak mode (single char input, no line buffering)
    RAW = "raw"  # Raw mode (completely raw input)


class TerminalManager:
    """
    Unified terminal state manager.

    Manages terminal settings (termios) to prevent conflicts between
    different components that need different terminal modes.

    Usage:
        terminal = TerminalManager()

        # Use context manager for automatic cleanup
        async with terminal.enter_mode(TerminalMode.CBREAK):
            # Terminal is in cbreak mode here
            ...
        # Terminal is automatically restored

        # Or manually manage
        await terminal.set_mode(TerminalMode.CBREAK)
        # ... use terminal ...
        terminal.restore()
    """

    def __init__(self):
        """Initialize terminal manager."""
        if not sys.stdin.isatty():
            self._fd = None
            self._original_settings = None
            self._available = False
            logger.debug("Not a TTY, terminal management disabled")
            return

        try:
            import termios

            self._fd = sys.stdin.fileno()
            self._original_settings = termios.tcgetattr(self._fd)
            self._available = True
            self._current_mode: TerminalMode | None = None
            self._lock = asyncio.Lock()
            logger.debug("Terminal manager initialized")
        except ImportError:
            self._fd = None
            self._original_settings = None
            self._available = False
            logger.warning("termios not available, terminal management disabled")
        except Exception as e:
            self._fd = None
            self._original_settings = None
            self._available = False
            logger.error(f"Failed to initialize terminal manager: {e}")

    @property
    def available(self) -> bool:
        """Check if terminal management is available."""
        return self._available

    @property
    def current_mode(self) -> TerminalMode | None:
        """Get current terminal mode."""
        return self._current_mode

    async def set_mode(self, mode: TerminalMode, force: bool = False) -> None:
        """
        Set terminal to specified mode.

        Args:
            mode: Terminal mode to set
            force: If True, set mode even if already in that mode (useful after external changes)
        """
        if not self._available:
            logger.debug(f"Terminal management not available, ignoring set_mode({mode})")
            return

        async with self._lock:
            if not force and self._current_mode == mode:
                return

            try:
                import termios
                import tty

                if mode == TerminalMode.CBREAK:
                    tty.setcbreak(self._fd)
                    logger.debug("Terminal set to cbreak mode")
                elif mode == TerminalMode.NORMAL:
                    if self._original_settings:
                        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._original_settings)
                        logger.debug("Terminal restored to normal mode")
                elif mode == TerminalMode.RAW:
                    tty.setraw(self._fd)
                    logger.debug("Terminal set to raw mode")
                else:
                    raise ValueError(f"Unknown terminal mode: {mode}")

                self._current_mode = mode
            except Exception as e:
                logger.error(f"Failed to set terminal mode to {mode}: {e}")
                raise

    def restore(self) -> None:
        """
        Restore terminal to original settings.

        Should be called on cleanup/shutdown.
        """
        if not self._available or not self._original_settings:
            return

        try:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._original_settings)
            self._current_mode = None
            logger.debug("Terminal restored to original settings")
        except Exception as e:
            logger.warning(f"Failed to restore terminal settings: {e}")

    @asynccontextmanager
    async def enter_mode(self, mode: TerminalMode):
        """
        Context manager for terminal mode.

        Automatically restores previous mode on exit.

        Args:
            mode: Terminal mode to enter

        Yields:
            TerminalManager instance
        """
        if not self._available:
            yield self
            return

        previous_mode = self._current_mode

        try:
            await self.set_mode(mode)
            yield self
        finally:
            if previous_mode:
                await self.set_mode(previous_mode)
            else:
                self.restore()


# Global terminal manager instance
_global_terminal: TerminalManager | None = None


def get_terminal_manager() -> TerminalManager:
    """
    Get or create global terminal manager instance.

    Returns:
        TerminalManager instance
    """
    global _global_terminal
    if _global_terminal is None:
        _global_terminal = TerminalManager()
    return _global_terminal


def reset_terminal_manager() -> None:
    """Reset global terminal manager (for testing)."""
    global _global_terminal
    if _global_terminal:
        _global_terminal.restore()
    _global_terminal = None
