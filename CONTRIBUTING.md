# Contributing to Wolo

Thank you for your interest in contributing to Wolo! This document provides guidelines and instructions for contributing.

## Code Style

We follow PEP 8 style guidelines with a few modifications:

- Use 4 spaces for indentation (no tabs)
- Maximum line length: 100 characters
- Use `const` over `let` when possible (avoid mutation)
- Prefer early returns over complex if/else chains
- Avoid unnecessary destructuring
- Keep logic in single functions unless composable/reusable

### Type Hints

All functions should have type hints for parameters and return values:

```python
async def my_function(param1: str, param2: int) -> dict[str, Any]:
    """Brief description of what this function does."""
    # Implementation
```

### Docstrings

Use Google-style docstrings:

```python
def agent_loop(config: Config, session_id: str) -> Message:
    """Run the main agent execution loop.

    Args:
        config: Agent configuration
        session_id: Session ID to process

    Returns:
        The final assistant message

    Raises:
        ValueError: If session_id is not found
    """
```

## Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/wolo.git
   cd wolo
   ```
3. Install development dependencies:
   ```bash
   make dev-install
   ```

## Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov
```

## Code Quality Checks

Before submitting a PR, run:

```bash
# Format code
make format

# Run linting
make lint

# Run all checks
make check
```

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements

### Examples

```
feat(agent): Add subagent delegation support

fix(tools): Correct shell command timeout handling

docs(readme): Update installation instructions

test(metrics): Add tests for StepMetrics class
```

## Pull Request Process

1. Create a branch from `dev`:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/my-feature
   ```

2. Make your changes and commit using conventional commit format

3. Run tests and code quality checks:
   ```bash
   make check
   ```

4. Push to your fork and submit a pull request

5. Ensure your PR description:
   - References any related issues
   - Describes the changes
   - Includes screenshots for UI changes (if applicable)

## Testing Guidelines

- Write tests for new features
- Maintain test coverage above 80%
- Add unit tests in `wolo/tests/test_*.py`
- Use descriptive test names that explain what is being tested

```python
def test_session_metrics_records_tool_errors():
    """Test that session metrics correctly record tool errors."""
    session = SessionMetrics(session_id="test", agent_type="general", start_time=datetime.now())
    session.record_tool_error("read", "file_not_found")

    assert session.tool_errors == 1
    assert session.errors_by_category == {"file_not_found": 1}
```

## Adding New Tools

When adding a new tool:

1. Add tool definition in `wolo/tools.py`
2. Add execute function following the pattern:
   ```python
   async def mytool_execute(param1: str, param2: int) -> dict[str, Any]:
       """Execute my tool."""
       # Implementation
       return {
           "title": "mytool: ...",
           "output": "...",
           "metadata": {...}
       }
   ```
3. Add tool schema constant
4. Wire up in `execute_tool()` function
5. Add tests for the new tool

## Questions?

Feel free to open an issue for questions or discussion about contributions.
