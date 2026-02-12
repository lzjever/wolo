# E2E Tests for Wolo

End-to-end tests that run Wolo in solo mode with real LLM API calls.

## Running Tests

### Prerequisites

1. Valid LLM configuration in `~/.wolo/config.yaml`
2. Set environment variable to enable e2e tests:

```bash
export WOLO_E2E_TESTS=1
```

### Run All E2E Tests

```bash
# Run all e2e tests
WOLO_E2E_TESTS=1 pytest tests/e2e/ -v --tb=short

# Run specific test class
WOLO_E2E_TESTS=1 pytest tests/e2e/test_e2e_solo_tasks.py::TestFileOperations -v

# Run specific test
WOLO_E2E_TESTS=1 pytest tests/e2e/test_e2e_solo_tasks.py::TestFileOperations::test_create_and_read_file -v
```

### Run with Increased Timeout

Some tests may need more time depending on LLM response speed:

```bash
# Increase pytest timeout
WOLO_E2E_TESTS=1 pytest tests/e2e/ -v --timeout=300
```

## Test Categories

| Category | Description | Tests |
|----------|-------------|-------|
| `TestFileOperations` | File creation, editing | 3 |
| `TestCodeAnalysis` | Code reading and analysis | 1 |
| `TestShellOperations` | Shell command execution | 2 |
| `TestSearchOperations` | File/content search | 1 |
| `TestMultiStepTasks` | Complex multi-step tasks | 1 |
| `TestMemoryOperations` | Memory save functionality | 1 |
| `TestErrorHandling` | Error handling scenarios | 1 |

## Test Tasks Summary

### Easy Tasks
- Create a simple text file
- List directory contents
- Search for text in files

### Medium Tasks
- Create and run a Python script
- Edit an existing file
- Analyze Python code and answer questions
- Create directory structure

### Harder Tasks
- Create a complete Python project with multiple files
- Verify the project runs correctly

## Adding New Tests

When adding new e2e tests:

1. Create test methods that are self-contained
2. Use `tmp_path` fixture for isolated test directories
3. Set appropriate timeouts (default 120s, increase for complex tasks)
4. Assert on concrete file/behavior outcomes, not on LLM output text
5. Skip tests gracefully if dependencies missing

Example:

```python
def test_my_new_feature(self, tmp_path: Path):
    """Task: Description of what to test."""
    prompt = "Your prompt to wolo"

    exit_code, stdout, stderr = run_wolo(prompt, tmp_path)

    assert exit_code == 0, f"Wolo failed: {stderr}"
    # Verify expected outcomes
    assert (tmp_path / "expected_file.txt").exists()
```
