# tests/path_safety/test_checker.py
from pathlib import Path

import pytest

from wolo.path_guard.checker import PathChecker, PathWhitelist
from wolo.path_guard.models import Operation


@pytest.fixture
def reset_checker():
    """Ensure no global state between tests."""
    yield
    # PathChecker has no global state after refactor


class TestPathWhitelist:
    def test_empty_whitelist_denies_everything(self):
        """Empty whitelist should deny all paths except defaults."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
        )
        assert whitelist.is_whitelisted(Path("/tmp/test.txt"))
        assert not whitelist.is_whitelisted(Path("/workspace/test.txt"))

    def test_workdir_has_highest_priority(self):
        """Workdir should allow paths within it."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=Path("/workspace"),
        )
        assert whitelist.is_whitelisted(Path("/workspace/test.txt"))
        assert whitelist.is_whitelisted(Path("/workspace/subdir/file.py"))
        assert not whitelist.is_whitelisted(Path("/etc/passwd"))

    def test_cli_paths_are_whitelisted(self):
        """CLI-provided paths should be whitelisted."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths={Path("/allowed")},
            workdir=None,
        )
        assert whitelist.is_whitelisted(Path("/allowed/file.txt"))
        assert not whitelist.is_whitelisted(Path("/workspace/file.txt"))

    def test_config_paths_are_whitelisted(self):
        """Config paths should be whitelisted."""
        whitelist = PathWhitelist(
            config_paths={Path("/project")},
            cli_paths=set(),
            workdir=None,
        )
        assert whitelist.is_whitelisted(Path("/project/file.txt"))
        assert not whitelist.is_whitelisted(Path("/etc/passwd"))

    def test_tmp_is_always_allowed(self):
        """/tmp should always be allowed as default safe directory."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
        )
        assert whitelist.is_whitelisted(Path("/tmp/file.txt"))
        assert whitelist.is_whitelisted(Path("/tmp/subdir/file.py"))

    def test_confirmed_dirs_are_whitelisted(self):
        """User-confirmed directories should be whitelisted."""
        whitelist = PathWhitelist(
            config_paths=set(),
            cli_paths=set(),
            workdir=None,
            confirmed_dirs={Path("/home/user/project")},
        )
        assert whitelist.is_whitelisted(Path("/home/user/project/file.txt"))
        assert not whitelist.is_whitelisted(Path("/etc/passwd"))


class TestPathChecker:
    def test_check_returns_allowed_result_for_whitelisted(self):
        """Should return allowed result for whitelisted paths."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths={Path("/workspace")},
                cli_paths=set(),
                workdir=None,
            )
        )
        result = checker.check("/workspace/file.py", Operation.WRITE)
        assert result.allowed is True
        assert result.requires_confirmation is False

    def test_check_returns_confirmation_for_unknown_path(self):
        """Should return confirmation required for unknown paths."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )
        result = checker.check("/workspace/file.py", Operation.WRITE)
        assert result.allowed is False
        assert result.requires_confirmation is True

    def test_read_operation_always_allowed(self):
        """Read operations should always be allowed (no confirmation)."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )
        result = checker.check("/any/path/file.txt", Operation.READ)
        assert result.allowed is True
        assert result.requires_confirmation is False

    def test_add_confirmed_directory(self):
        """Should be able to add confirmed directories."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )
        checker.confirm_directory("/workspace")

        # After confirmation, path should be allowed
        result = checker.check("/workspace/file.py", Operation.WRITE)
        assert result.allowed is True

    def test_confirm_directory_for_file(self):
        """Confirming a file path should confirm its parent directory."""
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )
        checker.confirm_directory("/workspace/file.py")

        # Parent directory should be confirmed
        result = checker.check("/workspace/other.py", Operation.WRITE)
        assert result.allowed is True

    def test_get_confirmed_directories(self):
        """Should return list of confirmed directories."""
        # Use /tmp which always exists
        checker = PathChecker(
            whitelist=PathWhitelist(
                config_paths=set(),
                cli_paths=set(),
                workdir=None,
            )
        )
        # /tmp exists, so it should be confirmed directly
        checker.confirm_directory("/tmp")
        # Create a temp file and confirm it (should confirm parent /tmp)
        import tempfile

        with tempfile.NamedTemporaryFile(dir="/tmp", delete=True) as f:
            checker.confirm_directory(f.name)

        confirmed = checker.get_confirmed_dirs()
        # Both /tmp (explicit) and /tmp (from file's parent) should be in confirmed
        # Note: Since /tmp is the same, we should have at least 1 entry
        assert len(confirmed) >= 1
        assert Path("/tmp") in confirmed
