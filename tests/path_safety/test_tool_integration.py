# tests/path_safety/test_tool_integration.py
import pytest
from pathlib import Path
from wolo.tools import write_execute
from wolo.path_guard import PathGuard, set_path_guard, Operation, reset_path_guard
from wolo.path_guard_exceptions import PathConfirmationRequired


class TestWriteExecuteIntegration:
    @pytest.fixture(autouse=True)
    def reset_guard(self):
        reset_path_guard()
        yield
        reset_path_guard()

    def test_allows_tmp_without_confirmation(self):
        """Writing to /tmp should be allowed without confirmation"""
        guard = PathGuard()
        set_path_guard(guard)

        import asyncio
        result = asyncio.run(write_execute("/tmp/test.txt", "content"))

        assert "Error" not in result["output"]
        assert "Permission denied" not in result["output"]

    def test_raises_confirmation_for_workspace(self):
        """Writing to a protected path should raise PathConfirmationRequired"""
        guard = PathGuard()
        set_path_guard(guard)

        import asyncio
        # Use /var/log which is a protected system directory
        with pytest.raises(PathConfirmationRequired) as exc_info:
            asyncio.run(write_execute("/var/log/test.txt", "content"))

        assert exc_info.value.path == "/var/log/test.txt"
        assert exc_info.value.operation == "write"

    def test_allows_whitelisted_path(self):
        """Writing to whitelisted path should be allowed"""
        import tempfile
        import os

        # Create a temporary directory to whitelist
        with tempfile.TemporaryDirectory() as tmpdir:
            guard = PathGuard(config_paths=[Path(tmpdir)])
            set_path_guard(guard)

            import asyncio
            test_file = os.path.join(tmpdir, "test.txt")
            result = asyncio.run(write_execute(test_file, "content"))

            assert "Permission denied" not in result["output"]
            assert os.path.exists(test_file)


class TestExecuteToolConfirmation:
    @pytest.mark.asyncio
    async def test_handles_confirmation_required_for_write(self):
        """execute_tool should handle PathConfirmationRequired for write tool"""
        from wolo.tools import ToolPart, execute_tool
        from wolo.path_guard_exceptions import PathConfirmationRequired
        from wolo.cli.path_confirmation import SessionCancelled
        from unittest.mock import patch, AsyncMock
        import tempfile
        import os

        # Create a PathGuard and set it
        guard = PathGuard()
        set_path_guard(guard)

        # Use a protected path that will require confirmation
        test_file = "/var/log/test_wolo_file.txt"

        tool_part = ToolPart(tool="write", input={"file_path": test_file, "content": "new content"})

        # Mock handle_path_confirmation to return True (user allowed)
        with patch('wolo.cli.path_confirmation.handle_path_confirmation', new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = True

            # Mock write_execute to first raise PathConfirmationRequired, then succeed
            call_count = [0]
            async def mock_write_impl(file_path, content):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise PathConfirmationRequired(file_path, "write")
                return {"title": f"write: {file_path}", "output": "Success", "metadata": {}}

            with patch('wolo.tools.write_execute', side_effect=mock_write_impl):
                # This should not raise an exception
                await execute_tool(tool_part)

                # Check that confirmation was called
                assert mock_confirm.called
                # Status should be completed (not error)
                assert tool_part.status == "completed"

    @pytest.mark.asyncio
    async def test_handles_confirmation_denied_for_write(self):
        """execute_tool should handle when user denies confirmation"""
        from wolo.tools import ToolPart, execute_tool
        from unittest.mock import patch, AsyncMock

        # Create a PathGuard and set it
        guard = PathGuard()
        set_path_guard(guard)

        # Use a protected path that will require confirmation
        test_file = "/var/log/test_wolo_file.txt"

        tool_part = ToolPart(tool="write", input={"file_path": test_file, "content": "new content"})

        # Mock handle_path_confirmation to return False (user denied)
        with patch('wolo.cli.path_confirmation.handle_path_confirmation', new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = False

            # This should set status to error
            await execute_tool(tool_part)

            # Status should be error
            assert tool_part.status == "error"
            assert "Permission denied by user" in tool_part.output
