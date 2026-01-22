"""
REPL command for Wolo CLI.

Starts an interactive conversation session.
Can be invoked as 'wolo chat' or 'wolo repl' (synonyms).
"""

import sys
import asyncio

from wolo.cli.commands.base import BaseCommand
from wolo.cli.parser import ParsedArgs
from wolo.cli.utils import get_message_from_sources
from wolo.cli.exit_codes import ExitCode


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
        # Get initial message if provided
        message, _ = get_message_from_sources(args)
        
        # Import execution function from execution module
        from wolo.cli.execution import run_repl_mode
        from wolo.cli.events import setup_event_handlers
        
        # Prepare all arguments for the execution function
        from wolo.config import Config
        from wolo.agents import get_agent, AGENTS
        from wolo.modes import ModeConfig, QuotaConfig
        from wolo.session import create_session
        from wolo.agent_names import get_random_agent_name
        
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
            
            if args.execution_options.debug_full_dir:
                import os
                os.makedirs(args.execution_options.debug_full_dir, exist_ok=True)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return ExitCode.CONFIG_ERROR
        
        # Validate agent type
        if args.execution_options.agent_type not in AGENTS:
            print(f"Error: Unknown agent type '{args.execution_options.agent_type}'. Available: {', '.join(AGENTS.keys())}", file=sys.stderr)
            return ExitCode.CONFIG_ERROR
        
        agent_config = get_agent(args.execution_options.agent_type)
        
        # REPL mode is always REPL, regardless of what was parsed
        from wolo.modes import ExecutionMode
        mode_config = ModeConfig.for_mode(ExecutionMode.REPL)
        quota_config = QuotaConfig(max_steps=args.execution_options.max_steps)
        
        # Create session
        agent_name = get_random_agent_name()
        session_id = create_session(agent_name=agent_name)
        from wolo.session import check_and_set_session_pid
        check_and_set_session_pid(session_id)
        
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
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to initialize MCP: {e}")
        
        # Run REPL
        async def run_repl():
            await setup_mcp()
            return await run_repl_mode(
                config, session_id, agent_config, mode_config, quota_config,
                message, args.execution_options.save_session,
                args.execution_options.benchmark_mode,
                args.execution_options.benchmark_output
            )
        
        from wolo.cli.async_utils import safe_async_run, _suppress_mcp_shutdown_errors
        
        try:
            return safe_async_run(run_repl())
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
            except Exception:
                # Fallback: use safe_async_run which creates a new loop
                return safe_async_run(run_repl())
