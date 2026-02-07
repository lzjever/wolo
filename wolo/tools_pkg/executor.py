"""Tool execution dispatcher."""

import asyncio
import logging
import time
from typing import Any

from wolo.events import bus
from wolo.exceptions import WoloPathSafetyError, WoloToolError
from wolo.file_time import FileModifiedError, FileTime
from wolo.session import ToolPart
from wolo.tool_registry import get_registry

# Import tool implementations
from wolo.tools_pkg.env import get_env_execute
from wolo.tools_pkg.file_read import read_execute
from wolo.tools_pkg.file_write import edit_execute, write_execute
from wolo.tools_pkg.search import file_exists_execute, glob_execute, grep_execute, ls_execute
from wolo.tools_pkg.shell import shell_execute
from wolo.tools_pkg.task import task_execute
from wolo.tools_pkg.todo import todoread_execute, todowrite_execute

logger = logging.getLogger(__name__)

# Canonical tool aliases accepted from model output.
TOOL_ALIASES = {
    "bash": "shell",
}


def _canonicalize_tool_name(tool_name: str) -> str:
    """Normalize tool aliases to registered tool names."""
    return TOOL_ALIASES.get(tool_name, tool_name)


async def execute_tool(
    tool_part: ToolPart, agent_config: Any = None, session_id: str = None, config: Any = None
) -> None:
    """Execute a tool call and update the part with results.

    Args:
        tool_part: The tool part to execute
        agent_config: Optional agent configuration for permission checking
        session_id: Optional session identifier for error tracking
        config: Optional configuration object

    Raises:
        WoloToolError: If tool execution fails
        WoloPathSafetyError: If path validation fails
    """
    registry = get_registry()
    wild_mode = bool(getattr(getattr(config, "path_safety", None), "wild_mode", False))
    original_tool_name = tool_part.tool
    canonical_tool_name = _canonicalize_tool_name(original_tool_name)
    if canonical_tool_name != original_tool_name:
        logger.warning(
            "Canonicalized tool alias '%s' to '%s'",
            original_tool_name,
            canonical_tool_name,
        )
        tool_part.tool = canonical_tool_name

    # Check permissions if agent_config is provided
    if agent_config and not wild_mode:
        from wolo.agents import check_permission

        permission = check_permission(agent_config, tool_part.tool)
        if permission == "deny":
            tool_part.status = "error"
            tool_part.output = (
                f"Permission denied: {tool_part.tool} is not allowed by {agent_config.name} agent"
            )
            # Publish both start and complete for consistent UI display
            start_event = registry.format_tool_start(tool_part.tool, tool_part.input)
            await bus.publish("tool-start", start_event)
            await bus.publish(
                "tool-complete",
                {
                    "tool": tool_part.tool,
                    "status": "error",
                    "duration": 0,
                    "brief": f"🚫 denied by {agent_config.name} agent",
                },
            )
            return
        elif permission == "ask":
            # For now, treat "ask" as "deny" since we don't have interactive prompts
            tool_part.status = "error"
            tool_part.output = f"Permission required: {tool_part.tool} requires user confirmation for {agent_config.name} agent"
            start_event = registry.format_tool_start(tool_part.tool, tool_part.input)
            await bus.publish("tool-start", start_event)
            await bus.publish(
                "tool-complete",
                {
                    "tool": tool_part.tool,
                    "status": "error",
                    "duration": 0,
                    "brief": "🔐 requires confirmation",
                },
            )
            return

    tool_part.status = "running"
    tool_part.start_time = time.time()

    # Use registry for tool-start event
    start_event = registry.format_tool_start(tool_part.tool, tool_part.input)
    await bus.publish("tool-start", start_event)

    try:
        if tool_part.tool == "shell":
            command = tool_part.input.get("command", "")
            timeout = tool_part.input.get("timeout", 30000)
            result = await shell_execute(
                command, timeout, session_id=session_id, wild_mode=wild_mode
            )
            tool_part.output = result["output"]
            tool_part.status = "error" if result.get("metadata", {}).get("error") else "completed"
            # Store metadata for verbose display
            tool_part._metadata = {
                "command": command,
                "exit_code": result.get("metadata", {}).get("exit_code", 0),
            }

        elif tool_part.tool == "read":
            file_path = tool_part.input.get("file_path", "")
            offset = tool_part.input.get("offset", 0)
            limit = tool_part.input.get("limit", 2000)
            result = await read_execute(file_path, offset, limit)
            tool_part.output = result["output"]
            metadata_error = result.get("metadata", {}).get("error", "")
            if isinstance(metadata_error, str) and metadata_error.startswith("path_"):
                tool_part.status = "error"
            else:
                tool_part.status = "completed"
            # Store metadata for verbose display
            tool_part._metadata = {
                "file_path": file_path,
                "total_lines": result.get("metadata", {}).get("total_lines", 0),
                "offset": offset,
                "showing_lines": result.get("metadata", {}).get("showing_lines", 0),
            }

            # Track file read time for modification detection
            if session_id and result["metadata"].get("error") is None:
                FileTime.read(session_id, file_path)

        elif tool_part.tool == "write":
            from wolo.path_guard import SessionCancelled
            from wolo.path_guard.models import Operation
            from wolo.tools_pkg.path_guard_executor import execute_with_path_guard

            file_path = tool_part.input.get("file_path", "")
            content = tool_part.input.get("content", "")

            # Check if file was modified externally since last read
            if session_id and not wild_mode:
                try:
                    FileTime.assert_not_modified(session_id, file_path)
                except FileModifiedError as e:
                    raise WoloToolError(
                        f"File '{file_path}' has been modified since you last read it. "
                        f"Please read the file again to see the current contents before writing.",
                        session_id=session_id,
                        tool_name="write",
                        error_type="FileModifiedError",
                    ) from e

            # Execute with path checking via middleware
            try:
                result = await execute_with_path_guard(
                    write_execute,
                    file_path=file_path,
                    operation=Operation.WRITE,
                    content=content,
                )
            except SessionCancelled as e:
                raise WoloPathSafetyError(
                    f"Session cancelled during path confirmation: {e.path}",
                    session_id=session_id,
                    path=e.path,
                ) from e

            tool_part.output = result["output"]
            metadata_error = result.get("metadata", {}).get("error", "")
            if isinstance(metadata_error, str) and metadata_error.startswith("path_"):
                tool_part.status = "error"
            else:
                tool_part.status = "completed"
            # Store metadata for verbose display
            lines = content.count("\n") + 1
            tool_part._metadata = {
                "file_path": file_path,
                "additions": lines,
                "deletions": 0,
                "size": len(content),
            }

            # Update file time after write
            if session_id and tool_part.status == "completed":
                FileTime.update(session_id, file_path)

        elif tool_part.tool == "edit":
            from wolo.path_guard import SessionCancelled
            from wolo.path_guard.models import Operation
            from wolo.tools_pkg.path_guard_executor import execute_with_path_guard

            file_path = tool_part.input.get("file_path", "")
            old_text = tool_part.input.get("old_text", "")
            new_text = tool_part.input.get("new_text", "")

            # Check if file was modified externally since last read
            if session_id and not wild_mode:
                try:
                    FileTime.assert_not_modified(session_id, file_path)
                except FileModifiedError as e:
                    raise WoloToolError(
                        f"File '{file_path}' has been modified since you last read it. "
                        f"Please read the file again to see the current contents before editing.",
                        session_id=session_id,
                        tool_name="edit",
                        error_type="FileModifiedError",
                    ) from e

            # Execute with path checking via middleware
            try:
                result = await execute_with_path_guard(
                    edit_execute,
                    file_path=file_path,
                    operation=Operation.WRITE,
                    old_text=old_text,
                    new_text=new_text,
                )
            except SessionCancelled as e:
                raise WoloPathSafetyError(
                    f"Session cancelled during path confirmation: {e.path}",
                    session_id=session_id,
                    path=e.path,
                ) from e

            tool_part.output = result["output"]
            metadata_error = result.get("metadata", {}).get("error", "")
            if isinstance(metadata_error, str) and metadata_error.startswith("path_"):
                tool_part.status = "error"
            else:
                tool_part.status = "completed"
            # Store metadata for verbose display (including diff)
            tool_part._metadata = {
                "file_path": file_path,
                "additions": result.get("metadata", {}).get("additions", 0),
                "deletions": result.get("metadata", {}).get("deletions", 0),
                "diff": result.get("metadata", {}).get("diff", ""),
            }

            # Update file time after edit
            if session_id and result["metadata"].get("error") is None:
                FileTime.update(session_id, file_path)

        elif tool_part.tool == "multiedit":
            edits = tool_part.input.get("edits", [])
            from wolo.path_guard import SessionCancelled
            from wolo.path_guard.models import Operation
            from wolo.tools_pkg.path_guard_executor import execute_with_path_guard

            results = []
            success_count = 0
            has_path_denial = False

            for edit in edits:
                file_path = edit.get("file_path", "")
                old_text = edit.get("old_text", "")
                new_text = edit.get("new_text", "")

                # Check if file was modified externally since last read
                if session_id and not wild_mode:
                    try:
                        FileTime.assert_not_modified(session_id, file_path)
                    except FileModifiedError as e:
                        raise WoloToolError(
                            f"File '{file_path}' has been modified since you last read it. "
                            f"Please read the file again to see the current contents before editing.",
                            session_id=session_id,
                            tool_name="multiedit",
                            error_type="FileModifiedError",
                        ) from e

                try:
                    result = await execute_with_path_guard(
                        edit_execute,
                        file_path=file_path,
                        operation=Operation.WRITE,
                        old_text=old_text,
                        new_text=new_text,
                    )
                except SessionCancelled as e:
                    raise WoloPathSafetyError(
                        f"Session cancelled during path confirmation: {e.path}",
                        session_id=session_id,
                        path=e.path,
                    ) from e

                results.append(result)
                metadata_error = result.get("metadata", {}).get("error", "")
                if isinstance(metadata_error, str) and metadata_error.startswith("path_"):
                    has_path_denial = True

                if "error" not in result.get("metadata", {}):
                    success_count += 1
                    if session_id:
                        FileTime.update(session_id, file_path)

            output_lines = [f"Multi-edit completed: {success_count}/{len(edits)} files edited\n"]
            for result in results:
                metadata = result.get("metadata", {})
                status = "✓" if "error" not in metadata else "✗"
                title = result.get("title", "unknown")
                summary = result.get("output", "").split("\n")[0]
                output_lines.append(f"{status} {title}: {summary}")

            tool_part.output = "\n".join(output_lines)
            tool_part.status = "error" if has_path_denial else "completed"

        elif tool_part.tool == "grep":
            pattern = tool_part.input.get("pattern", "")
            path = tool_part.input.get("path", ".")
            include_pattern = tool_part.input.get("include_pattern")
            result = await grep_execute(pattern, path, include_pattern)
            tool_part.output = result["output"]
            tool_part.status = "completed"
            # Store metadata for verbose display
            tool_part._metadata = {
                "pattern": pattern,
                "path": path,
                "matches": result.get("metadata", {}).get("matches", 0),
            }

        elif tool_part.tool == "glob":
            pattern = tool_part.input.get("pattern", "")
            path = tool_part.input.get("path", ".")
            result = await glob_execute(pattern, path)
            tool_part.output = result["output"]
            tool_part.status = "completed"
            # Store metadata for verbose display
            tool_part._metadata = {
                "pattern": pattern,
                "path": path,
                "matches": result.get("metadata", {}).get("matches", 0),
            }

        elif tool_part.tool == "ls":
            path = tool_part.input.get("path", ".")
            result = await ls_execute(path)
            tool_part.output = result["output"]
            tool_part.status = "completed"

        elif tool_part.tool == "file_exists":
            path = tool_part.input.get("path", "")
            result = await file_exists_execute(path)
            tool_part.output = result["output"]
            tool_part.status = "completed"

        elif tool_part.tool == "get_env":
            name = tool_part.input.get("name", "")
            default = tool_part.input.get("default", "")
            result = await get_env_execute(name, default)
            tool_part.output = result["output"]
            tool_part.status = "completed"

        elif tool_part.tool.startswith("mcp_"):
            # Handle MCP server tools
            from wolo.mcp_integration import call_mcp_tool

            result = await call_mcp_tool(tool_part.tool, tool_part.input)
            # Extract text content from MCP result
            content = result.get("content", [])
            if content and isinstance(content, list):
                text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
                tool_part.output = "\n".join(text_parts)
            else:
                tool_part.output = str(result)
            tool_part.status = "error" if result.get("isError") else "completed"

        elif tool_part.tool == "task":
            agent = tool_part.input.get("agent", "")
            message = tool_part.input.get("message", "")
            description = tool_part.input.get("description", "")

            if not session_id:
                tool_part.status = "error"
                tool_part.output = "Task tool requires session_id"
            elif not config:
                tool_part.status = "error"
                tool_part.output = "Task tool requires config"
            elif not agent or not message:
                tool_part.status = "error"
                tool_part.output = "Task tool requires 'agent' and 'message' parameters"
            else:
                result = await task_execute(agent, message, description, session_id, config)
                tool_part.output = result["output"]
                tool_part.status = "completed"

        elif tool_part.tool == "todowrite":
            todos = tool_part.input.get("todos", [])
            sid = tool_part.input.get("session_id") or session_id

            result = await todowrite_execute(todos, sid)
            tool_part.output = result["output"]
            tool_part.status = "completed" if "error" not in result.get("metadata", {}) else "error"
            if result.get("metadata", {}).get("todos"):
                tool_part._metadata = result["metadata"]

        elif tool_part.tool == "todoread":
            sid = tool_part.input.get("session_id") or session_id

            result = await todoread_execute(sid)
            tool_part.output = result["output"]
            tool_part.status = "completed" if "error" not in result.get("metadata", {}) else "error"

        elif tool_part.tool == "question":
            from wolo.question import (
                QuestionCancelledError,
                QuestionInfo,
                QuestionOption,
                QuestionTimeoutError,
                ask_questions,
            )

            questions_data = tool_part.input.get("questions", [])

            if not questions_data:
                tool_part.status = "error"
                tool_part.output = "No questions provided"
            elif not session_id:
                tool_part.status = "error"
                tool_part.output = "Question tool requires session_id"
            else:
                questions = [
                    QuestionInfo(
                        question=q.get("question", ""),
                        options=[
                            QuestionOption(
                                label=o.get("label", ""), description=o.get("description", "")
                            )
                            for o in q.get("options", [])
                        ],
                        header=q.get("header", ""),
                        allow_custom=q.get("allow_custom", True),
                    )
                    for q in questions_data
                ]

                try:
                    answers = await ask_questions(session_id, questions, timeout=300.0)

                    # Format output
                    output_lines = ["User answers:"]
                    for i, (q, a) in enumerate(zip(questions, answers)):
                        output_lines.append(f"\nQ{i + 1}: {q.question}")
                        if a:
                            output_lines.append(f"A{i + 1}: {', '.join(a)}")
                        else:
                            output_lines.append(f"A{i + 1}: (no answer)")

                    tool_part.output = "\n".join(output_lines)
                    tool_part.status = "completed"

                except QuestionCancelledError:
                    tool_part.output = "User cancelled the question"
                    tool_part.status = "error"
                except QuestionTimeoutError:
                    tool_part.output = "Question timed out waiting for user response"
                    tool_part.status = "error"

        elif tool_part.tool == "batch":
            tool_calls = tool_part.input.get("tool_calls", [])

            if not tool_calls:
                tool_part.status = "error"
                tool_part.output = "No tool calls provided"
            else:
                # Check for nested batch calls
                has_nested_batch = any(tc.get("tool") == "batch" for tc in tool_calls)
                if has_nested_batch:
                    tool_part.status = "error"
                    tool_part.output = "Nested batch calls are not allowed"
                else:
                    # Limit parallel calls
                    max_parallel = 10
                    if len(tool_calls) > max_parallel:
                        tool_part.status = "error"
                        tool_part.output = (
                            f"Too many tool calls ({len(tool_calls)}). Maximum is {max_parallel}."
                        )
                    else:
                        # Create ToolPart for each call
                        sub_parts = []
                        for tc in tool_calls:
                            sub_part = ToolPart(
                                tool=tc.get("tool", ""),
                                input=tc.get("input", {}),
                            )
                            sub_parts.append(sub_part)

                        # Execute in parallel
                        tasks = [
                            execute_tool(sp, agent_config=agent_config, session_id=session_id, config=config)
                            for sp in sub_parts
                        ]
                        results = await asyncio.gather(*tasks, return_exceptions=True)

                        # Check for exceptions
                        for sp, result in zip(sub_parts, results):
                            if isinstance(result, Exception):
                                sp.status = "error"
                                sp.output = str(result)

                        # Collect results
                        output_lines = [f"Batch execution results ({len(sub_parts)} tools):"]
                        success_count = 0
                        for i, sp in enumerate(sub_parts):
                            status_icon = "✓" if sp.status == "completed" else "✗"
                            if sp.status == "completed":
                                success_count += 1
                            output_lines.append(f"\n{i + 1}. [{status_icon}] {sp.tool}")
                            # Truncate individual outputs
                            if sp.output:
                                preview = sp.output[:200]
                                if len(sp.output) > 200:
                                    preview += "..."
                                output_lines.append(f"   {preview}")

                        output_lines.append(
                            f"\nSummary: {success_count}/{len(sub_parts)} succeeded"
                        )

                        tool_part.output = "\n".join(output_lines)
                        tool_part.status = (
                            "completed" if success_count == len(sub_parts) else "partial"
                        )

        elif tool_part.tool == "skill":
            from wolo.skill_tool import skill_execute

            skill_name = tool_part.input.get("name", "")
            if not skill_name:
                tool_part.status = "error"
                tool_part.output = "Skill name is required"
            else:
                result = await skill_execute(skill_name)
                tool_part.output = result
                tool_part.status = "completed"

        else:
            available_tools = ", ".join(sorted(spec.name for spec in registry.get_all()))
            raise WoloToolError(
                f"Unknown tool: {tool_part.tool}. Available tools: {available_tools}",
                session_id=session_id,
                tool_name=tool_part.tool,
                error_type="UnknownToolError",
            )

    # Handle specific exceptions with proper error types
    except (WoloToolError, WoloPathSafetyError) as e:
        # Set error status before re-raising so the finally block publishes correct state
        tool_part.status = "error"
        tool_part.output = tool_part.output or str(e)
        raise
    except FileNotFoundError as e:
        tool_part.status = "error"
        tool_part.output = f"Tool {tool_part.tool}: File not found - {e}"
        raise WoloToolError(
            f"Tool {tool_part.tool}: File not found - {e}",
            session_id=session_id,
            tool_name=tool_part.tool,
            error_type="FileNotFoundError",
        ) from e
    except PermissionError as e:
        tool_part.status = "error"
        tool_part.output = f"Tool {tool_part.tool}: Permission denied - {e}"
        raise WoloToolError(
            f"Tool {tool_part.tool}: Permission denied - {e}",
            session_id=session_id,
            tool_name=tool_part.tool,
            error_type="PermissionError",
        ) from e
    except OSError as e:
        tool_part.status = "error"
        tool_part.output = f"Tool {tool_part.tool}: OS error - {e}"
        raise WoloToolError(
            f"Tool {tool_part.tool}: OS error - {e}",
            session_id=session_id,
            tool_name=tool_part.tool,
            error_type="OSError",
        ) from e
    except Exception as e:
        # Catch-all for truly unexpected errors
        tool_part.status = "error"
        tool_part.output = f"Tool {tool_part.tool}: Unexpected error - {e}"
        raise WoloToolError(
            f"Tool {tool_part.tool}: Unexpected error - {e}",
            session_id=session_id,
            tool_name=tool_part.tool,
            error_type=type(e).__name__,
        ) from e
    finally:
        # Always record end time and publish tool-complete event,
        # even when exceptions are raised (prevents stuck UI spinners)
        if tool_part.start_time > 0:
            tool_part.end_time = time.time()
            duration = tool_part.end_time - tool_part.start_time

            # Collect metadata for display (used by verbose mode)
            tool_metadata = getattr(tool_part, "_metadata", {})

            # Use registry for tool-complete event
            complete_event = registry.format_tool_complete(
                tool_part.tool, tool_part.output, tool_part.status, duration, tool_metadata
            )
            await bus.publish("tool-complete", complete_event)
