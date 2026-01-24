# PROJECT KNOWLEDGE BASE

**Generated:** 2026-01-24
**Commit:** 0b68a5e
**Branch:** main

## OVERVIEW
Wolo - Minimal Python AI agent with MCP integration, session management, tool calling, and streaming responses.

## STRUCTURE
```
wolo/
├── wolo/                # Main package (23k lines)
│   ├── __init__.py      # Version + exports
│   ├── agent.py         # Agent loop (642 lines)
│   ├── session.py      # Session management (1,147 lines)
│   ├── llm.py          # Streaming LLM client
│   ├── tools.py        # Tool registry + implementations (1,396 lines)
│   ├── agents.py       # Agent types + permissions
│   ├── cli/            # CLI entry points
│   ├── compaction/     # Message compaction policies
│   ├── mcp/            # MCP (Model Context Protocol) integration
│   └── tests/          # Unit tests (32 files, 441 tests)
├── tests/              # Additional tests (compaction/)
├── Makefile            # Build/test commands
└── pyproject.toml      # Python project config
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Agent loop | wolo/agent.py | agent_loop(), step handling, doom loop detection |
| Session management | wolo/session.py | SessionSaver, layered storage (JSON + messages/) |
| Tool implementations | wolo/tools.py | File ops, search, shell, task (subagents) |
| Tool permissions | wolo/agents.py | Agent types with permission rulesets |
| MCP integration | wolo/mcp_integration.py | Loads skills, MCP servers |
| Message compaction | wolo/compaction/ | Policies, manager, token estimation |
| CLI entry | wolo/cli/main.py | Argument parsing, command routing |
| CLI routing | wolo/cli/parser.py | STRICT ORDER - DO NOT MODIFY |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| agent_loop | function | wolo/agent.py | Main agent execution loop |
| SessionSaver | class | wolo/session.py | Debounced auto-save |
| ToolRegistry | class | wolo/tool_registry.py | Tool registration/discovery |
| CompactionManager | class | wolo/compaction/manager.py | Compaction orchestration |
| GLMClient | class | wolo/llm.py | Streaming LLM client |

## CONVENTIONS

### Development
- Package manager: **uv** (with pip fallback)
- Linting/formatting: **ruff** (line-length: 100)
- Testing: **pytest** with pytest-asyncio, pytest-xdist
- Coverage: 60% minimum
- Version from `wolo/__init__.py` (dynamic setuptools)

### Tool System
- Tools registered via `@tool_registry.register()` decorator
- All tools implement `execute(context, **kwargs)` method
- File modification tracking prevents external modification edits
- Large outputs truncated to `.wolo_cache/truncated_outputs/`

### Agent Permissions
| Agent | Tools | Use Case |
|-------|-------|----------|
| general | All | Full coding tasks |
| plan | Read + shell (read-only) | Design/planning |
| explore | Read-only | Codebase analysis |
| compaction | Read-only | Context summarization |

### Session Management
- Layered storage: `session.json` (metadata) + `messages/*.json` (individual messages)
- Session ID format: `{AgentName}_{YYMMDD}_{HHMMSS}`
- Auto-save after each LLM response and tool completion
- TODO state persisted to `todos.json`

## ANTI-PATTERNS (THIS PROJECT)

### Tool Usage
- **NEVER** use bash tools for file operations - use Read/Edit/Write
- **ALWAYS** prefer editing existing files over creating new ones
- **DO NOT** modify file that was externally modified since last read

### Architecture
- **DO NOT** modify ROUTING PRIORITY in wolo/cli/main.py (strict order enforced)
- **NEVER** create files unless absolutely necessary
- **DO NOT** proceed until all tasks complete

### Known Issues
- Dual test directories: `./tests/` AND `./wolo/tests/` (should consolidate)
- `mbos_wolo.egg-info/` committed to git (should be in .gitignore)

## UNIQUE STYLES

### Doom Loop Detection
Agent detects repeated tool calls with identical input (5x threshold) and stops to prevent infinite loops.

### Smart Replace
Multiple matching strategies for `edit` tool:
1. Exact match with whitespace normalization
2. Fuzzy match with diff-based similarity

### Question Tool
Interactive user prompts with options, stored in `~/.wolo/sessions/{session_id}/questions/`.

### Subagent Delegation
`task` tool spawns subagents in subsessions for parallel work, tracking metrics in parent.

## COMMANDS
```bash
make dev-install          # Install with uv
uv run wolo "message"    # Run agent
uv run wolo --agent plan "Design X"  # Use specific agent type
uv run wolo --resume <session-id> "Continue"  # Resume session
make test                 # Run tests (parallel)
make lint                 # ruff check
make format               # ruff format
make benchmark            # Run benchmarks
```

## NOTES

### Configuration
- GLM API key required: `export GLM_API_KEY="your-api-key"`
- Config loaded from `~/.wolo/config.yaml` (endpoints, MCP servers, compaction settings)

### MCP Integration
- Loads skills from `~/.claude/custom_skills/`
- Loads MCP servers from `~/.claude/claude_desktop_config.json` or `~/.wolo/config.yaml`
- Supports local (stdio) and remote (HTTP/SSE) servers
- MCP tools prefixed with `mcp_`

### Session Persistence
- Immediate persistence to prevent data loss
- Each message stored as separate JSON file
- Metadata in session.json
- Todos persisted separately
