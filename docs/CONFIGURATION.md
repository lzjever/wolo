# Wolo Configuration Guide

This document describes all configuration options available in Wolo's `~/.wolo/config.yaml` file.

## Configuration File Location

Wolo reads configuration from: `~/.wolo/config.yaml`

If the file doesn't exist, Wolo will use environment variables or default values.

## Configuration Structure

```yaml
# API Endpoints Configuration
endpoints:
  - name: default
    model: glm-4
    api_base: https://open.bigmodel.cn/api/paas/v4
    api_key: your-api-key-here
    temperature: 0.7
    max_tokens: 16384

default_endpoint: default

# MCP Servers
mcp_servers:
  - server1
  - server2

# Claude Compatibility
claude:
  enabled: false
  config_dir: ~/.claude
  skills:
    enabled: true
  mcp:
    enabled: true
  node_strategy: auto  # auto, require, skip, python_fallback

# MCP Configuration
mcp:
  enabled: true
  node_strategy: auto
  servers:
    server1:
      command: node
      args: ["path/to/server.js"]

# Enable GLM Thinking Mode
enable_think: false

# History Compaction Configuration
compaction:
  enabled: true
  auto_compact: true
  check_interval_steps: 3
  overflow_threshold: 0.9
  reserved_tokens: 2000
  
  summary_policy:
    enabled: true
    recent_exchanges_to_keep: 6
    summary_max_tokens: null  # null = no limit
    summary_prompt_template: ""  # empty = use default
    include_tool_calls_in_summary: true
  
  tool_pruning_policy:
    enabled: true
    protect_recent_turns: 2
    protect_token_threshold: 40000
    minimum_prune_tokens: 20000
    protected_tools: []  # Tool names that should never be pruned
    replacement_text: "[Output pruned to save context space]"
  
  policy_priority:
    tool_pruning: 50
    summary: 100
```

## Configuration Sections

### Endpoints

Configure multiple API endpoints for different models or providers.

**Fields:**
- `name` (string, required): Unique identifier for this endpoint
- `model` (string, required): Model name (e.g., "glm-4", "glm-4-plus")
- `api_base` (string, required): API base URL
- `api_key` (string, required): API key for authentication
- `temperature` (float, default: 0.7): Sampling temperature (0.0-2.0)
- `max_tokens` (int, default: 16384): Maximum tokens in response
- `source_model` (string, optional): Source model for compatibility

**Example:**
```yaml
endpoints:
  - name: default
    model: glm-4
    api_base: https://open.bigmodel.cn/api/paas/v4
    api_key: ${GLM_API_KEY}
    temperature: 0.7
    max_tokens: 16384
  
  - name: plus
    model: glm-4-plus
    api_base: https://open.bigmodel.cn/api/paas/v4
    api_key: ${GLM_API_KEY}
    temperature: 0.8
    max_tokens: 32768
```

### Default Endpoint

Specify which endpoint to use by default.

**Field:**
- `default_endpoint` (string): Name of the default endpoint

### MCP Servers

List of MCP server names to enable.

**Field:**
- `mcp_servers` (list of strings): Server names

### Claude Compatibility

Configure Claude compatibility mode to import skills and MCP servers from Claude.

**Fields:**
- `enabled` (bool, default: false): Enable Claude compatibility
- `config_dir` (string, optional): Claude config directory (default: ~/.claude)
- `skills.enabled` (bool, default: true): Import skills from Claude
- `mcp.enabled` (bool, default: true): Import MCP servers from Claude
- `node_strategy` (string, default: "auto"): Node.js handling strategy
  - `auto`: Auto-detect and use Node.js if available
  - `require`: Require Node.js, fail if not available
  - `skip`: Skip Node.js-based servers
  - `python_fallback`: Use Python fallback implementations

### MCP Configuration

Configure MCP (Model Context Protocol) servers.

**Fields:**
- `enabled` (bool, default: true): Enable MCP support
- `node_strategy` (string, default: "auto"): Node.js handling strategy
- `servers` (dict): Server configurations
  - Each server can have `command`, `args`, `env`, etc.

**Example:**
```yaml
mcp:
  enabled: true
  node_strategy: auto
  servers:
    filesystem:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    github:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: ${GITHUB_TOKEN}
```

### Enable Think Mode

Enable GLM thinking mode for reasoning.

**Field:**
- `enable_think` (bool, default: false): Enable thinking mode

### Compaction Configuration

Configure history compaction to manage long conversation contexts.

#### Main Settings

- `enabled` (bool, default: true): Enable compaction functionality
- `auto_compact` (bool, default: true): Automatically trigger compaction
- `check_interval_steps` (int, default: 3): Steps between automatic checks
- `overflow_threshold` (float, default: 0.9): Token usage ratio to trigger compaction (0.0-1.0)
- `reserved_tokens` (int, default: 2000): Tokens to reserve for system prompt and responses

#### Summary Policy

Compacts old messages by generating an LLM summary.

- `enabled` (bool, default: true): Enable summary compaction
- `recent_exchanges_to_keep` (int, default: 6): Number of recent user-assistant exchanges to preserve
- `summary_max_tokens` (int | null, default: null): Maximum tokens for summary (null = no limit)
- `summary_prompt_template` (string, default: ""): Custom prompt template (empty = use default)
- `include_tool_calls_in_summary` (bool, default: true): Include tool call info in summary

#### Tool Pruning Policy

Selectively removes old tool outputs while preserving tool call metadata.

- `enabled` (bool, default: true): Enable tool output pruning
- `protect_recent_turns` (int, default: 2): Number of recent turns to protect from pruning
- `protect_token_threshold` (int, default: 40000): Token threshold before starting to prune
- `minimum_prune_tokens` (int, default: 20000): Minimum tokens to prune (skip if less)
- `protected_tools` (list of strings, default: []): Tool names that should never be pruned
- `replacement_text` (string, default: "[Output pruned to save context space]"): Text to replace pruned outputs

#### Policy Priority

Control the order in which compaction policies are applied.

- `policy_priority` (dict): Priority values for each policy (higher = execute first)
  - `tool_pruning` (int, default: 50): Tool pruning priority
  - `summary` (int, default: 100): Summary compaction priority

## Environment Variables

You can also configure Wolo using environment variables:

- `GLM_API_KEY`: API key (required if not in config file)
- `WOLO_MODEL`: Model name (default: "glm-4")
- `WOLO_API_BASE`: API base URL
- `WOLO_TEMPERATURE`: Temperature (default: 0.7)
- `WOLO_MAX_TOKENS`: Max tokens (default: 16384)
- `WOLO_MCP_SERVERS`: Comma-separated list of MCP server names
- `WOLO_ENABLE_THINK`: Enable thinking mode ("true", "1", "yes")

## Configuration Priority

Configuration is loaded in the following priority order (highest to lowest):

1. Command-line arguments
2. Environment variables
3. `~/.wolo/config.yaml` file
4. Default values

## Example Configuration File

See `config.example.yaml` for a complete example configuration file.

## Validation

Wolo validates configuration on startup. Invalid values will cause errors with clear messages indicating what needs to be fixed.

## Getting Help

For more information:
- Run `wolo --help` for CLI options
- Check the documentation at `docs/`
- See `config.example.yaml` for examples
