# CLI Comprehensive Test Suite

## Overview

This test suite (`test_cli_comprehensive.py`) provides comprehensive coverage of the Wolo CLI, testing all parameter combinations, edge cases, and usage scenarios.

## Test Coverage

### 1. Basic Command Tests

#### RunCommand Basic Tests
- ✅ Command name and description
- ✅ Validation with/without messages
- ✅ REPL mode message requirements

#### ReplCommand Tests
- ✅ Command name
- ✅ Validation (always passes)
- ✅ With/without initial message

#### SessionCommandGroup Tests
- ✅ Command name
- ✅ All subcommands (list, create, resume, watch, delete, info)

### 2. Session Options Tests

- ✅ Resume without message (should fail)
- ✅ Resume with message (should pass)
- ✅ Watch in run command (should error)
- ✅ Session name with message
- ✅ Auto-generate session name (empty string)

### 3. Execution Mode Tests

- ✅ Silent mode with message
- ✅ Silent mode without message (should fail)
- ✅ Interactive mode with message
- ✅ Interactive mode without message (should fail)
- ✅ REPL mode (message optional)
- ✅ All modes with various parameters

### 4. Agent Type Tests

- ✅ All agent types: general, plan, explore, compaction
- ✅ Agent type with different modes
- ✅ Invalid agent type handling

### 5. Other Options Tests

- ✅ Prompt file input
- ✅ Max steps configuration
- ✅ Save session flag
- ✅ Benchmark mode flag
- ✅ Debug options

### 6. Parameter Combination Tests

- ✅ Basic run with all options
- ✅ Resume with all options
- ✅ Silent mode with save
- ✅ Interactive mode with benchmark
- ✅ REPL mode with session name
- ✅ Prompt file with session name
- ✅ Max steps with different modes
- ✅ Agent type with different modes

### 7. Edge Cases Tests

- ✅ Empty message string
- ✅ Whitespace-only message
- ✅ Very long message (10KB)
- ✅ Max steps = 0
- ✅ Max steps negative
- ✅ Max steps very large
- ✅ Resume with empty session ID
- ✅ Session name with special characters
- ✅ Multiple mode flags handling

### 8. Input Method Tests

- ✅ Positional message argument
- ✅ Stdin input
- ✅ Prompt file input
- ✅ Prompt file priority over message

### 9. Integration Scenarios Tests

- ✅ Workflow: Create session, run task
- ✅ Workflow: Resume and continue
- ✅ Workflow: Silent automation
- ✅ Workflow: REPL conversation
- ✅ Workflow: Benchmark testing
- ✅ Workflow: Debug mode

### 10. Error Handling Tests

- ✅ Invalid agent type validation
- ✅ Resume workflow validation
- ✅ Session creation workflow validation
- ✅ Auto session workflow validation

### 11. Parameter Parsing Edge Cases

- ✅ Session name with spaces
- ✅ Resume ID with path separators (security)
- ✅ Prompt file with relative path
- ✅ Prompt file with absolute path

### 12. Coverage Verification Tests

- ✅ All execution modes covered
- ✅ All session options covered

## Test Statistics

- **Total Tests**: 71
- **Test Classes**: 12
- **Coverage Areas**: 12 major categories

## Running the Tests

```bash
# Run all comprehensive tests
uv run pytest wolo/tests/test_cli_comprehensive.py -v

# Run specific test class
uv run pytest wolo/tests/test_cli_comprehensive.py::TestRunCommandBasic -v

# Run with coverage
uv run pytest wolo/tests/test_cli_comprehensive.py --cov=wolo.cli.commands --cov-report=term
```

## Test Organization

Tests are organized into logical groups:

1. **Basic Tests**: Fundamental command functionality
2. **Option Tests**: Individual parameter testing
3. **Combination Tests**: Multiple parameters together
4. **Edge Cases**: Boundary conditions and unusual inputs
5. **Integration Tests**: Real-world usage scenarios
6. **Error Handling**: Failure cases and validation

## Key Testing Principles

1. **Comprehensive Coverage**: Test all parameter combinations
2. **Edge Cases**: Test boundary conditions and unusual inputs
3. **Real Scenarios**: Test realistic usage workflows
4. **Error Handling**: Verify proper error messages and validation
5. **Isolation**: Each test is independent and can run alone

## Future Enhancements

Potential areas for additional testing:

- [ ] End-to-end integration tests with actual LLM calls (mocked)
- [ ] Performance tests for large inputs
- [ ] Concurrent session tests
- [ ] File system permission tests
- [ ] Network error handling tests
- [ ] Unicode and internationalization tests

## Notes

- Tests use mocks where appropriate to avoid external dependencies
- File operations use temporary directories
- Tests are designed to be fast and isolated
- All tests should pass before merging code changes
