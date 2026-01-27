"""Agent loop for Wolo - Refactored version."""

import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Optional

from wolo.agents import AgentConfig
from wolo.compaction import CompactionManager, CompactionStatus
from wolo.config import Config
from wolo.events import bus

# Dynamic import based on configuration will be handled in agent_loop function
from wolo.llm import get_token_usage, reset_token_usage
from wolo.metrics import MetricsCollector, StepMetrics
from wolo.session import (
    Message,
    SessionSaver,
    TextPart,
    ToolPart,
    add_assistant_message,
    add_user_message,
    find_last_assistant_message,
    find_last_user_message,
    get_pending_tool_calls,
    get_session_messages,
    get_session_saver,
    has_pending_tool_calls,
    remove_session_saver,
    to_llm_messages,
    update_message,
)
from wolo.tools import execute_tool, get_all_tools

if TYPE_CHECKING:
    from wolo.control import ControlManager

logger = logging.getLogger(__name__)

# Doom loop detection
DOOM_LOOP_THRESHOLD = 5
_doom_loop_history: list[tuple[str, str, str]] = []


def _hash_tool_input(tool_input: dict[str, Any]) -> str:
    """Create a hash of tool input for comparison."""
    return hashlib.md5(json.dumps(tool_input, sort_keys=True).encode()).hexdigest()


def _check_doom_loop(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Check if this tool call is a doom loop."""
    read_only_tools = {"read", "glob", "grep", "file_exists", "get_env"}
    if tool_name in read_only_tools:
        return False

    if tool_name == "shell":
        command = tool_input.get("command", "")
        read_only_prefixes = (
            "python3 -m py_compile",
            "ls ",
            "cat ",
            "echo ",
            "git status",
            "git diff",
        )
        if any(command.startswith(prefix) for prefix in read_only_prefixes):
            return False

    input_hash = _hash_tool_input(tool_input)
    context_hash = ""
    key = (tool_name, input_hash, context_hash)

    _doom_loop_history.append(key)
    if len(_doom_loop_history) > DOOM_LOOP_THRESHOLD:
        _doom_loop_history.pop(0)

    if len(_doom_loop_history) >= DOOM_LOOP_THRESHOLD:
        if len(set(_doom_loop_history)) == 1:
            logger.warning(
                f"DOOM LOOP DETECTED: {tool_name} called {DOOM_LOOP_THRESHOLD} times with same input"
            )
            return True

    return False


async def _handle_step_boundary(
    control: Optional["ControlManager"],
    ui: Any | None,
    session_id: str,
    agent_config: AgentConfig,
    step: int,
    max_steps: int,
    agent_display_name: str,
) -> tuple[bool, str | None]:
    """Handle step boundary control checkpoints. Returns (should_continue, user_input)."""
    if not control:
        return True, None

    control.set_step(step + 1, max_steps)
    check_result = control.check_step_boundary()

    if check_result == "WAIT":
        logger.info("Waiting for user input at step boundary")
        user_input = await ui.wait_for_input_with_keyboard() if ui else None

        from wolo.control import ControlState

        control._set_state(ControlState.RUNNING)

        if user_input:
            add_user_message(session_id, user_input)
            logger.info(f"User interjected: {user_input[:50]}...")
            print(f"\033[94m{agent_display_name}\033[0m: ", end="", flush=True)

        return True, user_input

    return True, None


async def _handle_pending_tools(
    last_assistant: Message,
    control: Optional["ControlManager"],
    ui: Any | None,
    agent_config: AgentConfig,
    session_id: str,
    config: Config,
    step: int,
    agent_display_name: str,
    saver: Optional["SessionSaver"] = None,
) -> tuple[bool, str | None, int]:
    """Handle pending tool calls. Returns (should_continue, user_input, new_step)."""
    if not has_pending_tool_calls(last_assistant):
        return True, None, step

    pending = get_pending_tool_calls(last_assistant)
    logger.info(f"Executing {len(pending)} pending tool calls")
    tool_start_time = time.time()

    for tool_call in pending:
        if control:
            if control.should_interrupt():
                logger.info("Interrupted before tool execution")
                tool_call.status = "interrupted"
                tool_call.output = "[Tool execution interrupted by user]"
                # Auto-save on interrupt
                if saver:
                    saver.save(force=True)
                break
            await control.wait_if_paused()

        await execute_tool(tool_call, agent_config, session_id, config)
        await bus.publish(
            "tool-result",
            {"tool": tool_call.tool, "output": tool_call.output, "status": tool_call.status},
        )
        update_message(session_id, last_assistant)

        # Auto-save after each tool call completion
        if saver:
            saver.save()

    (time.time() - tool_start_time) * 1000

    # Check for interrupt after tool execution
    if control and control.should_interrupt():
        from wolo.control import ControlState

        control._set_state(ControlState.WAIT_INPUT)
        logger.info("Waiting for user input after interrupt")
        user_input = await ui.wait_for_input_with_keyboard() if ui else None
        control._set_state(ControlState.RUNNING)

        if user_input:
            add_user_message(session_id, user_input)
            print(f"\033[94m{agent_display_name}\033[0m: ", end="", flush=True)
            return True, user_input, step
        else:
            return False, None, step

    return True, None, step + 1


def _should_exit_loop(
    last_assistant: Message | None,
    step: int,
    max_steps: int,
    session_id: str,
) -> bool:
    """Check if we should exit the loop."""
    if not last_assistant or not last_assistant.finished:
        return False

    finish_reason = (last_assistant.finish_reason or "").lower()
    has_tool_calls = any(isinstance(p, ToolPart) for p in last_assistant.parts)

    logger.debug(
        f"Checking exit: finished={last_assistant.finished}, finish_reason={finish_reason}, has_tool_calls={has_tool_calls}"
    )

    if has_tool_calls or finish_reason in ("tool_calls", "unknown"):
        return False

    from wolo.tools import _todos

    session_todos = _todos.get(session_id, [])
    incomplete_todos = [t for t in session_todos if t.get("status") != "completed"]
    logger.debug(f"Incomplete todos: {len(incomplete_todos)}/{len(session_todos)}")

    if not incomplete_todos:
        logger.info(f"All todos completed, exiting with reason: {last_assistant.finish_reason}")
        return True
    elif step >= max_steps - 1:
        logger.warning(f"Max steps reached with {len(incomplete_todos)} incomplete todos")
        return True
    else:
        logger.info(f"Continuing with {len(incomplete_todos)} incomplete todos")
        return False


async def _handle_interrupt(
    control: Optional["ControlManager"],
    ui: Any | None,
    session_id: str,
    agent_config: AgentConfig,
    agent_display_name: str,
) -> tuple[bool, str | None]:
    """Handle user interrupt. Returns (should_continue, user_input)."""
    if not control or not control.should_interrupt():
        return True, None

    from wolo.control import ControlState

    control._set_state(ControlState.WAIT_INPUT)
    logger.info("Interrupted before LLM call")
    user_input = await ui.wait_for_input_with_keyboard() if ui else None
    control._set_state(ControlState.RUNNING)

    if user_input:
        add_user_message(session_id, user_input)
        print(f"\033[94m{agent_display_name}\033[0m: ", end="", flush=True)
        return True, user_input
    else:
        return False, None


async def _call_llm(
    client: Any,  # GLMClient or WoloLLMClient based on configuration
    messages: list[Message],
    config: Config,
    session_id: str,
    step: int,
    max_steps: int,
    control: Optional["ControlManager"],
    assistant_msg: Message,
    excluded_tools: set[str] = None,
) -> tuple[Message, list[dict], bool, float]:
    """Call LLM and handle streaming. Returns (assistant_msg, tool_calls, interrupted, llm_start_time)."""
    # Check if we need compaction using the new CompactionManager
    messages_to_use = messages

    if config.compaction and config.compaction.enabled and config.compaction.auto_compact:
        check_interval = config.compaction.check_interval_steps
        if step > 0 and step % check_interval == 0:
            compaction_manager = CompactionManager(config.compaction, config)
            decision = compaction_manager.should_compact(messages, session_id)

            if decision.should_compact:
                logger.info(
                    f"Compaction triggered: {decision.current_tokens} tokens "
                    f"(threshold: {decision.overflow_ratio:.1%})"
                )
                try:
                    result = await compaction_manager.compact(messages, session_id)
                    if result.status == CompactionStatus.APPLIED:
                        messages_to_use = list(result.result_messages)
                        logger.info(
                            f"Compaction applied: saved {result.total_tokens_saved} tokens, "
                            f"policies: {[p.value for p in result.policies_applied]}"
                        )
                except Exception as e:
                    logger.warning(f"Compaction failed, using original messages: {e}")
                    messages_to_use = messages

    # Build LLM messages
    llm_messages = to_llm_messages(messages_to_use)
    logger.debug(f"Built {len(llm_messages)} LLM messages")

    # Add max_steps warning if approaching limit
    is_last_step = step >= max_steps - 1
    if is_last_step:
        max_steps_warning = (
            "CRITICAL - MAXIMUM STEPS REACHED\n\n"
            "The maximum number of steps for this task has been reached.\n\n"
            "IMPORTANT:\n"
            "1. Complete all remaining work immediately\n"
            "2. Do NOT create new files - summarize what's left to do\n"
            "3. If you have incomplete todos, list them\n"
            "4. Provide clear next steps for the user\n\n"
            "You must provide a text summary - no more tool calls."
        )
        llm_messages.append({"role": "system", "content": max_steps_warning})

    # Wait if paused
    if control:
        await control.wait_if_paused()

    # Call LLM with streaming
    current_text_part = TextPart()
    assistant_msg.parts.append(current_text_part)

    llm_start_time = time.time()
    reset_token_usage()
    tool_calls_this_step = []
    interrupted_during_stream = False

    try:
        tools = get_all_tools(excluded_tools=excluded_tools or set())
        async for event in client.chat_completion(llm_messages, tools=tools):
            if control:
                if control.should_interrupt():
                    logger.info("Interrupted during LLM streaming")
                    interrupted_during_stream = True
                    break
                await control.wait_if_paused()

            if event.get("type") == "tool-call":
                tool_calls_this_step.append(
                    {"tool": event.get("tool"), "input": event.get("input")}
                )
            await process_event(event, assistant_msg, current_text_part)
    except Exception as e:
        logger.error(f"Error during LLM call: {e}")
        assistant_msg.finished = True
        assistant_msg.finish_reason = "error"
        await bus.publish("finish", {"reason": "error", "error": str(e)})
        raise

    return assistant_msg, tool_calls_this_step, interrupted_during_stream, llm_start_time


async def agent_loop(
    config: Config,
    session_id: str,
    agent_config: AgentConfig | None = None,
    control: Optional["ControlManager"] = None,
    excluded_tools: set[str] = None,
    max_steps: int = 100,
    agent_display_name: str = None,
    is_repl_mode: bool = False,
) -> Message:
    """Main agent execution loop."""
    from wolo.agents import GENERAL_AGENT

    if agent_config is None:
        agent_config = GENERAL_AGENT

    # Get display name if not provided
    if agent_display_name is None:
        from wolo.agent_names import get_random_agent_name

        agent_display_name = get_random_agent_name()

    step = 0

    # ✅ Dynamic client selection based on configuration
    if config.use_lexilux_client:
        from wolo.llm_adapter import WoloLLMClient as GLMClient

        logger.info("Using lexilux-based LLM client (supports all OpenAI-compatible models)")
    else:
        from wolo.llm import GLMClient

        logger.info("Using legacy LLM client")

    client = GLMClient(config, agent_config, session_id, agent_display_name=agent_display_name)

    global _doom_loop_history
    _doom_loop_history = []

    collector = MetricsCollector()
    metrics = collector.create_session(session_id, agent_config.name)

    from wolo.session import load_session_todos
    from wolo.tools import _todos

    persisted_todos = load_session_todos(session_id)
    if persisted_todos:
        _todos[session_id] = persisted_todos
        logger.debug(f"Loaded {len(persisted_todos)} todos from disk")

    ui = None
    if control:
        from wolo.terminal import get_terminal_manager
        from wolo.ui import SimpleUI, register_ui

        terminal = get_terminal_manager()
        ui = SimpleUI(control, terminal=terminal)
        register_ui(ui)

    logger.info(
        f"Starting agent loop for session {session_id} (agent={agent_config.name}, max_steps={max_steps})"
    )

    # Get session saver for auto-save (debounced)
    saver = get_session_saver(session_id)

    try:
        while step < max_steps:
            logger.debug(f"Agent loop step {step + 1}/{max_steps}")

            # Step boundary check
            should_continue, user_input = await _handle_step_boundary(
                control, ui, session_id, agent_config, step, max_steps, agent_display_name
            )
            if not should_continue:
                break
            if user_input:
                continue

            # Get message history
            messages = get_session_messages(session_id)
            logger.debug(f"Current message count: {len(messages)}")

            last_user = find_last_user_message(messages)
            last_assistant = find_last_assistant_message(messages)

            if not last_user:
                logger.warning("No user message found, exiting loop")
                break

            # Handle pending tools
            if last_assistant:
                should_continue, user_input, step = await _handle_pending_tools(
                    last_assistant,
                    control,
                    ui,
                    agent_config,
                    session_id,
                    config,
                    step,
                    agent_display_name,
                    saver,
                )
                if not should_continue:
                    break
                if user_input:
                    continue

            # Check if we should exit
            # Both REPL and non-REPL modes should check for new user messages
            # (important for session resume with -r flag)
            has_new_user_message = False
            if last_user and last_assistant:
                # Compare timestamps to see if user message is newer
                if last_user.timestamp > last_assistant.timestamp:
                    has_new_user_message = True
                    logger.debug("New user message detected after assistant response")
            elif last_user and not last_assistant:
                # First message, definitely process it
                has_new_user_message = True

            # Only exit if task is complete AND no new user message
            if not has_new_user_message:
                if _should_exit_loop(last_assistant, step, max_steps, session_id):
                    if is_repl_mode:
                        logger.info("Task completed, exiting to REPL loop")
                    else:
                        logger.info("Exiting agent loop")
                    break
            else:
                logger.debug("New user message found, continuing processing")

            # Create new assistant message
            assistant_msg = add_assistant_message(session_id)
            logger.debug(f"Created new assistant message: {assistant_msg.id}")

            # Check for interrupt before LLM call
            should_continue, user_input = await _handle_interrupt(
                control, ui, session_id, agent_config, agent_display_name
            )
            if not should_continue:
                break
            if user_input:
                continue

            # Call LLM
            try:
                assistant_msg, tool_calls_this_step, interrupted, llm_start_time = await _call_llm(
                    client,
                    messages,
                    config,
                    session_id,
                    step,
                    max_steps,
                    control,
                    assistant_msg,
                    excluded_tools=excluded_tools,
                )
            except Exception as e:
                metrics.record_tool_error("llm", type(e).__name__)
                break

            # Handle interrupt during streaming
            if interrupted:
                from wolo.control import ControlState

                control._set_state(ControlState.WAIT_INPUT)
                assistant_msg.finished = True
                assistant_msg.finish_reason = "interrupted"
                logger.info("Waiting for user input after stream interrupt")
                user_input = await ui.wait_for_input_with_keyboard() if ui else None
                control._set_state(ControlState.RUNNING)

                if user_input:
                    add_user_message(session_id, user_input)
                    print(f"\033[94m{agent_display_name}\033[0m: ", end="", flush=True)
                    continue
                else:
                    break

            # Persist after LLM response
            update_message(session_id, assistant_msg)

            # Auto-save after assistant response
            saver.save()

            # Record metrics
            llm_latency = (time.time() - llm_start_time) * 1000
            token_usage = get_token_usage()
            step_metrics = StepMetrics(
                step_number=step + 1,
                llm_latency_ms=llm_latency,
                prompt_tokens=token_usage.get("prompt_tokens", 0),
                completion_tokens=token_usage.get("completion_tokens", 0),
                tool_calls=tool_calls_this_step,
                tool_duration_ms=0,
            )
            metrics.record_step(step_metrics)

            step += 1

            # Check if we exited due to max_steps
            if step >= max_steps:
                logger.warning(f"Max steps ({max_steps}) reached")
                from wolo.tools import _todos

                session_todos = _todos.get(session_id, [])
                incomplete_todos = [t for t in session_todos if t.get("status") != "completed"]

                messages = get_session_messages(session_id)
                final_message = find_last_assistant_message(messages)

                if final_message:
                    warning_text = "\n\n---\n\n**MAXIMUM STEPS REACHED**\n\n"
                    warning_text += (
                        f"The maximum number of steps ({max_steps}) has been reached.\n\n"
                    )

                    if incomplete_todos:
                        warning_text += f"**Remaining tasks ({len(incomplete_todos)}):**\n"
                        for t in incomplete_todos:
                            status = t.get("status", "pending")
                            content = t.get("content", "")
                            status_sym = {"pending": "[ ]", "in_progress": "[~]"}
                            warning_text += f"- {status_sym.get(status, '[?]')} {content}\n"
                        warning_text += "\n"
                    else:
                        warning_text += "All tracked tasks are completed.\n\n"

                    warning_text += "**Summary:** The agent has reached its step limit. "
                    warning_text += "You can provide additional input to continue working on the remaining tasks."

                    for part in final_message.parts:
                        if hasattr(part, "text"):
                            part.text += warning_text
                            break

                    final_message.finished = True
                    if not final_message.finish_reason or final_message.finish_reason in (
                        "tool_calls",
                        "unknown",
                    ):
                        final_message.finish_reason = "max_steps"

        logger.info(f"Agent loop completed after {step} steps")

        # Finalize metrics
        messages = get_session_messages(session_id)
        final_message = find_last_assistant_message(messages) or Message(role="assistant")
        finish_reason = final_message.finish_reason or "unknown"
        collector.finalize_session(session_id, finish_reason)

        return final_message
    finally:
        # Flush any pending saves before cleanup
        saver.flush()
        remove_session_saver(session_id)

        if ui:
            from wolo.ui import unregister_ui

            unregister_ui()


async def process_event(
    event: dict[str, Any], message: Message, current_text_part: TextPart
) -> None:
    """Process a streaming event from the LLM."""
    event_type = event.get("type")

    if event_type == "reasoning-delta":
        text = event.get("text", "")
        if not hasattr(message, "reasoning_content"):
            message.reasoning_content = ""
        message.reasoning_content += text
        await bus.publish("text-delta", {"text": text, "reasoning": True})

    elif event_type == "text-delta":
        text = event.get("text", "")
        current_text_part.text += text
        await bus.publish("text-delta", {"text": text})

    elif event_type == "tool-call-streaming":
        # LLM started streaming a tool call - show early feedback
        tool_name = event.get("tool", "")
        tool_id = event.get("id", "")
        length = event.get("length", 0)
        await bus.publish(
            "tool-call-streaming",
            {"tool": tool_name, "id": tool_id, "length": length},
        )

    elif event_type == "tool-call-progress":
        # LLM is generating tool call arguments - show progress
        index = event.get("index", 0)
        length = event.get("length", 0)
        await bus.publish(
            "tool-call-progress",
            {"index": index, "length": length},
        )

    elif event_type == "tool-call":
        tool_name = event.get("tool", "")
        tool_input = event.get("input", {})
        tool_call_id = event.get("id", "")
        logger.info(
            f"Received tool call: {tool_name} with input: {list(tool_input.keys()) if isinstance(tool_input, dict) else tool_input}"
        )

        if _check_doom_loop(tool_name, tool_input):
            current_text_part.text += f"\n\n[DOOM LOOP DETECTED: {tool_name} has been called {DOOM_LOOP_THRESHOLD} times with the same input. Stopping to prevent infinite loop.]"
            message.finished = True
            message.finish_reason = "doom_loop"
            await bus.publish("finish", {"reason": "doom_loop", "message": "Doom loop detected"})
            return

        if current_text_part.text:
            current_text_part = TextPart()
            message.parts.append(current_text_part)

        part_id = tool_call_id if tool_call_id else ""
        tool_input_dict = tool_input if isinstance(tool_input, dict) else {}
        tool_part = ToolPart(id=part_id, tool=tool_name, input=tool_input_dict)
        message.parts.append(tool_part)

    elif event_type == "finish":
        reason = event.get("reason", "unknown")
        logger.info(f"Received finish event: {reason}")
        message.finished = True
        message.finish_reason = reason
        if reason == "stop":
            await bus.publish("finish", {"reason": reason})
