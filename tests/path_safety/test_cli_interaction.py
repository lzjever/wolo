# tests/path_safety/test_cli_interaction.py
import pytest
from unittest.mock import patch, MagicMock
from wolo.cli.path_confirmation import handle_path_confirmation, SessionCancelled
from wolo.path_guard import reset_path_guard


@pytest.fixture(autouse=True)
def reset_guard():
    """Reset PathGuard before each test"""
    reset_path_guard()
    yield
    reset_path_guard()


class TestPathConfirmation:
    @patch('sys.stdin.isatty', return_value=True)
    @patch('wolo.cli.path_confirmation.Console.input', return_value='y')
    @pytest.mark.asyncio
    async def test_confirm_allows_operation(self, mock_input, mock_isatty):
        """User confirming 'y' should allow the operation"""
        result = await handle_path_confirmation("/workspace/file.py", "write")
        assert result is True

    @patch('sys.stdin.isatty', return_value=True)
    @patch('wolo.cli.path_confirmation.Console.input', return_value='n')
    @pytest.mark.asyncio
    async def test_deny_refuses_operation(self, mock_input, mock_isatty):
        """User entering 'n' should refuse the operation"""
        result = await handle_path_confirmation("/etc/passwd", "write")
        assert result is False

    @patch('sys.stdin.isatty', return_value=False)
    @pytest.mark.asyncio
    async def test_non_interactive_refuses(self, mock_isatty):
        """Non-interactive mode should refuse without prompting"""
        result = await handle_path_confirmation("/workspace/file.py", "write")
        assert result is False

    @patch('sys.stdin.isatty', return_value=True)
    @patch('wolo.cli.path_confirmation.Console.input', return_value='a')
    @pytest.mark.asyncio
    async def test_confirm_allows_directory(self, mock_input, mock_isatty):
        """Confirming with 'a' should allow the entire directory"""
        result = await handle_path_confirmation("/workspace/project/file.py", "write")
        assert result is True

    @patch('sys.stdin.isatty', return_value=True)
    @patch('wolo.cli.path_confirmation.Console.input', return_value='q')
    @pytest.mark.asyncio
    async def test_quit_raises_session_cancelled(self, mock_input, mock_isatty):
        """User entering 'q' should raise SessionCancelled"""
        with pytest.raises(SessionCancelled):
            await handle_path_confirmation("/workspace/file.py", "write")
