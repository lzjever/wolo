"""
Help system for Wolo CLI.

Provides context-sensitive help for all commands and subcommands.
"""

from wolo.cli.exit_codes import ExitCode
from wolo.cli.parser import ParsedArgs


def show_help(args: ParsedArgs) -> int:
    """
    Show help information.

    Args:
        args: Parsed arguments with help context

    Returns:
        Exit code
    """
    help_context = args.positional_args if args.positional_args else ["main"]

    if help_context[0] == "main":
        show_main_help()
    elif help_context[0] == "session":
        if len(help_context) > 1:
            show_subcommand_help("session", help_context[1])
        else:
            show_command_help("session")
    elif help_context[0] == "config":
        if len(help_context) > 1:
            show_subcommand_help("config", help_context[1])
        else:
            show_command_help("config")
    elif help_context[0] == "chat":
        show_command_help("chat")
    else:
        show_main_help()

    return ExitCode.SUCCESS


def show_main_help() -> None:
    """Show main help (wolo --help)."""
    help_text = """Wolo - AI Agent CLI

USAGE:
    wolo [OPTIONS] [PROMPT]
    wolo chat [OPTIONS]
    wolo session <SUBCOMMAND>
    wolo config <SUBCOMMAND>

EXECUTION MODES:
    (none)          SOLO mode (default): autonomous execution, no questions
                    Best for: scripts, automation, batch processing

    --coop          COOP mode: cooperative execution, AI may ask questions
                    Best for: complex tasks needing user guidance

    --repl          REPL mode: continuous conversation, loops for input
                    Best for: interactive exploration, debugging

BASIC USAGE:
    wolo "your prompt"                    Execute task (solo mode)
    wolo --coop "your prompt"             Execute with questions enabled
    wolo --repl                           Start interactive REPL
    wolo --repl "initial prompt"          REPL with initial message
    wolo chat                             Same as --repl
    cat file | wolo "do X"                Context + prompt

SESSION OPTIONS:
    -s, --session <name>    Create/use named session
    -r, --resume <id>       Resume session (REPL mode by default)
    -r, --resume <id> --solo "prompt"
                            Resume session (one-shot execution)

QUICK COMMANDS:
    -l, --list              List all sessions
    -w, --watch <id>        Watch running session
    -h, --help              Show this help

OTHER OPTIONS:
    -a, --agent <type>      Agent: general, plan, explore, compaction
    --base-url <url>        LLM service base URL (direct, bypasses config)
    -m, --model <model>     Model name (required if using --base-url)
    --api-key <key>         API key (required if using --base-url)
    -n, --max-steps <n>     Max steps (default: 100)
    --log-level <lvl>       DEBUG, INFO, WARNING, ERROR
    --save                  Force save session on completion
    -C, --workdir <path>    Working directory (automatically whitelisted)
    -P, --allow-path <path> Add path to whitelist (repeatable)

    If --base-url is specified, all three (--base-url, --model, --api-key) are required.
    Otherwise, Wolo uses endpoints from ~/.wolo/config.yaml

PATH PROTECTION:
    Wolo uses whitelist-based path protection for safe file operations.
    By default, only the working directory (if set via -C) and /tmp are allowed.

    Path Whitelist Priority (highest to lowest):
        1. Working directory (-C/--workdir) - highest priority
        2. CLI whitelist paths (-P/--allow-path)
        3. Config file whitelist (path_safety.allowed_write_paths)
        4. Default allowed (/tmp)

    Examples:
        wolo -C /path/to/project "modify files"
        wolo -C /project -P /home/user/docs "modify files"

OUTPUT OPTIONS:
    --output-style <s>      Output style: minimal, default, verbose
    --no-color              Disable color output
    --show-reasoning        Show model reasoning/thinking
    --hide-reasoning        Hide model reasoning/thinking
    --json                  JSON output (implies minimal style)

DEBUG OPTIONS:
    --debug-llm <file>      Log LLM requests/responses
    --debug-full <dir>      Save full JSON request/response
    --benchmark             Enable benchmark mode
    --benchmark-output <f>  Benchmark output file

EXAMPLES:
    wolo "fix the bug in main.py"
    git diff | wolo "write commit message"
    wolo --coop "design login feature"
    wolo --repl "let's explore the codebase"
    wolo -r mysession                        # Resume in REPL
    wolo -r mysession --solo "add tests"     # Resume one-shot

SESSION MANAGEMENT:
    wolo session list               List sessions
    wolo session show <id>          Show session info
    wolo session resume <id>        Resume in REPL mode
    wolo session watch <id>         Watch running session
    wolo session delete <id>        Delete session
    wolo session clean [days]       Clean old sessions

CONFIGURATION:
    wolo config init           Initialize configuration (first-time setup)
    wolo config list-endpoints List configured endpoints
    wolo config show           Show current configuration

See 'wolo <command> -h' for more information on a command.
"""
    print(help_text)


def show_command_help(command: str) -> None:
    """Show command help."""
    if command == "session":
        help_text = """Session Management

USAGE:
    wolo session <subcommand> [options]

SUBCOMMANDS:
    list             List all sessions
    show <id>        Show session details (non-blocking)
    resume <id>      Resume session in REPL mode (blocking)
    create [name]    Create a new session
    watch <id>       Watch a running session (read-only)
    delete <id>      Delete a session
    clean [days]     Clean old sessions (default: 30 days)

QUICK OPTIONS:
    wolo -l                  Same as: wolo session list
    wolo -w <id>             Same as: wolo session watch <id>
    wolo -r <id>             Resume session (REPL mode, default)
    wolo -r <id> --solo "p"  Resume session (one-shot execution)

EXAMPLES:
    wolo session list
    wolo session show myproject
    wolo session resume myproject           # Enter REPL
    wolo -r myproject                       # Same as above
    wolo -r myproject --solo "add tests"    # One-shot execution
    echo "task" | wolo -r myproject         # REPL with initial message

NOTE:
    - 'session show' displays info and exits (non-blocking)
    - 'session resume' and '-r' both enter REPL mode by default
    - Use '-r <id> --solo "prompt"' for one-shot execution
"""
        print(help_text)
    elif command == "config":
        help_text = """Configuration Management

USAGE:
    wolo config <subcommand>

SUBCOMMANDS:
    init                Initialize Wolo configuration (first-time setup)
    list-endpoints      List configured endpoints
    show                Show current configuration
    docs                Show configuration documentation
    example             Show example configuration file

EXAMPLES:
    wolo config init
    wolo config list-endpoints
    wolo config show
    wolo config docs
    wolo config example
"""
        print(help_text)
    elif command == "chat":
        help_text = """Wolo Chat - Interactive Conversation Mode

USAGE:
    wolo chat [OPTIONS]
    wolo --repl [OPTIONS] [PROMPT]

DESCRIPTION:
    Start an interactive REPL session. The agent will respond to each
    message and wait for your next input.

    'wolo chat' and 'wolo --repl' are equivalent.

OPTIONS:
    -s, --session <n>   Use named session
    -a, --agent <type>  Agent type
    --base-url <url>    LLM service base URL (bypasses config)
    -m, --model <m>     Model name (required if using --base-url)
    --api-key <key>     API key (required if using --base-url)
    -n, --max-steps <n> Max steps per turn
    -C, --workdir <p>   Working directory (automatically whitelisted)
    -P, --allow-path <p> Add path to whitelist (repeatable)

    See 'wolo --help' for PATH PROTECTION details

REPL COMMANDS:
    /exit, /quit        Exit REPL
    Ctrl+C              Exit REPL

EXAMPLES:
    wolo chat
    wolo --repl
    wolo --repl "let's explore the codebase"
    wolo chat -s myproject
    wolo chat --agent plan

TO RESUME AN EXISTING SESSION:
    wolo -r <session_id>
    wolo session resume <session_id>
"""
        print(help_text)
    else:
        show_main_help()


def show_subcommand_help(command: str, subcommand: str) -> None:
    """Show subcommand help."""
    if command == "session":
        if subcommand == "create":
            print("""wolo session create [name]

Create a new session. If name is not provided, a name will be auto-generated.

EXAMPLES:
    wolo session create myproject
    wolo session create              # Auto-generate name
""")
        elif subcommand == "list":
            print("""wolo session list

List all saved sessions with their status and metadata.

ALIAS:
    wolo -l
""")
        elif subcommand == "show":
            print("""wolo session show <id>

Show detailed information about a specific session.
This is a non-blocking command that displays info and exits.

EXAMPLES:
    wolo session show myproject
""")
        elif subcommand == "resume":
            print("""wolo session resume <id>

Resume a session in REPL mode for continued conversation.
This is a blocking command that enters interactive REPL.

If stdin has content (pipe), it becomes the first message.

EXAMPLES:
    wolo session resume myproject              # Enter REPL
    wolo -r myproject                          # Same as above
    echo "task" | wolo -r myproject            # REPL with initial msg

FOR ONE-SHOT EXECUTION:
    Use '-r' with '--solo' flag:
    wolo -r myproject --solo "your prompt"
""")
        elif subcommand == "watch":
            print("""wolo session watch <id>

Watch a running session in read-only mode.
Real-time output will be displayed.

ALIAS:
    wolo -w <id>

EXAMPLES:
    wolo session watch myproject
    wolo -w myproject
""")
        elif subcommand == "delete":
            print("""wolo session delete <id>

Delete a session. The session must not be running.

EXAMPLES:
    wolo session delete myproject
""")
        elif subcommand == "clean":
            print("""wolo session clean [days]

Clean (delete) sessions older than the specified number of days.
Default is 30 days.

EXAMPLES:
    wolo session clean          # Delete sessions older than 30 days
    wolo session clean 7        # Delete sessions older than 7 days
""")
        else:
            show_command_help("session")
    elif command == "config":
        if subcommand == "init":
            print("""wolo config init

Initialize Wolo configuration for first-time setup.
This command will prompt you for:
  - API Endpoint URL (must start with http:// or https://)
  - API Key
  - Model name

The configuration will be saved to ~/.wolo/config.yaml

If a configuration file already exists, this command will show an error
and exit. To reinitialize, delete the existing config file first.

EXAMPLES:
    wolo config init
""")
        elif subcommand == "list-endpoints":
            print("""wolo config list-endpoints

List all configured endpoints from ~/.wolo/config.yaml
""")
        elif subcommand == "show":
            print("""wolo config show

Show the current configuration file contents.
""")
        elif subcommand == "docs":
            print("""wolo config docs

Show the full configuration documentation.
""")
        elif subcommand == "example":
            print("""wolo config example

Show an example configuration file that can be saved to ~/.wolo/config.yaml
""")
        else:
            show_command_help("config")
    else:
        show_main_help()
