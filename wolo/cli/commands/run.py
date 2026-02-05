"""
Run command for Wolo CLI.

Executes a task with the AI agent in SOLO or COOP mode.
This is the default command when a prompt is provided.
"""

import asyncio
import sys

from wolo.cli.async_utils import safe_async_run
from wolo.cli.commands.base import BaseCommand
from wolo.cli.exit_codes import ExitCode
from wolo.cli.parser import ParsedArgs
from wolo.cli.utils import get_message_from_sources, handle_keyboard_interrupt
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
        """
        Validate run command arguments.

        Rules:
            1. -r/--resume with --solo requires a prompt (one-shot execution)
            2. -w/--watch should be handled by router, not here
            3. Non-REPL execution requires a message
        """
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
                    return (
                        False,
                        f"Error: -r/--resume with --solo requires a prompt.\n"
                        f"       Use 'wolo -r {args.session_options.resume_id}' for REPL mode (no prompt needed).\n"
                        f"       Or:  'wolo -r {args.session_options.resume_id} --solo \"your prompt\"' for one-shot.",
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
            print(error_msg, file=sys.stderr)
            return ExitCode.ERROR

        # Check for first run
        from wolo.config import Config

        if Config.is_first_run():
            from wolo.cli.utils import show_first_run_message

            show_first_run_message()

        # Get message
        message, _ = get_message_from_sources(args)

        # Import execution function from execution module
        from wolo.agent_names import get_random_agent_name
        from wolo.agents import AGENTS, get_agent
        from wolo.cli.events import setup_event_handlers
        from wolo.cli.execution import run_single_task_mode
        from wolo.cli.utils import print_session_info

        # Prepare all arguments for the execution function
        from wolo.config import Config
        from wolo.modes import ModeConfig, QuotaConfig
        from wolo.question_ui import setup_question_handler
        from wolo.session import (
            check_and_set_session_pid,
            create_session,
            get_session_status,
            load_session,
        )

        # Setup configuration
        try:
            config = Config.from_env(
                api_key=args.execution_options.api_key,
                base_url=args.execution_options.base_url,
                model=args.execution_options.model,
            )
            config.debug_llm_file = args.execution_options.debug_llm_file
            config.debug_full_dir = args.execution_options.debug_full_dir

            if args.execution_options.debug_full_dir:
                import os

                os.makedirs(args.execution_options.debug_full_dir, exist_ok=True)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return ExitCode.CONFIG_ERROR

        # Validate agent type
        if args.execution_options.agent_type not in AGENTS:
            print(
                f"Error: Unknown agent type '{args.execution_options.agent_type}'. Available: {', '.join(AGENTS.keys())}",
                file=sys.stderr,
            )
            return ExitCode.CONFIG_ERROR

        agent_config = get_agent(args.execution_options.agent_type)
        mode_config = ModeConfig.for_mode(args.execution_options.mode)
        quota_config = QuotaConfig(max_steps=args.execution_options.max_steps)

        # Setup question handler if needed (only for COOP mode)
        question_handler = None
        if mode_config.enable_question_tool:
            question_handler = setup_question_handler()

        # Create or resume session
        if args.session_options.resume_id:
            # Resume existing session
            resume_id = args.session_options.resume_id
            status = get_session_status(resume_id)
            if not status.get("exists"):
                print(f"Error: Session not found: {resume_id}", file=sys.stderr)
                return ExitCode.SESSION_ERROR

            if status.get("is_running"):
                pid = status.get("pid")
                print(
                    f"Error: Session '{resume_id}' is already running (PID: {pid})", file=sys.stderr
                )
                print(f"       Use 'wolo -w {resume_id}' to watch it.", file=sys.stderr)
                return ExitCode.SESSION_ERROR

            if not check_and_set_session_pid(resume_id):
                print(f"Error: Failed to acquire session lock for: {resume_id}", file=sys.stderr)
                return ExitCode.SESSION_ERROR

            try:
                load_session(resume_id)
                session_id = resume_id
            except (FileNotFoundError, ValueError) as e:
                print(f"Error: {e}", file=sys.stderr)
                return ExitCode.SESSION_ERROR

            # Check workdir match (warning only, don't block)
            from wolo.cli.utils import check_workdir_match, print_workdir_warning

            matches, session_workdir, current_workdir = check_workdir_match(session_id)
            if not matches and session_workdir:
                print_workdir_warning(session_workdir, current_workdir)

        elif args.session_options.session_name is not None:
            # Create named session
            session_name = args.session_options.session_name
            workdir = args.execution_options.workdir  # May be None (defaults to cwd)
            if session_name == "":
                # Auto-generate name
                agent_name = get_random_agent_name()
                session_id = create_session(agent_name=agent_name, workdir=workdir)
            else:
                session_id = create_session(session_id=session_name, workdir=workdir)
            check_and_set_session_pid(session_id)
        else:
            # Auto-generate session
            agent_name = get_random_agent_name()
            workdir = args.execution_options.workdir  # May be None (defaults to cwd)
            session_id = create_session(agent_name=agent_name, workdir=workdir)
            check_and_set_session_pid(session_id)

        # Change to working directory
        # This ensures the working directory is the highest priority path
        workdir_to_use = None
        if args.execution_options.workdir:
            import os

            workdir_to_use = os.path.abspath(args.execution_options.workdir)
            try:
                os.chdir(workdir_to_use)
            except OSError as e:
                print(
                    f"Error: Cannot change to working directory '{workdir_to_use}': {e}",
                    file=sys.stderr,
                )
                return ExitCode.ERROR

        # Setup output configuration first (needed for print_session_info)
        from wolo.cli.output import OutputConfig

        output_config = OutputConfig.from_args_and_config(
            output_style=args.execution_options.output_style,
            no_color=args.execution_options.no_color,
            show_reasoning=args.execution_options.show_reasoning,
            json_output=args.execution_options.json_output,
            config_data=Config._load_config_file(),
        )

        # Print session info banner (unless --no-banner)
        if not args.execution_options.no_banner:
            print_session_info(session_id, show_resume_hints=False, output_config=output_config)

        # Setup event handlers
        setup_event_handlers(output_config)

        # Setup MCP if needed
        async def setup_mcp():
            if config.claude.enabled or config.mcp.enabled:
                try:
                    from wolo.mcp_integration import initialize_mcp

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
                question_handler,
                output_config,  # Pass output_config for minimal mode check
            )

        try:
            return safe_async_run(run_task())
        except KeyboardInterrupt:
            return handle_keyboard_interrupt(session_id)
        except RuntimeError:
            # Event loop already running, try to get it
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Can't use asyncio.run, need to create task
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(safe_async_run, run_task())
                        return future.result()
                else:
                    # Set exception handler for existing loop
                    from wolo.cli.async_utils import _suppress_mcp_shutdown_errors

                    loop.set_exception_handler(_suppress_mcp_shutdown_errors)
                    return loop.run_until_complete(run_task())
            except KeyboardInterrupt:
                return handle_keyboard_interrupt(session_id)
            except Exception:
                # Fallback: use safe_async_run which creates a new loop
                try:
                    return safe_async_run(run_task())
                except KeyboardInterrupt:
                    return handle_keyboard_interrupt(session_id)
