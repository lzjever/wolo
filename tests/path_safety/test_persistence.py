# tests/path_safety/test_persistence.py
"""Tests for PathGuardPersistence module."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from wolo.path_guard.persistence import PathGuardPersistence


@pytest.fixture
def temp_session_dir(tmp_path):
    """Create a temporary session directory."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir(exist_ok=True)
    return session_dir


class TestPathGuardPersistence:
    def test_init(self, temp_session_dir):
        """Should initialize with session directory."""
        persistence = PathGuardPersistence(temp_session_dir)
        assert persistence._session_dir == temp_session_dir

    def test_save_confirmed_dirs(self, temp_session_dir):
        """Should save confirmed directories to JSON file."""
        persistence = PathGuardPersistence(temp_session_dir)
        confirmed_dirs = [Path("/tmp/confirmed"), Path("/workspace/project")]

        persistence.save_confirmed_dirs("test_session", confirmed_dirs)

        # Check file exists
        file_path = temp_session_dir / "test_session" / "path_confirmations.json"
        assert file_path.exists()

        # Check content
        with open(file_path) as f:
            data = json.load(f)

        assert data["confirmed_dirs"] == ["/tmp/confirmed", "/workspace/project"]
        assert data["confirmation_count"] == 2
        assert "last_updated" in data

    def test_save_creates_session_directory(self, temp_session_dir):
        """Should create session directory if it doesn't exist."""
        persistence = PathGuardPersistence(temp_session_dir)
        confirmed_dirs = [Path("/tmp/confirmed")]

        persistence.save_confirmed_dirs("new_session", confirmed_dirs)

        session_dir = temp_session_dir / "new_session"
        assert session_dir.exists()
        assert session_dir.is_dir()

    def test_load_confirmed_dirs(self, temp_session_dir):
        """Should load confirmed directories from JSON file."""
        persistence = PathGuardPersistence(temp_session_dir)

        # First save some data
        confirmed_dirs = [Path("/tmp/confirmed"), Path("/workspace/project")]
        persistence.save_confirmed_dirs("test_session", confirmed_dirs)

        # Then load it
        loaded = persistence.load_confirmed_dirs("test_session")

        assert len(loaded) == 2
        assert Path("/tmp/confirmed") in loaded
        assert Path("/workspace/project") in loaded

    def test_load_nonexistent_session(self, temp_session_dir):
        """Should return empty list for non-existent session."""
        persistence = PathGuardPersistence(temp_session_dir)

        loaded = persistence.load_confirmed_dirs("nonexistent_session")

        assert loaded == []

    def test_save_and_load_roundtrip(self, temp_session_dir):
        """Should be able to save and load the same data."""
        persistence = PathGuardPersistence(temp_session_dir)
        original = [Path("/tmp/confirmed"), Path("/workspace"), Path("/home/user")]

        persistence.save_confirmed_dirs("roundtrip_test", original)
        loaded = persistence.load_confirmed_dirs("roundtrip_test")

        assert len(loaded) == len(original)
        for path in original:
            assert path in loaded

    def test_save_empty_list(self, temp_session_dir):
        """Should handle empty list of confirmed directories."""
        persistence = PathGuardPersistence(temp_session_dir)

        persistence.save_confirmed_dirs("empty_session", [])

        file_path = temp_session_dir / "empty_session" / "path_confirmations.json"
        assert file_path.exists()

        with open(file_path) as f:
            data = json.load(f)

        assert data["confirmed_dirs"] == []
        assert data["confirmation_count"] == 0

    def test_load_empty_list(self, temp_session_dir):
        """Should load empty list correctly."""
        persistence = PathGuardPersistence(temp_session_dir)

        # Save empty list
        persistence.save_confirmed_dirs("empty_session", [])

        # Load it back
        loaded = persistence.load_confirmed_dirs("empty_session")

        assert loaded == []

    def test_multiple_sessions(self, temp_session_dir):
        """Should handle multiple sessions independently."""
        persistence = PathGuardPersistence(temp_session_dir)

        # Save different data for different sessions
        persistence.save_confirmed_dirs("session1", [Path("/tmp/session1")])
        persistence.save_confirmed_dirs("session2", [Path("/tmp/session2")])

        # Load and verify
        loaded1 = persistence.load_confirmed_dirs("session1")
        loaded2 = persistence.load_confirmed_dirs("session2")

        assert Path("/tmp/session1") in loaded1
        assert Path("/tmp/session2") not in loaded1
        assert Path("/tmp/session2") in loaded2
        assert Path("/tmp/session1") not in loaded2

    def test_last_updated_timestamp(self, temp_session_dir):
        """Should include timestamp in saved data."""
        persistence = PathGuardPersistence(temp_session_dir)
        confirmed_dirs = [Path("/tmp/confirmed")]

        before_save = datetime.now()
        persistence.save_confirmed_dirs("timestamp_test", confirmed_dirs)
        after_save = datetime.now()

        file_path = temp_session_dir / "timestamp_test" / "path_confirmations.json"
        with open(file_path) as f:
            data = json.load(f)

        # Verify timestamp is recent
        last_updated = datetime.fromisoformat(data["last_updated"])
        assert before_save <= last_updated <= after_save
