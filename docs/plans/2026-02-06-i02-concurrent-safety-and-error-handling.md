# I02@A02: Concurrent Safety and Error Handling Improvements

**Status:** Design Approved
**Based on:** A01 Review Findings
**Scope:** P0 + P1 Issues (Global State, Error Handling, Testing)

## Overview

This document outlines the improvements for I02@A02, addressing critical and high-priority issues identified in the A01 code review. The design focuses on three key areas:

1. **Concurrent Safety (P0)** - Replace global state with thread-safe `contextvars`
2. **Error Handling (P1)** - Standardize with custom exception hierarchy
3. **Security & Testing (P1)** - Environment variable priority for API keys, 70%+ test coverage

## Architecture

The I02@A02 improvements maintain Wolo's existing layered architecture while introducing three new subsystems:

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│                    (wolo/cli/main.py)                       │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Execution Layer                          │
│                  (wolo/execution.py)                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                     Agent Layer                             │
│               (wolo/agent.py, llm_adapter.py)               │
│                      Uses Context-State                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                      Tools Layer                            │
│              (wolo/tools.py, wolo/tool_registry.py)         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    NEW SUBSYSTEMS                           │
├─────────────────────────────────────────────────────────────┤
│  1. Context-State (wolo/context_state/)                     │
│     - Thread-safe, task-local storage via contextvars       │
│     - Replaces: _api_token_usage, _doom_loop_history, _todos│
│                                                              │
│  2. Exception Hierarchy (wolo/exceptions.py)                │
│     - WoloError base with subclasses                        │
│     - Replaces: bare except Exception catches               │
│                                                              │
│  3. Security-First Config (modifies wolo/config.py)         │
│     - Environment variables take precedence                 │
│     - Fallback to config file with warning                  │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Context-State Subsystem

**Location:** `wolo/context_state/`

**Purpose:** Provide thread-safe, task-local storage for session-specific state.

**Structure:**
```
wolo/context_state/
├── __init__.py       # Public API, backward-compatible accessors
├── vars.py           # ContextVar definitions
└── _init.py          # Initialization functions
```

**Public API:**
```python
# Token usage tracking
def get_api_token_usage() -> TokenUsage
def reset_api_token_usage()

# Doom loop detection
def get_doom_loop_history() -> list[str]
def add_doom_loop_entry(entry: str)
def clear_doom_loop_history()

# Session todos
def get_session_todos() -> list[Todo]
def set_session_todos(todos: list[Todo])
```

### 2. Exception Hierarchy

**Location:** `wolo/exceptions.py`

**Purpose:** Provide specific, catchable exception types with structured metadata.

**Hierarchy:**
```python
WoloError(Exception)
├── WoloConfigError      # Configuration/credential issues
├── WoloToolError        # Tool execution failures
├── WoloSessionError     # Session lifecycle issues
├── WoloLLMError         # LLM API communication failures
└── WoloPathSafetyError  # Path validation failures
```

**Base Exception:**
```python
class WoloError(Exception):
    """Base exception for all Wolo errors."""

    def __init__(self, message: str, session_id: str | None = None, **context):
        super().__init__(message)
        self.session_id = session_id
        self.context = context
```

### 3. Security-First Config

**Location:** Modifies `wolo/config.py`

**Priority Order:**
1. Environment variables (`WOLO_API_KEY`, `GLM_API_KEY`)
2. Config file (fallback, with warning)
3. Direct mode (`--api-key` flag)

**Changes:**
- Log warning when reading API key from config file
- Update documentation to recommend env vars for production
- Add config validation for missing credentials

## Data Flow

### Session Initialization
```
1. Session start (session.py)
   ↓
2. Initialize context vars (context_state._init)
   ↓
3. Agent loop runs (agent.py)
   ↓
4. Token usage tracked via get_api_token_usage()
   ↓
5. Doom loop detection via get_doom_loop_history()
```

### Error Propagation
```
1. Error occurs in tool/LLM
   ↓
2. Specific exception raised (WoloToolError, WoloLLMError, etc.)
   ↓
3. Exception bubbles up with metadata
   ↓
4. CLI catches and displays user-friendly message
```

## Implementation Strategy

### Phase 1: Foundation (Error Hierarchy)
- Create `wolo/exceptions.py` with full exception hierarchy
- Add unit tests for each exception type
- **Risk:** Low - New module, no existing code changes

### Phase 2: Context-State Infrastructure
- Create `wolo/context_state/` module with ContextVar definitions
- Add accessor functions maintaining backward compatibility
- Add unit tests for context isolation
- **Risk:** Low - New module, backward-compatible API

### Phase 3: Integration - Replace Global State
- Update `wolo/llm_adapter.py` to use context-state for token usage
- Update `wolo/agent.py` to use context-state for doom loop history
- Update `wolo/session.py` to use context-state for todos
- Add integration tests verifying concurrent safety
- **Risk:** Medium - Core module changes, requires careful testing

### Phase 4: Error Handling Migration
- Replace bare `except Exception` with specific exception types
- Update CLI to handle new exception types gracefully
- Add tests for error paths
- **Risk:** Medium - Changes error handling behavior

### Phase 5: Security & Testing
- Update config.py to prioritize environment variables
- Add integration tests for core workflows
- Run coverage analysis, target 70%+
- **Risk:** Low - Config behavior change, test additions

## Testing Strategy

### New Test Files

**Integration Tests:**
1. `tests/integration/test_agent_loop.py` - End-to-end agent execution
2. `tests/integration/test_session_lifecycle.py` - Session management
3. `tests/integration/test_error_handling.py` - Error propagation
4. `tests/integration/test_concurrent_sessions.py` - Concurrent isolation

**Unit Tests:**
1. `tests/unit/test_context_state.py` - Context state isolation
2. `tests/unit/test_exceptions.py` - Exception hierarchy

### Coverage Targets
- `wolo/exceptions.py`: 95%+
- `wolo/context_state/`: 90%+
- `wolo/agent.py`: 70%+
- `wolo/llm_adapter.py`: 70%+
- `wolo/session.py`: 70%+
- **Overall: 70%+**

### Testing Tools
- `pytest-asyncio` for async tests
- `pytest-xdist` for concurrent isolation tests
- `pytest-cov` for coverage reporting

## Risk Mitigation

### High-Risk Areas

| Risk | Mitigation | Rollback |
|------|------------|----------|
| ContextVar isolation edge cases | Comprehensive concurrent tests | Keep old globals as fallback |
| Error handling changes miss errors | Logging at catch sites | Gradual migration with safety net |
| Config behavior breaks workflows | Deprecation warning | Revert priority order |
| Test coverage regression | CI fails if coverage < 65% | Block merge if not met |

## Success Criteria

### Functional Requirements
- ✅ Multiple Wolo sessions run simultaneously without state interference
- ✅ Token usage tracking isolated per session
- ✅ Doom loop history isolated per session
- ✅ All bare `except Exception` catches replaced with specific types
- ✅ CLI displays user-friendly error messages for each error type
- ✅ Environment variables take precedence over config file for API keys
- ✅ Overall test coverage: 70%+

### Non-Functional Requirements
- ✅ No measurable performance degradation from ContextVar usage
- ✅ Existing function signatures unchanged (backward compatibility)
- ✅ All new code documented with docstrings

## Files Modified

### New Files
- `wolo/exceptions.py`
- `wolo/context_state/__init__.py`
- `wolo/context_state/vars.py`
- `wolo/context_state/_init.py`
- `tests/unit/test_exceptions.py`
- `tests/unit/test_context_state.py`
- `tests/integration/test_agent_loop.py`
- `tests/integration/test_session_lifecycle.py`
- `tests/integration/test_error_handling.py`
- `tests/integration/test_concurrent_sessions.py`

### Modified Files
- `wolo/llm_adapter.py` - Use context-state for token usage
- `wolo/agent.py` - Use context-state for doom loop history
- `wolo/session.py` - Use context-state for todos
- `wolo/config.py` - Prioritize environment variables
- `wolo/cli/main.py` - Handle new exception types
- `wolo/tools.py` - Raise specific exceptions
- `wolo/tool_registry.py` - Raise specific exceptions
- `CLAUDE.md` - Update documentation
- `README.md` - Update API key usage examples

## Next Steps

1. Create detailed implementation plan using `superpowers:writing-plans`
2. Set up git worktree for isolated development
3. Execute implementation following the 5-phase strategy
4. Run full test suite and verify 70%+ coverage
5. Code review and merge
