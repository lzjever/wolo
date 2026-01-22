# Wolo CLI Redesign Development Specification

**Version:** 1.0  
**Status:** Approved for Implementation  
**Date:** 2026-01-22

---

## Table of Contents

1. [Overview](#1-overview)
2. [Exit Codes Definition](#2-exit-codes-definition)
3. [Execution Modes](#3-execution-modes)
4. [CLI Interface Specification](#4-cli-interface-specification)
5. [Routing Logic](#5-routing-logic)
6. [Dual Input Handling](#6-dual-input-handling)
7. [Session Behavior](#7-session-behavior)
8. [Auto-Save Strategy](#8-auto-save-strategy)
9. [Conflict Detection](#9-conflict-detection)
10. [Help System](#10-help-system)
11. [Migration & Deprecation](#11-migration--deprecation)
12. [Implementation Tasks](#12-implementation-tasks)
13. [File Change Summary](#13-file-change-summary)

---

## 1. Overview

### 1.1 Goals

- Simplify CLI interface to prompt-centric model
- Replace confusing `--silent`/`--interactive` with intuitive `--solo`/`--coop`
- Support dual input (pipe + CLI prompt)
- Improve session resume experience with REPL mode
- Add robust conflict detection
- Maximize session recoverability with aggressive auto-save

### 1.2 Key Changes Summary

| Current | New | Change Type |
|---------|-----|-------------|
| `wolo run "prompt"` | `wolo "prompt"` | Remove `run` command |
| `--prompt-file` | `cat file \| wolo` | Remove option |
| `--silent` | `--solo` | Rename + semantic change |
| `--interactive` | `--coop` | Rename |
| `wolo repl` | `wolo chat` / `wolo repl` | Keep both as synonyms |
| `wolo session resume <id>` (show info) | `wolo session show <id>` | New command |
| `wolo session resume <id>` | Enters REPL | Behavior change |
| No conflict detection | Full conflict detection | New feature |
| Priority-based input | Dual input concatenation | New feature |

---

## 2. Exit Codes Definition

All exit codes MUST be documented in module docstrings and used consistently.

```python
"""
Exit Codes:
    0   - Success: Task completed successfully
    1   - Error: General error (invalid arguments, runtime error)
    2   - Quota Exceeded: Max steps or token limit reached
    3   - Session Error: Session not found, locked, or corrupted
    4   - Configuration Error: Invalid config, missing API key, etc.
    130 - Interrupted: User pressed Ctrl+C (SIGINT)
    131 - Terminated: Process received SIGTERM
"""

# Define in wolo/cli/exit_codes.py
class ExitCode:
    SUCCESS = 0
    ERROR = 1
    QUOTA_EXCEEDED = 2
    SESSION_ERROR = 3
    CONFIG_ERROR = 4
    INTERRUPTED = 130  # 128 + SIGINT(2)
    TERMINATED = 131   # 128 + SIGTERM(15)
```

### 2.1 Exit Code Usage Rules

| Situation | Exit Code | Example |
|-----------|-----------|---------|
| Task completed | 0 | Agent finished normally |
| Invalid CLI arguments | 1 | `--solo --coop` conflict |
| Runtime exception | 1 | Network error, API error |
| Max steps reached | 2 | `--max-steps 50` exceeded |
| Session not found | 3 | `-r nonexistent` |
| Session already running | 3 | Resume locked session |
| Missing API key | 4 | No ANTHROPIC_API_KEY |
| Invalid endpoint | 4 | `--endpoint unknown` |
| Ctrl+C | 130 | User interrupt |

---

## 3. Execution Modes

### 3.1 Mode Definitions

Replace `ExecutionMode` enum in `wolo/modes.py`:

```python
class ExecutionMode(Enum):
    """
    Execution mode enumeration.
    
    SOLO: Autonomous execution. AI works independently without asking questions.
          - Keyboard shortcuts: ENABLED (pause, stop)
          - Question tool: DISABLED
          - UI state display: ENABLED
          - Best for: Scripting, automation, batch processing
    
    COOP: Cooperative execution. AI may ask clarifying questions.
          - Keyboard shortcuts: ENABLED
          - Question tool: ENABLED
          - UI state display: ENABLED
          - Best for: Complex tasks requiring user guidance
    
    REPL: Continuous conversation mode.
          - Keyboard shortcuts: ENABLED
          - Question tool: ENABLED
          - UI state display: ENABLED
          - Loops for continuous input
          - Best for: Interactive exploration, debugging
    """
    SOLO = "solo"
    COOP = "coop"
    REPL = "repl"
```

### 3.2 Mode Configuration Matrix

| Feature | SOLO | COOP | REPL |
|---------|------|------|------|
| `enable_keyboard_shortcuts` | True | True | True |
| `enable_question_tool` | **False** | True | True |
| `enable_ui_state` | True | True | True |
| `exit_after_task` | True | True | **False** |
| `auto_save_per_tool` | True | True | True |

### 3.3 Default Mode

**Default is `SOLO`** (changed from current `INTERACTIVE`).

Rationale: Most CLI usage is scripted or single-shot. Users who want interaction explicitly opt-in with `--coop` or use REPL.

---

## 4. CLI Interface Specification

### 4.1 Complete Option List

```
wolo [OPTIONS] [PROMPT]
wolo chat|repl [OPTIONS]
wolo session <SUBCOMMAND>
wolo config <SUBCOMMAND>

EXECUTION MODES:
    --solo              Solo mode: autonomous, no questions (DEFAULT)
    --coop              Coop mode: AI may ask clarifying questions

SESSION OPTIONS:
    -s, --session <NAME>    Create/use named session
    -r, --resume <ID>       Resume existing session (REQUIRES prompt)

QUICK COMMANDS:
    -l, --list              Shortcut for: wolo session list
    -w, --watch <ID>        Shortcut for: wolo session watch <ID>
    -h, --help              Show help

EXECUTION OPTIONS:
    -a, --agent <TYPE>      Agent type: general, plan, explore, compaction
    -e, --endpoint <NAME>   Use configured endpoint
    -m, --model <MODEL>     Override model name
    -n, --max-steps <N>     Maximum steps (default: 100)
    -L, --log-level <LVL>   Log level: DEBUG, INFO, WARNING, ERROR
    -S, --save              Force save session on completion (legacy, now default)

DEBUG OPTIONS:
    --api-key <KEY>         Override API key
    --debug-llm <FILE>      Log LLM requests/responses
    --debug-full <DIR>      Save full JSON request/response
    --benchmark             Enable benchmark mode
    --benchmark-output <F>  Benchmark output file
```

### 4.2 Short Option Mapping

```python
SHORT_OPTIONS = {
    "-s": "--session",
    "-r": "--resume",
    "-l": "--list",
    "-w": "--watch",
    "-S": "--save",
    "-h": "--help",
    "-a": "--agent",
    "-e": "--endpoint",
    "-m": "--model",
    "-L": "--log-level",
    "-n": "--max-steps",
}
```

### 4.3 Options Requiring Values

```python
OPTIONS_NEEDING_VALUE = {
    "--session", "-s",
    "--resume", "-r",
    "--watch", "-w",
    "--agent", "-a",
    "--endpoint", "-e",
    "--model", "-m",
    "--log-level", "-L",
    "--max-steps", "-n",
    "--api-key",
    "--debug-llm",
    "--debug-full",
    "--benchmark-output",
}
```

### 4.4 Removed Options

The following options are **REMOVED**:

| Option | Replacement |
|--------|-------------|
| `--prompt-file <FILE>` | `cat FILE \| wolo ...` |
| `--silent` | `--solo` |
| `--interactive` | `--coop` |
| `--repl` | `wolo chat` or `wolo repl` |

---

## 5. Routing Logic

### 5.1 Command Routing Table

```python
def _route_command(args: list[str], has_stdin: bool) -> tuple[str, list[str]]:
    """
    Route command to appropriate handler.
    
    ROUTING PRIORITY (STRICT ORDER - DO NOT MODIFY):
    1. Help: -h, --help (highest priority)
    2. Quick commands: -l, -w
    3. Subcommands: session, config, debug
    4. REPL entry: chat, repl
    5. Execution: prompt provided (CLI or stdin)
    6. Default: show brief help
    """
```

### 5.2 Routing Decision Tree

```
INPUT: args[], has_stdin

1. IF args[0] in ("-h", "--help") OR args[1] == "-h"/"--help":
   → RETURN ("help", context)

2. IF args[0] == "-l" OR args[0] == "--list":
   → RETURN ("session_list", [])

3. IF args[0] == "-w" OR args[0] == "--watch":
   → REQUIRE args[1] exists
   → RETURN ("session_watch", [args[1]])

4. IF args[0] == "session":
   → RETURN ("session", args[1:])

5. IF args[0] == "config":
   → RETURN ("config", args[1:])

6. IF args[0] == "debug":
   → RETURN ("debug", args[1:])

7. IF args[0] in ("chat", "repl"):
   → RETURN ("repl", args[1:])

8. IF has_stdin OR has_positional_prompt(args):
   → RETURN ("execute", args)

9. ELSE (no args, no stdin):
   → RETURN ("default_help", [])
```

### 5.3 Default Behavior (No Input)

When user runs `wolo` without any arguments or stdin:

```python
def show_brief_help() -> int:
    """Show brief help when no input provided."""
    print("""Wolo - AI Agent CLI

Usage:
  wolo "your prompt"                    Execute a task
  cat file | wolo "analyze this"        Context + prompt
  wolo chat                             Start interactive session
  wolo -r <id> "continue"               Resume session

Quick commands:
  wolo -l                               List sessions
  wolo -w <id>                          Watch running session
  wolo -h                               Full help

Examples:
  wolo "fix the bug in main.py"
  git diff | wolo "write commit message"
  wolo --coop "help me design the API"
""")
    return ExitCode.SUCCESS
```

---

## 6. Dual Input Handling

### 6.1 Input Priority (OLD - REMOVED)

~~Stdin takes priority over CLI prompt~~

### 6.2 New Behavior: Input Concatenation

When BOTH stdin (pipe) AND CLI prompt are provided, concatenate them:

```python
DUAL_INPUT_TEMPLATE = """## Context (from stdin)

{pipe_input}

---

## Task

{user_prompt}
"""
```

### 6.3 Implementation

```python
def combine_inputs(pipe_input: str | None, cli_prompt: str | None) -> tuple[str, bool]:
    """
    Combine pipe input and CLI prompt into final message.
    
    Args:
        pipe_input: Content from stdin (may be None or empty)
        cli_prompt: Content from CLI arguments (may be None or empty)
    
    Returns:
        (combined_message, has_message)
    
    Rules:
        1. Both provided → Concatenate using template
        2. Only pipe → Use pipe content
        3. Only CLI → Use CLI content
        4. Neither → Return ("", False)
    """
    pipe_input = (pipe_input or "").strip()
    cli_prompt = (cli_prompt or "").strip()
    
    if pipe_input and cli_prompt:
        # Both provided - concatenate
        message = DUAL_INPUT_TEMPLATE.format(
            pipe_input=pipe_input,
            user_prompt=cli_prompt
        )
        return (message, True)
    elif pipe_input:
        return (pipe_input, True)
    elif cli_prompt:
        return (cli_prompt, True)
    else:
        return ("", False)
```

### 6.4 Stdin Reading

```python
def read_stdin_if_available() -> str | None:
    """
    Read from stdin if it's a pipe (non-TTY).
    
    For pipes: Block until EOF (writing end closes)
    For TTY: Return None immediately (don't block interactive terminal)
    
    Returns:
        Content string or None
    """
    if sys.stdin.isatty():
        return None
    
    try:
        data = sys.stdin.read()
        return data.strip() if data.strip() else None
    except Exception:
        return None
```

---

## 7. Session Behavior

### 7.1 Session Subcommands

```
wolo session <SUBCOMMAND>

SUBCOMMANDS:
    list                List all sessions with status
    show <ID>           Show session details (non-blocking)
    resume <ID>         Resume session in REPL mode (blocking)
    watch <ID>          Watch running session (read-only)
    delete <ID>         Delete a session
    clean [DAYS]        Clean sessions older than DAYS (default: 30)
```

### 7.2 `session show` vs `session resume`

| Command | Behavior | Blocking | Modifies Session |
|---------|----------|----------|------------------|
| `session show <id>` | Display info, exit | No | No |
| `session resume <id>` | Enter REPL mode | Yes | Yes |

### 7.3 `session show` Output Format

```
$ wolo session show brave-fox

Session: brave-fox
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Agent:     Claude (brave-fox)
  Created:   2026-01-22 14:30:15
  Messages:  12
  Status:    Stopped
  
  Last activity: 2 hours ago
  
  Resume: wolo session resume brave-fox
  Or:     wolo -r brave-fox "your prompt"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 7.4 `session resume` Behavior

```
$ wolo session resume brave-fox

Session: brave-fox
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Agent:     Claude (brave-fox)
  Created:   2026-01-22 14:30:15
  Messages:  12
  Status:    Running (this process)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Entering REPL mode. Type your message and press Enter.
Press Ctrl+C or type /exit to quit.

> _
```

### 7.5 `-r` Quick Resume (Requires Prompt)

```bash
# VALID: Resume with new prompt
wolo -r brave-fox "continue the task"
cat prompt.txt | wolo -r brave-fox

# INVALID: -r without prompt
wolo -r brave-fox
# Error: -r/--resume requires a prompt.
#        Use 'wolo session resume brave-fox' for REPL mode.
#        Or:  'wolo -r brave-fox "your prompt"' for one-shot execution.
```

### 7.6 Session Resume with Pipe

When pipe is used with `session resume`:

```bash
# This enters REPL with initial message from pipe
echo "analyze this" | wolo session resume brave-fox
```

Behavior:
1. Load session
2. Use pipe content as first message
3. Continue in REPL mode

---

## 8. Auto-Save Strategy

### 8.1 Save Points

Sessions are saved at these points (**ALL modes, no exceptions**):

1. **After each tool call completion** (success or failure)
2. **After each assistant message completion**
3. **On Ctrl+C interrupt**
4. **On any error/exception**
5. **On normal completion**

### 8.2 Implementation

```python
async def agent_loop(...):
    """
    Main agent loop.
    
    Auto-save is performed:
    - After every tool call (in tool execution handler)
    - After every assistant response
    - On any exception (in finally block)
    """
    try:
        while not should_stop:
            # ... LLM call ...
            
            # After assistant response
            save_session(session_id)
            
            # Process tool calls
            for tool_call in tool_calls:
                result = await execute_tool(tool_call)
                # After each tool call
                save_session(session_id)
            
    except KeyboardInterrupt:
        save_session(session_id)
        raise
    except Exception:
        save_session(session_id)
        raise
    finally:
        # Final save (redundant but safe)
        save_session(session_id)
```

### 8.3 Save Performance

To avoid performance issues with frequent saves:

```python
class SessionSaver:
    """Debounced session saver."""
    
    MIN_SAVE_INTERVAL = 0.5  # seconds
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.last_save_time = 0
        self.pending_save = False
    
    def save(self, force: bool = False):
        """
        Save session with debouncing.
        
        Args:
            force: If True, save immediately regardless of interval
        """
        now = time.time()
        if force or (now - self.last_save_time) >= self.MIN_SAVE_INTERVAL:
            _do_save(self.session_id)
            self.last_save_time = now
            self.pending_save = False
        else:
            self.pending_save = True
    
    def flush(self):
        """Force save if there's a pending save."""
        if self.pending_save:
            _do_save(self.session_id)
            self.pending_save = False
```

---

## 9. Conflict Detection

### 9.1 Mutually Exclusive Option Groups

```python
MUTUALLY_EXCLUSIVE_GROUPS = [
    # Execution modes (only one allowed)
    {"--solo", "--coop"},
    
    # Session creation vs resume (can't do both)
    {"-s", "--session", "-r", "--resume"},
]
```

### 9.2 Validation Function

```python
def validate_option_conflicts(options: dict) -> tuple[bool, str]:
    """
    Validate that no mutually exclusive options are used together.
    
    Args:
        options: Parsed options dictionary
    
    Returns:
        (is_valid, error_message)
    
    Example:
        >>> validate_option_conflicts({"--solo": True, "--coop": True})
        (False, "Error: --solo and --coop are mutually exclusive")
    """
    for group in MUTUALLY_EXCLUSIVE_GROUPS:
        found = []
        for opt in group:
            # Check both with and without -- prefix
            if opt in options or opt.lstrip("-") in options:
                found.append(opt)
        
        if len(found) > 1:
            return (False, f"Error: {' and '.join(found)} are mutually exclusive")
    
    return (True, "")
```

### 9.3 Context-Specific Validation

```python
def validate_command_context(command_type: str, args: ParsedArgs) -> tuple[bool, str]:
    """
    Validate options in context of the command.
    
    Rules:
        1. -r/--resume requires a prompt (unless in session resume subcommand)
        2. -w/--watch cannot have other execution options
        3. REPL mode cannot accept stdin (interactive by nature)
    """
    # Rule 1: -r requires prompt
    if args.session_options.resume_id:
        if command_type == "execute":
            message, has_message = combine_inputs(
                args.pipe_input, args.cli_prompt
            )
            if not has_message:
                return (False, 
                    "Error: -r/--resume requires a prompt.\n"
                    "       Use 'wolo session resume <id>' for REPL mode.\n"
                    "       Or:  'wolo -r <id> \"your prompt\"' for one-shot execution."
                )
    
    # Rule 2: -w is standalone
    if args.session_options.watch_id:
        if any([args.session_options.resume_id, 
                args.session_options.session_name]):
            return (False, "Error: -w/--watch cannot be combined with -r or -s")
    
    return (True, "")
```

---

## 10. Help System

### 10.1 Help Routing

```python
def show_help(args: ParsedArgs) -> int:
    """
    Show help based on context.
    
    Contexts:
        ["main"]           → Main help
        ["session"]        → Session command help
        ["session", "X"]   → Session subcommand X help
        ["config"]         → Config command help
        ["chat"] / ["repl"] → REPL help
    """
```

### 10.2 Main Help Text

```
Wolo - AI Agent CLI

USAGE:
    wolo [OPTIONS] [PROMPT]
    wolo chat|repl [OPTIONS]
    wolo session <SUBCOMMAND>
    wolo config <SUBCOMMAND>

BASIC USAGE:
    wolo "your prompt"                    Execute task (solo mode)
    cat file | wolo "do X"                Context + prompt
    wolo chat                             Start interactive REPL
    wolo -r <id> "continue"               Resume session with prompt
    wolo session resume <id>              Resume session in REPL

EXECUTION MODES:
    --solo          Solo mode: autonomous, no questions (default)
    --coop          Coop mode: AI may ask clarifying questions

SESSION OPTIONS:
    -s, --session <name>    Create/use named session
    -r, --resume <id>       Resume session (requires prompt)

QUICK COMMANDS:
    -l, --list              List all sessions
    -w, --watch <id>        Watch running session
    -h, --help              Show this help

OTHER OPTIONS:
    -a, --agent <type>      Agent: general, plan, explore, compaction
    -e, --endpoint <name>   Use configured endpoint
    -m, --model <model>     Override model
    -n, --max-steps <n>     Max steps (default: 100)
    -L, --log-level <lvl>   DEBUG, INFO, WARNING, ERROR

EXAMPLES:
    wolo "fix the bug in main.py"
    git diff | wolo "write commit message"
    wolo --coop "design login feature"
    wolo -s myproject "implement auth"
    wolo -r myproject "add tests"

SESSION MANAGEMENT:
    wolo session list               List sessions
    wolo session show <id>          Show session info
    wolo session resume <id>        Resume in REPL mode
    wolo session watch <id>         Watch running session
    wolo session delete <id>        Delete session
    wolo session clean [days]       Clean old sessions

See 'wolo <command> -h' for more information on a command.
```

### 10.3 Chat/REPL Help

```
Wolo REPL - Interactive Conversation Mode

USAGE:
    wolo chat [OPTIONS]
    wolo repl [OPTIONS]

DESCRIPTION:
    Start an interactive REPL session. The agent will respond to each
    message and wait for your next input.

OPTIONS:
    --coop              Enable AI questions (default in REPL)
    -s, --session <n>   Use named session
    -a, --agent <type>  Agent type
    -e, --endpoint <n>  Use endpoint
    -m, --model <m>     Override model
    -n, --max-steps <n> Max steps per turn

REPL COMMANDS:
    /exit, /quit        Exit REPL
    /save               Force save session
    /status             Show session status
    Ctrl+C              Exit REPL

EXAMPLES:
    wolo chat
    wolo repl -s myproject
    wolo chat --agent plan
```

---

## 11. Migration & Deprecation

### 11.1 Deprecated Options

For **2 versions**, show deprecation warnings:

```python
DEPRECATED_OPTIONS = {
    "--silent": ("--solo", "Use --solo instead of --silent"),
    "--interactive": ("--coop", "Use --coop instead of --interactive"),
    "--prompt-file": (None, "Use 'cat FILE | wolo' instead of --prompt-file"),
    "run": (None, "The 'run' command is deprecated. Use 'wolo \"prompt\"' directly."),
}

def check_deprecated(args: list[str]) -> None:
    """Print deprecation warnings for old options."""
    for arg in args:
        if arg in DEPRECATED_OPTIONS:
            new_opt, message = DEPRECATED_OPTIONS[arg]
            print(f"Warning: {message}", file=sys.stderr)
```

### 11.2 Backward Compatibility

During deprecation period:
- `--silent` → Maps to `--solo`
- `--interactive` → Maps to `--coop`
- `wolo run "x"` → Works but shows warning
- `--prompt-file` → Shows error with migration hint

After deprecation period (2 versions):
- Remove all deprecated options
- Remove compatibility mapping

---

## 12. Implementation Tasks

### Phase 1: Core Infrastructure (Priority: HIGH)

#### Task 1.1: Create Exit Codes Module
**File:** `wolo/cli/exit_codes.py` (NEW)

```python
"""
Exit code definitions for Wolo CLI.

Exit Codes:
    0   - SUCCESS: Task completed successfully
    1   - ERROR: General error
    2   - QUOTA_EXCEEDED: Max steps/tokens reached
    3   - SESSION_ERROR: Session issues
    4   - CONFIG_ERROR: Configuration issues
    130 - INTERRUPTED: Ctrl+C
    131 - TERMINATED: SIGTERM
"""

class ExitCode:
    SUCCESS = 0
    ERROR = 1
    QUOTA_EXCEEDED = 2
    SESSION_ERROR = 3
    CONFIG_ERROR = 4
    INTERRUPTED = 130
    TERMINATED = 131
```

**Acceptance Criteria:**
- [ ] File created with all exit codes
- [ ] Docstring documents all codes
- [ ] All commands use ExitCode instead of magic numbers

---

#### Task 1.2: Update ExecutionMode Enum
**File:** `wolo/modes.py`

Changes:
1. Rename `SILENT` → `SOLO`
2. Rename `INTERACTIVE` → `COOP`
3. Update `ModeConfig.for_mode()` accordingly
4. Update docstrings

**Before:**
```python
class ExecutionMode(Enum):
    SILENT = "silent"
    INTERACTIVE = "interactive"
    REPL = "repl"
```

**After:**
```python
class ExecutionMode(Enum):
    """
    Execution mode enumeration.
    
    SOLO: Autonomous execution, no questions asked.
    COOP: Cooperative execution, AI may ask questions.
    REPL: Continuous conversation mode.
    """
    SOLO = "solo"
    COOP = "coop"
    REPL = "repl"
```

**Acceptance Criteria:**
- [ ] Enum values renamed
- [ ] `ModeConfig.for_mode()` updated for new names
- [ ] SOLO config has `enable_question_tool=False`
- [ ] All imports updated

---

#### Task 1.3: Update Parser Options
**File:** `wolo/cli/parser.py`

Changes:
1. Remove `--prompt-file` from OPTIONS_NEEDING_VALUE
2. Remove `prompt_file` from ExecutionOptions
3. Add conflict detection
4. Add dual input handling
5. Update `_apply_options()` for new mode flags

**New Functions:**
```python
def validate_option_conflicts(options: dict) -> tuple[bool, str]: ...
def combine_inputs(pipe_input: str | None, cli_prompt: str | None) -> tuple[str, bool]: ...
```

**Acceptance Criteria:**
- [ ] `--prompt-file` removed
- [ ] `--solo`/`--coop` handling added
- [ ] Conflict detection implemented
- [ ] Dual input concatenation working
- [ ] Default mode is SOLO

---

### Phase 2: Command Updates (Priority: HIGH)

#### Task 2.1: Update Main Router
**File:** `wolo/cli/main.py`

Changes:
1. Add routing for `chat` and `repl` commands
2. Update default behavior (no input → show brief help)
3. Remove `run` from explicit routing (keep as fallback)
4. Add deprecation warnings

**Acceptance Criteria:**
- [ ] `wolo chat` routes to REPL
- [ ] `wolo repl` routes to REPL
- [ ] `wolo` (no args) shows brief help
- [ ] Deprecated options show warnings

---

#### Task 2.2: Add SessionShowCommand
**File:** `wolo/cli/commands/session.py`

Add new `SessionShowCommand` class:

```python
class SessionShowCommand(BaseCommand):
    """wolo session show <id> - Display session info without entering REPL."""
    
    def execute(self, args: ParsedArgs) -> int:
        # Get session_id from args
        # Call get_session_status()
        # Print formatted info (see format in spec)
        # Return ExitCode.SUCCESS or ExitCode.SESSION_ERROR
```

**Acceptance Criteria:**
- [ ] Shows session info in specified format
- [ ] Returns appropriate exit code
- [ ] Includes resume hints in output

---

#### Task 2.3: Update SessionResumeCommand
**File:** `wolo/cli/commands/session.py`

Changes:
1. Remove "show info if no message" behavior
2. Always enter REPL mode
3. Accept pipe input as initial message
4. Show session info header before REPL prompt

**Acceptance Criteria:**
- [ ] `session resume <id>` enters REPL
- [ ] Pipe input becomes first message
- [ ] Session info displayed at start
- [ ] Proper exit handling

---

#### Task 2.4: Update RunCommand for `-r` Validation
**File:** `wolo/cli/commands/run.py`

Changes:
1. Update error message for `-r` without prompt
2. Use new exit codes
3. Remove `--prompt-file` handling

**Acceptance Criteria:**
- [ ] `-r` without prompt shows correct error message
- [ ] Exit codes are correct
- [ ] No prompt-file references

---

### Phase 3: Auto-Save Implementation (Priority: HIGH)

#### Task 3.1: Implement SessionSaver
**File:** `wolo/session.py`

Add `SessionSaver` class with debouncing:

```python
class SessionSaver:
    MIN_SAVE_INTERVAL = 0.5
    
    def __init__(self, session_id: str): ...
    def save(self, force: bool = False): ...
    def flush(self): ...
```

**Acceptance Criteria:**
- [ ] Debounced saves (0.5s minimum interval)
- [ ] `force=True` bypasses debounce
- [ ] `flush()` saves pending changes

---

#### Task 3.2: Update Agent Loop for Auto-Save
**File:** `wolo/agent.py`

Changes:
1. Create SessionSaver at loop start
2. Call `saver.save()` after each tool call
3. Call `saver.save()` after each assistant response
4. Call `saver.save(force=True)` on error/interrupt
5. Call `saver.flush()` in finally block

**Acceptance Criteria:**
- [ ] Save after every tool call
- [ ] Save after every response
- [ ] Force save on exceptions
- [ ] Flush on cleanup

---

### Phase 4: Help System Update (Priority: MEDIUM)

#### Task 4.1: Update Help Texts
**File:** `wolo/cli/help.py`

Changes:
1. Update main help text (as specified)
2. Add chat/repl help
3. Update session help
4. Remove run-specific help (merge into main)
5. Remove prompt-file from examples

**Acceptance Criteria:**
- [ ] All help texts match specification
- [ ] No references to deprecated options
- [ ] Examples use new syntax

---

#### Task 4.2: Add Brief Help Function
**File:** `wolo/cli/help.py`

Add `show_brief_help()` function as specified.

**Acceptance Criteria:**
- [ ] Shows concise help with examples
- [ ] Returns ExitCode.SUCCESS

---

### Phase 5: Testing (Priority: HIGH)

#### Task 5.1: Update CLI Tests
**File:** `wolo/tests/test_cli_*.py`

Update all CLI tests for:
1. New mode names (`--solo`, `--coop`)
2. Dual input handling
3. Conflict detection
4. New session commands
5. Exit codes

**Acceptance Criteria:**
- [ ] All existing tests updated
- [ ] New tests for conflict detection
- [ ] New tests for dual input
- [ ] New tests for session show/resume

---

#### Task 5.2: Add Integration Tests
**File:** `wolo/tests/test_cli_integration.py` (NEW)

Test scenarios:
1. `wolo "prompt"` → executes in SOLO
2. `wolo --coop "prompt"` → executes in COOP
3. `echo "ctx" | wolo "task"` → dual input
4. `wolo -r X "msg"` → resume + execute
5. `wolo session resume X` → enters REPL
6. `wolo --solo --coop` → conflict error
7. `wolo` → brief help

**Acceptance Criteria:**
- [ ] All scenarios have tests
- [ ] Tests verify exit codes
- [ ] Tests verify output format

---

### Phase 6: Cleanup (Priority: LOW)

#### Task 6.1: Remove Deprecated Code
After deprecation period, remove:
- `--silent`/`--interactive` handling
- `--prompt-file` handling
- `run` command routing
- Deprecation warning code

**Acceptance Criteria:**
- [ ] All deprecated code removed
- [ ] No compiler warnings
- [ ] All tests pass

---

## 13. File Change Summary

| File | Action | Changes |
|------|--------|---------|
| `wolo/cli/exit_codes.py` | CREATE | Exit code definitions |
| `wolo/modes.py` | MODIFY | Rename SILENT→SOLO, INTERACTIVE→COOP |
| `wolo/cli/parser.py` | MODIFY | Remove prompt-file, add conflicts, dual input |
| `wolo/cli/main.py` | MODIFY | Add chat/repl routing, default help |
| `wolo/cli/commands/session.py` | MODIFY | Add show, update resume to REPL |
| `wolo/cli/commands/run.py` | MODIFY | Update -r validation, exit codes |
| `wolo/cli/help.py` | MODIFY | All help texts updated |
| `wolo/session.py` | MODIFY | Add SessionSaver class |
| `wolo/agent.py` | MODIFY | Auto-save integration |
| `wolo/tests/test_cli_*.py` | MODIFY | Update all tests |
| `wolo/tests/test_cli_integration.py` | CREATE | New integration tests |

---

## Appendix A: Dual Input Template

```python
DUAL_INPUT_TEMPLATE = """## Context (from stdin)

{pipe_input}

---

## Task

{user_prompt}
"""
```

## Appendix B: Session Show Output Format

```
Session: {session_id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Agent:     {agent_display_name}
  Created:   {created_at:%Y-%m-%d %H:%M:%S}
  Messages:  {message_count}
  Status:    {Running (PID: X) | Stopped}
  
  Last activity: {relative_time}
  
  Resume: wolo session resume {session_id}
  Or:     wolo -r {session_id} "your prompt"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Appendix C: Error Message Templates

```python
ERROR_MESSAGES = {
    "resume_no_prompt": (
        "Error: -r/--resume requires a prompt.\n"
        "       Use 'wolo session resume {id}' for REPL mode.\n"
        "       Or:  'wolo -r {id} \"your prompt\"' for one-shot execution."
    ),
    "conflict_mode": "Error: --solo and --coop are mutually exclusive",
    "conflict_session": "Error: -s/--session and -r/--resume are mutually exclusive",
    "session_not_found": "Error: Session '{id}' not found",
    "session_running": (
        "Error: Session '{id}' is already running (PID: {pid})\n"
        "       Use 'wolo -w {id}' to watch it."
    ),
}
```

---

**END OF SPECIFICATION**
