# PathGuard Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close current PathGuard protection gaps so all file-write tools enforce consistent directory safety and denial semantics.

**Architecture:** Keep PathGuard as the single path-policy engine, and route every write-capable tool through it. Add missing runtime controls (confirmation cap + denial audit), align CLI/docs with real behavior, and make denial states explicit in tool outcomes. Keep changes incremental and test-first.

**Tech Stack:** Python 3.14, pytest, existing Wolo CLI/tool executor architecture, PathGuard modules.

## Scope

- In scope:
  - `multiedit` path protection bypass
  - denial status/metadata consistency
  - CLI/documentation mismatch around `--allow-path/-P`
  - `max_confirmations_per_session` and `audit_denied` runtime enforcement
  - remove dead/duplicate init path
- Out of scope in this plan:
  - full shell command AST parsing for filesystem writes
  - OS-level sandboxing

## Task 1: Add CLI allow-path support (or remove from docs) and lock behavior with tests

**Files:**
- Modify: `wolo/cli/parser.py`
- Modify: `wolo/cli/help.py`
- Modify: `wolo/cli/path_guard.py`
- Modify: `wolo/cli/commands/run.py`
- Modify: `wolo/cli/commands/repl.py`
- Modify: `wolo/cli/commands/session.py`
- Test: `tests/unit/test_cli_allow_path.py` (new)

**Step 1: Write failing parser tests**

```python
def test_parse_allow_path_long_and_short():
    parser = FlexibleArgumentParser()
    args = parser.parse(["-P", "/workspace", "--allow-path", "/data", "task"], check_stdin=False)
    assert args.execution_options.allow_paths == ["/workspace", "/data"]
```

**Step 2: Run tests to verify failure**

Run: `pytest -q -o addopts='' tests/unit/test_cli_allow_path.py`
Expected: FAIL with missing `allow_paths` parsing support.

**Step 3: Implement minimal parser + propagation**

- Add `allow_paths: list[str]` to `ExecutionOptions`.
- Add `--allow-path` and `-P` to parser option tables and multi-value option handling.
- Pass parsed allow paths into `initialize_path_guard_for_session(..., cli_paths=...)` in all three command entrypoints.

**Step 4: Re-run tests**

Run: `pytest -q -o addopts='' tests/unit/test_cli_allow_path.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add wolo/cli/parser.py wolo/cli/help.py wolo/cli/path_guard.py wolo/cli/commands/run.py wolo/cli/commands/repl.py wolo/cli/commands/session.py tests/unit/test_cli_allow_path.py
git commit -m "feat(path-safety): add --allow-path/-P CLI support and propagation"
```

## Task 2: Enforce PathGuard for `multiedit`

**Files:**
- Modify: `wolo/tools_pkg/executor.py`
- Modify: `wolo/tools_pkg/file_write.py` (only if helper refactor is needed)
- Test: `tests/path_safety/test_executor_multiedit_guard.py` (new)

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_multiedit_denied_for_unallowed_path(...):
    # initialize middleware without allowing /workspace
    # execute tool "multiedit" targeting /workspace/a.py
    # assert denial metadata
```

**Step 2: Verify RED**

Run: `pytest -q -o addopts='' tests/path_safety/test_executor_multiedit_guard.py`
Expected: FAIL because current `multiedit` path bypasses guard.

**Step 3: Implement minimal fix**

- In `multiedit` branch of executor, iterate edits and call `execute_with_path_guard(edit_execute, ...)` per file.
- Preserve per-file output summary and accumulate success/failure counts.
- Map `SessionCancelled` to `WoloPathSafetyError` consistently (same as `write/edit`).

**Step 4: Verify GREEN**

Run: `pytest -q -o addopts='' tests/path_safety/test_executor_multiedit_guard.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add wolo/tools_pkg/executor.py tests/path_safety/test_executor_multiedit_guard.py
git commit -m "fix(path-safety): route multiedit through PathGuard"
```

## Task 3: Normalize denial semantics (status + metadata)

**Files:**
- Modify: `wolo/tools_pkg/executor.py`
- Test: `tests/path_safety/test_denial_status_semantics.py` (new)

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_write_denial_sets_error_status(...):
    # unsafe write denied by strategy
    # assert tool_part.status == "error"
```

**Step 2: Verify RED**

Run: `pytest -q -o addopts='' tests/path_safety/test_denial_status_semantics.py`
Expected: FAIL because denied writes currently end as `completed`.

**Step 3: Implement minimal fix**

- After guarded call for `write/edit/multiedit`, if `result["metadata"]["error"]` starts with `path_`, set `tool_part.status = "error"` and preserve output.
- Keep non-path tool errors unchanged.

**Step 4: Verify GREEN**

Run: `pytest -q -o addopts='' tests/path_safety/test_denial_status_semantics.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add wolo/tools_pkg/executor.py tests/path_safety/test_denial_status_semantics.py
git commit -m "fix(path-safety): mark guarded path denials as tool errors"
```

## Task 4: Implement confirmation cap and denial audit logging

**Files:**
- Modify: `wolo/path_guard/cli_strategy.py`
- Modify: `wolo/tools_pkg/path_guard_executor.py`
- Modify: `wolo/cli/path_guard.py`
- Modify: `wolo/config.py` (wire existing fields into runtime)
- Test: `tests/path_safety/test_cli_strategy_limits_audit.py` (new)

**Step 1: Write failing tests**

```python
async def test_confirmations_exceed_limit_auto_deny(...)
async def test_denied_operation_writes_audit_log(...)
```

**Step 2: Verify RED**

Run: `pytest -q -o addopts='' tests/path_safety/test_cli_strategy_limits_audit.py`
Expected: FAIL (limit/audit not enforced yet).

**Step 3: Implement minimal runtime wiring**

- Extend `CLIConfirmationStrategy` constructor with:
  - `max_confirmations_per_session: int | None`
  - `audit_denied: bool`
  - `audit_log_file: Path | None`
- Track confirmation count in strategy instance.
- When denied (interactive or non-interactive), append structured log line to audit file when enabled.
- Inject config values at strategy creation time in `initialize_path_guard_middleware(...)`.

**Step 4: Verify GREEN**

Run: `pytest -q -o addopts='' tests/path_safety/test_cli_strategy_limits_audit.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add wolo/path_guard/cli_strategy.py wolo/tools_pkg/path_guard_executor.py wolo/cli/path_guard.py wolo/config.py tests/path_safety/test_cli_strategy_limits_audit.py
git commit -m "feat(path-safety): enforce confirmation cap and denial audit logging"
```

## Task 5: Align confirmation semantics and docs

**Files:**
- Modify: `docs/PATH_SAFETY.md`
- Modify: `wolo/path_guard/cli_strategy.py` (if semantic change is chosen)
- Test: `tests/path_safety/test_cli_strategy.py` (update existing)

**Step 1: Choose one canonical behavior**

- Option A: Keep current code behavior (Y confirms directory scope) and update docs.
- Option B: Implement true single-operation approval for Y and keep docs as-is.

**Step 2: Write/adjust failing tests for selected option**

Run: `pytest -q -o addopts='' tests/path_safety/test_cli_strategy.py`
Expected: FAIL before implementation/docs alignment.

**Step 3: Implement selected option minimally**

- If A: update docs language and prompts.
- If B: add ephemeral single-path approval flow without directory promotion on `Y`.

**Step 4: Verify tests**

Run: `pytest -q -o addopts='' tests/path_safety/test_cli_strategy.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/PATH_SAFETY.md wolo/path_guard/cli_strategy.py tests/path_safety/test_cli_strategy.py
git commit -m "docs(path-safety): align confirmation semantics with implementation"
```

## Task 6: Remove dead initialization path and consolidate entrypoint

**Files:**
- Modify: `wolo/cli/main.py`
- Test: `tests/path_safety/test_cli_path_guard_helper.py` (reuse/extend)

**Step 1: Write failing regression test (if needed)**

- Assert command entrypoint still initializes middleware through active helper.

**Step 2: Verify RED**

Run: `pytest -q -o addopts='' tests/path_safety/test_cli_path_guard_helper.py`
Expected: RED only if additional guard is introduced.

**Step 3: Implement cleanup**

- Remove unused `_initialize_path_guard` in `wolo/cli/main.py` or delegate it to `wolo/cli/path_guard.py` and call from one place only.
- Ensure no duplicate init paths remain.

**Step 4: Verify GREEN**

Run: `pytest -q -o addopts='' tests/path_safety/test_cli_path_guard_helper.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add wolo/cli/main.py wolo/cli/path_guard.py tests/path_safety/test_cli_path_guard_helper.py
git commit -m "refactor(path-safety): remove dead PathGuard init path"
```

## Final Verification Matrix

Run in order:

1. `pytest -q -o addopts='' tests/path_safety/test_checker.py`
2. `pytest -q -o addopts='' tests/path_safety/test_middleware.py`
3. `pytest -q -o addopts='' tests/path_safety/test_cli_strategy.py`
4. `pytest -q -o addopts='' tests/path_safety/test_session_persistence.py`
5. `pytest -q -o addopts='' tests/path_safety/test_cli_path_guard_helper.py`
6. `pytest -q -o addopts='' tests/path_safety/test_executor_multiedit_guard.py`
7. `pytest -q -o addopts='' tests/path_safety/test_denial_status_semantics.py`
8. `pytest -q -o addopts='' tests/path_safety/test_cli_strategy_limits_audit.py`
9. `python -m compileall -q wolo`

Expected:
- All tests pass.
- No `PathGuard middleware not initialized` regression.
- `multiedit` unsafe path operations are denied or require explicit confirmation.
- Denials surface as `error` status, not false `completed`.

## Rollback Plan

- Revert each task commit independently with `git revert <commit>`.
- If Task 4 (limit/audit) causes runtime friction, revert only that commit first.
- Keep Task 2 (`multiedit` guard) as non-negotiable baseline security fix.

## Decision Gates

- Gate A (Task 5): choose `Y` semantics (single op vs directory-scope).
- Gate B (optional follow-up): whether to add strict shell policy in a separate plan (`path_safety.strict_shell=true` -> deny shell tool by default).

## Related Skills for Execution

- `@superpowers:test-driven-development`
- `@superpowers:systematic-debugging`
- `@superpowers:verification-before-completion`
- `@superpowers:requesting-code-review`

