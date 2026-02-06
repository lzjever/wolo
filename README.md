# Wolo

Wolo is a minimal Python AI agent CLI tool, similar to Claude Code or opencode. It supports multiple OpenAI-compatible LLM backends and provides a complete toolset for coding tasks.

## Features

- **Multi-Model Support**: Works with any OpenAI-compatible API (OpenAI, Anthropic, DeepSeek, GLM, etc.)
- **Rich Tool System**: Built-in tools for shell commands, file operations, search, and more
- **Session Management**: Persistent sessions with resume capability
- **MCP Integration**: Extend capabilities via Model Context Protocol
- **Token Compaction**: Automatic context management for long sessions
- **Path Safety**: Configurable write protection for sensitive directories

## Installation

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

## Quick Start

```bash
# Execute a single task
wolo "fix the bug in main.py"

# Pipe context with prompt
git diff | wolo "write commit message"

# Start interactive session
wolo chat

# Resume a session
wolo -r <session-id>
```

## Configuration

Wolo can be configured via environment variables or config file.

**Environment Variables (Recommended for Production):**

```bash
export WOLO_API_KEY="your-api-key-here"
# or
export GLM_API_KEY="your-api-key-here"
```

**Config File (Development):**

```bash
wolo config init
```

The config file is stored at `~/.wolo/config.yaml`:

```yaml
endpoints:
  - name: default
    model: gpt-4
    api_base: https://api.openai.com/v1
    api_key: your-api-key

# Optional: Enable lexilux client for better compatibility
use_lexilux_client: true

# Optional: MCP server configuration
mcp:
  enabled: true
  servers:
    my-server:
      command: npx
      args: ["-y", "@my/mcp-server"]
```

**Priority**: Environment variables take precedence over config file (`WOLO_API_KEY` > `GLM_API_KEY` > config file).

## Commands

| Command | Description |
|---------|-------------|
| `wolo "prompt"` | Execute a task |
| `wolo chat` | Start interactive REPL |
| `wolo -r <id>` | Resume session |
| `wolo -l` | List sessions |
| `wolo -w <id>` | Watch running session |
| `wolo config show` | Show configuration |
| `wolo config docs` | Configuration help |

## Built-in Tools

| Tool | Description |
|------|-------------|
| `shell` | Execute shell commands |
| `read` | Read file contents |
| `write` | Write file contents |
| `edit` | Edit file by replacement |
| `multiedit` | Batch file edits |
| `grep` | Search file contents |
| `glob` | Find files by pattern |
| `task` | Spawn sub-agent |
| `todowrite` | Track task progress |
| `question` | Ask user questions |
| `batch` | Parallel tool execution |
| `skill` | Load custom skills |

## Development

```bash
# Install with dev dependencies
make dev-install

# Run tests
make test

# Run with coverage
make test-cov

# Lint and format
make lint
make format

# Build package
make build
```

## Project Structure

```
wolo/
├── wolo/              # Main package
│   ├── agent.py       # Agent loop
│   ├── llm_adapter.py # LLM client (lexilux-based)
│   ├── session.py     # Session management
│   ├── tools.py       # Tool implementations
│   ├── cli/           # CLI subsystem
│   ├── compaction/    # Token compaction
│   └── mcp/           # MCP integration
├── tests/             # Test suite
├── docs/              # Documentation
└── pyproject.toml     # Project config
```

## License

Apache-2.0

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
