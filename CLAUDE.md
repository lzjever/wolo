# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Installation
uv sync                    # Install dependencies
pip install -e .           # Fallback if uv unavailable

# Running
wolo "your prompt"         # Execute a task
wolo chat                  # Start interactive REPL
wolo -r <session-id>       # Resume a session

# Configuration
wolo config init           # First-time setup wizard
wolo config show           # Show current configuration
wolo config docs           # Show configuration documentation

# Testing
pytest                     # Run tests (auto-detects pytest-asyncio)
pytest -n auto             # Run tests in parallel (pytest-xdist)
pytest tests/test_file.py  # Run specific test file
pytest -k "test_name"      # Run tests matching pattern
pytest --cov=wolo          # Run with coverage

# Code Quality
ruff check .               # Lint
ruff format .              # Format
ruff check --fix .         # Auto-fix lint issues
```

## High-Level Architecture

### Core Components

**Agent Loop** (`wolo/agent.py`)
- Main execution loop: `agent_loop()` - runs LLM calls, handles tool execution, checks for completion
- Doom loop detection: prevents infinite loops by detecting repeated tool calls with identical input
- Step boundary handling: supports pause/resume via `ControlManager`
- Uses `WoloLLMClient` from `wolo/llm_adapter.py` for all LLM interactions

**Session Management** (`wolo/session.py`)
- Layered storage: `session.json` (metadata) + `messages/*.json` (individual messages) + `todos.json`
- Session ID format: `{AgentName}_{YYMMDD}_{HHMMSS}`
- `SessionSaver`: debounced auto-save (0.5s min interval) with immediate persistence
- PID tracking: detects if session is already running in another process

**Tool System** (`wolo/tools.py`, `wolo/tool_registry.py`)
- Tools registered via `ToolSpec` in registry
- Built-in tools: `read`, `write`, `edit`, `multiedit`, `grep`, `glob`, `ls`, `shell`, `batch`, `task`, `question`, `todowrite`, `todoread`, `skill`
- File modification tracking via `FileTime`: prevents editing files that changed externally since last read
- MCP tools prefixed with `mcp_` and loaded dynamically

**LLM Client** (`wolo/llm_adapter.py`)
- `WoloLLMClient`: unified LLM client using lexilux library
- Supports all OpenAI-compatible models (OpenAI, Anthropic, DeepSeek, GLM, etc.)
- Token tracking via `get_token_usage()` and `reset_token_usage()`
- Debug logging to file/directory when configured

**MCP Integration** (`wolo/mcp_integration.py`, `wolo/mcp/`)
- Loads MCP servers from Claude Desktop config (`~/.claude/claude_desktop_config.json`) or Wolo config
- Supports local (stdio) and remote (HTTP/SSE) servers
- Skills loaded from `~/.wolo/skills/` and optionally `~/.claude/custom_skills/`
- Background initialization: servers start asynchronously, tools registered as they connect

**Message Compaction** (`wolo/compaction/`)
- `CompactionManager`: orchestrates compaction policies
- Policies: `ToolOutputPruningPolicy` (truncates tool outputs), `SummaryCompactionPolicy` (LLM summarization)
- Token estimation via `TokenEstimator`
- Compaction history tracked per session

**Agent Types** (`wolo/agents.py`)
- `general`: Full tool access for coding tasks
- `plan`: Read-only tools for planning/design
- `explore`: Read-only for codebase analysis
- Permission checks: `deny`, `ask`, `allow` per tool per agent type

### CLI Architecture (`wolo/cli/`)

**Command Routing** (`main.py`)
- STRICT ROUTING PRIORITY (do not modify order):
  1. Help: `-h`, `--help`
  2. Quick commands: `-l` (list), `-w` (watch)
  3. Subcommands: `session`, `config`, `debug`
  4. REPL entry: `chat`, `repl`
  5. Execution: prompt provided (CLI or stdin)
  6. Default: brief help

**Parser** (`parser.py`)
- `FlexibleArgumentParser`: handles mixed options and positional arguments
- Stdin detection: reads piped input
- Option conflict validation

### Configuration (`wolo/config.py`)

- Primary config file: `~/.wolo/config.yaml`
- Environment variables: `WOLO_API_KEY`, `GLM_API_KEY`, `WOLO_MODEL`, `WOLO_API_BASE`
- API key priority: `WOLO_API_KEY` > `GLM_API_KEY` > config file (with warning)
- Direct mode: `--baseurl` + `--api-key` + `--model` bypasses config file
- Modular configs: `ClaudeCompatConfig`, `MCPConfig`, `CompactionConfig`, `PathSafetyConfig`

### Context-State Subsystem (`wolo/context_state/`)

- **Purpose**: Thread-safe, task-local storage using Python's `contextvars`
- **Components**:
  - `vars.py`: ContextVar definitions for token_usage, doom_loop_history, session_todos
  - `_init.py`: Accessor functions (get_*, reset_*, set_*)
  - `__init__.py`: Public API exports
- **Benefits**: Each async task gets isolated state, enabling concurrent sessions
- **Public API**:
  - `get_api_token_usage()`, `reset_api_token_usage()`
  - `get_doom_loop_history()`, `add_doom_loop_entry()`, `clear_doom_loop_history()`
  - `get_session_todos()`, `set_session_todos()`

### Exception Hierarchy (`wolo/exceptions.py`)

- **WoloError**: Base exception for all Wolo-specific errors
- **WoloConfigError**: Configuration-related errors (missing API key, invalid config)
- **WoloToolError**: Tool execution failures (timeout, not found, invalid args)
- **WoloSessionError**: Session lifecycle errors (not found, load/save failures, PID conflicts)
- **WoloLLMError**: LLM API errors (auth, rate limiting, network, token limits)
- **WoloPathSafetyError**: Path validation violations (protected paths, traversal attempts)
- All exceptions carry `session_id` and structured `context` metadata for debugging

## Key Patterns and Conventions

### Tool Implementation Pattern
```python
async def mytool_execute(param: str) -> dict[str, Any]:
    """Execute tool and return result."""
    try:
        # Do work
        return {"title": "mytool: ...", "output": "...", "metadata": {...}}
    except Exception as e:
        return {"title": "mytool: ...", "output": f"Error: {e}", "metadata": {"error": str(e)}}
```

### File Operations
- **ALWAYS** use `Read` tool before `Edit`/`Write` for file modification tracking
- `FileTime.assert_not_modified()` raises `FileModifiedError` if file changed externally
- Large outputs truncated to `.wolo_cache/truncated_outputs/` via `truncate_output()`

### Session Resume Flow
1. Check PID: `check_and_set_session_pid()` - fails if already running
2. Load messages: `get_session_messages()`
3. Load todos: `load_session_todos()`
4. Run `agent_loop()` with `is_repl_mode=True` for REPL, `False` for single-shot

### Event System (`wolo/events.py`)
- `bus.publish()` for events: `text-delta`, `tool-start`, `tool-complete`, `finish`
- Used by UI/watch server for real-time updates

### Context-State Usage

- **Always use accessor functions** instead of accessing ContextVars directly
- **Accessor functions return copies** - prevents accidental mutation
- **Initialize context-state at session start** - call `load_session_todos_to_context_state()`
- **Save context-state before session end** - call `save_session_todos_from_context_state()`

### Exception Handling

- **Use specific exception types** from `wolo.exceptions` instead of generic `Exception`
- **Always include session_id** when raising WoloError subclasses for tracking
- **CLI formats errors** via `_format_error_message()` for user-friendly display
- **Tool execution** raises `WoloToolError` or `WoloPathSafetyError` with metadata

## Important Gotchas

1. **CLI Routing Order**: The routing priority in `wolo/cli/main.py:_route_command()` is strict and must not be modified.

2. **Session PID Tracking**: When resuming sessions, the PID check prevents multiple processes from using the same session. Use `clear_session_pid()` on exit.

3. **MCP Background Init**: MCP servers start asynchronously. Tools may not be immediately available. Use `refresh_mcp_tools()` during polling.

4. **Lexilux Dependency**: The lexilux library is a local path dependency. This must be available for the LLM client to work.

5. **Test Directory Structure**: Tests are organized as:
   - `tests/unit/` - Unit tests for individual modules
   - `tests/integration/` - Integration tests for concurrent sessions
   - `tests/compaction/` - Compaction subsystem tests
   - `tests/path_safety/` - Path safety feature tests

6. **API Key Security**: Always use environment variables (`WOLO_API_KEY` or `GLM_API_KEY`) instead of config file for production deployments. The CLI logs a warning when API key is read from config file.
