"""
Exit code definitions for Wolo CLI.

This module defines all exit codes used by the Wolo CLI.
All commands MUST use these constants instead of magic numbers.

Exit Codes:
    0   - SUCCESS: Task completed successfully
    1   - ERROR: General error (invalid arguments, runtime error)
    2   - QUOTA_EXCEEDED: Max steps or token limit reached
    3   - SESSION_ERROR: Session not found, locked, or corrupted
    4   - CONFIG_ERROR: Invalid config, missing API key, etc.
    130 - INTERRUPTED: User pressed Ctrl+C (SIGINT)
    131 - TERMINATED: Process received SIGTERM

Usage:
    from wolo.cli.exit_codes import ExitCode

    return ExitCode.SUCCESS
    return ExitCode.ERROR
"""


class ExitCode:
    """Exit code constants for Wolo CLI."""

    # Success
    SUCCESS = 0
    """Task completed successfully."""

    # General errors
    ERROR = 1
    """General error: invalid arguments, runtime error, etc."""

    # Quota/limit errors
    QUOTA_EXCEEDED = 2
    """Max steps or token limit reached."""

    # Session errors
    SESSION_ERROR = 3
    """Session not found, locked, or corrupted."""

    # Configuration errors
    CONFIG_ERROR = 4
    """Invalid config, missing API key, endpoint not found, etc."""

    # Signal-based exits (128 + signal number)
    INTERRUPTED = 130
    """User pressed Ctrl+C (128 + SIGINT=2)."""

    TERMINATED = 131
    """Process received SIGTERM (128 + SIGTERM=15)."""
