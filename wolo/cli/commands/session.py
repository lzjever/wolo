"""
Session management commands for Wolo CLI.

Commands:
    create [name]    Create a new session
    list             List all sessions
    show <id>        Show session details (non-blocking)
    resume <id>      Resume session in REPL mode (blocking)
    watch <id>       Watch a running session (read-only)
    delete <id>      Delete a session
    clean [days]     Clean old sessions
"""

import sys
import asyncio
from datetime import datetime, timedelta

from wolo.cli.commands.base import BaseCommand
from wolo.cli.parser import ParsedArgs
from wolo.cli.exit_codes import ExitCode


class SessionCommandGroup(BaseCommand):
    """Session management command group."""
    
    @property
    def name(self) -> str:
        return "session"
    
    @property
    def description(self) -> str:
        return "Manage sessions"
    
    def execute(self, args: ParsedArgs) -> int:
        """Route to subcommand."""
        subcommand = args.subcommand or "list"  # Default to list
        
        if subcommand == "create":
            return SessionCreateCommand().execute(args)
        elif subcommand == "list":
            return SessionListCommand().execute(args)
        elif subcommand == "show":
            return SessionShowCommand().execute(args)
        elif subcommand == "resume":
            return SessionResumeCommand().execute(args)
        elif subcommand == "watch":
            return SessionWatchCommand().execute(args)
        elif subcommand == "delete":
            return SessionDeleteCommand().execute(args)
        elif subcommand == "clean":
            return SessionCleanCommand().execute(args)
        else:
            print(f"Error: Unknown subcommand '{subcommand}'", file=sys.stderr)
            print(f"Available subcommands: create, list, show, resume, watch, delete, clean", file=sys.stderr)
            return ExitCode.ERROR


class SessionCreateCommand(BaseCommand):
    """wolo session create [name]"""
    
    @property
    def name(self) -> str:
        return "session create"
    
    @property
    def description(self) -> str:
        return "Create a new session"
    
    def validate_args(self, args: ParsedArgs) -> tuple[bool, str]:
        """Validate create command arguments."""
        # Optional name, no validation needed
        return (True, "")
    
    def execute(self, args: ParsedArgs) -> int:
        """Execute create command."""
        from wolo.session import create_session, get_session_status
        from wolo.agent_names import get_random_agent_name
        from wolo.cli.utils import print_session_info
        
        # Get session name from positional args
        session_name = None
        if args.positional_args:
            session_name = args.positional_args[0]
        
        try:
            if session_name:
                # Check if session already exists
                status = get_session_status(session_name)
                if status.get("exists"):
                    print(f"Error: Session '{session_name}' already exists", file=sys.stderr)
                    return ExitCode.SESSION_ERROR
                session_id = create_session(session_id=session_name)
            else:
                # Auto-generate name
                agent_name = get_random_agent_name()
                session_id = create_session(agent_name=agent_name)
            
            print(f"Created session: {session_id}")
            print_session_info(session_id, show_resume_hints=True)
            return ExitCode.SUCCESS
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return ExitCode.SESSION_ERROR


class SessionListCommand(BaseCommand):
    """wolo session list"""
    
    @property
    def name(self) -> str:
        return "session list"
    
    @property
    def description(self) -> str:
        return "List all sessions"
    
    def execute(self, args: ParsedArgs) -> int:
        """Execute list command."""
        from wolo.session import list_sessions
        
        sessions = list_sessions()
        if not sessions:
            print("No saved sessions found")
        else:
            print(f"Wolo sessions:")
            print()
            for s in sessions:
                created = s.get("created_at", 0)
                created_str = datetime.fromtimestamp(created).strftime("%m/%d/%y %H:%M:%S") if created else "Unknown"
                
                session_id = s.get("id", "unknown")
                message_count = s.get("message_count", 0)
                is_running = s.get("is_running", False)
                pid = s.get("pid")
                
                # Status display
                status = "(Running)" if is_running else "(Stopped)"
                pid_str = f" PID:{pid}" if pid and is_running else ""
                
                print(f"  {session_id}{pid_str}")
                print(f"    {created_str}    {status}    ({message_count} messages)")
                print()
            print(f"{len(sessions)} session(s) in ~/.wolo/sessions/")
        return ExitCode.SUCCESS


class SessionShowCommand(BaseCommand):
    """
    wolo session show <id>
    
    Display session information without entering REPL.
    This is a non-blocking command that shows info and exits.
    """
    
    @property
    def name(self) -> str:
        return "session show"
    
    @property
    def description(self) -> str:
        return "Show session details (non-blocking)"
    
    def validate_args(self, args: ParsedArgs) -> tuple[bool, str]:
        """Validate show command arguments."""
        if not args.positional_args:
            return (False, "Error: session show requires a session ID")
        return (True, "")
    
    def execute(self, args: ParsedArgs) -> int:
        """Execute show command."""
        is_valid, error_msg = self.validate_args(args)
        if not is_valid:
            print(error_msg, file=sys.stderr)
            return ExitCode.ERROR
        
        session_id = args.positional_args[0]
        
        from wolo.session import get_session_status
        from wolo.cli.utils import print_session_info
        
        status = get_session_status(session_id)
        if not status.get("exists"):
            print(f"Error: Session '{session_id}' not found", file=sys.stderr)
            return ExitCode.SESSION_ERROR
        
        # Show info with resume hints
        print_session_info(session_id, show_resume_hints=True)
        return ExitCode.SUCCESS


class SessionResumeCommand(BaseCommand):
    """
    wolo session resume <id>
    
    Resume a session in REPL mode for continued conversation.
    This is a blocking command that enters interactive REPL.
    
    If stdin has content (pipe), it becomes the first message.
    """
    
    @property
    def name(self) -> str:
        return "session resume"
    
    @property
    def description(self) -> str:
        return "Resume session in REPL mode (blocking)"
    
    def validate_args(self, args: ParsedArgs) -> tuple[bool, str]:
        """Validate resume command arguments."""
        if not args.positional_args:
            return (False, "Error: session resume requires a session ID")
        return (True, "")
    
    def execute(self, args: ParsedArgs) -> int:
        """
        Execute resume command.
        
        Enters REPL mode with the specified session.
        If pipe input is provided, it becomes the first message.
        """
        is_valid, error_msg = self.validate_args(args)
        if not is_valid:
            print(error_msg, file=sys.stderr)
            return ExitCode.ERROR
        
        session_id = args.positional_args[0]
        
        from wolo.session import get_session_status, load_session, check_and_set_session_pid
        from wolo.cli.utils import print_session_info
        from wolo.modes import ExecutionMode
        
        status = get_session_status(session_id)
        if not status.get("exists"):
            print(f"Error: Session '{session_id}' not found", file=sys.stderr)
            return ExitCode.SESSION_ERROR
        
        # Check if already running
        if status.get("is_running"):
            pid = status.get("pid")
            print(f"Error: Session '{session_id}' is already running (PID: {pid})", file=sys.stderr)
            print(f"       Use 'wolo -w {session_id}' to watch it.", file=sys.stderr)
            return ExitCode.SESSION_ERROR
        
        # Acquire lock
        if not check_and_set_session_pid(session_id):
            print(f"Error: Failed to acquire session lock for: {session_id}", file=sys.stderr)
            return ExitCode.SESSION_ERROR
        
        try:
            # Load session
            load_session(session_id)
            
            # Show session info
            print_session_info(session_id, show_resume_hints=False)
            
            # Get initial message from pipe or remaining args
            initial_message = ""
            if args.pipe_input:
                initial_message = args.pipe_input
            elif len(args.positional_args) > 1:
                initial_message = " ".join(args.positional_args[1:])
            
            # Enter REPL mode
            from wolo.cli.commands.repl import ReplCommand
            
            # Prepare args for REPL
            args.session_options.resume_id = session_id
            args.execution_options.mode = ExecutionMode.REPL
            args.message = initial_message
            
            # Delegate to REPL command with existing session
            return self._run_repl_with_session(args, session_id, initial_message)
            
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return ExitCode.SESSION_ERROR
    
    def _run_repl_with_session(self, args: ParsedArgs, session_id: str, initial_message: str) -> int:
        """Run REPL mode with an existing session."""
        from wolo.cli.execution import run_repl_mode
        from wolo.cli.events import setup_event_handlers
        from wolo.cli.async_utils import safe_async_run
        from wolo.config import Config
        from wolo.agents import get_agent, AGENTS
        from wolo.modes import ModeConfig, QuotaConfig, ExecutionMode
        
        # Setup configuration
        try:
            config = Config.from_env(
                args.execution_options.api_key,
                args.execution_options.endpoint_name
            )
            if args.execution_options.model:
                config.model = args.execution_options.model
            config.debug_llm_file = args.execution_options.debug_llm_file
            config.debug_full_dir = args.execution_options.debug_full_dir
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return ExitCode.CONFIG_ERROR
        
        # Validate agent type
        if args.execution_options.agent_type not in AGENTS:
            print(f"Error: Unknown agent type '{args.execution_options.agent_type}'", file=sys.stderr)
            return ExitCode.CONFIG_ERROR
        
        agent_config = get_agent(args.execution_options.agent_type)
        mode_config = ModeConfig.for_mode(ExecutionMode.REPL)
        quota_config = QuotaConfig(max_steps=args.execution_options.max_steps)
        
        # Setup event handlers
        setup_event_handlers()
        
        # Setup MCP if needed
        async def setup_mcp():
            if config.claude.enabled or config.mcp.enabled:
                try:
                    from wolo.mcp_integration import initialize_mcp
                    await initialize_mcp(config)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Failed to initialize MCP: {e}")
        
        # Run REPL
        async def run_repl():
            await setup_mcp()
            return await run_repl_mode(
                config, session_id, agent_config, mode_config, quota_config,
                initial_message, args.execution_options.save_session,
                args.execution_options.benchmark_mode,
                args.execution_options.benchmark_output
            )
        
        try:
            return safe_async_run(run_repl())
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(safe_async_run, run_repl())
                        return future.result()
                else:
                    from wolo.cli.async_utils import _suppress_mcp_shutdown_errors
                    loop.set_exception_handler(_suppress_mcp_shutdown_errors)
                    return loop.run_until_complete(run_repl())
            except Exception:
                return safe_async_run(run_repl())


class SessionWatchCommand(BaseCommand):
    """wolo session watch <id>"""
    
    @property
    def name(self) -> str:
        return "session watch"
    
    @property
    def description(self) -> str:
        return "Watch a running session (read-only)"
    
    def validate_args(self, args: ParsedArgs) -> tuple[bool, str]:
        """Validate watch command arguments."""
        if not args.positional_args and not args.session_options.watch_id:
            return (False, "Error: session watch requires a session ID")
        return (True, "")
    
    def execute(self, args: ParsedArgs) -> int:
        """Execute watch command."""
        # Get session ID from positional args or watch_id option
        session_id = args.positional_args[0] if args.positional_args else args.session_options.watch_id
        if not session_id:
            print("Error: session watch requires a session ID", file=sys.stderr)
            return ExitCode.ERROR
        
        # Import watch mode function
        from wolo.cli.execution import run_watch_mode
        from wolo.cli.async_utils import safe_async_run, _suppress_mcp_shutdown_errors
        
        # Run watch mode
        try:
            return safe_async_run(run_watch_mode(session_id))
        except RuntimeError:
            # Event loop already running
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(safe_async_run, run_watch_mode(session_id))
                        return future.result()
                else:
                    loop.set_exception_handler(_suppress_mcp_shutdown_errors)
                    return loop.run_until_complete(run_watch_mode(session_id))
            except Exception:
                # Fallback: use safe_async_run which creates a new loop
                return safe_async_run(run_watch_mode(session_id))


class SessionDeleteCommand(BaseCommand):
    """wolo session delete <id>"""
    
    @property
    def name(self) -> str:
        return "session delete"
    
    @property
    def description(self) -> str:
        return "Delete a session"
    
    def validate_args(self, args: ParsedArgs) -> tuple[bool, str]:
        """Validate delete command arguments."""
        if not args.positional_args:
            return (False, "Error: session delete requires a session ID")
        return (True, "")
    
    def execute(self, args: ParsedArgs) -> int:
        """Execute delete command."""
        is_valid, error_msg = self.validate_args(args)
        if not is_valid:
            print(error_msg, file=sys.stderr)
            return ExitCode.ERROR
        
        session_id = args.positional_args[0]
        
        from wolo.session import delete_session, get_session_status
        
        # Check if session exists
        status = get_session_status(session_id)
        if not status.get("exists"):
            print(f"Error: Session '{session_id}' not found", file=sys.stderr)
            return ExitCode.SESSION_ERROR
        
        # Check if running
        if status.get("is_running"):
            pid = status.get("pid")
            print(f"Error: Session '{session_id}' is currently running (PID: {pid})", file=sys.stderr)
            print(f"       Stop the session before deleting it.", file=sys.stderr)
            return ExitCode.SESSION_ERROR
        
        try:
            delete_session(session_id)
            print(f"Deleted session: {session_id}")
            return ExitCode.SUCCESS
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return ExitCode.ERROR


class SessionCleanCommand(BaseCommand):
    """wolo session clean [days]"""
    
    @property
    def name(self) -> str:
        return "session clean"
    
    @property
    def description(self) -> str:
        return "Clean old sessions"
    
    def validate_args(self, args: ParsedArgs) -> tuple[bool, str]:
        """Validate clean command arguments."""
        # Optional days parameter
        if args.positional_args:
            try:
                days = int(args.positional_args[0])
                if days < 0:
                    return (False, "Error: days must be non-negative")
            except ValueError:
                return (False, "Error: days must be a number")
        return (True, "")
    
    def execute(self, args: ParsedArgs) -> int:
        """Execute clean command."""
        is_valid, error_msg = self.validate_args(args)
        if not is_valid:
            print(error_msg, file=sys.stderr)
            return ExitCode.ERROR
        
        days = 30  # Default
        if args.positional_args:
            try:
                days = int(args.positional_args[0])
            except ValueError:
                print(f"Error: Invalid days value: {args.positional_args[0]}", file=sys.stderr)
                return ExitCode.ERROR
        
        from wolo.session import list_sessions, delete_session, get_session_status
        
        cutoff_time = (datetime.now() - timedelta(days=days)).timestamp()
        sessions = list_sessions()
        
        deleted_count = 0
        for s in sessions:
            session_id = s.get("id")
            created = s.get("created_at", 0)
            
            # Skip if running
            status = get_session_status(session_id)
            if status.get("is_running"):
                continue
            
            # Delete if older than cutoff
            if created < cutoff_time:
                try:
                    delete_session(session_id)
                    deleted_count += 1
                except Exception:
                    pass  # Continue on error
        
        print(f"Cleaned {deleted_count} session(s) older than {days} days")
        return ExitCode.SUCCESS
