"""
Tool system for Wolo.

This module is a backward-compatibility wrapper that re-exports from the
refactored wolo.tools_pkg package. All tool implementations have been
moved to separate modules for better organization:

- wolo.tools_pkg.shell - Shell execution
- wolo.tools_pkg.file_read - File reading (text, images, PDFs)
- wolo.tools_pkg.file_write - File writing and editing
- wolo.tools_pkg.search - Grep, glob, ls, file_exists
- wolo.tools_pkg.env - Environment variable access
- wolo.tools_pkg.task - Subagent task execution
- wolo.tools_pkg.todo - Todo management
- wolo.tools_pkg.registry - Tool schema generation
- wolo.tools_pkg.executor - Main tool dispatcher
"""

# Re-export everything from the package for backward compatibility
from wolo.tools_pkg import (
    _BINARY_EXTENSIONS,
    _MAX_OUTPUT_LINES,
    _MAX_SHELL_HISTORY,
    BINARY_EXTENSIONS,
    MAX_OUTPUT_LINES,
    MAX_SHELL_HISTORY,
    _is_binary_file,
    _suggest_similar_files,
    _todos,
    clear_shell_state,
    edit_execute,
    execute_tool,
    file_exists_execute,
    get_all_tools,
    get_env_execute,
    get_shell_status,
    get_todos,
    glob_execute,
    grep_execute,
    ls_execute,
    multiedit_execute,
    read_execute,
    set_todos,
    shell_execute,
    task_execute,
    todoread_execute,
    todowrite_execute,
    write_execute,
)

__all__ = [
    # Constants
    "BINARY_EXTENSIONS",
    "MAX_OUTPUT_LINES",
    "MAX_SHELL_HISTORY",
    "_BINARY_EXTENSIONS",
    "_MAX_OUTPUT_LINES",
    "_MAX_SHELL_HISTORY",
    # Utils
    "_is_binary_file",
    "_suggest_similar_files",
    # Shell
    "shell_execute",
    "get_shell_status",
    "clear_shell_state",
    # File read
    "read_execute",
    # File write
    "write_execute",
    "edit_execute",
    "multiedit_execute",
    # Search
    "grep_execute",
    "ls_execute",
    "glob_execute",
    "file_exists_execute",
    # Environment
    "get_env_execute",
    # Task
    "task_execute",
    # Todo
    "_todos",
    "get_todos",
    "set_todos",
    "todoread_execute",
    "todowrite_execute",
    # Registry
    "get_all_tools",
    # Executor
    "execute_tool",
]
