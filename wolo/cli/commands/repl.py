"""
REPL command for Wolo CLI.

Starts an interactive conversation session.
Can be invoked as:
- 'wolo chat' or 'wolo --repl' (new session)
- 'wolo -r <id>' or 'wolo session resume <id>' (resume session)
"""

import asyncio
import sys

from wolo.cli.commands.base import BaseCommand
from wolo.cli.exit_codes import ExitCode
from wolo.cli.parser import ParsedArgs
from wolo.cli.utils import get_message_from_sources, handle_keyboard_interrupt


class ReplCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "repl"

    @property
    def description(self) -> str:
        return "REPL mode: continuous conversation"

    def validate_args(self, args: ParsedArgs) -> tuple[bool, str]:
        """Validate repl command arguments."""
        # REPL doesn't require message (can start empty)
        return (True, "")

    def execute(self, args: ParsedArgs) -> int:
        """Execute repl command."""
        # Check for first run
        from wolo.config import Config

        if Config.is_first_run():
            from wolo.cli.utils import show_first_run_message

            show_first_run_message()

        # Get initial message if provided
        message, _ = get_message_from_sources(args)

        # Import execution function from execution module
        from wolo.agent_names import get_random_agent_name
        from wolo.agents import AGENTS, get_agent
        from wolo.cli.events import setup_event_handlers
        from wolo.cli.execution import run_repl_mode

        # Prepare all arguments for the execution function
        from wolo.config import Config
        from wolo.modes import ModeConfig, QuotaConfig
        from wolo.session import create_session

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

        # REPL mode is always REPL, regardless of what was parsed
        from wolo.modes import ExecutionMode

        mode_config = ModeConfig.for_mode(ExecutionMode.REPL)
        quota_config = QuotaConfig(max_steps=args.execution_options.max_steps)

        # Handle session: resume existing or create new
        from wolo.session import (
            check_and_set_session_pid,
            get_session_status,
            load_session,
        )

        workdir = args.execution_options.workdir  # May be None (defaults to cwd)
        workdir_to_use = None  # Will be set below

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
                    f"Error: Session '{resume_id}' is already running (PID: {pid})",
                    file=sys.stderr,
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
        else:
            # Create new session
            agent_name = get_random_agent_name()

            # Change to working directory
            workdir_to_use = None
            if workdir:
                import os

                workdir_to_use = os.path.abspath(workdir)
                try:
                    os.chdir(workdir_to_use)
                except OSError as e:
                    print(
                        f"Error: Cannot change to working directory '{workdir_to_use}': {e}",
                        file=sys.stderr,
                    )
                    return ExitCode.ERROR

            session_id = create_session(agent_name=agent_name, workdir=workdir)
            check_and_set_session_pid(session_id)

        # For resume case, get workdir_to_use from session or CLI
        if args.session_options.resume_id:
            workdir_to_use = workdir
            if workdir_to_use:
                import os

                workdir_to_use = os.path.abspath(workdir_to_use)
                try:
                    os.chdir(workdir_to_use)
                except OSError as e:
                    print(
                        f"Error: Cannot change to working directory '{workdir_to_use}': {e}",
                        file=sys.stderr,
                    )
                    return ExitCode.ERROR

        # Setup output configuration and event handlers
        from wolo.cli.output import OutputConfig

        output_config = OutputConfig.from_args_and_config(
            output_style=args.execution_options.output_style,
            no_color=args.execution_options.no_color,
            show_reasoning=args.execution_options.show_reasoning,
            json_output=args.execution_options.json_output,
            config_data=Config._load_config_file(),
        )
        setup_event_handlers(output_config)

        # Print session info banner (unless --no-banner)
        if not args.execution_options.no_banner:
            from wolo.cli.utils import print_session_info

            print_session_info(session_id, show_resume_hints=False, output_config=output_config)

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

        # Run REPL
        async def run_repl():
            await setup_mcp()
            return await run_repl_mode(
                config,
                session_id,
                agent_config,
                mode_config,
                quota_config,
                message,
                args.execution_options.save_session,
                args.execution_options.benchmark_mode,
                args.execution_options.benchmark_output,
                output_config,  # Pass output_config for minimal mode check
            )

        from wolo.cli.async_utils import _suppress_mcp_shutdown_errors, safe_async_run

        try:
            return safe_async_run(run_repl())
        except KeyboardInterrupt:
            return handle_keyboard_interrupt(session_id)
        except RuntimeError:
            # Event loop already running
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(safe_async_run, run_repl())
                        return future.result()
                else:
                    loop.set_exception_handler(_suppress_mcp_shutdown_errors)
                    return loop.run_until_complete(run_repl())
            except KeyboardInterrupt:
                return handle_keyboard_interrupt(session_id)
            except Exception:
                # Fallback: use safe_async_run which creates a new loop
                try:
                    return safe_async_run(run_repl())
                except KeyboardInterrupt:
                    return handle_keyboard_interrupt(session_id)
