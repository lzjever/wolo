"""FileTime tracking tests."""
import time
from pathlib import Path

import pytest

from wolo.file_time import FileModifiedError, FileTime


class TestFileTimeRead:
    """FileTime.read tests."""

    def test_read_existing_file(self, tmp_path):
        """Read existing file records mtime."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mtime = FileTime.read("test_session", str(test_file))

        assert mtime is not None
        assert mtime > 0

    def test_read_nonexistent_file(self, tmp_path):
        """Read non-existent file returns None."""
        mtime = FileTime.read("test_session", str(tmp_path / "nonexistent.txt"))
        assert mtime is None

    def test_read_updates_record(self, tmp_path):
        """Multiple reads update the record."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content1")

        mtime1 = FileTime.read("test_session", str(test_file))

        # Modify file
        time.sleep(0.01)
        test_file.write_text("content2")

        mtime2 = FileTime.read("test_session", str(test_file))

        assert mtime2 > mtime1


class TestFileTimeAssertNotModified:
    """FileTime.assert_not_modified tests."""

    def test_unmodified_file_passes(self, tmp_path):
        """Unmodified file passes assertion."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        FileTime.read("test_session", str(test_file))

        # Should not raise
        FileTime.assert_not_modified("test_session", str(test_file))

    def test_modified_file_raises(self, tmp_path):
        """Modified file raises error."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content1")

        FileTime.read("test_session_mod", str(test_file))

        # Modify file
        time.sleep(0.01)
        test_file.write_text("content2")

        with pytest.raises(FileModifiedError) as exc_info:
            FileTime.assert_not_modified("test_session_mod", str(test_file))

        assert str(test_file) in str(exc_info.value)

    def test_deleted_file_raises(self, tmp_path):
        """Deleted file raises error."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        FileTime.read("test_session_del", str(test_file))

        # Delete file
        test_file.unlink()

        with pytest.raises(FileModifiedError):
            FileTime.assert_not_modified("test_session_del", str(test_file))

    def test_unread_file_passes(self, tmp_path):
        """File that was never read passes (no record)."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Should not raise - no record exists
        FileTime.assert_not_modified("test_session_unread", str(test_file))


class TestFileTimeUpdate:
    """FileTime.update tests."""

    def test_update_after_write(self, tmp_path):
        """Update records new mtime after write."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content1")

        FileTime.read("test_session_upd", str(test_file))

        # Modify file
        time.sleep(0.01)
        test_file.write_text("content2")

        # Update should record new mtime
        FileTime.update("test_session_upd", str(test_file))

        # Now assertion should pass
        FileTime.assert_not_modified("test_session_upd", str(test_file))


class TestFileTimeClear:
    """FileTime clear methods tests."""

    def test_clear_session(self, tmp_path):
        """Clear session removes all records."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        FileTime.read("test_session_clear", str(test_file))
        assert FileTime.get_read_time("test_session_clear", str(test_file)) is not None

        FileTime.clear_session("test_session_clear")

        assert FileTime.get_read_time("test_session_clear", str(test_file)) is None

    def test_clear_file(self, tmp_path):
        """Clear file removes specific record."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("1")
        file2.write_text("2")

        FileTime.read("test_session_cf", str(file1))
        FileTime.read("test_session_cf", str(file2))

        FileTime.clear_file("test_session_cf", str(file1))

        assert FileTime.get_read_time("test_session_cf", str(file1)) is None
        assert FileTime.get_read_time("test_session_cf", str(file2)) is not None


class TestFileTimeHelpers:
    """FileTime helper methods tests."""

    def test_get_read_time(self, tmp_path):
        """Get read time returns recorded mtime."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mtime = FileTime.read("test_session_grt", str(test_file))
        recorded = FileTime.get_read_time("test_session_grt", str(test_file))

        assert recorded == mtime

    def test_get_all_read_files(self, tmp_path):
        """Get all read files returns list of paths."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("1")
        file2.write_text("2")

        FileTime.read("test_session_garf", str(file1))
        FileTime.read("test_session_garf", str(file2))

        files = FileTime.get_all_read_files("test_session_garf")

        assert len(files) == 2


class TestFileModifiedError:
    """FileModifiedError tests."""

    def test_error_message(self):
        """Error message contains path and times."""
        error = FileModifiedError("/path/to/file", 1000.0, 2000.0)

        assert "/path/to/file" in str(error)
        assert "1000" in str(error)
        assert "2000" in str(error)

    def test_error_attributes(self):
        """Error has correct attributes."""
        error = FileModifiedError("/path/to/file", 1000.0, 2000.0)

        assert error.path == "/path/to/file"
        assert error.read_time == 1000.0
        assert error.current_time == 2000.0
