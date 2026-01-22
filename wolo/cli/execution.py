"""Execution functions for running tasks, REPL, and watch modes."""

import asyncio
import json
import logging

from wolo.agent import agent_loop
from wolo.agents import get_agent
from wolo.config import Config
from wolo.control import get_manager, remove_manager
from wolo.llm import GLMClient
from wolo.metrics import MetricsCollector, generate_report
from wolo.modes import ModeConfig, QuotaConfig
from wolo.session import (
    add_user_message,
    save_session,
)
from wolo.ui import create_ui
from wolo.cli.events import set_watch_server, DIM, RESET
from wolo.cli.exit_codes import ExitCode

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
    # Get or create agent display name from session (persists across runs)
    from wolo.session import get_or_create_agent_display_name
    agent_display_name = get_or_create_agent_display_name(session_id)
    
    # Create control manager and UI based on mode
    control = None
    ui = None
    keyboard = None
    
    if mode_config.enable_ui_state:
        control = get_manager(session_id)
        ui, keyboard = create_ui(control)
        # Print shortcuts hint immediately when UI is enabled
        ui.print_shortcuts()
        print()
    else:
        # Silent mode: minimal control manager (no keyboard shortcuts)
        control = get_manager(session_id)

    # Add user message (no display)
    add_user_message(session_id, message_text)
    
    # Print agent name prompt
    print(f"\033[94m{agent_display_name}\033[0m: ", end="", flush=True)

    # Start control and keyboard listener (if enabled)
    if control:
        control.start_running()
    if keyboard:
        keyboard.start()

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
        result = await agent_loop(
            config, session_id, agent_config, control,
            excluded_tools=excluded_tools,
            max_steps=quota_config.max_steps,
            agent_display_name=agent_display_name,
            is_repl_mode=False
        )
        print()  # Final newline
        logger.info(f"Agent loop completed. Finish reason: {result.finish_reason}")

        # Save session if requested
        if save_session_flag:
            save_session(session_id)
            print(f"Session saved: {session_id}")
            print(f"Session file: ~/.wolo/sessions/{session_id}.json")
            logger.info(f"Session saved: {session_id}")

        # Export benchmark results if in benchmark mode
        if benchmark_mode:
            collector = MetricsCollector()
            session_metrics = collector.export_session(session_id)
            if session_metrics:
                # Add name to metrics for better reporting
                session_metrics["name"] = message_text[:50] + ("..." if len(message_text) > 50 else "")
                results = [session_metrics]

                # Save to JSON file
                with open(benchmark_output, "w") as f:
                    json.dump(results, f, indent=2, default=str)
                print(f"Benchmark results saved to: {benchmark_output}")

                # Print formatted report
                print()
                print(generate_report(results))
                print()

        return ExitCode.SUCCESS
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully - auto-save session
        print(f"\n\033[93mInterrupted by user. Saving session...\033[0m")
        save_session(session_id)
        print(f"Session saved: {session_id}")
        print(f"Session file: ~/.wolo/sessions/{session_id}/")
        print(f"Resume with: wolo -r {session_id} \"your prompt\"")
        return ExitCode.INTERRUPTED
    except Exception as e:
        print(f"\n\033[91mError: {e}\033[0m")
        logger.exception("Agent loop failed")
        # Auto-save session on error too
        try:
            save_session(session_id)
            print(f"Session saved: {session_id}")
        except Exception:
            pass  # Don't fail if save fails

        # Still export benchmark results even on error
        if benchmark_mode:
            collector = MetricsCollector()
            session_metrics = collector.export_session(session_id)
            if session_metrics:
                session_metrics["name"] = message_text[:50] + ("..." if len(message_text) > 50 else "")
                results = [session_metrics]
                with open(benchmark_output, "w") as f:
                    json.dump(results, f, indent=2, default=str)
                print(f"Benchmark results (with error) saved to: {benchmark_output}")

        return ExitCode.ERROR
    finally:
        # Cleanup
        if keyboard:
            keyboard.stop()
        if control:
            control.finish()
        remove_manager(session_id)
        
        # 清除 PID（重要：确保进程退出时清理）
        from wolo.session import clear_session_pid
        try:
            clear_session_pid(session_id)
        except Exception as e:
            logger.warning(f"Failed to clear PID for session {session_id}: {e}")
        
        # 停止 watch 服务器
        try:
            from wolo.watch_server import stop_watch_server
            await stop_watch_server(session_id)
        except Exception as e:
            logger.warning(f"Failed to stop watch server: {e}")
        set_watch_server(None, None)
        
        # Close HTTP connection pool
        await GLMClient.close_all_sessions()
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
    # Get or create agent display name from session (persists across runs)
    from wolo.session import get_or_create_agent_display_name
    agent_display_name = get_or_create_agent_display_name(session_id)
    
    # Create control manager and UI
    control = get_manager(session_id)
    ui, keyboard = create_ui(control)
    
    # Setup question handler
    from wolo.question_ui import setup_question_handler
    question_handler = setup_question_handler()

    try:
        # Start keyboard listener
        keyboard.start()
        
        # Print shortcuts hint immediately when entering REPL
        ui.print_shortcuts()
        print()
        
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
                # Get user input
                try:
                    user_input = await ui.prompt_for_input("> ")
                    if not user_input:
                        # Empty input or Esc - exit REPL
                        print(f"\n{DIM}Exiting REPL mode{RESET}")
                        break
                    current_message = user_input
                except KeyboardInterrupt:
                    print(f"\n{DIM}Exiting REPL mode{RESET}")
                    break
            
            # Add user message (no display)
            add_user_message(session_id, current_message)
            task_count += 1
            
            # Print agent name prompt
            print(f"\033[94m{agent_display_name}\033[0m: ", end="", flush=True)
            
            # Start control
            control.start_running()
            
            # Determine excluded tools (REPL mode always allows question tool)
            excluded_tools = set()
            
            # Run agent loop
            try:
                result = await agent_loop(
                    config, session_id, agent_config, control,
                    excluded_tools=excluded_tools,
                    max_steps=quota_config.max_steps,
                    agent_display_name=agent_display_name,
                    is_repl_mode=True
                )
                print()  # Final newline
                logger.info(f"Task {task_count} completed. Finish reason: {result.finish_reason}")
                
                # Save session after each task if requested
                if save_session_flag:
                    save_session(session_id)
                    logger.info(f"Session saved: {session_id}")
                
                # Reset for next task
                current_message = None
                control.reset()
                
            except KeyboardInterrupt:
                # Ctrl+C during execution - exit REPL
                print(f"\n\033[93mInterrupted by user. Exiting REPL...\033[0m")
                if save_session_flag:
                    save_session(session_id)
                    print(f"Session saved: {session_id}")
                break
            except Exception as e:
                print(f"\n\033[91mError: {e}\033[0m")
                logger.exception("Agent loop failed")
                # Continue REPL even on error
                current_message = None
                control.reset()
        
        return ExitCode.SUCCESS
        
    finally:
        # Cleanup
        keyboard.stop()
        control.finish()
        remove_manager(session_id)
        
        # Clear PID (important: ensure cleanup on exit)
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
        
        # Close HTTP connection pool
        await GLMClient.close_all_sessions()
        # Shutdown MCP integration
        try:
            from wolo.mcp_integration import shutdown_mcp
            await shutdown_mcp()
        except Exception:
            pass


async def run_watch_mode(session_id: str) -> int:
    """
    只读观察模式：连接到 watch 服务器，实时显示 session 输出。
    
    重要：这个模式只读取数据，不修改任何 session 状态。
    
    Args:
        session_id: 要观察的 session ID
        
    Returns:
        退出代码
    """
    import json
    from pathlib import Path
    from wolo.cli.utils import print_session_info
    from wolo.cli.events import DIM, RESET, GREEN, RED, YELLOW, CYAN
    from wolo.session import get_session_status
    
    # Check session status (process + watch server)
    status = get_session_status(session_id)
    if not status.get("exists"):
        print(f"Error: Session '{session_id}' not found.")
        return ExitCode.SESSION_ERROR
    
    is_running = status.get("is_running", False)
    watch_server_available = status.get("watch_server_available", False)
    pid = status.get("pid")
    
    # Check process and watch server status
    if not is_running:
        print(f"Error: Session '{session_id}' is not running.")
        print(f"       Make sure the session is started first.")
        return ExitCode.SESSION_ERROR
    
    if not watch_server_available:
        # Process running but watch server not available
        print(f"Error: Session '{session_id}' is running (PID: {pid}) but watch server is not available.")
        print(f"       The watch server may have failed to start or the session was started with an older version.")
        print(f"       Try resuming the session to restart the watch server.")
        return ExitCode.SESSION_ERROR
    
    # 获取 socket 路径
    socket_path = Path.home() / ".wolo" / "sessions" / session_id / "watch.sock"
    
    # 显示 session 信息
    print_session_info(session_id)
    print(f"\033[96mWatching session: {session_id}\033[0m")
    print(f"Press Ctrl+C to stop watching.\n")
    
    try:
        # 连接到 Unix Domain Socket
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        
        # 读取事件流
        while True:
            try:
                # 读取一行（JSON 格式）
                line_bytes = await asyncio.wait_for(reader.readline(), timeout=1.0)
                if not line_bytes:
                    # 连接关闭
                    print("\nWatch server disconnected.")
                    break
                
                # 解析 JSON
                try:
                    event = json.loads(line_bytes.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                
                # 处理事件（只显示，不修改任何数据）
                event_type = event.get("type")
                
                if event_type == "connected":
                    # 连接成功消息（已显示 session 信息，可以忽略）
                    continue
                elif event_type == "text-delta":
                    # 文本输出
                    text = event.get("text", "")
                    if event.get("reasoning"):
                        print(f"{DIM}{text}{RESET}", end="", flush=True)
                    else:
                        print(text, end="", flush=True)
                elif event_type == "tool-start":
                    # 工具开始（不显示，等待 complete 事件）
                    pass
                elif event_type == "tool-complete":
                    # 工具完成
                    tool = event.get("tool", "")
                    status = event.get("status", "unknown")
                    duration = event.get("duration", 0)
                    brief = event.get("brief", "")
                    
                    # 格式化持续时间
                    if duration >= 1:
                        duration_str = f"{duration:.1f}s"
                    else:
                        duration_str = f"{int(duration*1000)}ms"
                    
                    # 状态指示器
                    if status == "completed":
                        status_icon = "✓"
                        status_color = GREEN
                    elif status == "error":
                        status_icon = "✗"
                        status_color = RED
                    else:
                        status_icon = "○"
                        status_color = YELLOW
                    
                    if brief:
                        print(f"\n{CYAN}▶{RESET} {brief} {DIM}→{RESET} {status_color}{status_icon} {brief}{RESET} {DIM}({duration_str}){RESET}", flush=True)
                    else:
                        print(f"\n{CYAN}▶{RESET} {tool} {DIM}→{RESET} {status_color}{status_icon}{RESET} {DIM}({duration_str}){RESET}", flush=True)
                elif event_type == "finish":
                    # 完成事件
                    reason = event.get("reason", "unknown")
                    print(f"\n{DIM}Agent finished: {reason}{RESET}")
                
            except asyncio.TimeoutError:
                # 超时是正常的，继续等待
                continue
            except KeyboardInterrupt:
                print("\n\nStopped watching.")
                break
        
        return ExitCode.SUCCESS
        
    except FileNotFoundError:
        print(f"Error: Watch server socket not found for session '{session_id}'.")
        print(f"       Make sure the session is running.")
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
