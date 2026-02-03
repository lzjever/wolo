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
    async def test_handles_confirmation_required(self):
        """execute_tool should handle PathConfirmationRequired"""
        from wolo.tools import ToolPart
        from wolo.path_guard_exceptions import PathConfirmationRequired
        from unittest.mock import patch, AsyncMock

        tool_part = ToolPart(tool="write", input={"file_path": "/workspace/test.txt", "content": "test"})

        # Mock handle_path_confirmation to return True (user allowed)
        with patch('wolo.tools.handle_path_confirmation', return_value=True):
            with patch('wolo.tools.write_execute', new_callable=AsyncMock) as mock_write:
                mock_write.return_value = {"title": "write: /workspace/test.txt", "output": "Success"}

                # Import execute_tool after mocking
                from wolo.tools import execute_tool

                # This should not raise an exception
                await execute_tool(tool_part)

                assert tool_part.status != "error"
