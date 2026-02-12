"""E2E tests for Wolo solo mode with medium-difficulty tasks.

These tests run Wolo in solo mode (--wild) to verify end-to-end functionality.
They require a valid LLM configuration and will make real API calls.

Run with:
    pytest tests/e2e/test_e2e_solo_tasks.py -v --tb=short -x

Or run all e2e tests:
    pytest tests/e2e/ -v --tb=short
"""

import os
import subprocess
from pathlib import Path

import pytest

# Skip all tests if E2E_TESTS is not set
pytestmark = pytest.mark.skipif(
    os.environ.get("WOLO_E2E_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set WOLO_E2E_TESTS=1 to run e2e tests (requires LLM API calls)",
)

# Timeout for each test (seconds)
E2E_TIMEOUT = 120


def run_wolo(prompt: str, workdir: Path, timeout: int = E2E_TIMEOUT) -> tuple[int, str, str]:
    """Run wolo in solo mode and return (exit_code, stdout, stderr).

    Args:
        prompt: The prompt to send to wolo
        workdir: Working directory for the command
        timeout: Timeout in seconds

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    cmd = ["uv", "run", "wolo", "--wild", "--workdir", str(workdir), prompt]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=Path(__file__).parent.parent.parent,  # Project root
    )

    return result.returncode, result.stdout, result.stderr


class TestFileOperations:
    """Test file creation, editing, and searching."""

    def test_create_and_read_file(self, tmp_path: Path):
        """Task: Create a simple text file and verify its contents."""
        prompt = "Create a file called 'hello.txt' with the content 'Hello, Wolo E2E Test!'"

        exit_code, stdout, stderr = run_wolo(prompt, tmp_path)

        # Check command succeeded
        assert exit_code == 0, f"Wolo failed with stderr: {stderr}"

        # Verify file was created
        hello_file = tmp_path / "hello.txt"
        assert hello_file.exists(), "File 'hello.txt' was not created"

        # Verify contents
        content = hello_file.read_text()
        assert "Hello" in content or "Wolo" in content or "E2E" in content, (
            f"File content doesn't match expected: {content}"
        )

    def test_create_python_script(self, tmp_path: Path):
        """Task: Create a simple Python script that performs calculation."""
        prompt = """Create a Python file called 'calculator.py' with a function called 'add'
that takes two numbers and returns their sum. Also add a main block that
prints the result of add(2, 3)."""

        exit_code, stdout, stderr = run_wolo(prompt, tmp_path, timeout=180)

        assert exit_code == 0, f"Wolo failed with stderr: {stderr}"

        # Verify file was created
        calc_file = tmp_path / "calculator.py"
        assert calc_file.exists(), "File 'calculator.py' was not created"

        # Verify the script runs correctly
        result = subprocess.run(
            ["python", str(calc_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "5" in result.stdout, f"Expected output to contain '5', got: {result.stdout}"

    def test_edit_existing_file(self, tmp_path: Path):
        """Task: Edit an existing file to add content."""
        # Pre-create a file
        test_file = tmp_path / "todo.md"
        test_file.write_text("# TODO List\n\n- Item 1\n")

        prompt = """Edit the file 'todo.md' to add a new item '- Item 2' at the end of the list.
Do not remove existing content."""

        exit_code, stdout, stderr = run_wolo(prompt, tmp_path)

        assert exit_code == 0, f"Wolo failed with stderr: {stderr}"

        # Verify file was edited
        content = test_file.read_text()
        assert "Item 1" in content, "Original content was removed"
        assert "Item 2" in content, f"New item was not added. Content: {content}"


class TestCodeAnalysis:
    """Test code reading and analysis capabilities."""

    def test_analyze_python_code(self, tmp_path: Path):
        """Task: Analyze a Python file and answer questions about it."""
        # Create a Python file to analyze
        source_file = tmp_path / "sample.py"
        source_file.write_text('''
def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"

class Counter:
    def __init__(self):
        self._count = 0

    def increment(self) -> int:
        self._count += 1
        return self._count

    def get_count(self) -> int:
        return self._count
''')

        prompt = """Read the file 'sample.py' and create a file called 'analysis.txt' that contains:
1. The name of the function that takes a string parameter
2. The name of the class
3. The number of methods in the class (just the number)"""

        exit_code, stdout, stderr = run_wolo(prompt, tmp_path)

        assert exit_code == 0, f"Wolo failed with stderr: {stderr}"

        # Verify analysis file was created
        analysis_file = tmp_path / "analysis.txt"
        assert analysis_file.exists(), "File 'analysis.txt' was not created"

        content = analysis_file.read_text().lower()
        # Check for expected content
        assert "greet" in content, f"Expected 'greet' in analysis, got: {content}"
        assert "counter" in content, f"Expected 'counter' in analysis, got: {content}"
        # Class has 2 or 3 methods depending on whether __init__ is counted
        assert any(x in content for x in ["2", "3", "two", "three"]), (
            f"Expected method count in analysis, got: {content}"
        )


class TestShellOperations:
    """Test shell command execution."""

    def test_list_directory(self, tmp_path: Path):
        """Task: List directory contents and save to file."""
        # Create some files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        (tmp_path / "subdir").mkdir()

        prompt = """Run 'ls -la' command and save the output to a file called 'listing.txt'"""

        exit_code, stdout, stderr = run_wolo(prompt, tmp_path)

        assert exit_code == 0, f"Wolo failed with stderr: {stderr}"

        # Verify listing file was created
        listing_file = tmp_path / "listing.txt"
        assert listing_file.exists(), "File 'listing.txt' was not created"

        content = listing_file.read_text()
        assert "file1.txt" in content, f"Expected 'file1.txt' in listing, got: {content}"
        assert "file2.txt" in content, f"Expected 'file2.txt' in listing, got: {content}"

    def test_create_directory_structure(self, tmp_path: Path):
        """Task: Create a directory structure using shell commands."""
        prompt = """Create a directory structure using shell commands:
- Create 'project/src' directory
- Create 'project/tests' directory
- Create an empty file 'project/src/main.py'
- Create an empty file 'project/tests/test_main.py'"""

        exit_code, stdout, stderr = run_wolo(prompt, tmp_path)

        assert exit_code == 0, f"Wolo failed with stderr: {stderr}"

        # Verify directory structure
        assert (tmp_path / "project" / "src").exists(), "Directory 'project/src' not created"
        assert (tmp_path / "project" / "tests").exists(), "Directory 'project/tests' not created"
        assert (tmp_path / "project" / "src" / "main.py").exists(), "File 'main.py' not created"
        assert (tmp_path / "project" / "tests" / "test_main.py").exists(), (
            "File 'test_main.py' not created"
        )


class TestSearchOperations:
    """Test file search and content search."""

    def test_search_file_content(self, tmp_path: Path):
        """Task: Search for content in files and report findings."""
        # Create multiple files
        (tmp_path / "doc1.txt").write_text("Python is a programming language.")
        (tmp_path / "doc2.txt").write_text("JavaScript is also popular.")
        (tmp_path / "doc3.txt").write_text("Python has great libraries.")

        prompt = """Search for files containing the word 'Python' and create a file called
'python_files.txt' listing the names of files that contain it (one per line)."""

        exit_code, stdout, stderr = run_wolo(prompt, tmp_path)

        assert exit_code == 0, f"Wolo failed with stderr: {stderr}"

        # Verify result file
        result_file = tmp_path / "python_files.txt"
        assert result_file.exists(), "File 'python_files.txt' was not created"

        content = result_file.read_text()
        assert "doc1" in content, f"Expected 'doc1' in result, got: {content}"
        assert "doc3" in content, f"Expected 'doc3' in result, got: {content}"
        # doc2 should not be included
        assert "doc2" not in content, f"'doc2' should not be in result: {content}"


class TestMultiStepTasks:
    """Test multi-step tasks that require planning and execution."""

    def test_create_simple_project(self, tmp_path: Path):
        """Task: Create a simple project structure with multiple files."""
        prompt = """Create a simple Python project called 'mathutils' with:
1. A directory 'mathutils'
2. A file 'mathutils/__init__.py' that's empty
3. A file 'mathutils/operations.py' with functions:
   - add(a, b): returns a + b
   - subtract(a, b): returns a - b
   - multiply(a, b): returns a * b
4. A file 'main.py' that imports from mathutils and tests all three functions
   by printing the results of add(5, 3), subtract(5, 3), and multiply(5, 3)
"""

        exit_code, stdout, stderr = run_wolo(prompt, tmp_path, timeout=180)

        assert exit_code == 0, f"Wolo failed with stderr: {stderr}"

        # Verify structure
        assert (tmp_path / "mathutils").is_dir(), "Directory 'mathutils' not created"
        assert (tmp_path / "mathutils" / "__init__.py").exists(), "__init__.py not created"
        assert (tmp_path / "mathutils" / "operations.py").exists(), "operations.py not created"
        assert (tmp_path / "main.py").exists(), "main.py not created"

        # Verify operations.py has the functions
        ops_content = (tmp_path / "mathutils" / "operations.py").read_text()
        assert "def add" in ops_content, "add function not found"
        assert "def subtract" in ops_content, "subtract function not found"
        assert "def multiply" in ops_content, "multiply function not found"

        # Verify main.py runs correctly
        result = subprocess.run(
            ["python", str(tmp_path / "main.py")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout
        assert "8" in output, f"Expected add(5,3)=8 in output, got: {output}"
        assert "2" in output, f"Expected subtract(5,3)=2 in output, got: {output}"
        assert "15" in output, f"Expected multiply(5,3)=15 in output, got: {output}"


class TestMemoryOperations:
    """Test memory save functionality."""

    def test_save_and_verify_memory(self, tmp_path: Path):
        """Task: Save something to memory and verify it's stored."""
        # Setup project-local config to isolate memories
        wolo_dir = tmp_path / ".wolo"
        wolo_dir.mkdir()
        config_file = wolo_dir / "config.yaml"
        config_file.write_text("""
endpoints:
  - name: default
    model: dummy
    api_base: https://api.example.com/v1
    api_key: dummy-key

ltm:
  enabled: true
""")

        prompt = """Save a memory with the title 'E2E Test Memory' and content
'This is a test memory created during e2e testing. The secret code is ALPHABETA123.'
Use tags ['e2e', 'test']. Just save the memory, no other actions needed."""

        exit_code, stdout, stderr = run_wolo(prompt, tmp_path)

        assert exit_code == 0, f"Wolo failed with stderr: {stderr}"

        # Verify memory was saved (check for .md file in memories directory)
        memories_dir = wolo_dir / "memories"
        if memories_dir.exists():
            md_files = list(memories_dir.glob("*.md"))
            assert len(md_files) > 0, "No memory file was created"

            # Check content
            content = md_files[0].read_text()
            assert "ALPHABETA123" in content or "E2E Test Memory" in content, (
                f"Memory content doesn't contain expected text: {content[:500]}"
            )


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_nonexistent_file_read(self, tmp_path: Path):
        """Task: Try to read a non-existent file and handle gracefully."""
        prompt = """Read the file 'nonexistent.txt' and report what happened.
Create a file called 'result.txt' with either the file contents or an error message."""

        exit_code, stdout, stderr = run_wolo(prompt, tmp_path)

        # Should still complete (not crash)
        assert exit_code == 0, f"Wolo failed with stderr: {stderr}"

        # Result file should exist
        result_file = tmp_path / "result.txt"
        assert result_file.exists(), "File 'result.txt' was not created"

        content = result_file.read_text().lower()
        # Should contain some indication of error or file not found
        assert any(
            word in content for word in ["error", "not found", "does not exist", "cannot", "unable"]
        ), f"Expected error message in result, got: {content}"
