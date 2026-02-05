"""
Tool system for Wolo.

This package provides all tool implementations and the central executor.
All public APIs are re-exported here for backward compatibility.
"""

# Constants (backward compatibility)
from wolo.tools_pkg.constants import (
    _BINARY_EXTENSIONS,
    _MAX_OUTPUT_LINES,
    _MAX_SHELL_HISTORY,
    BINARY_EXTENSIONS,
    MAX_OUTPUT_LINES,
    MAX_SHELL_HISTORY,
)

# Environment tools
from wolo.tools_pkg.env import get_env_execute

# Executor (main dispatcher)
from wolo.tools_pkg.executor import execute_tool

# File read tools
from wolo.tools_pkg.file_read import read_execute

# File write tools
from wolo.tools_pkg.file_write import edit_execute, multiedit_execute, write_execute

# Registry
from wolo.tools_pkg.registry import get_all_tools

# Search tools
from wolo.tools_pkg.search import file_exists_execute, glob_execute, grep_execute, ls_execute

# Shell tools
from wolo.tools_pkg.shell import clear_shell_state, get_shell_status, shell_execute

# Task tools
from wolo.tools_pkg.task import task_execute

# Todo tools and state (agent.py imports _todos directly)
from wolo.tools_pkg.todo import _todos, get_todos, set_todos, todoread_execute, todowrite_execute

# Utils
from wolo.tools_pkg.utils import _is_binary_file, _suggest_similar_files

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
