"""
Run command for Wolo CLI.

Executes a task with the AI agent in SOLO or COOP mode.
This is the default command when a prompt is provided.
"""

import asyncio

from wolo.cli.async_utils import safe_async_run
from wolo.cli.commands.base import BaseCommand
from wolo.cli.exit_codes import ExitCode
from wolo.cli.parser import ParsedArgs
from wolo.cli.path_guard import initialize_path_guard_for_session
from wolo.cli.utils import (
    get_message_from_sources,
    handle_keyboard_interrupt,
    print_error,
    print_warning,
)
from wolo.modes import ExecutionMode


class RunCommand(BaseCommand):
    """
    Execute a task with the AI agent.

    Usage:
        wolo "your prompt"
        wolo --coop "your prompt"
        cat file | wolo "process this"
        wolo -r <session_id> "continue"
    """

    @property
    def name(self) -> str:
        return "run"

    @property
    def description(self) -> str:
        return "Execute a task (default behavior)"

    def validate_args(self, args: ParsedArgs) -> tuple[bool, str]:
        """Validate run command arguments."""
        # -w should not be here (handled by router)
        if args.session_options.watch_id:
            return (
                False,
                "Error: -w/--watch is a standalone command. Use 'wolo -w <id>' or 'wolo session watch <id>'",
            )

        # Need message for non-REPL execution (SOLO/COOP modes)
        if args.execution_options.mode != ExecutionMode.REPL:
            message, has_message = get_message_from_sources(args)
            if not has_message:
                if args.session_options.resume_id:
                    current_mode = args.execution_options.mode.value
                    return (
                        False,
                        f"Error: -r/--resume with {current_mode} mode requires a prompt.\n"
                        f"       Use 'wolo -r {args.session_options.resume_id} --repl' for REPL mode (no prompt needed).\n"
                        f"       Or:  'wolo -r {args.session_options.resume_id} \"your prompt\"' to continue.",
                    )
                return (
                    False,
                    "Error: A prompt is required. Use 'wolo \"your prompt\"' or 'cat file | wolo'",
                )

        return (True, "")

    def execute(self, args: ParsedArgs) -> int:
        """Execute run command."""
        # Validation
        is_valid, error_msg = self.validate_args(args)
        if not is_valid:
            print_error(error_msg)
            return ExitCode.ERROR

        # Check for first run
        from wolo.config import Config

        if Config.is_first_run():
            from wolo.cli.utils import show_first_run_message

            show_first_run_message()

        # Get message
        message, _ = get_message_from_sources(args)

        # Import execution function from execution module
        from wolo.agents import AGENTS, get_agent
        from wolo.cli.events import setup_event_handlers
        from wolo.cli.execution import run_single_task_mode
        from wolo.config import Config
        from wolo.modes import ModeConfig, QuotaConfig
        from wolo.session import (
            check_and_set_session_pid,
            create_session,
            get_session_status,
            load_session,
            update_session_mode,
        )

        # Setup configuration
        try:
            config = Config.from_env(
                api_key=args.execution_options.api_key,
                base_url=args.execution_options.base_url,
                model=args.execution_options.model,
            )
            # Set session storage to use config's sessions_dir (project-local or home)
            from wolo.session import set_storage_base_dir

            set_storage_base_dir(config.sessions_dir)

            solo_mode = args.execution_options.mode == ExecutionMode.SOLO
            if solo_mode and not args.execution_options.wild_mode_explicit:
                config.path_safety.wild_mode = True
            elif args.execution_options.wild_mode:
                config.path_safety.wild_mode = True
            config.debug_llm_file = args.execution_options.debug_llm_file
            config.debug_full_dir = args.execution_options.debug_full_dir

            if args.execution_options.debug_full_dir:
                import os

                os.makedirs(args.execution_options.debug_full_dir, exist_ok=True)
        except ValueError as e:
            print_error(str(e))
            return ExitCode.CONFIG_ERROR

        # Validate agent type
        if args.execution_options.agent_type not in AGENTS:
            print_error(
                f"Unknown agent type '{args.execution_options.agent_type}'. Available: {', '.join(AGENTS.keys())}"
            )
            return ExitCode.CONFIG_ERROR

        agent_config = get_agent(args.execution_options.agent_type)
        mode_config = ModeConfig.for_mode(args.execution_options.mode)
        quota_config = QuotaConfig(max_steps=args.execution_options.max_steps)

        # Create or resume session
        if args.session_options.resume_id:
            resume_id = args.session_options.resume_id
            status = get_session_status(resume_id)
            if not status.get("exists"):
                workdir = args.execution_options.workdir
                session_id = create_session(session_id=resume_id, workdir=workdir)
                check_and_set_session_pid(session_id)
            else:
                if status.get("is_running"):
                    pid = status.get("pid")
                    print_error(f"Session '{resume_id}' is already running (PID: {pid})")
                    return ExitCode.SESSION_ERROR

                if not check_and_set_session_pid(resume_id):
                    print_error(f"Failed to acquire session lock for: {resume_id}")
                    return ExitCode.SESSION_ERROR

                try:
                    load_session(resume_id)
                    session_id = resume_id
                except (FileNotFoundError, ValueError) as e:
                    print_error(str(e))
                    return ExitCode.SESSION_ERROR

                # Check workdir match
                from wolo.cli.utils import check_workdir_match, print_workdir_warning

                matches, session_workdir, current_workdir = check_workdir_match(session_id)
                if not matches and session_workdir:
                    print_workdir_warning(session_workdir, current_workdir)

        elif args.session_options.session_name is not None:
            session_name = args.session_options.session_name
            workdir = args.execution_options.workdir
            if session_name == "":
                session_id = create_session(workdir=workdir)
            else:
                session_id = create_session(session_id=session_name, workdir=workdir)
            check_and_set_session_pid(session_id)
        else:
            workdir = args.execution_options.workdir
            session_id = create_session(workdir=workdir)
            check_and_set_session_pid(session_id)

        # Change to working directory
        workdir_to_use = None
        if args.execution_options.workdir:
            import os

            workdir_to_use = os.path.abspath(args.execution_options.workdir)
            try:
                os.chdir(workdir_to_use)
            except OSError as e:
                print_error(f"Cannot change to working directory '{workdir_to_use}': {e}")
                return ExitCode.ERROR

        # PathGuard must be initialized before any file write/edit tools run.
        initialize_path_guard_for_session(
            config=config,
            session_id=session_id,
            workdir=workdir_to_use,
            cli_paths=args.execution_options.allow_paths,
        )

        # Load long-term memories if requested (-M/--load-ltm)
        if args.execution_options.load_ltm:
            from wolo.tools_pkg.memory import load_memories_for_session

            ltm_context = load_memories_for_session(args.execution_options.load_ltm)
            if ltm_context:
                message = f"{ltm_context}\n\n{message}"
            else:
                not_found = ", ".join(args.execution_options.load_ltm)
                print_warning(f"No long-term memories found for: {not_found}")

        # Setup event handlers
        setup_event_handlers()

        # Setup MCP if needed
        async def setup_mcp():
            if config.claude.enabled or config.mcp.enabled:
                try:
                    from wolo.mcp_integration import get_mcp_status, initialize_mcp

                    get_mcp_status()
                    await initialize_mcp(config)
                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to initialize MCP: {e}")

        # Run the task
        async def run_task():
            await setup_mcp()
            return await run_single_task_mode(
                config,
                session_id,
                agent_config,
                mode_config,
                quota_config,
                message,
                args.execution_options.save_session,
                args.execution_options.benchmark_mode,
                args.execution_options.benchmark_output,
                None,  # question_handler (simplified - no question tool support)
            )

        try:
            result = safe_async_run(run_task())
            if result == ExitCode.SUCCESS:
                update_session_mode(session_id, args.execution_options.mode.value)
            return result
        except KeyboardInterrupt:
            return handle_keyboard_interrupt(session_id)
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(safe_async_run, run_task())
                        result = future.result()
                        if result == ExitCode.SUCCESS:
                            update_session_mode(session_id, args.execution_options.mode.value)
                        return result
                else:
                    from wolo.cli.async_utils import _suppress_mcp_shutdown_errors

                    loop.set_exception_handler(_suppress_mcp_shutdown_errors)
                    result = loop.run_until_complete(run_task())
                    if result == ExitCode.SUCCESS:
                        update_session_mode(session_id, args.execution_options.mode.value)
                    return result
            except KeyboardInterrupt:
                return handle_keyboard_interrupt(session_id)
            except Exception:
                try:
                    result = safe_async_run(run_task())
                    if result == ExitCode.SUCCESS:
                        update_session_mode(session_id, args.execution_options.mode.value)
                    return result
                except KeyboardInterrupt:
                    return handle_keyboard_interrupt(session_id)
