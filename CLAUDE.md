# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

```bash
# Installation (development mode)
make dev-install
# or
uv sync --group dev --all-extras

# Running tests
make test           # Run all tests in parallel
pytest tests/ -v    # Direct pytest invocation

# Running a single test file
pytest tests/unit/test_session.py -v

# Running a specific test function
pytest tests/unit/test_session.py::test_create_session -v

# Code quality
make lint          # ruff linting
make format        # ruff formatting
make mypy          # Type checking (focused)
make check         # Run all checks

# Building
make build         # Build source and wheel distributions
```

### Local Development

When developing on this codebase, use `uv run` to ensure you're using the project code:

```bash
uv run wolo "your prompt"
# or
./wolo-dev "your prompt"  # Wrapper script in project root
```

## Architecture Overview

Wolo is a minimal Python AI agent CLI tool with a modular architecture:

### Core Components

- **Agent Loop** (`wolo/agent.py`): Main execution loop with doom loop detection, step boundary control, and LLM/tool orchestration. Uses helper functions for subprocess-style modularity.

- **LLM Adapter** (`wolo/llm_adapter.py`): Uses `lexilux` library for OpenAI-compatible API communication. Handles streaming events, token usage tracking, reasoning mode support, and error handling.

- **Session Management** (`wolo/session.py`): Layered storage with immediate persistence. Stores sessions in `~/.wolo/sessions/{session_id}/` with separate message files. Includes debounced auto-save via `SessionSaver`.

- **Tools System** (`wolo/tools_pkg/`): Refactored tool implementations organized by category:
  - `shell.py` - Shell command execution
  - `file_read.py`, `file_write.py` - File operations
  - `search.py` - Grep, glob, file operations
  - `task.py` - Subagent task execution
  - `registry.py` - Tool schema generation
  - `executor.py` - Main tool dispatcher

- **PathGuard** (`wolo/path_guard/`): Modular path protection for file operations. Provides pluggable confirmation strategies and session-based persistence for confirmed directories.

- **Compaction** (`wolo/compaction/`): Strategy-based token compaction for long sessions. Supports summary and pruning policies with priority ordering.

- **MCP Integration** (`wolo/mcp_integration.py`): Loads and manages Model Context Protocol servers from both Claude Desktop config and Wolo config.

- **Control System** (`wolo/control.py`): Manages user interruptions (Ctrl+A interject, Ctrl+B interrupt, Ctrl+P pause) during agent execution.

- **Context State** (`wolo/context_state/`): Provides concurrent-safe session isolation using contextvars. Used for doom loop detection, token tracking, and todo state.

### CLI Structure (`wolo/cli/`)

- `main.py` - Entry point with async initialization
- `parser.py` - Argument parsing with `argparse`
- `commands/` - Subcommands (run, repl, config, session)
- `output/` - Output formatters (default, minimal, verbose)

## Configuration

Configuration is loaded from `~/.wolo/config.yaml` with environment variable overrides:

- **Endpoints**: Multiple LLM endpoints with `api_key`, `model`, `api_base`
- **MCP**: Server configurations with `node_strategy` (auto/require/skip/python_fallback)
- **Path Safety**: `allowed_write_paths`, `max_confirmations_per_session`
- **Compaction**: Token thresholds and policy settings

Priority: CLI args > environment variables > config file

## Testing Strategy

Tests are organized by module:
- `tests/unit/` - Unit tests for individual components
- `tests/compaction/` - Compaction-specific tests
- `tests/path_safety/` - PathGuard tests
- `tests/integration/` - Multi-module integration tests

Tests use `pytest-asyncio` for async support and `pytest-xdist` for parallel execution (`-n auto`).

## Important Patterns

### Session ID Format
Session IDs follow the pattern: `{AgentName}_{YYMMDD}_{HHMMSS}`

### Message Persistence
Messages are persisted immediately with file locking. Always use `SessionSaver` for debounced saves and call `flush()` in finally blocks.

### Context State for Concurrent Safety
Use `wolo/context_state` for any state that needs to be isolated across concurrent sessions:
- `_token_usage_ctx` - Token tracking
- Doom loop history
- Session todos

### Tool Execution Flow
1. Tool call received from LLM
2. PathGuard checks (if write operation)
3. Tool executor runs the tool
4. Result published to event bus
5. Message updated and saved

### Control Flow Integration
When adding new operations to the agent loop, check:
- `control.should_interrupt()` - Should we stop immediately?
- `await control.wait_if_paused()` - Wait if paused
- Step boundaries via `control.check_step_boundary()`
