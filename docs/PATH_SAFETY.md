# Path Safety - PathGuard Documentation

## Overview

PathGuard is a modular, whitelist-based path protection system for file write operations in wolo. It prevents accidental writes to unintended locations by requiring user confirmation for paths outside the configured allowlist.

## Architecture

PathGuard is organized into modular components with clear separation of concerns:

### Core Components

**PathChecker** (`wolo/path_guard/checker.py`)
- Pure path checking logic with no external dependencies
- Checks if paths are whitelisted
- Manages confirmed directories during session

**PathGuardConfig** (`wolo/path_guard/config.py`)
- Configuration management for PathGuard
- Converts from legacy PathSafetyConfig format
- Creates PathWhitelist and PathChecker instances

**PathWhitelist** (`wolo/path_guard/checker.py`)
- Immutable collection of whitelisted paths
- Supports multiple path sources with priority ordering

**ConfirmationStrategy** (`wolo/path_guard/strategy.py`)
- Abstract base for confirmation handlers
- Built-in strategies: AutoAllow, AutoDeny, CLI

**PathGuardMiddleware** (`wolo/path_guard/middleware.py`)
- Middleware pattern for tool execution
- Wraps tools with path checking

**PathGuardPersistence** (`wolo/path_guard/persistence.py`)
- Session persistence for confirmed directories
- Saves and loads confirmations per session

### Path Priority Order

When checking if a path is allowed, PathGuard checks in this order:

1. **workdir** (highest) - Set via `-C/--workdir`
2. **/tmp** (default) - Always allowed
3. **cli_paths** - From `--allow-path/-P` CLI arguments
4. **config_paths** - From `path_safety.allowed_write_paths` in config
5. **confirmed_dirs** - Directories confirmed during session

## Default Behavior

- **Allowed without confirmation**: Only `/tmp`
- **Requires confirmation**: All other paths (including home directory `~`)
- **Confirmation persists**: Confirmed directories are remembered for the session

## Configuration

### Config File

Add to `~/.wolo/config.yaml`:

```yaml
path_safety:
  # Paths where write operations are allowed without confirmation
  allowed_write_paths:
    - /workspace
    - /var/tmp
    - /home/user/projects

  # Maximum number of confirmations per session (prevents confirmation fatigue)
  max_confirmations_per_session: 10

  # Enable audit logging for denied operations
  audit_denied: true

  # Audit log file location
  audit_log_file: ~/.wolo/path_audit.log

  # Wild mode: bypass all path safety checks and restrictions
  wild_mode: false
```

### Command Line

```bash
# Set working directory (highest priority)
wolo -C /workspace "create files"

# Add a single path to allowlist
wolo --allow-path /workspace "create a file"

# Add multiple paths
wolo -P /workspace -P /var/tmp "run task"

# Wild mode (bypass path checks and safety restrictions)
wolo --wild "run unrestricted task"
```

### Wild Mode

Wild mode is an explicit bypass for safety checks. It is intended for trusted, controlled automation contexts (for example sandbox scripts).

Enable via CLI:

```bash
wolo --wild "your prompt"
```

Enable via environment variable:

```bash
WOLO_WILD_MODE=true wolo "your prompt"
```

When wild mode is enabled:
- PathGuard checks/confirmations are bypassed.
- Shell high-risk pattern prompts are bypassed.
- Tool permission gate (`deny/ask`) is bypassed.
- FileTime external-modification checks before write/edit/multiedit are bypassed.

## User Interaction

When a write operation requires confirmation:

```
Path Confirmation Required
Operation: write
Path: /workspace/project/file.py
This path is not in the default allowlist (/tmp) or configured whitelist.

Allow this operation? [Y/n/a/q]
```

**Options:**
- `Y` or `y` - Allow and confirm the path's containing directory for this session
- `n` - Deny this operation
- `a` - Allow entire directory (and subdirectories)
- `q` - Cancel the entire session

## Session Persistence

Confirmed directories are saved to `~/.wolo/sessions/<session_id>/path_confirmations.json`. When you resume a session, previously confirmed directories remain allowed.

## Examples

### Example 1: First Time Writing to Workspace

```bash
$ wolo "create a file in /workspace/test.txt"

Path Confirmation Required
Operation: write
Path: /workspace/test.txt
This path is not in the default allowlist (/tmp) or configured whitelist.

Allow this operation? [Y/n/a/q] a
* /workspace and subdirectories added to session whitelist
```

### Example 2: Using Config File Whitelist

```yaml
# ~/.wolo/config.yaml
path_safety:
  allowed_write_paths:
    - /workspace
    - /home/user/myproject
```

```bash
$ wolo "write to /workspace/file.py"
# No confirmation needed - /workspace is in whitelist
```

### Example 3: Using Working Directory

```bash
$ wolo -C /tmp/work "create files"
# All paths under /tmp/work are allowed without confirmation
```

### Example 4: Temporary Whitelist via CLI

```bash
$ wolo -P /tmp/work -P /var/cache "process files"
# /tmp/work and /var/cache are allowed for this session only
```

## Security Model

PathGuard uses a **whitelist-only approach**:

1. **Default allowlist**: Only `/tmp`
2. **Config file**: Additional paths from `path_safety.allowed_write_paths`
3. **CLI arguments**: Paths from `--allow-path` / `-P`
4. **Working directory**: Paths under `-C/--workdir`
5. **Session confirmations**: Directories confirmed during the session

### Confirmation Limits and Auditing

- `path_safety.max_confirmations_per_session`: Caps how many confirmations are allowed in one session.
- `path_safety.audit_denied`: When enabled, denied operations are logged.
- `path_safety.audit_log_file`: Path to the denial audit log file.

All paths are **normalized** (resolving symlinks and relative paths) before checking.

## Migration from Legacy System

The legacy `PathSafetyConfig` in `wolo/config.py` now includes a conversion method:

```python
from wolo.config import PathSafetyConfig
from wolo.path_guard.config import PathGuardConfig

# Legacy config
legacy_config = PathSafetyConfig(
    allowed_write_paths=[Path("/workspace")]
)

# Convert to new PathGuardConfig
guard_config = legacy_config.to_path_guard_config(
    cli_paths=[Path("/tmp")],
    workdir=Path("/home/user/project")
)

# Create PathChecker
checker = guard_config.create_checker(confirmed_dirs=set())
```

## Troubleshooting

### "Permission denied" when writing to home directory

This is expected behavior. Either:
1. Confirm the directory when prompted
2. Add to config file whitelist
3. Use `--allow-path ~/specific/path`

### Non-interactive mode denial

In scripts or non-interactive terminals, operations are auto-denied. Pre-configure allowlist in config file.

### Session confirmations lost

Confirmations are saved per session. Use `-r <session_id>` to resume and keep confirmations.

## Module Reference

### wolo.path_guard.checker

- `PathChecker`: Core path checking logic
- `PathWhitelist`: Immutable whitelist configuration

### wolo.path_guard.config

- `PathGuardConfig`: Configuration management

### wolo.path_guard.strategy

- `ConfirmationStrategy`: Abstract confirmation handler
- `AutoAllowConfirmationStrategy`: Always allow
- `AutoDenyConfirmationStrategy`: Always deny
- `CLIConfirmationStrategy`: Interactive CLI prompts

### wolo.path_guard.middleware

- `PathGuardMiddleware`: Middleware for path-checked tool execution

### wolo.path_guard.persistence

- `PathGuardPersistence`: Session persistence

### wolo.path_guard.exceptions

- `PathGuardError`: Base exception
- `PathCheckError`: Check operation failed
- `PathConfirmationRequired`: Confirmation needed
- `SessionCancelled`: User cancelled session
