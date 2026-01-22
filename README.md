# Wolo 🤖

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/lzjever/wolo/workflows/CI/badge.svg)](https://github.com/lzjever/wolo/actions)

**Wolo** is a minimal Python AI agent that helps with software engineering tasks through a clean, modular architecture. It implements an agent loop with comprehensive tool support, streaming responses, session management, and performance benchmarking.

## ✨ Features

- 🎯 **Agent Loop Architecture** - Clean, modular agent implementation with multiple agent types
- 🛠️ **Comprehensive Tools** - Shell, file operations, search, web scraping, and more
- 📊 **Built-in Benchmarking** - Track tokens, latency, tool usage, and performance metrics
- 💾 **Session Management** - Persistent sessions with save/resume capabilities
- 🔀 **Streaming Responses** - Real-time output as the agent thinks and works
- 🌐 **Web Integration** - Built-in web search and page fetching
- 📈 **Multiple Agent Types** - General, Plan, Explore, and Compaction agents
- 🔄 **Subagent Delegation** - Spawn specialized agents for parallel work

## 📦 Installation

### Quick Install

```bash
pip install -e .
```

### Development Setup with uv (Recommended)

This project uses [uv](https://github.com/astral-sh/uv) for fast dependency management. Install uv first:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then set up the development environment:

```bash
# Install with all development dependencies
make dev-install

# Or manually with uv
uv sync --all-extras
```

### Manual Setup

For development with all dependencies using pip:

```bash
pip install -e ".[dev]"
```

## 🚀 Configuration

Set your GLM API key as an environment variable:

```bash
export GLM_API_KEY="your-api-key"
```

Get your API key from [https://open.bigmodel.cn/](https://open.bigmodel.cn/)

## 🚀 Quick Start

### Basic Usage

```bash
# Simple question
uv run wolo "What is 2+2?"

# Use specific agent
uv run wolo --agent plan "Design a feature for user authentication"

# File operations
uv run wolo "Read README.md and summarize it"

# Run with benchmarking
uv run wolo --benchmark "List all Python files in the project"
```

### Using Make

```bash
# Run with a message
make run MSG="What is the weather like?"

# Run benchmark
make benchmark

# Run full benchmark suite
make benchmark-all
```

### Advanced Usage

```bash
# Use different model
uv run wolo --model glm-4-plus "Explain quantum computing"

# Resume saved session
uv run wolo --resume <session-id> "Continue the task"

# Save session for later
uv run wolo --save "Create a TODO API"

# Custom log level
uv run wolo --log-level DEBUG "Debug this code"
```

## 🏗️ Architecture

```
wolo/
├── wolo/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point and argument parsing
│   ├── config.py           # Configuration management
│   ├── session.py          # Session and message management
│   ├── agent.py            # Agent loop (core logic)
│   ├── llm.py              # GLM API client with streaming
│   ├── tools.py            # Tool definitions and execution
│   ├── agents.py           # Agent type configurations
│   ├── compaction.py       # Message compaction for token efficiency
│   ├── events.py           # Event bus for UI updates
│   ├── metrics.py          # Benchmark system and metrics collection
│   └── errors.py           # Error classification and handling
├── wolo/tests/
│   ├── test_agents.py      # Agent configuration tests
│   ├── test_session.py     # Session management tests
│   ├── test_errors.py      # Error handling tests
│   ├── test_metrics.py     # Metrics system tests
│   └── benchmark.py        # Benchmark test suite
├── Makefile                # Convenient commands
├── pyproject.toml          # Project configuration
└── README.md
```

## 🔧 Available Tools

| Tool | Description |
|------|-------------|
| `shell` | Execute bash commands (git, npm, python, etc.) |
| `read` | Read file contents with offset/limit support |
| `write` | Create or overwrite files |
| `edit` | Edit files by exact text replacement |
| `multiedit` | Edit multiple files at once |
| `grep` | Search for patterns in files (regex support) |
| `glob` | Find files matching patterns |
| `web_search` | Search the web (DuckDuckGo) |
| `web_fetch` | Fetch and extract web page content |
| `file_exists` | Check if files/directories exist |
| `get_env` | Get environment variables |
| `task` | Spawn subagents for parallel work |

## 🤖 Agent Types

| Agent | Description | Permissions |
|-------|-------------|-------------|
| `general` | Full access for coding tasks | All tools |
| `plan` | Read-only planning agent | Read/search only |
| `explore` | Codebase analysis | Read/search only |
| `compaction` | Context summarization | Read-only |

## 📊 Benchmarking

Wolo includes a comprehensive benchmarking system to track agent performance:

```bash
# Run single benchmark
uv run wolo --benchmark "Your task here"

# Run full benchmark suite
uv run python -m wolo.tests.benchmark
```

### Metrics Tracked

- **Session Metrics**: steps, duration, tokens, LLM calls, tool usage, errors
- **Step Metrics**: per-step latency, token counts, tool calls
- **Reports**: JSON export and formatted terminal output

Example output:
```
================================================================================
WOLO BENCHMARK RESULTS
================================================================================

Test                      Steps    Tokens    Tools    Duration
--------------------------------------------------------------------------------
simple_math               2        500       0        1200ms
file_read                 3        1200      1        2500ms
```

## 🧪 Testing

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run linting
make lint

# Format code
make format

# Run all checks
make check
```

## 📚 Development

### Code Quality

```bash
# Lint code
make lint

# Format code
make format

# Check formatting
make format-check

# Run all checks
make check
```

### Building

```bash
# Build distributions
make build

# Build source distribution
make sdist

# Build wheel
make wheel
```

### Cleanup

```bash
# Clean build artifacts
make clean
```

## 📖 Examples

### File Operations

```bash
uv run wolo "Create a file called hello.txt with content 'Hello World'"
uv run wolo "Read hello.txt"
uv run wolo "Replace 'World' with 'Universe' in hello.txt"
```

### Code Analysis

```bash
# Search for patterns
uv run wolo "Use grep to find all async functions in the project"

# Find files
uv run wolo "Use glob to find all Python test files"

# Multi-step task
uv run wolo "Analyze the wolo agent implementation and suggest improvements"
```

### Web Integration

```bash
# Search the web
uv run wolo "Search for information about Python async best practices"

# Fetch documentation
uv run wolo "Fetch and read the documentation for aiohttp"
```

## 🔗 Links

- **📦 GitHub**: [github.com/lzjever/wolo](https://github.com/lzjever/wolo)
- **📖 GLM API**: [open.bigmodel.cn](https://open.bigmodel.cn/)

## 📄 License

Wolo is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

**Built with ❤️ by the Wolo Team**
