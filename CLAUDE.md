# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Wolo** is a minimal Python AI agent that implements an agent loop with comprehensive tool support, streaming responses, and session management. It uses the GLM API (similar to Claude's architecture) and supports MCP (Model Context Protocol) servers for extensibility.

## Development Commands

This project uses [uv](https://github.com/astral-sh/uv) for fast dependency management. If `uv` is not available, commands fall back to pip.

```bash
# Installation
make dev-install          # Install with all development dependencies

# Running
uv run wolo "message"     # Run agent with a message
make run MSG="msg"        # Alternative using Make
uv run wolo --agent plan "Design X"  # Use specific agent type
uv run wolo --resume <session-id> "Continue"  # Resume saved session

# Testing
make test                 # Run all unit tests
make test-cov             # Run with coverage report
pytest wolo/tests/test_specific.py -v  # Run single test file

# Code Quality
make lint                 # Run linting checks (ruff)
make format               # Format code with ruff
make format-check         # Check code formatting
make check                # Run all checks (lint + format + test)

# Building
make build                # Build source and wheel distributions
```

## Configuration

The GLM API key must be set:

```bash
export GLM_API_KEY="your-api-key"
```

Configuration is loaded from `~/.wolo/config.yaml` (supports multiple endpoints, MCP servers, compaction settings). See `config.example.yaml` for reference.

## Architecture

### Core Agent Loop (`wolo/agent.py`)

The `agent_loop()` function is the heart of Wolo. Key flow:

1. **Step boundary control** - Handles user interruption/checkpoints at each step
2. **Pending tool execution** - Executes tools from previous LLM response
3. **Exit conditions** - Checks if task is complete (todos, finish_reason, max_steps)
4. **LLM call** - Streams response with tool calls
5. **Metrics recording** - Tracks tokens, latency, tool usage

**Doom loop detection**: The agent detects when the same tool is called repeatedly with identical input (5x threshold) and stops to prevent infinite loops.

### Message Compaction (`wolo/compaction/`)

Token-efficient context management through automatic message summarization:

- `manager.py`: `CompactionManager` - decides when to compact and orchestrates policies
- `history.py`: Policies for removing/summarizing messages (roundtrip, head, tail)
- `token.py`: `TokenEstimator` - estimates token counts for messages

Compaction is triggered automatically based on token thresholds configured in `~/.wolo/config.yaml`.

### Agent Types (`wolo/agents.py`)

Four agent types with different permission levels:

| Agent | Permissions | Use Case |
|-------|-------------|----------|
| `general` | All tools | Full coding tasks |
| `plan` | Read + shell (exploration only) | Design/planning |
| `explore` | Read-only | Codebase analysis |
| `compaction` | Read-only | Context summarization |

Permissions are checked in `execute_tool()` via `check_permission()`.

### Tools (`wolo/tools.py`)

Tools are defined via a registry system in `tool_registry.py`. Built-in tools include:

- **File ops**: `read` (supports images/PDFs), `write`, `edit`, `multiedit`
- **Search**: `grep` (ripgrep fallback), `glob`
- **Execution**: `shell`, `task` (spawn subagents)
- **Utilities**: `file_exists`, `get_env`, `todowrite`, `todoread`, `question`, `batch`, `skill`

**File modification tracking**: The `file_time.py` module tracks when files are read and prevents writes/edits if a file was externally modified since last read (raises `FileModifiedError`).

**Output truncation**: Large tool outputs are automatically truncated and saved to `.wolo_cache/truncated_outputs/` to stay within token limits.

### Session Management (`wolo/session.py`)

Layered storage architecture for crash resilience:

- `~/.wolo/sessions/{session_id}/session.json` - Metadata
- `~/.wolo/sessions/{session_id}/messages/*.json` - Individual messages
- `~/.wolo/sessions/{session_id}/todos.json` - Todo state

Session ID format: `{AgentName}_{YYMMDD}_{HHMMSS}`

**Auto-save**: `SessionSaver` provides debounced auto-save after each LLM response and tool completion.

### MCP Integration (`wolo/mcp_integration.py`)

Integrates with Claude Desktop configuration and MCP servers:

- Loads skills from `~/.claude/custom_skills/`
- Loads MCP servers from `~/.claude/claude_desktop_config.json` or `~/.wolo/config.yaml`
- Supports local (stdio) and remote (HTTP/SSE) servers
- Node.js strategy: `auto`, `require`, `skip`, `python_fallback`

MCP tools are prefixed with `mcp_` and added to the tool registry.

### Streaming LLM Client (`wolo/llm.py`)

`GLMClient` provides streaming chat completion with:

- Connection pooling via `aiohttp.ClientSession`
- GLM "thinking mode" support (`enable_think`)
- Request/response debugging via `debug_llm_file` or `debug_full_dir`
- Retry logic with exponential backoff
- User-Agent header mimicking opencode

Events emitted: `reasoning-delta`, `text-delta`, `tool-call`, `finish`

### Metrics & Benchmarking (`wolo/metrics.py`)

`MetricsCollector` tracks per-session and per-step metrics:

- Steps, duration, tokens, LLM calls
- Tool usage counts and errors
- Subagent session tracking

Run `uv run wolo --benchmark "task"` or `uv run python -m wolo.tests.benchmark` for benchmarking.

### Control Flow (`wolo/control.py`)

`ControlManager` handles interactive control:

- Pause/resume execution
- User interruption (Ctrl+C)
- Step boundary checkpoints

### Event System (`wolo/events.py`)

Simple event bus for UI updates. Published events:

- `text-delta`: Streaming text output
- `tool-start`: Tool execution started
- `tool-complete`: Tool execution finished
- `finish`: Agent finished

## Important Implementation Details

### Todo System

Todos are stored in-memory per session (`_todos` dict in `tools.py`) and persisted to `todos.json`. The agent loop checks for incomplete todos before exiting. The agent does NOT stop if todos remain incomplete unless `max_steps` is reached.

### Smart Replace

The `smart_replace()` function in `smart_replace.py` provides multiple matching strategies for `edit` tool:

1. Exact match with whitespace normalization
2. Fuzzy match with diff-based similarity

### Question Tool

The `question` tool enables interactive user prompts with options. Results are stored in `~/.wolo/sessions/{session_id}/questions/`.

### Subagent Delegation

The `task` tool spawns subagents in subsessions for parallel work. Subagent metrics are tracked in parent session.

### Shell Process Tracking

Running shell processes are tracked for Ctrl+S viewing (`get_shell_status()`). Completed shells are stored in history (last 10).

## Entry Points

- CLI: `wolo/cli:main_async()` - Argument parsing and session initialization
- Package: `wolo.__main__:main()` - `python -m wolo`
- REPL: `wolo/cli:repl_mode()` - Interactive mode

## Error Handling

`wolo/errors.py` classifies API errors and provides user-friendly messages. Retry strategy is determined by error type.

## Package Management

Wolo follows the same packaging approach as [lexilux](https://github.com/lzjever/lexilux):

- **Version management**: Version is defined in `wolo/__init__.py` as `__version__` and dynamically read by setuptools
- **Build system**: Uses `setuptools` with `dynamic = ["version"]` in pyproject.toml
- **Release workflow**: GitHub Actions reads version from `__init__.py` using regex (not from pyproject.toml)

### Local Lexilux Reference

The lexilux development branch is available locally at:
```
/home/percy/works/mygithub/mbos-agent/lexilux
```

Use this as a reference when aligning packaging, CI/CD, or other implementation patterns with lexilux.
