"""
Tool Registry - Centralized tool metadata and formatting.

This module provides a single source of truth for all tool definitions,
including:
- LLM function schemas (descriptions loaded from .txt files)
- Display formatting (icons, colors, briefs)
- Output handling rules

Adding a new tool only requires adding one ToolSpec entry here.
Tool descriptions are stored in wolo/tools/descriptions/*.txt files.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from wolo.tool_descriptions import load_tool_description

# ==================== ANSI Colors ====================


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


# ==================== Tool Categories ====================


class ToolCategory:
    """Tool categories for grouping and styling."""

    SHELL = "shell"  # Shell commands
    FILE_READ = "file_read"  # File reading operations
    FILE_WRITE = "file_write"  # File writing operations
    SEARCH = "search"  # Search operations (grep, glob)
    WEB = "web"  # Web operations
    AGENT = "agent"  # Sub-agent operations
    META = "meta"  # Meta operations (todos, etc.)


# Category to color mapping
CATEGORY_COLORS = {
    ToolCategory.SHELL: Colors.YELLOW,
    ToolCategory.FILE_READ: Colors.CYAN,
    ToolCategory.FILE_WRITE: Colors.MAGENTA,
    ToolCategory.SEARCH: Colors.CYAN,
    ToolCategory.WEB: Colors.BLUE,
    ToolCategory.AGENT: Colors.BLUE,
    ToolCategory.META: Colors.GREEN,
}


# ==================== Helper Functions ====================


def _truncate(text: str, max_len: int = 60) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


# ==================== Tool Spec ====================


@dataclass
class ToolSpec:
    """
    Complete specification for a tool.

    This is the single source of truth for tool metadata.
    """

    # Identity
    name: str
    description: str

    # LLM schema
    parameters: dict[str, Any]
    required_params: list[str] = field(default_factory=list)

    # Display
    category: str = ToolCategory.META
    icon: str = "▶"

    # Output handling
    show_output: bool = False  # Whether to show full output in CLI

    # Custom formatters (optional)
    _brief_formatter: Callable[[dict], str] | None = None
    _result_formatter: Callable[[str, str], str] | None = None

    def get_color(self) -> str:
        """Get the color for this tool based on category."""
        return CATEGORY_COLORS.get(self.category, Colors.WHITE)

    def format_brief(self, params: dict) -> str:
        """Format a brief description of the tool call."""
        if self._brief_formatter:
            try:
                return self._brief_formatter(params)
            except Exception:
                pass
        return f"{self.icon} {self.name}"

    def format_result(self, output: str, status: str) -> str:
        """Format a brief description of the tool result (WITHOUT status icon)."""
        if self._result_formatter:
            try:
                return self._result_formatter(output, status)
            except Exception:
                pass

        # Default result formatting (no icon - CLI adds it)
        if status == "error":
            return _truncate(output, 60) if output else "failed"
        return "done"

    def to_llm_schema(self) -> dict:
        """Convert to LLM function schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required_params,
                },
            },
        }


# ==================== Tool Definitions ====================


# Shell tool
def _shell_brief(p: dict) -> str:
    cmd = p.get("command", "")
    timeout = p.get("timeout")

    # Truncate long commands
    cmd_display = _truncate(cmd, 65)

    # Show timeout if non-default
    if timeout and timeout != 30000:
        timeout_sec = timeout / 1000
        if timeout_sec >= 60:
            return f"$ {cmd_display} ({timeout_sec / 60:.0f}m)"
        else:
            return f"$ {cmd_display} ({timeout_sec:.0f}s)"

    return f"$ {cmd_display}"


def _shell_result(output: str, status: str) -> str:
    """Return result description WITHOUT status icon (CLI adds it)."""
    if status == "error":
        # Try to extract useful error info
        lines = output.strip().split("\n") if output else []
        if lines:
            last_line = lines[-1].strip()
            if last_line:
                return _truncate(last_line, 60)
        return _truncate(output, 60) if output else "failed"

    lines = [ln for ln in output.strip().split("\n") if ln.strip()] if output else []
    if not lines:
        return "(no output)"
    elif len(lines) == 1:
        return _truncate(lines[0], 60)
    else:
        # Show line count and preview of last meaningful line
        last = _truncate(lines[-1], 40)
        return f"{len(lines)} lines: {last}"


SHELL = ToolSpec(
    name="shell",
    description=load_tool_description("shell"),
    parameters={
        "command": {"type": "string", "description": "The command to execute"},
        "timeout": {"type": "number", "description": "Timeout in milliseconds (default 30000)"},
    },
    required_params=["command"],
    category=ToolCategory.SHELL,
    icon="$",
    show_output=False,
    _brief_formatter=_shell_brief,
    _result_formatter=_shell_result,
)


# Read tool
def _read_brief(p: dict) -> str:
    return f"📄 {p.get('file_path', '')}"


def _read_result(output: str, status: str) -> str:
    """Return result description WITHOUT status icon (CLI adds it)."""
    if status == "error":
        return _truncate(output, 60)
    lines = output.strip().split("\n") if output else []
    return f"{len(lines)} lines"


READ = ToolSpec(
    name="read",
    description=load_tool_description("read"),
    parameters={
        "file_path": {"type": "string", "description": "The path to the file to read"},
        "offset": {"type": "number", "description": "Skip N lines from the start (default: 0)"},
        "limit": {
            "type": "number",
            "description": "Maximum number of lines to read (default: 2000)",
        },
    },
    required_params=["file_path"],
    category=ToolCategory.FILE_READ,
    icon="📄",
    show_output=False,
    _brief_formatter=_read_brief,
    _result_formatter=_read_result,
)


# Write tool
def _write_brief(p: dict) -> str:
    content = p.get("content", "")
    return f"📝 {p.get('file_path', '')} ({len(content)} chars)"


WRITE = ToolSpec(
    name="write",
    description=load_tool_description("write"),
    parameters={
        "file_path": {"type": "string", "description": "The path to the file to write"},
        "content": {"type": "string", "description": "The content to write to the file"},
    },
    required_params=["file_path", "content"],
    category=ToolCategory.FILE_WRITE,
    icon="📝",
    show_output=False,
    _brief_formatter=_write_brief,
)


# Edit tool
def _edit_brief(p: dict) -> str:
    return f"✏️  {p.get('file_path', '')}"


EDIT = ToolSpec(
    name="edit",
    description=load_tool_description("edit"),
    parameters={
        "file_path": {"type": "string", "description": "The path to the file to edit"},
        "old_text": {"type": "string", "description": "The text to find and replace"},
        "new_text": {"type": "string", "description": "The replacement text"},
    },
    required_params=["file_path", "old_text", "new_text"],
    category=ToolCategory.FILE_WRITE,
    icon="✏️",
    show_output=False,
    _brief_formatter=_edit_brief,
)


# Multiedit tool
def _multiedit_brief(p: dict) -> str:
    edits = p.get("edits", [])
    return f"✏️  {len(edits)} edits"


MULTIEDIT = ToolSpec(
    name="multiedit",
    description=load_tool_description("multiedit"),
    parameters={
        "edits": {
            "type": "array",
            "description": "List of edits to apply",
            "items": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["file_path", "old_text", "new_text"],
            },
        }
    },
    required_params=["edits"],
    category=ToolCategory.FILE_WRITE,
    icon="✏️",
    show_output=False,
    _brief_formatter=_multiedit_brief,
)


# Grep tool
def _grep_brief(p: dict) -> str:
    return f"🔍 '{_truncate(p.get('pattern', ''), 30)}' in {p.get('path', '.')}"


def _grep_result(output: str, status: str) -> str:
    """Return result description WITHOUT status icon (CLI adds it)."""
    if status == "error":
        return _truncate(output, 60)
    if "No matches found" in output:
        return "no matches"
    lines = output.strip().split("\n") if output else []
    return f"{len(lines)} matches"


GREP = ToolSpec(
    name="grep",
    description=load_tool_description("grep"),
    parameters={
        "pattern": {"type": "string", "description": "The regex pattern to search for"},
        "path": {
            "type": "string",
            "description": "The path to search in (default: current directory)",
        },
        "include_pattern": {
            "type": "string",
            "description": "File pattern to include (e.g., '*.py')",
        },
    },
    required_params=["pattern"],
    category=ToolCategory.SEARCH,
    icon="🔍",
    show_output=False,
    _brief_formatter=_grep_brief,
    _result_formatter=_grep_result,
)


# Glob tool
def _glob_brief(p: dict) -> str:
    return f"📂 {p.get('pattern', '')} in {p.get('path', '.')}"


def _glob_result(output: str, status: str) -> str:
    """Return result description WITHOUT status icon (CLI adds it)."""
    if status == "error":
        return _truncate(output, 60)
    lines = [ln for ln in output.strip().split("\n") if ln] if output else []
    return f"{len(lines)} files"


GLOB = ToolSpec(
    name="glob",
    description=load_tool_description("glob"),
    parameters={
        "pattern": {"type": "string", "description": "The glob pattern (e.g., '**/*.py')"},
        "path": {
            "type": "string",
            "description": "The base path to search from (default: current directory)",
        },
    },
    required_params=["pattern"],
    category=ToolCategory.SEARCH,
    icon="📂",
    show_output=False,
    _brief_formatter=_glob_brief,
    _result_formatter=_glob_result,
)


# Web tools removed - will be provided via MCP


# Task/subagent tool
def _task_brief(p: dict) -> str:
    agent = p.get("agent_type", "general")
    goal = p.get("goal", "") or p.get("description", "")
    return f"🤖 [{agent}] {_truncate(goal, 40)}"


TASK = ToolSpec(
    name="task",
    description=load_tool_description("task"),
    parameters={
        "description": {"type": "string", "description": "Description of the task"},
        "goal": {"type": "string", "description": "The goal for the sub-agent"},
        "agent_type": {"type": "string", "description": "Type of agent (general, plan, explore)"},
    },
    required_params=["description"],
    category=ToolCategory.AGENT,
    icon="🤖",
    show_output=False,
    _brief_formatter=_task_brief,
)


# Todowrite tool
def _todo_brief(p: dict) -> str:
    todos = p.get("todos", [])
    return f"📋 {len(todos)} todos"


TODOWRITE = ToolSpec(
    name="todowrite",
    description=load_tool_description("todowrite"),
    parameters={
        "todos": {
            "type": "array",
            "description": "List of todo items",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "content": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                },
                "required": ["id", "content", "status"],
            },
        },
        "session_id": {"type": "string", "description": "Session ID (auto-filled)"},
    },
    required_params=["todos"],
    category=ToolCategory.META,
    icon="📋",
    show_output=True,  # Show todo list updates
    _brief_formatter=_todo_brief,
)


# TodoRead tool
def _todoread_brief(p: dict) -> str:
    return "📋 reading todos"


TODOREAD = ToolSpec(
    name="todoread",
    description=load_tool_description("todoread"),
    parameters={
        "session_id": {"type": "string", "description": "Session ID (auto-filled)"},
    },
    required_params=[],
    category=ToolCategory.META,
    icon="📋",
    show_output=True,
    _brief_formatter=_todoread_brief,
)


# Question tool
def _question_brief(p: dict) -> str:
    questions = p.get("questions", [])
    return f"❓ {len(questions)} question(s)"


QUESTION = ToolSpec(
    name="question",
    description=load_tool_description("question"),
    parameters={
        "questions": {
            "type": "array",
            "description": "List of questions to ask",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question text"},
                    "options": {
                        "type": "array",
                        "description": "Optional list of choices",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["label"],
                        },
                    },
                    "header": {"type": "string", "description": "Optional header/title"},
                },
                "required": ["question"],
            },
        }
    },
    required_params=["questions"],
    category=ToolCategory.META,
    icon="❓",
    show_output=True,
    _brief_formatter=_question_brief,
)


# Batch tool
def _batch_brief(p: dict) -> str:
    calls = p.get("tool_calls", [])
    return f"⚡ batch: {len(calls)} tools"


BATCH = ToolSpec(
    name="batch",
    description=load_tool_description("batch"),
    parameters={
        "tool_calls": {
            "type": "array",
            "description": "List of tool calls to execute in parallel",
            "items": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "description": "Tool name"},
                    "input": {"type": "object", "description": "Tool input parameters"},
                },
                "required": ["tool", "input"],
            },
        }
    },
    required_params=["tool_calls"],
    category=ToolCategory.META,
    icon="⚡",
    show_output=True,
    _brief_formatter=_batch_brief,
)


# Memory tools
def _memory_save_brief(p: dict) -> str:
    summary = p.get("summary", "")
    return f"🧠 saving memory: {_truncate(summary, 40)}"


MEMORY_SAVE = ToolSpec(
    name="memory_save",
    description=load_tool_description("memory_save"),
    parameters={
        "summary": {
            "type": "string",
            "description": "Description of what to remember from the current conversation",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tags for categorizing the memory (e.g., ['python', 'architecture'])",
        },
    },
    required_params=["summary"],
    category=ToolCategory.META,
    icon="🧠",
    show_output=True,
    _brief_formatter=_memory_save_brief,
)

# Note: memory_list, memory_recall, memory_delete removed - users should manage
# memories directly via filesystem (.wolo/memories/*.md or ~/.wolo/memories/*.md)


# Skill tool - dynamically generated schema
def _skill_brief(p: dict) -> str:
    return f"📚 loading skill: {p.get('name', 'unknown')}"


SKILL = ToolSpec(
    name="skill",
    description=load_tool_description(
        "skill"
    ),  # Base description, dynamically extended with available skills
    parameters={
        "name": {"type": "string", "description": "The skill identifier from available_skills"},
    },
    required_params=["name"],
    category=ToolCategory.META,
    icon="📚",
    show_output=True,  # Show loaded skill content
    _brief_formatter=_skill_brief,
)


# ==================== Tool Registry ====================


class ToolRegistry:
    """
    Central registry for all tools.

    Usage:
        registry = ToolRegistry()
        spec = registry.get("shell")
        all_schemas = registry.get_llm_schemas()
    """

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register all default tools."""
        # Core tools:
        # - shell: general command execution
        # - read: read file contents
        # - write: write file contents
        # - edit: edit file by replacement
        # - multiedit: batch edits
        # - grep: search file contents
        # - glob: find files by pattern
        # - task: delegate to sub-agent
        # - todowrite/todoread: track progress
        # - question: ask user questions
        # - batch: parallel execution
        #
        # Removed (can be done via shell):
        # - ls, file_exists, get_env
        #
        # Removed (will be provided via MCP):
        # - web_search, web_fetch
        defaults = [
            SHELL,
            READ,
            WRITE,
            EDIT,
            MULTIEDIT,
            GREP,
            GLOB,
            TASK,
            TODOWRITE,
            TODOREAD,
            QUESTION,
            BATCH,
            SKILL,
            MEMORY_SAVE,
        ]
        for spec in defaults:
            self.register(spec)

    def register(self, spec: ToolSpec) -> None:
        """Register a tool specification."""
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        """Get a tool specification by name."""
        return self._tools.get(name)

    def get_all(self) -> list[ToolSpec]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_llm_schemas(self) -> list[dict]:
        """Get all tools in LLM schema format."""
        return [spec.to_llm_schema() for spec in self._tools.values()]

    def format_tool_start(self, tool_name: str, params: dict) -> dict:
        """
        Format tool-start event data.

        Returns a dict with all display information.
        """
        spec = self.get(tool_name)
        if spec:
            return {
                "tool": tool_name,
                "brief": spec.format_brief(params),
                "color": spec.get_color(),
                "icon": spec.icon,
                "category": spec.category,
            }
        return {
            "tool": tool_name,
            "brief": tool_name,
            "color": Colors.WHITE,
            "icon": "▶",
            "category": "unknown",
        }

    def format_tool_complete(
        self,
        tool_name: str,
        output: str,
        status: str,
        duration: float,
        metadata: dict | None = None,
    ) -> dict:
        """
        Format tool-complete event data.

        Args:
            tool_name: Name of the tool
            output: Tool output text
            status: Completion status
            duration: Execution duration in seconds
            metadata: Additional metadata from tool execution (diff, matches, etc.)

        Returns a dict with all display information.
        """
        metadata = metadata or {}
        spec = self.get(tool_name)
        if spec:
            return {
                "tool": tool_name,
                "status": status,
                "duration": duration,
                "brief": spec.format_result(output, status),
                "show_output": spec.show_output,
                "output": output
                if spec.show_output
                else output,  # Always pass output for verbose mode
                "metadata": metadata,
            }
        return {
            "tool": tool_name,
            "status": status,
            "duration": duration,
            "brief": "done" if status == "completed" else status,
            "show_output": False,
            "output": output,
            "metadata": metadata,
        }


# Global registry instance
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
