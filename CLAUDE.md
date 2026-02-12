# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

```bash
# Installation (development mode)
make dev-install
# or
uv sync --group dev --all-extras

# Running tests
make test           # Run all tests in parallel (-n auto)
make test-cov       # Run with coverage report
pytest tests/unit/test_session.py -v              # Single test file
pytest tests/unit/test_session.py::test_name -v   # Specific test

# Code quality
make lint          # ruff linting
make format        # ruff formatting
make mypy          # Type checking (focused on path_guard modules)
make check         # Run all checks (lint + mypy + format + tests)

# Building
make build         # Build source and wheel distributions
```

### Local Development

Use `uv run` or the wrapper script to ensure you're using project code:

```bash
uv run wolo "your prompt"
# or
./wolo-dev "your prompt"  # Wrapper script in project root
```

For long development sessions, use editable install: `uv pip install -e .`

## Architecture Overview

Wolo is a minimal Python AI agent CLI tool supporting multiple OpenAI-compatible LLM backends.

### Core Components

- **Agent Loop** (`wolo/agent.py`): Main execution loop with doom loop detection, step boundary control, and LLM/tool orchestration.

- **LLM Adapter** (`wolo/llm_adapter.py`): Uses `lexilux` library for OpenAI-compatible API communication. Handles streaming, token tracking, and reasoning mode (`enable_think`).

- **Session Management** (`wolo/session.py`): Layered storage in `~/.wolo/sessions/{session_id}/` with separate message files. Uses `SessionSaver` for debounced auto-save.

- **Tools System** (`wolo/tools_pkg/`): Modular tools organized by category:
  - `shell.py`, `file_read.py`, `file_write.py`, `search.py` - Core operations
  - `task.py` - Subagent task execution
  - `todo.py` - Task tracking
  - `memory.py` - Long-term memory (LTM)
  - `executor.py` - Main dispatcher with permission checks

- **PathGuard** (`wolo/path_guard/`): Modular path protection with pluggable confirmation strategies and session-based persistence.

- **Compaction** (`wolo/compaction/`): Strategy-based token compaction with summary and pruning policies.

- **MCP Integration** (`wolo/mcp_integration.py`): Loads MCP servers from both Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`) and Wolo config.

- **Control System** (`wolo/control.py`): User interruptions via Ctrl+A (interject), Ctrl+B (interrupt), Ctrl+P (pause).

- **Context State** (`wolo/context_state/`): Concurrent-safe session isolation using contextvars for token tracking, doom loop history, and todos.

### CLI Structure (`wolo/cli/`)

- `main.py` - Entry point with async initialization
- `parser.py` - Argument parsing
- `commands/` - Subcommands (run, repl, config, session)
- `output/` - Output formatters (default, minimal, verbose via `-O` flag)

## Agent Types

Defined in `wolo/agents.py` with role-based permissions:

| Agent | Purpose | Permissions |
|-------|---------|-------------|
| `general` | Full multi-step tasks | Full access |
| `plan` | Read-only planning | Read-only tools |
| `explore` | Codebase analysis | Read-only tools |
| `compaction` | Context summarization | Limited tools |

## Configuration

Configuration loaded from `~/.wolo/config.yaml` with environment variable overrides:

```yaml
endpoints:
  - name: default
    model: gpt-4
    api_base: https://api.openai.com/v1
    api_key: your-api-key

use_lexilux_client: true  # Recommended for better compatibility
enable_think: true        # Enable reasoning mode

mcp:
  enabled: true
  servers:
    my-server:
      command: npx
      args: ["-y", "@my/mcp-server"]
      node_strategy: auto  # auto/require/skip/python_fallback

path_safety:
  allowed_write_paths: ["~/projects"]
  max_confirmations_per_session: 10
```

**Priority**: CLI args > environment variables > config file

## Important Patterns

### Session ID Format
`{AgentName}_{YYMMDD}_{HHMMSS}` (spaces removed from agent name)

### PathGuard Priority Order (highest to lowest)
1. workdir (`-C`/`--workdir`)
2. `/tmp` (default)
3. CLI paths (`--allow-path`/`-P`)
4. Config paths (`path_safety.allowed_write_paths`)
5. Session confirmations

### Wild Mode
`WOLO_WILD_MODE=1` or `--wild` bypasses all safety checks (PathGuard, shell high-risk prompts, tool permission gates, FileTime checks).

### Tool Execution Flow
1. Tool call received from LLM
2. PathGuard checks (if write operation)
3. Permission check (agent ruleset)
4. Tool executor runs
5. Result published to event bus
6. Message updated and saved

### Control Flow Integration
When adding operations to agent loop:
- `control.should_interrupt()` - Should we stop immediately?
- `await control.wait_if_paused()` - Wait if paused
- `control.check_step_boundary()` - Step boundaries

### Message Persistence
Always use `SessionSaver` for debounced saves and call `flush()` in finally blocks. Writes use file locking.

### Context State Usage
Use `wolo/context_state` accessors for concurrent-safe state. Accessor functions return copies.

## Commit Message Format

Uses [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`

Examples: `feat(agent): Add subagent delegation`, `fix(tools): Correct shell timeout handling`
