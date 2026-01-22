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
    elif help_context[0] == "debug":
        if len(help_context) > 1:
            show_subcommand_help("debug", help_context[1])
        else:
            show_command_help("debug")
    elif help_context[0] in ("chat", "repl"):
        show_command_help("chat")
    else:
        show_main_help()
    
    return ExitCode.SUCCESS


def show_main_help() -> None:
    """Show main help (wolo --help)."""
    help_text = """Wolo - AI Agent CLI

USAGE:
    wolo [OPTIONS] [PROMPT]
    wolo chat|repl [OPTIONS]
    wolo session <SUBCOMMAND>
    wolo config <SUBCOMMAND>

BASIC USAGE:
    wolo "your prompt"                    Execute task (solo mode)
    cat file | wolo "do X"                Context + prompt
    wolo chat                             Start interactive REPL
    wolo -r <id> "continue"               Resume session with prompt
    wolo session resume <id>              Resume session in REPL

EXECUTION MODES:
    --solo          Solo mode: autonomous, no questions (default)
    --coop          Coop mode: AI may ask clarifying questions

SESSION OPTIONS:
    -s, --session <name>    Create/use named session
    -r, --resume <id>       Resume session (requires prompt)

QUICK COMMANDS:
    -l, --list              List all sessions
    -w, --watch <id>        Watch running session
    -h, --help              Show this help

OTHER OPTIONS:
    -a, --agent <type>      Agent: general, plan, explore, compaction
    -e, --endpoint <name>   Use configured endpoint
    -m, --model <model>     Override model
    -n, --max-steps <n>     Max steps (default: 100)
    -L, --log-level <lvl>   DEBUG, INFO, WARNING, ERROR
    -S, --save              Force save session on completion

DEBUG OPTIONS:
    --debug-llm <file>      Log LLM requests/responses
    --debug-full <dir>      Save full JSON request/response
    --benchmark             Enable benchmark mode

EXAMPLES:
    wolo "fix the bug in main.py"
    git diff | wolo "write commit message"
    wolo --coop "design login feature"
    wolo -s myproject "implement auth"
    wolo -r myproject "add tests"

SESSION MANAGEMENT:
    wolo session list               List sessions
    wolo session show <id>          Show session info
    wolo session resume <id>        Resume in REPL mode
    wolo session watch <id>         Watch running session
    wolo session delete <id>        Delete session
    wolo session clean [days]       Clean old sessions

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
    wolo -r <id> "prompt"    Resume with prompt (one-shot, not REPL)

EXAMPLES:
    wolo session list
    wolo session show myproject
    wolo session resume myproject           # Enter REPL
    wolo -r myproject "continue work"       # One-shot execution
    echo "task" | wolo session resume myproject   # REPL with initial message

NOTE:
    - 'session show' displays info and exits (non-blocking)
    - 'session resume' enters REPL mode (blocking, interactive)
    - Use '-r' for one-shot execution with a new prompt
"""
        print(help_text)
    elif command == "config":
        help_text = """Configuration Management

USAGE:
    wolo config <subcommand>

SUBCOMMANDS:
    list-endpoints   List configured endpoints
    show             Show current configuration
    docs             Show configuration documentation
    example          Show example configuration file

EXAMPLES:
    wolo config list-endpoints
    wolo config show
    wolo config docs
    wolo config example
"""
        print(help_text)
    elif command == "debug":
        help_text = """Debugging Tools

USAGE:
    wolo debug <subcommand> [options]

SUBCOMMANDS:
    llm <file>       Show usage for LLM debugging (use --debug-llm flag instead)
    full <dir>       Show usage for full debug (use --debug-full flag instead)
    benchmark        Show usage for benchmark mode (use --benchmark flag instead)

Note: Debug options are typically used as execution flags:

    wolo --debug-llm <file> "your prompt"
        Log LLM requests/responses to file

    wolo --debug-full <dir> "your prompt"
        Save full JSON request/response to directory

    wolo --benchmark "your prompt"
        Enable benchmark mode and export metrics

EXAMPLES:
    wolo --debug-llm llm.log "fix bug"
    wolo --debug-full ./debug "implement feature"
    wolo --benchmark "run tests"
"""
        print(help_text)
    elif command in ("chat", "repl"):
        help_text = """Wolo REPL - Interactive Conversation Mode

USAGE:
    wolo chat [OPTIONS]
    wolo repl [OPTIONS]

DESCRIPTION:
    Start an interactive REPL session. The agent will respond to each
    message and wait for your next input.
    
    'chat' and 'repl' are synonyms.

OPTIONS:
    --coop              Enable AI questions (default in REPL)
    -s, --session <n>   Use named session
    -a, --agent <type>  Agent type
    -e, --endpoint <n>  Use endpoint
    -m, --model <m>     Override model
    -n, --max-steps <n> Max steps per turn

REPL COMMANDS:
    /exit, /quit        Exit REPL
    Ctrl+C              Exit REPL

EXAMPLES:
    wolo chat
    wolo repl -s myproject
    wolo chat --agent plan

TO RESUME AN EXISTING SESSION:
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
    echo "task" | wolo session resume myproject # REPL with initial msg

FOR ONE-SHOT EXECUTION:
    Use '-r' flag instead:
    wolo -r myproject "your prompt"
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
        if subcommand == "list-endpoints":
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
    elif command == "debug":
        if subcommand == "llm":
            print("""wolo debug llm <file>

Show usage information for LLM debugging.
Note: Use 'wolo --debug-llm <file> "your prompt"' instead.

This subcommand is provided for reference only.
""")
        elif subcommand == "full":
            print("""wolo debug full <dir>

Show usage information for full debug mode.
Note: Use 'wolo --debug-full <dir> "your prompt"' instead.

This subcommand is provided for reference only.
""")
        elif subcommand == "benchmark":
            print("""wolo debug benchmark

Show usage information for benchmark mode.
Note: Use 'wolo --benchmark "your prompt"' instead.

This subcommand is provided for reference only.
""")
        else:
            show_command_help("debug")
    else:
        show_main_help()
