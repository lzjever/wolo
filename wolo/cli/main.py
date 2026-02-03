"""
Main CLI entry point for Wolo.

This module handles command routing and dispatches to appropriate handlers.
"""

import sys
from pathlib import Path

from wolo.cli.commands.config import ConfigCommandGroup
from wolo.cli.commands.debug import DebugCommandGroup
from wolo.cli.commands.repl import ReplCommand
from wolo.cli.commands.run import RunCommand
from wolo.cli.commands.session import SessionCommandGroup
from wolo.cli.exit_codes import ExitCode
from wolo.cli.parser import (
    FlexibleArgumentParser,
    ParsedArgs,
    validate_option_conflicts,
)


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

    ROUTING PRIORITY (STRICT ORDER - DO NOT MODIFY):
    1. Help: -h, --help (highest priority)
    2. Quick commands: -l, -w
    3. Subcommands: session, config, debug
    4. REPL entry: chat, repl
    5. Deprecated: run (shows warning, still works)
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

    # 3. Check for empty args
    if not args:
        if has_stdin:
            # Stdin input with no args means execution mode
            return ("execute", [])
        # No args, no stdin → show brief help
        return ("default_help", [])

    first = args[0]

    # 4. Subcommands
    if first == "session":
        return ("session", args[1:])
    if first == "config":
        return ("config", args[1:])
    if first == "debug":
        return ("debug", args[1:])

    # 5. REPL entry: chat and repl are synonyms
    if first in ("chat", "repl"):
        return ("repl", args[1:])

    # 6. Deprecated: run command (still works but shows warning)
    if first == "run":
        print(
            "Warning: The 'run' command is deprecated. Use 'wolo \"prompt\"' directly.",
            file=sys.stderr,
        )
        return ("execute", args[1:])

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
  wolo "your prompt"                    Execute a task
  cat file | wolo "analyze this"        Context + prompt
  wolo chat                             Start interactive session
  wolo -r <id> "continue"               Resume session

Quick commands:
  wolo -l                               List sessions
  wolo -w <id>                          Watch running session
  wolo -h                               Full help

Configuration:
  wolo config init            Initialize configuration (first-time setup)

Examples:
  wolo "fix the bug in main.py"
  git diff | wolo "write commit message"
  wolo --coop "help me design the API"
""")
    return ExitCode.SUCCESS


def _initialize_path_guard(config, cli_paths: list[str]) -> None:
    """Initialize PathGuard with config and CLI-provided paths.

    Args:
        config: Configuration object containing path_safety settings
        cli_paths: List of paths provided via --allow-path CLI argument
    """
    from wolo.path_guard import PathGuard, set_path_guard

    config_paths = config.path_safety.allowed_write_paths
    cli_path_objects = [Path(p).resolve() for p in cli_paths]

    guard = PathGuard(
        config_paths=config_paths,
        cli_paths=cli_path_objects,
    )
    set_path_guard(guard)


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
    if parsed.execution_options.mode.value == "solo":
        # Check if --solo was explicitly set vs default
        # We need to check the original args for explicit flags
        if "--solo" in args or "solo" in args:
            options_for_check["--solo"] = True
    if "--coop" in args or "coop" in args:
        options_for_check["--coop"] = True
    if parsed.session_options.session_name is not None:
        options_for_check["--session"] = True
    if parsed.session_options.resume_id is not None:
        options_for_check["--resume"] = True

    is_valid, error_msg = validate_option_conflicts(options_for_check)
    if not is_valid:
        print(error_msg, file=sys.stderr)
        return ExitCode.ERROR

    # Extract subcommand for command groups
    if command_type in ("session", "config", "debug") and remaining_args:
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
    if command_type == "execute":
        return RunCommand().execute(parsed)
    elif command_type == "repl":
        from wolo.modes import ExecutionMode

        # Set mode to REPL for chat/repl command
        parsed.execution_options.mode = ExecutionMode.REPL
        return ReplCommand().execute(parsed)
    elif command_type == "session":
        return SessionCommandGroup().execute(parsed)
    elif command_type == "config":
        return ConfigCommandGroup().execute(parsed)
    elif command_type == "debug":
        return DebugCommandGroup().execute(parsed)

    # Unknown command type
    print(f"Error: Unknown command type: {command_type}", file=sys.stderr)
    return ExitCode.ERROR
