"""
Main CLI entry point for Wolo.

This module handles command routing and dispatches to appropriate handlers.
"""

import sys

from wolo.cli.commands.config import ConfigCommandGroup
from wolo.cli.commands.repl import ReplCommand
from wolo.cli.commands.run import RunCommand
from wolo.cli.commands.session import SessionCommandGroup
from wolo.cli.exit_codes import ExitCode
from wolo.cli.parser import (
    FlexibleArgumentParser,
    ParsedArgs,
    validate_option_conflicts,
)
from wolo.exceptions import (
    WoloConfigError,
    WoloError,
    WoloLLMError,
    WoloPathSafetyError,
    WoloSessionError,
    WoloToolError,
)


def _format_error_message(error: WoloError) -> str:
    """Format WoloError for user-friendly display.

    Args:
        error: The WoloError to format

    Returns:
        User-friendly error message
    """
    if isinstance(error, WoloConfigError):
        return f"Configuration Error: {error}"
    if isinstance(error, WoloToolError):
        tool_name = error.context.get("tool_name", "unknown")
        return f"Tool Error ({tool_name}): {error}"
    if isinstance(error, WoloSessionError):
        session = error.session_id or error.context.get("session_id", "unknown")
        return f"Session Error ({session}): {error}"
    if isinstance(error, WoloLLMError):
        model = error.context.get("model", "unknown")
        return f"LLM Error ({model}): {error}"
    if isinstance(error, WoloPathSafetyError):
        path = error.context.get("path", "unknown")
        return f"Path Safety Error: {error} (path: {path})"
    return f"Error: {error}"


def _check_stdin() -> bool:
    """
    Check if stdin should be checked for input.

    Returns True if stdin is a pipe (not a TTY), even if data hasn't arrived yet.
    This allows piped input to work: cmd1 | cmd2
    """
    # If stdin is a TTY (interactive terminal), don't check for pipe input
    if sys.stdin.isatty():
        return False

    # If stdin is a pipe (not a TTY), always check it
    # The parser will handle reading (which may block until data arrives)
    return True


def _route_command(args: list[str], has_stdin: bool) -> tuple[str, list[str]]:
    """
    Route command to appropriate handler.

    ROUTING PRIORITY (STRICT ORDER):
    1. Help: -h, --help (highest priority)
    2. Quick commands: -l, -w
    3. Mode flags: --repl (routes to REPL mode)
    4. Subcommands: session, config
    5. REPL entry: chat
    6. Execution: prompt provided (CLI or stdin)
    7. Default: show brief help (no input)

    Args:
        args: Command-line arguments
        has_stdin: Whether stdin has data

    Returns:
        (command_type, remaining_args)
    """
    # 1. Help commands (highest priority - check FIRST, even before stdin)
    if args:
        first = args[0]
        if first in ("-h", "--help"):
            return ("help", ["main"])
        if len(args) > 1 and args[1] in ("-h", "--help"):
            return ("help", [first])
        if len(args) > 2 and args[2] in ("-h", "--help"):
            return ("help", [first, args[1]])

    # 2. Quick commands (check BEFORE stdin and subcommands)
    if args:
        first = args[0]
        # Quick list command
        if first in ("-l", "--list"):
            return ("session_list", args[1:])

        # Quick watch command
        if first in ("-w", "--watch"):
            if len(args) < 2:
                return ("error", ["watch requires session id"])
            return ("session_watch", [args[1]])

    # 3. Mode flags: --repl routes to REPL mode (can have optional initial prompt)
    if "--repl" in args:
        # Remove --repl from args and route to repl command
        remaining = [a for a in args if a != "--repl"]
        return ("repl", remaining)

    # 4. Check for empty args
    if not args:
        if has_stdin:
            # Stdin input with no args means execution mode
            return ("execute", [])
        # No args, no stdin → show brief help
        return ("default_help", [])

    first = args[0]

    # 5. Subcommands
    if first == "session":
        return ("session", args[1:])
    if first == "config":
        return ("config", args[1:])

    # 6. REPL entry: 'chat' command
    if first == "chat":
        return ("repl", args[1:])

    # 7. Execution mode: has prompt (args) or stdin
    if has_stdin or args:
        return ("execute", args)

    # 8. Default: show brief help
    return ("default_help", [])


def _show_brief_help() -> int:
    """
    Show brief help when no input provided.

    Returns:
        ExitCode.SUCCESS
    """
    print("""Wolo - AI Agent CLI

Usage:
  wolo "your prompt"                    Execute task (solo mode, default)
  wolo --coop "your prompt"             Execute with AI questions enabled
  wolo --repl                           Start interactive conversation
  wolo --repl "initial prompt"          REPL with initial message
  cat file | wolo "analyze this"        Context + prompt

Session:
  wolo -r <id>                          Resume session (REPL mode)
  wolo -r <id> --solo "prompt"          Resume session (one-shot)
  wolo -l                               List sessions
  wolo -w <id>                          Watch running session

More:
  wolo -h                               Full help
  wolo config init                      First-time setup

Examples:
  wolo "fix the bug in main.py"
  git diff | wolo "write commit message"
  wolo --coop "help me design the API"
""")
    return ExitCode.SUCCESS


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (see wolo.cli.exit_codes.ExitCode)
    """
    args = sys.argv[1:]
    has_stdin = _check_stdin()

    # Route command
    command_type, remaining_args = _route_command(args, has_stdin)

    # Handle errors from routing
    if command_type == "error":
        print(f"Error: {remaining_args[0]}", file=sys.stderr)
        return ExitCode.ERROR

    # Handle default help (no input)
    if command_type == "default_help":
        return _show_brief_help()

    # Handle help command early (before parsing)
    if command_type == "help":
        from wolo.cli.help import show_help

        parsed = ParsedArgs()
        parsed.command_type = "help"
        parsed.positional_args = remaining_args if remaining_args else ["main"]
        return show_help(parsed)

    # Handle quick commands that don't need parsing
    if command_type == "session_list":
        # Quick list - don't parse, just execute
        parsed = ParsedArgs()
        parsed.command_type = "session"
        parsed.subcommand = "list"
        return SessionCommandGroup().execute(parsed)
    elif command_type == "session_watch":
        # Quick watch - set subcommand and session ID
        parsed = ParsedArgs()
        parsed.command_type = "session"
        parsed.subcommand = "watch"
        if remaining_args:
            parsed.session_options.watch_id = remaining_args[0]
            parsed.positional_args = [remaining_args[0]]
        return SessionCommandGroup().execute(parsed)

    # Parse arguments for other commands
    parser = FlexibleArgumentParser()
    parsed = parser.parse(remaining_args, check_stdin=has_stdin)
    parsed.command_type = command_type

    # Validate option conflicts after parsing
    # Build options dict from parsed for conflict check
    options_for_check = {}
    if "--solo" in args:
        options_for_check["--solo"] = True
    if "--coop" in args:
        options_for_check["--coop"] = True
    if "--repl" in args:
        options_for_check["--repl"] = True
    if parsed.session_options.session_name is not None:
        options_for_check["--session"] = True
    if parsed.session_options.resume_id is not None:
        options_for_check["--resume"] = True

    is_valid, error_msg = validate_option_conflicts(options_for_check)
    if not is_valid:
        print(error_msg, file=sys.stderr)
        return ExitCode.ERROR

    # Handle -r/--resume: default to REPL mode unless --solo is explicit
    if parsed.session_options.resume_id is not None:
        from wolo.modes import ExecutionMode

        if "--solo" not in args:
            # Resume defaults to REPL mode
            parsed.execution_options.mode = ExecutionMode.REPL

    # Extract subcommand for command groups
    if command_type in ("session", "config") and remaining_args:
        # Set subcommand from remaining_args (before parsing removes it)
        parsed.subcommand = remaining_args[0]
        # The parser may have already added it to positional_args, remove it
        if remaining_args[0] in parsed.positional_args:
            parsed.positional_args.remove(remaining_args[0])
        # Clear args.message for subcommands - it shouldn't contain subcommand/session_id
        # The subcommand handler should get message from its own positional_args
        parsed.message = ""
        parsed.pipe_input = None
        parsed.cli_prompt = None
        parsed.message_from_stdin = False

    # Execute command
    try:
        if command_type == "execute":
            from wolo.modes import ExecutionMode

            # If mode is REPL (from --resume without --solo), use ReplCommand
            if parsed.execution_options.mode == ExecutionMode.REPL:
                return ReplCommand().execute(parsed)
            return RunCommand().execute(parsed)
        elif command_type == "repl":
            from wolo.modes import ExecutionMode

            # Set mode to REPL for chat command
            parsed.execution_options.mode = ExecutionMode.REPL
            return ReplCommand().execute(parsed)
        elif command_type == "session":
            return SessionCommandGroup().execute(parsed)
        elif command_type == "config":
            return ConfigCommandGroup().execute(parsed)

        # Unknown command type
        print(f"Error: Unknown command type: {command_type}", file=sys.stderr)
        return ExitCode.ERROR
    except WoloError as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(str(e), extra={"session_id": e.session_id})
        print(_format_error_message(e), file=sys.stderr)
        return ExitCode.ERROR
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return ExitCode.INTERRUPTED
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Unexpected error")
        print(f"Unexpected error: {e}", file=sys.stderr)
        return ExitCode.ERROR
