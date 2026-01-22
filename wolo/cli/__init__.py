"""CLI package for Wolo."""

from wolo.cli.main import main
from wolo.cli.events import setup_event_handlers
from wolo.cli.utils import print_session_info
from wolo.cli.logging_utils import setup_logging

# For backward compatibility with entry point
def main_async() -> int:
    """Entry point for uv scripts."""
    return main()

__all__ = ["main", "main_async", "setup_event_handlers", "print_session_info", "setup_logging"]
