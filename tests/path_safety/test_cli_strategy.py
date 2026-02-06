# tests/path_safety/test_cli_strategy.py
"""Tests for CLIConfirmationStrategy module."""

from unittest.mock import MagicMock, patch

import pytest

from wolo.path_guard.checker import PathChecker, PathWhitelist
from wolo.path_guard.cli_strategy import CLIConfirmationStrategy
from wolo.path_guard.exceptions import SessionCancelled


@pytest.mark.asyncio
class TestCLIConfirmationStrategy:
    async def test_confirm_yes_response(self):
        """Should allow when user responds with 'y'."""
        mock_instance = MagicMock()
        mock_instance.input.return_value = "y"

        # Set up the path_guard with a mock checker
        from wolo.path_guard import set_path_guard

        checker = PathChecker(PathWhitelist())
        set_path_guard(checker)

        with patch("wolo.path_guard.cli_strategy.Console", return_value=mock_instance):
            with patch("sys.stdin.isatty", return_value=True):
                strategy = CLIConfirmationStrategy()
                result = await strategy.confirm("/workspace/file.py", "write")

        assert result is True
        # Verify the directory was confirmed
        confirmed = checker.get_confirmed_dirs()
        assert len(confirmed) > 0

    async def test_confirm_empty_response_means_yes(self):
        """Should allow when user presses Enter (empty response)."""
        mock_instance = MagicMock()
        mock_instance.input.return_value = ""

        from wolo.path_guard import set_path_guard

        checker = PathChecker(PathWhitelist())
        set_path_guard(checker)

        with patch("wolo.path_guard.cli_strategy.Console", return_value=mock_instance):
            with patch("sys.stdin.isatty", return_value=True):
                strategy = CLIConfirmationStrategy()
                result = await strategy.confirm("/workspace/file.py", "write")

        assert result is True

    async def test_confirm_full_yes(self):
        """Should allow when user responds with 'yes'."""
        mock_instance = MagicMock()
        mock_instance.input.return_value = "yes"

        from wolo.path_guard import set_path_guard

        checker = PathChecker(PathWhitelist())
        set_path_guard(checker)

        with patch("wolo.path_guard.cli_strategy.Console", return_value=mock_instance):
            with patch("sys.stdin.isatty", return_value=True):
                strategy = CLIConfirmationStrategy()
                result = await strategy.confirm("/workspace/file.py", "write")

        assert result is True

    async def test_confirm_no_response(self):
        """Should deny when user responds with 'n'."""
        mock_instance = MagicMock()
        mock_instance.input.return_value = "n"

        from wolo.path_guard import set_path_guard

        checker = PathChecker(PathWhitelist())
        set_path_guard(checker)

        with patch("wolo.path_guard.cli_strategy.Console", return_value=mock_instance):
            with patch("sys.stdin.isatty", return_value=True):
                strategy = CLIConfirmationStrategy()
                result = await strategy.confirm("/workspace/file.py", "write")

        assert result is False
        # No directories should be confirmed
        assert len(checker.get_confirmed_dirs()) == 0

    async def test_confirm_full_no(self):
        """Should deny when user responds with 'no'."""
        mock_instance = MagicMock()
        mock_instance.input.return_value = "no"

        from wolo.path_guard import set_path_guard

        checker = PathChecker(PathWhitelist())
        set_path_guard(checker)

        with patch("wolo.path_guard.cli_strategy.Console", return_value=mock_instance):
            with patch("sys.stdin.isatty", return_value=True):
                strategy = CLIConfirmationStrategy()
                result = await strategy.confirm("/workspace/file.py", "write")

        assert result is False

    async def test_confirm_allow_parent(self):
        """Should allow parent directory when user responds with 'a'."""
        mock_instance = MagicMock()
        mock_instance.input.return_value = "a"

        from wolo.path_guard import set_path_guard

        checker = PathChecker(PathWhitelist())
        set_path_guard(checker)

        with patch("wolo.path_guard.cli_strategy.Console", return_value=mock_instance):
            with patch("sys.stdin.isatty", return_value=True):
                strategy = CLIConfirmationStrategy()
                result = await strategy.confirm("/workspace/project/file.py", "write")

        assert result is True
        # Parent directory should be confirmed
        confirmed = checker.get_confirmed_dirs()
        # The parent is /workspace/project, but it gets resolved to absolute path
        assert len(confirmed) > 0

    async def test_confirm_quit_raises_cancelled(self):
        """Should raise SessionCancelled when user responds with 'q'."""
        mock_instance = MagicMock()
        mock_instance.input.return_value = "q"

        from wolo.path_guard import set_path_guard

        checker = PathChecker(PathWhitelist())
        set_path_guard(checker)

        with patch("wolo.path_guard.cli_strategy.Console", return_value=mock_instance):
            with patch("sys.stdin.isatty", return_value=True):
                strategy = CLIConfirmationStrategy()
                with pytest.raises(SessionCancelled):
                    await strategy.confirm("/workspace/file.py", "write")

    async def test_non_interactive_denies(self):
        """Should auto-deny in non-interactive mode."""
        mock_instance = MagicMock()

        from wolo.path_guard import set_path_guard

        checker = PathChecker(PathWhitelist())
        set_path_guard(checker)

        with patch("wolo.path_guard.cli_strategy.Console", return_value=mock_instance):
            strategy = CLIConfirmationStrategy()

            with patch("sys.stdin.isatty", return_value=False):
                result = await strategy.confirm("/workspace/file.py", "write")

        assert result is False
        mock_instance.input.assert_not_called()

    @pytest.mark.parametrize(
        "response",
        [
            "Y",
            "YES",
            "N",
            "NO",
            "A",
            "Q",
        ],
    )
    async def test_case_insensitive_responses(self, response):
        """Should handle uppercase responses correctly."""
        mock_instance = MagicMock()
        mock_instance.input.return_value = response

        from wolo.path_guard import set_path_guard

        checker = PathChecker(PathWhitelist())
        set_path_guard(checker)

        with patch("wolo.path_guard.cli_strategy.Console", return_value=mock_instance):
            with patch("sys.stdin.isatty", return_value=True):
                strategy = CLIConfirmationStrategy()

                if response.upper() in ("Y", "YES"):
                    result = await strategy.confirm("/workspace/file.py", "write")
                    assert result is True
                elif response.upper() in ("N", "NO"):
                    result = await strategy.confirm("/workspace/file.py", "write")
                    assert result is False
                elif response.upper() == "A":
                    result = await strategy.confirm("/workspace/file.py", "write")
                    assert result is True
                elif response.upper() == "Q":
                    with pytest.raises(SessionCancelled):
                        await strategy.confirm("/workspace/file.py", "write")
