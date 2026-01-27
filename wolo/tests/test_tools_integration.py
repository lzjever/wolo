"""Tools integration tests for Phase 1 features."""

import pytest

from wolo.tools import (
    _is_binary_file,
    _suggest_similar_files,
    edit_execute,
    glob_execute,
    grep_execute,
    read_execute,
    shell_execute,
)


class TestReadExecute:
    """Read tool tests."""

    @pytest.mark.asyncio
    async def test_read_with_line_numbers(self, tmp_path):
        """Read output includes line numbers."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\nline3")

        result = await read_execute(str(test_file))

        assert result["metadata"].get("error") is None
        assert "    1| line1" in result["output"]
        assert "    2| line2" in result["output"]
        assert "    3| line3" in result["output"]

    @pytest.mark.asyncio
    async def test_read_with_offset(self, tmp_path):
        """Read with offset starts from correct line."""
        test_file = tmp_path / "test.py"
        test_file.write_text("\n".join(f"line{i}" for i in range(100)))

        result = await read_execute(str(test_file), offset=50, limit=10)

        assert "   51| line50" in result["output"]
        assert "line0" not in result["output"]

    @pytest.mark.asyncio
    async def test_read_file_not_found_suggestions(self, tmp_path):
        """File not found suggests similar files."""
        # Create similar files
        (tmp_path / "config.py").write_text("config")
        (tmp_path / "configfile.json").write_text("{}")

        result = await read_execute(str(tmp_path / "config"))

        assert "not found" in result["output"].lower()
        # Suggestions only appear if similar files exist
        # The function looks for files where base is in name or name is in base

    @pytest.mark.asyncio
    async def test_read_binary_file_rejected(self, tmp_path):
        """Binary files are rejected."""
        binary_file = tmp_path / "test.exe"
        binary_file.write_bytes(b"\x00\x01\x02\x03")

        result = await read_execute(str(binary_file))

        assert "binary" in result["output"].lower()
        assert result["metadata"].get("error") == "binary_file"

    @pytest.mark.asyncio
    async def test_read_file_header(self, tmp_path):
        """Read output includes file header."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        result = await read_execute(str(test_file))

        assert "<file" in result["output"]
        assert "path=" in result["output"]
        assert "lines=" in result["output"]


class TestEditExecute:
    """Edit tool tests with smart replace."""

    @pytest.mark.asyncio
    async def test_edit_exact_match(self, tmp_path):
        """Edit with exact match."""
        test_file = tmp_path / "test.py"
        test_file.write_text("hello world")

        result = await edit_execute(str(test_file), "world", "universe")

        assert "Successfully" in result["output"]
        assert test_file.read_text() == "hello universe"

    @pytest.mark.asyncio
    async def test_edit_whitespace_tolerance(self, tmp_path):
        """Edit tolerates whitespace differences."""
        test_file = tmp_path / "test.py"
        test_file.write_text("  def foo():  \n    pass")

        result = await edit_execute(str(test_file), "def foo():\npass", "def bar():\nreturn")

        assert "Successfully" in result["output"]
        assert "def bar():" in test_file.read_text()

    @pytest.mark.asyncio
    async def test_edit_indentation_tolerance(self, tmp_path):
        """Edit tolerates indentation differences."""
        test_file = tmp_path / "test.py"
        test_file.write_text("    if True:\n        x = 1")

        result = await edit_execute(str(test_file), "if True:\n    x = 1", "if False:\n    x = 2")

        assert "Successfully" in result["output"]
        assert "if False:" in test_file.read_text()

    @pytest.mark.asyncio
    async def test_edit_generates_diff(self, tmp_path):
        """Edit output includes diff."""
        test_file = tmp_path / "test.py"
        test_file.write_text("hello\nworld")

        result = await edit_execute(str(test_file), "world", "universe")

        assert "diff" in result["output"].lower() or "Changes:" in result["output"]

    @pytest.mark.asyncio
    async def test_edit_not_found(self, tmp_path):
        """Edit reports when text not found."""
        test_file = tmp_path / "test.py"
        test_file.write_text("hello")

        result = await edit_execute(str(test_file), "nonexistent", "replacement")

        assert "not found" in result["output"].lower()


class TestShellExecute:
    """Shell tool tests."""

    @pytest.mark.asyncio
    async def test_shell_basic(self):
        """Basic shell command."""
        result = await shell_execute("echo hello")

        assert "hello" in result["output"]
        assert result["metadata"]["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_shell_large_output_truncated(self):
        """Large output is truncated."""
        # Generate large output
        result = await shell_execute("seq 1 5000")

        # Should be truncated
        if result["metadata"].get("truncated"):
            assert "truncated" in result["output"].lower()

    @pytest.mark.asyncio
    async def test_shell_timeout(self):
        """Shell command timeout."""
        result = await shell_execute("sleep 10", timeout=200)

        assert "timed out" in result["output"].lower()
        assert result["metadata"]["exit_code"] == -1


class TestGrepExecute:
    """Grep tool tests."""

    @pytest.mark.asyncio
    async def test_grep_basic(self, tmp_path):
        """Basic grep search."""
        (tmp_path / "test.py").write_text("def hello():\n    pass")

        result = await grep_execute("hello", str(tmp_path))

        assert result["metadata"]["matches"] > 0
        assert "hello" in result["output"]

    @pytest.mark.asyncio
    async def test_grep_include_pattern(self, tmp_path):
        """Grep with file pattern filter."""
        (tmp_path / "test.py").write_text("hello python")
        (tmp_path / "test.js").write_text("hello javascript")

        result = await grep_execute("hello", str(tmp_path), include_pattern="*.py")

        assert "python" in result["output"]
        # JS file should not be included
        assert "javascript" not in result["output"]

    @pytest.mark.asyncio
    async def test_grep_no_matches(self, tmp_path):
        """Grep with no matches."""
        (tmp_path / "test.py").write_text("hello")

        result = await grep_execute("nonexistent", str(tmp_path))

        assert result["metadata"]["matches"] == 0


class TestGlobExecute:
    """Glob tool tests."""

    @pytest.mark.asyncio
    async def test_glob_basic(self, tmp_path):
        """Basic glob search."""
        (tmp_path / "test1.py").write_text("1")
        (tmp_path / "test2.py").write_text("2")
        (tmp_path / "test.js").write_text("js")

        result = await glob_execute("*.py", str(tmp_path))

        assert result["metadata"]["matches"] == 2
        assert "test1.py" in result["output"]
        assert "test2.py" in result["output"]

    @pytest.mark.asyncio
    async def test_glob_recursive(self, tmp_path):
        """Recursive glob search."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.py").write_text("root")
        (subdir / "nested.py").write_text("nested")

        result = await glob_execute("**/*.py", str(tmp_path))

        assert result["metadata"]["matches"] == 2

    @pytest.mark.asyncio
    async def test_glob_no_matches(self, tmp_path):
        """Glob with no matches."""
        result = await glob_execute("*.nonexistent", str(tmp_path))

        assert result["metadata"]["matches"] == 0


class TestBinaryDetection:
    """Binary file detection tests."""

    def test_binary_by_extension(self, tmp_path):
        """Binary detected by extension."""
        exe_file = tmp_path / "test.exe"
        exe_file.write_text("not actually binary")

        assert _is_binary_file(exe_file) is True

    def test_binary_by_content(self, tmp_path):
        """Binary detected by content."""
        bin_file = tmp_path / "test.dat"
        bin_file.write_bytes(b"\x00\x01\x02\x03" * 100)

        assert _is_binary_file(bin_file) is True

    def test_text_file_not_binary(self, tmp_path):
        """Text file not detected as binary."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello, World!")

        assert _is_binary_file(txt_file) is False


class TestImageRead:
    """Image file reading tests."""

    @pytest.mark.asyncio
    async def test_read_png_image(self, tmp_path):
        """Read PNG image returns base64."""
        from PIL import Image

        # Create a simple test image
        img = Image.new("RGB", (100, 100), color="red")
        img_path = tmp_path / "test.png"
        img.save(img_path)

        result = await read_execute(str(img_path))

        assert result["metadata"].get("type") == "image"
        assert result["metadata"]["width"] == 100
        assert result["metadata"]["height"] == 100
        assert "base64" in result["output"]

    @pytest.mark.asyncio
    async def test_read_jpeg_image(self, tmp_path):
        """Read JPEG image returns base64."""
        from PIL import Image

        img = Image.new("RGB", (50, 50), color="blue")
        img_path = tmp_path / "test.jpg"
        img.save(img_path)

        result = await read_execute(str(img_path))

        assert result["metadata"].get("type") == "image"
        assert "image/jpeg" in result["output"]


class TestPdfRead:
    """PDF file reading tests."""

    @pytest.mark.asyncio
    async def test_read_pdf_with_text(self, tmp_path):
        """Read PDF extracts text."""
        pytest.importorskip("fitz")
        import fitz

        # Create a simple PDF with text
        pdf_path = tmp_path / "test.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Hello PDF World!")
        doc.save(pdf_path)
        doc.close()

        result = await read_execute(str(pdf_path))

        assert result["metadata"].get("type") == "pdf"
        assert result["metadata"]["pages"] == 1
        assert "Hello PDF World" in result["output"]


class TestFileSuggestions:
    """File suggestion tests."""

    def test_suggest_similar_files(self, tmp_path):
        """Suggests similar files."""
        (tmp_path / "config.py").write_text("1")
        (tmp_path / "configfile.json").write_text("2")
        (tmp_path / "other.txt").write_text("3")

        # Looking for "config" should find "config.py" and "configfile.json"
        suggestions = _suggest_similar_files(tmp_path / "config")

        assert len(suggestions) >= 1
        assert any("config" in s for s in suggestions)

    def test_no_suggestions_empty_dir(self, tmp_path):
        """No suggestions for empty directory."""
        suggestions = _suggest_similar_files(tmp_path / "nonexistent.txt")

        assert len(suggestions) == 0
