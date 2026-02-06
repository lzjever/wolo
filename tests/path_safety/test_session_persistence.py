# tests/path_safety/test_session_persistence.py
import json
from pathlib import Path

from wolo.session import load_path_confirmations, save_path_confirmations


class TestPathConfirmationPersistence:
    def test_save_and_load(self, tmp_path, monkeypatch):
        """Should save and load path confirmations"""
        # Create mock session directory
        session_dir = tmp_path / "sessions" / "test_session"
        session_dir.mkdir(parents=True)

        # Mock get_session_dir
        import wolo.session

        monkeypatch.setattr(wolo.session, "get_session_dir", lambda sid: session_dir)

        confirmed_dirs = [Path("/workspace"), Path("/tmp/project")]

        save_path_confirmations("test_session", confirmed_dirs)

        # Verify file was created
        confirmation_file = session_dir / "path_confirmations.json"
        assert confirmation_file.exists()

        # Load and verify
        loaded = load_path_confirmations("test_session")
        assert len(loaded) == 2
        assert any(p == Path("/workspace").resolve() for p in loaded)
        assert any(p == Path("/tmp/project").resolve() for p in loaded)

    def test_file_format(self, tmp_path, monkeypatch):
        """Saved file should have correct format"""
        session_dir = tmp_path / "sessions" / "format_test"
        session_dir.mkdir(parents=True)

        import wolo.session

        monkeypatch.setattr(wolo.session, "get_session_dir", lambda sid: session_dir)

        save_path_confirmations("format_test", [Path("/workspace")])

        confirmation_file = session_dir / "path_confirmations.json"
        data = json.loads(confirmation_file.read_text())

        assert "confirmed_dirs" in data
        assert "confirmation_count" in data
        assert "last_updated" in data
        assert data["confirmation_count"] == 1

    def test_load_nonexistent_returns_empty(self, tmp_path, monkeypatch):
        """Loading non-existent confirmation file should return empty list"""
        session_dir = tmp_path / "sessions" / "nonexistent"
        session_dir.mkdir(parents=True)

        import wolo.session

        monkeypatch.setattr(wolo.session, "get_session_dir", lambda sid: session_dir)

        loaded = load_path_confirmations("nonexistent")
        assert loaded == []


class TestSessionResumeWithConfirmations:
    def test_resume_loads_confirmations_to_pathguard(self, tmp_path, monkeypatch):
        """Resuming a session should load confirmations into PathChecker"""
        import wolo.session
        from wolo.path_guard import Operation, PathChecker, PathGuardConfig, reset_path_guard

        # Setup mock session directory
        session_dir = tmp_path / "sessions" / "resume_test"
        session_dir.mkdir(parents=True)
        monkeypatch.setattr(wolo.session, "get_session_dir", lambda sid: session_dir)

        # Create confirmation file
        wolo.session.save_path_confirmations("resume_test", [Path("/workspace")])

        # Reset and load
        reset_path_guard()
        confirmed = wolo.session.load_path_confirmations("resume_test")

        # Create PathChecker with loaded confirmations using PathGuardConfig
        config = PathGuardConfig(
            config_paths=[],
            cli_paths=[],
        )
        whitelist = config.create_whitelist(confirmed_dirs=set(confirmed))
        checker = PathChecker(whitelist)

        # Verify paths are allowed
        result = checker.check("/workspace/file.py", Operation.WRITE)

        assert result.allowed is True
        assert result.requires_confirmation is False


class TestSaveConfirmationsOnExit:
    def test_saves_on_session_save(self, tmp_path, monkeypatch):
        """Saving session should also save path confirmations"""
        import wolo.session
        from wolo.path_guard import reset_path_guard
        from wolo.tools_pkg.path_guard_executor import (
            get_confirmed_dirs,
            initialize_path_guard_middleware,
        )

        session_dir = tmp_path / "sessions" / "save_test"
        session_dir.mkdir(parents=True)
        monkeypatch.setattr(wolo.session, "get_session_dir", lambda sid: session_dir)

        # Initialize middleware with a pre-confirmed directory
        reset_path_guard()
        initialize_path_guard_middleware(
            config_paths=[],
            cli_paths=[],
            workdir=None,
            confirmed_dirs=["/workspace"],  # Pre-confirm a directory
        )

        # Save confirmations using the executor function
        confirmed = get_confirmed_dirs()
        wolo.session.save_path_confirmations("save_test", confirmed)

        # Verify file exists
        confirmation_file = session_dir / "path_confirmations.json"
        assert confirmation_file.exists()

        data = json.loads(confirmation_file.read_text())
        assert len(data["confirmed_dirs"]) == 1
