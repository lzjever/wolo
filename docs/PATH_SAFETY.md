# Path Safety - PathGuard Documentation

## Overview

PathGuard is a whitelist-based path protection system for file write operations in wolo. It prevents accidental writes to unintended locations by requiring user confirmation for paths outside the configured allowlist.

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
```

### Command Line

```bash
# Add a single path to allowlist
wolo --allow-path /workspace "create a file"

# Add multiple paths
wolo -P /workspace -P /var/tmp "run task"
```

## User Interaction

When a write operation requires confirmation:

```
⚠️  Path Confirmation Required
Operation: write
Path: /workspace/project/file.py
This path is not in the default allowlist (/tmp) or configured whitelist.

Allow this operation? [Y/n/a/q]
```

**Options:**
- `Y` or `y` - Allow this specific operation
- `n` - Deny this operation
- `a` - Allow entire directory (and subdirectories)
- `q` - Cancel the entire session

## Session Persistence

Confirmed directories are saved to `~/.wolo/sessions/<session_id>/path_confirmations.json`. When you resume a session, previously confirmed directories remain allowed.

## Examples

### Example 1: First Time Writing to Workspace

```bash
$ wolo "create a file in /workspace/test.txt"

⚠️  Path Confirmation Required
Operation: write
Path: /workspace/test.txt
This path is not in the default allowlist (/tmp) or configured whitelist.

Allow this operation? [Y/n/a/q] a
✓ /workspace and subdirectories added to session whitelist
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

### Example 3: Temporary Whitelist via CLI

```bash
$ wolo -P /tmp/work -P /var/cache "process files"
# /tmp/work and /var/cache are allowed for this session only
```

## Security Model

PathGuard uses a **whitelist-only approach**:

1. **Default allowlist**: Only `/tmp`
2. **Config file**: Additional paths from `path_safety.allowed_write_paths`
3. **CLI arguments**: Paths from `--allow-path` / `-P`
4. **Session confirmations**: Directories confirmed during the session

All paths are **normalized** (resolving symlinks and relative paths) before checking.

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
