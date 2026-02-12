"""E2E tests for Wolo session continuity.

Tests that verify wolo can maintain context and state across multiple
invocations using the same session (-r/--resume or -s/--session).

Run with:
    WOLO_E2E_TESTS=1 pytest tests/e2e/test_e2e_session_continuity.py -v --tb=short
"""

import os
import subprocess
import time
from pathlib import Path

import pytest

# Skip all tests if E2E_TESTS is not set
pytestmark = pytest.mark.skipif(
    os.environ.get("WOLO_E2E_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set WOLO_E2E_TESTS=1 to run e2e tests (requires LLM API calls)",
)

# Timeout for each wolo call (seconds)
E2E_TIMEOUT = 120


def run_wolo(
    prompt: str,
    workdir: Path,
    session_id: str | None = None,
    is_resume: bool = False,
    timeout: int = E2E_TIMEOUT,
) -> tuple[int, str, str]:
    """Run wolo and return (exit_code, stdout, stderr).

    Args:
        prompt: The prompt to send to wolo
        workdir: Working directory for the command
        session_id: Optional session ID to create or resume
        is_resume: If True, use -r (resume); if False with session_id, use -s (create)
        timeout: Timeout in seconds

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    cmd = ["uv", "run", "wolo", "--wild", "--workdir", str(workdir)]
    if session_id:
        if is_resume:
            cmd.extend(["-r", session_id])
        else:
            cmd.extend(["-s", session_id])
    cmd.append(prompt)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=Path(__file__).parent.parent.parent,  # Project root
    )

    return result.returncode, result.stdout, result.stderr


def extract_session_id(stdout: str) -> str | None:
    """Extract session ID from wolo output if present."""
    import re

    # Look for session ID patterns in output
    # Pattern 1: "Session: xxx" or "session_id: xxx"
    match = re.search(r"(?:session|Session)[\s:_]+([A-Za-z0-9_]+)", stdout)
    if match:
        return match.group(1)
    return None


class TestSessionContinuity:
    """Test session continuity across multiple wolo invocations."""

    def test_context_retention_across_calls(self, tmp_path: Path):
        """Test that wolo remembers information from previous calls in same session."""
        session_id = f"ctx_test_{int(time.time())}"

        # Step 1: Tell wolo some information to remember (create new session)
        prompt1 = """Create a file called 'secret.txt' with the content 'The secret code is BANANA-42'.
Do not mention this in any other file."""

        exit_code, stdout, stderr = run_wolo(prompt1, tmp_path, session_id, is_resume=False)
        assert exit_code == 0, f"First call failed: {stderr}"

        # Verify file was created
        secret_file = tmp_path / "secret.txt"
        assert secret_file.exists(), "secret.txt was not created"
        assert "BANANA-42" in secret_file.read_text()

        time.sleep(1)  # Brief pause between calls

        # Step 2: Ask wolo to recall the information (resume session)
        prompt2 = """Read the file 'secret.txt' and create a file called 'recall.txt'
containing ONLY the secret code (nothing else)."""

        exit_code, stdout, stderr = run_wolo(prompt2, tmp_path, session_id, is_resume=True)
        assert exit_code == 0, f"Second call failed: {stderr}"

        # Verify recall
        recall_file = tmp_path / "recall.txt"
        assert recall_file.exists(), "recall.txt was not created"
        assert "BANANA-42" in recall_file.read_text(), (
            f"Secret code not found in recall.txt: {recall_file.read_text()}"
        )

    def test_progressive_task_completion(self, tmp_path: Path):
        """Test that wolo can complete a task progressively across multiple calls."""
        session_id = f"prog_test_{int(time.time())}"

        # Step 1: Create initial structure
        prompt1 = """Create a directory called 'myapp' with an empty file '__init__.py' inside."""

        exit_code, stdout, stderr = run_wolo(prompt1, tmp_path, session_id, is_resume=False)
        assert exit_code == 0, f"Step 1 failed: {stderr}"
        assert (tmp_path / "myapp" / "__init__.py").exists()

        time.sleep(1)

        # Step 2: Add a module to the existing structure
        prompt2 = """Add a new file 'myapp/utils.py' with a function called 'greet(name)'
that returns f"Hello, {name}!" """

        exit_code, stdout, stderr = run_wolo(prompt2, tmp_path, session_id, is_resume=True)
        assert exit_code == 0, f"Step 2 failed: {stderr}"
        assert (tmp_path / "myapp" / "utils.py").exists()

        time.sleep(1)

        # Step 3: Create a test file that uses the module
        prompt3 = """Create a file 'test_utils.py' in the root directory that:
1. Imports greet from myapp.utils
2. Calls greet("World")
3. Prints the result
4. Make it runnable as a script"""

        exit_code, stdout, stderr = run_wolo(prompt3, tmp_path, session_id, is_resume=True)
        assert exit_code == 0, f"Step 3 failed: {stderr}"
        assert (tmp_path / "test_utils.py").exists()

        # Verify the whole thing works
        result = subprocess.run(
            ["python", str(tmp_path / "test_utils.py")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "Hello, World" in result.stdout, (
            f"Expected 'Hello, World' in output, got: {result.stdout}"
        )

    def test_conversation_memory(self, tmp_path: Path):
        """Test that wolo remembers conversation context across calls."""
        session_id = f"conv_test_{int(time.time())}"

        # Step 1: Establish a context/role
        prompt1 = """You are helping me build a library management system.
Create a file 'book.py' with a Book class that has:
- title (str)
- author (str)
- isbn (str)
- A method is_available() that returns True"""

        exit_code, stdout, stderr = run_wolo(prompt1, tmp_path, session_id, is_resume=False)
        assert exit_code == 0, f"Step 1 failed: {stderr}"

        book_file = tmp_path / "book.py"
        assert book_file.exists(), "book.py was not created"
        content = book_file.read_text()
        assert "Book" in content and "is_available" in content

        time.sleep(1)

        # Step 2: Add related functionality (should understand context)
        prompt2 = """Now add a 'Library' class to the same project.
Create 'library.py' with:
- A list to store books
- add_book(book) method
- find_by_isbn(isbn) method that returns the book or None"""

        exit_code, stdout, stderr = run_wolo(prompt2, tmp_path, session_id, is_resume=True)
        assert exit_code == 0, f"Step 2 failed: {stderr}"

        library_file = tmp_path / "library.py"
        assert library_file.exists(), "library.py was not created"

        time.sleep(1)

        # Step 3: Create integration test (should understand the full context)
        prompt3 = """Create a file 'main.py' that:
1. Imports Book and Library
2. Creates a library
3. Adds 2 books with realistic data
4. Searches for one book by ISBN
5. Prints the result"""

        exit_code, stdout, stderr = run_wolo(prompt3, tmp_path, session_id, is_resume=True)
        assert exit_code == 0, f"Step 3 failed: {stderr}"

        main_file = tmp_path / "main.py"
        assert main_file.exists(), "main.py was not created"

        # Verify it runs
        result = subprocess.run(
            ["python", str(tmp_path / "main.py")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Should not crash and should have some output
        assert result.returncode == 0, f"main.py failed: {result.stderr}"
        assert len(result.stdout) > 0, "main.py produced no output"

    def test_state_isolation_between_sessions(self, tmp_path: Path):
        """Test that different sessions don't interfere with each other."""
        session_a = f"isol_a_{int(time.time())}"
        session_b = f"isol_b_{int(time.time())}"

        # Create dir_a for session A
        dir_a = tmp_path / "session_a"
        dir_a.mkdir()

        # Create dir_b for session B
        dir_b = tmp_path / "session_b"
        dir_b.mkdir()

        # Session A: Create a file with specific content
        prompt_a = "Create 'info.txt' with content 'This is Session A'"
        exit_code, _, stderr = run_wolo(prompt_a, dir_a, session_a, is_resume=False)
        assert exit_code == 0, f"Session A failed: {stderr}"

        time.sleep(1)

        # Session B: Create a file with different content
        prompt_b = "Create 'info.txt' with content 'This is Session B'"
        exit_code, _, stderr = run_wolo(prompt_b, dir_b, session_b, is_resume=False)
        assert exit_code == 0, f"Session B failed: {stderr}"

        # Verify isolation
        content_a = (dir_a / "info.txt").read_text()
        content_b = (dir_b / "info.txt").read_text()

        assert "Session A" in content_a, f"Session A content wrong: {content_a}"
        assert "Session B" in content_b, f"Session B content wrong: {content_b}"

    def test_error_recovery_in_session(self, tmp_path: Path):
        """Test that wolo can recover from errors within a session."""
        session_id = f"error_test_{int(time.time())}"

        # Step 1: Try to do something that will fail
        prompt1 = """Try to read a file called 'nonexistent_file.xyz' and then
create a file called 'error_handled.txt' with content 'I handled the error'"""

        exit_code, stdout, stderr = run_wolo(prompt1, tmp_path, session_id, is_resume=False)
        assert exit_code == 0, f"Step 1 failed: {stderr}"

        # Should have created the error_handled.txt despite the read failure
        error_file = tmp_path / "error_handled.txt"
        assert error_file.exists(), "error_handled.txt was not created"

        time.sleep(1)

        # Step 2: Continue with normal work
        prompt2 = """Create a file called 'after_error.txt' with content 'Still working!'"""

        exit_code, stdout, stderr = run_wolo(prompt2, tmp_path, session_id, is_resume=True)
        assert exit_code == 0, f"Step 2 failed: {stderr}"

        after_file = tmp_path / "after_error.txt"
        assert after_file.exists(), "after_error.txt was not created"
        assert "Still working" in after_file.read_text()

    def test_todo_tracking_across_calls(self, tmp_path: Path):
        """Test that wolo can track and complete tasks across multiple calls."""
        session_id = f"todo_test_{int(time.time())}"

        # Step 1: Create a task list
        prompt1 = """Create a file 'tasks.md' with this exact content:
# Tasks
- [ ] Create user model
- [ ] Create product model
- [ ] Create order model"""

        exit_code, stdout, stderr = run_wolo(prompt1, tmp_path, session_id, is_resume=False)
        assert exit_code == 0, f"Step 1 failed: {stderr}"

        tasks_file = tmp_path / "tasks.md"
        original_content = tasks_file.read_text()
        assert "Create user model" in original_content

        time.sleep(1)

        # Step 2: Complete first task
        prompt2 = """Update 'tasks.md' to mark 'Create user model' as done (change [ ] to [x]).
Also create a file 'models/user.py' with a simple User class."""

        exit_code, stdout, stderr = run_wolo(prompt2, tmp_path, session_id, is_resume=True)
        assert exit_code == 0, f"Step 2 failed: {stderr}"

        # Verify task marked complete
        updated_content = tasks_file.read_text()
        assert "[x]" in updated_content or "[X]" in updated_content, (
            f"Task not marked complete: {updated_content}"
        )
        assert (tmp_path / "models" / "user.py").exists()

        time.sleep(1)

        # Step 3: Complete more tasks
        prompt3 = """Continue with the remaining tasks:
1. Mark 'Create product model' as done
2. Create 'models/product.py' with a Product class"""

        exit_code, stdout, stderr = run_wolo(prompt3, tmp_path, session_id, is_resume=True)
        assert exit_code == 0, f"Step 3 failed: {stderr}"

        # Verify progress
        final_content = tasks_file.read_text()
        # Should have at least 2 completed tasks now
        completed_count = final_content.count("[x]") + final_content.count("[X]")
        assert completed_count >= 2, f"Expected 2+ completed tasks, got {completed_count}"
        assert (tmp_path / "models" / "product.py").exists()


class TestSessionPersistence:
    """Test that session state is properly persisted."""

    def test_session_resumes_with_context(self, tmp_path: Path):
        """Test that resuming a session brings back the context."""
        session_id = f"persist_test_{int(time.time())}"

        # Create initial context
        prompt1 = """I'm working on a weather app.
Create 'weather.py' with a function get_temperature(city) that returns 25"""

        exit_code, stdout, stderr = run_wolo(prompt1, tmp_path, session_id, is_resume=False)
        assert exit_code == 0, f"First call failed: {stderr}"

        # Verify file exists
        weather_file = tmp_path / "weather.py"
        assert weather_file.exists()

        time.sleep(1)

        # Simulate "some time later" - resume and add related functionality
        prompt2 = """Remember we're building a weather app?
Add a 'format_weather(city, temp)' function to weather.py that returns
'The temperature in {city} is {temp}°C'"""

        exit_code, stdout, stderr = run_wolo(prompt2, tmp_path, session_id, is_resume=True)
        assert exit_code == 0, f"Second call failed: {stderr}"

        # Verify function was added
        content = weather_file.read_text()
        assert "format_weather" in content, f"format_weather not found: {content}"

        time.sleep(1)

        # Third call - should still remember context
        prompt3 = """Create a test file 'test_weather.py' that:
1. Imports both functions from weather.py
2. Tests get_temperature('Beijing')
3. Tests format_weather('Beijing', 25)
4. Prints 'All tests passed' at the end"""

        exit_code, stdout, stderr = run_wolo(prompt3, tmp_path, session_id, is_resume=True)
        assert exit_code == 0, f"Third call failed: {stderr}"

        # Verify test file works
        result = subprocess.run(
            ["python", str(tmp_path / "test_weather.py")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Test failed: {result.stderr}"
        assert "passed" in result.stdout.lower() or "25" in result.stdout, (
            f"Unexpected output: {result.stdout}"
        )
