"""
Execution functions for running tasks, REPL, and watch modes.

Minimal output style - no banners, no echoing, natural language tool calls.
"""

import asyncio
import json
import logging
from pathlib import Path

from wolo.agent import agent_loop
from wolo.cli.events import set_watch_server
from wolo.cli.exit_codes import ExitCode
from wolo.cli.output import (
    print_repl_prompt,
    print_tool_complete,
)
from wolo.config import Config
from wolo.control import get_manager, remove_manager
from wolo.llm_adapter import WoloLLMClient
from wolo.metrics import MetricsCollector, generate_report
from wolo.modes import ModeConfig, QuotaConfig
from wolo.session import (
    add_user_message,
    get_or_create_agent_display_name,
    save_session,
)

logger = logging.getLogger(__name__)


async def run_single_task_mode(
    config: Config,
    session_id: str,
    agent_config,
    mode_config: ModeConfig,
    quota_config: QuotaConfig,
    message_text: str,
    save_session_flag: bool,
    benchmark_mode: bool,
    benchmark_output: str,
    question_handler,
) -> int:
    """Run a single task in SOLO or COOP mode."""

    # Create control manager
    control = get_manager(session_id)

    # Add user message (silently, no echo)
    add_user_message(session_id, message_text)

    # Start control
    control.start_running()

    # Determine excluded tools based on mode
    excluded_tools = set()
    if not mode_config.enable_question_tool:
        excluded_tools.add("question")

    # Setup watch server
    try:
        from wolo.watch_server import start_watch_server

        watch_server = await start_watch_server(session_id)
        set_watch_server(session_id, watch_server)
    except Exception as e:
        logger.warning(f"Failed to start watch server: {e}")
        set_watch_server(None, None)

    # Run agent loop
    try:
        agent_display_name = get_or_create_agent_display_name(session_id)
        result = await agent_loop(
            config,
            session_id,
            agent_config,
            control,
            excluded_tools=excluded_tools,
            max_steps=quota_config.max_steps,
            agent_display_name=agent_display_name,
            is_repl_mode=False,
        )
        logger.info(f"Agent loop completed. Finish reason: {result.finish_reason}")

        # Save session if requested
        if save_session_flag:
            save_session(session_id)
            print(f"\nSession saved: {session_id}")
            logger.info(f"Session saved: {session_id}")

        # Export benchmark results if in benchmark mode
        if benchmark_mode:
            collector = MetricsCollector()
            session_metrics = collector.export_session(session_id)
            if session_metrics:
                session_metrics["name"] = message_text[:50] + (
                    "..." if len(message_text) > 50 else ""
                )
                results = [session_metrics]

                with open(benchmark_output, "w") as f:
                    json.dump(results, f, indent=2, default=str)
                print(f"Benchmark results saved to: {benchmark_output}")
                print(generate_report(results))

        return ExitCode.SUCCESS
    except KeyboardInterrupt:
        print("\nInterrupted. Saving session...")
        save_session(session_id)
        print(f"Session saved: {session_id}")
        print(f'Resume with: wolo -r {session_id} "your prompt"')
        return ExitCode.INTERRUPTED
    except Exception as e:
        print(f"\nError: {e}")
        logger.exception("Agent loop failed")
        try:
            save_session(session_id)
            print(f"Session saved: {session_id}")
        except Exception:
            pass

        if benchmark_mode:
            collector = MetricsCollector()
            session_metrics = collector.export_session(session_id)
            if session_metrics:
                session_metrics["name"] = message_text[:50] + (
                    "..." if len(message_text) > 50 else ""
                )
                results = [session_metrics]
                with open(benchmark_output, "w") as f:
                    json.dump(results, f, indent=2, default=str)
                print(f"Benchmark results (with error) saved to: {benchmark_output}")

        return ExitCode.ERROR
    finally:
        # Only show session ID for non-SOLO modes when interrupted or saved
        # (already printed above in those cases)

        # Cleanup
        control.finish()
        remove_manager(session_id)

        # Clear PID
        from wolo.session import clear_session_pid

        try:
            clear_session_pid(session_id)
        except Exception as e:
            logger.warning(f"Failed to clear PID for session {session_id}: {e}")

        # Stop watch server
        try:
            from wolo.watch_server import stop_watch_server

            await stop_watch_server(session_id)
        except Exception as e:
            logger.warning(f"Failed to stop watch server: {e}")
        set_watch_server(None, None)

        # Close HTTP connections
        await WoloLLMClient.close_all_sessions()

        # Shutdown MCP integration
        try:
            from wolo.mcp_integration import shutdown_mcp

            await shutdown_mcp()
        except Exception:
            pass


async def run_repl_mode(
    config: Config,
    session_id: str,
    agent_config,
    mode_config: ModeConfig,
    quota_config: QuotaConfig,
    initial_message: str,
    save_session_flag: bool,
    benchmark_mode: bool,
    benchmark_output: str,
) -> int:
    """Run REPL mode: continuous conversation loop."""
    # Create control manager
    control = get_manager(session_id)

    try:
        # Setup watch server
        try:
            from wolo.watch_server import start_watch_server

            watch_server = await start_watch_server(session_id)
            set_watch_server(session_id, watch_server)
        except Exception as e:
            logger.warning(f"Failed to start watch server: {e}")
            set_watch_server(None, None)

        # REPL loop
        current_message = initial_message
        task_count = 0

        while True:
            # Wait for input if no initial message or after task completion
            if not current_message:
                print_repl_prompt()
                try:
                    user_input = input()
                    if not user_input.strip():
                        # Empty input = exit
                        print("Goodbye!")
                        break
                    current_message = user_input
                except (KeyboardInterrupt, EOFError):
                    print("\nGoodbye!")
                    break

            # Handle slash commands
            if current_message.startswith("/"):
                from wolo.cli.slash import handle_slash_command

                slash_result = await handle_slash_command(
                    session_id, current_message, config, agent_config
                )
                if slash_result.handled:
                    if slash_result.output:
                        print(slash_result.output)
                    if slash_result.inject_as_user_message:
                        current_message = slash_result.inject_as_user_message
                    else:
                        current_message = None
                        continue

            # Add user message (silently, no echo)
            add_user_message(session_id, current_message)
            task_count += 1

            # Start control
            control.start_running()

            # Run agent loop (AI output flows naturally)
            try:
                agent_display_name = get_or_create_agent_display_name(session_id)
                result = await agent_loop(
                    config,
                    session_id,
                    agent_config,
                    control,
                    excluded_tools=set(),
                    max_steps=quota_config.max_steps,
                    agent_display_name=agent_display_name,
                    is_repl_mode=True,
                )
                logger.info(f"Task {task_count} completed. Finish reason: {result.finish_reason}")

                # Save session after each task
                if save_session_flag:
                    save_session(session_id)
                    logger.info(f"Session saved: {session_id}")

                # Reset for next task
                current_message = None
                control.reset()

            except KeyboardInterrupt:
                print("\nInterrupted.")
                if save_session_flag:
                    save_session(session_id)
                    print(f"Session saved: {session_id}")
                break
            except Exception as e:
                print(f"\nError: {e}")
                logger.exception("Agent loop failed")
                current_message = None
                control.reset()

        # Show session ID on normal REPL exit
        print(f"Session: {session_id}")
        return ExitCode.SUCCESS

    finally:
        # Cleanup
        control.finish()
        remove_manager(session_id)

        # Clear PID
        from wolo.session import clear_session_pid

        try:
            clear_session_pid(session_id)
        except Exception as e:
            logger.warning(f"Failed to clear PID for session {session_id}: {e}")

        # Stop watch server
        try:
            from wolo.watch_server import stop_watch_server

            await stop_watch_server(session_id)
        except Exception as e:
            logger.warning(f"Failed to stop watch server: {e}")
        set_watch_server(None, None)

        # Close HTTP connections
        await WoloLLMClient.close_all_sessions()

        # Shutdown MCP integration
        try:
            from wolo.mcp_integration import shutdown_mcp

            await shutdown_mcp()
        except Exception:
            pass


async def run_watch_mode(session_id: str) -> int:
    """
    Watch mode: connect to watch server, display session output in real-time.
    Read-only mode - doesn't modify any session state.
    """
    from wolo.session import get_session_status

    # Check session status
    status = get_session_status(session_id)
    if not status.get("exists"):
        print(f"Error: Session '{session_id}' not found.")
        return ExitCode.SESSION_ERROR

    is_running = status.get("is_running", False)
    watch_server_available = status.get("watch_server_available", False)
    pid = status.get("pid")

    if not is_running:
        print(f"Error: Session '{session_id}' is not running.")
        print("       Make sure the session is started first.")
        return ExitCode.SESSION_ERROR

    if not watch_server_available:
        print(
            f"Error: Session '{session_id}' is running (PID: {pid}) but watch server is not available."
        )
        print("       Try resuming the session to restart the watch server.")
        return ExitCode.SESSION_ERROR

    # Get socket path
    socket_path = Path.home() / ".wolo" / "sessions" / session_id / "watch.sock"

    # Show minimal info
    print(f"Watching session: {session_id}")
    print("Press Ctrl+C to stop.\n")

    try:
        # Connect to Unix Domain Socket
        reader, writer = await asyncio.open_unix_connection(str(socket_path))

        # Read event stream
        while True:
            try:
                line_bytes = await asyncio.wait_for(reader.readline(), timeout=1.0)
                if not line_bytes:
                    print("\nDisconnected.")
                    break

                # Parse JSON
                try:
                    event = json.loads(line_bytes.decode("utf-8"))
                except json.JSONDecodeError:
                    continue

                # Handle events with natural output style
                event_type = event.get("type")

                if event_type == "connected":
                    continue
                elif event_type == "text-delta":
                    text = event.get("text", "")
                    print(text, end="", flush=True)
                elif event_type == "tool-start":
                    # Tool start is handled in tool-complete now
                    pass
                elif event_type == "tool-complete":
                    tool = event.get("tool", "")
                    status = event.get("status", "unknown")
                    duration = event.get("duration", 0)
                    brief = event.get("brief", "")
                    output = event.get("output", "")
                    metadata = event.get("metadata", {})
                    print_tool_complete(tool, status, duration, brief, output, metadata)
                elif event_type == "finish":
                    print()  # Final newline

            except TimeoutError:
                continue
            except KeyboardInterrupt:
                print("\n\nStopped watching.")
                break

        return ExitCode.SUCCESS

    except FileNotFoundError:
        print(f"Error: Watch server socket not found for session '{session_id}'.")
        return ExitCode.SESSION_ERROR
    except ConnectionRefusedError:
        print(f"Error: Cannot connect to watch server for session '{session_id}'.")
        return ExitCode.SESSION_ERROR
    except Exception as e:
        print(f"Error: {e}")
        logger.exception("Watch mode failed")
        return ExitCode.ERROR
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
