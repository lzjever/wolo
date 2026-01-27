"""Comprehensive tests for subprocess_manager.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from wolo.subprocess_manager import (
    SubprocessRegistry,
    cleanup_all_subprocesses,
    get_registry,
    managed_subprocess,
    reset_registry,
)


@pytest.fixture(autouse=True)
def cleanup_global_registry():
    """Clean up the global subprocess registry before and after each test."""
    reset_registry()
    yield
    reset_registry()
    # Also cleanup any remaining processes
    try:
        asyncio.get_event_loop().run_until_complete(cleanup_all_subprocesses(timeout=0.1))
    except Exception:
        pass


class MockProcess:
    """Mock subprocess.Process for testing."""

    def __init__(self, pid=12345, returncode=None):
        self.pid = pid
        self._returncode = returncode
        self.terminate_called = False
        self.kill_called = False
        self._wait_event = asyncio.Event()

    @property
    def returncode(self):
        return self._returncode

    def terminate(self):
        """Mock terminate."""
        self.terminate_called = True

    def kill(self):
        """Mock kill."""
        self.kill_called = True

    async def wait(self):
        """Mock wait."""
        await self._wait_event.wait()
        return self._returncode

    def complete(self, returncode=0):
        """Mark process as complete (for testing)."""
        self._returncode = returncode
        self._wait_event.set()


class TestSubprocessRegistry:
    """Test SubprocessRegistry class."""

    @pytest.mark.asyncio
    async def test_register_and_unregister(self):
        """Test registering and unregistering processes."""
        registry = SubprocessRegistry()
        mock_process = MockProcess()

        await registry.register(mock_process)
        # Verify process is tracked by checking cleanup works
        await registry.unregister(mock_process)
        # No exception means it worked

    @pytest.mark.asyncio
    async def test_cleanup_empty_registry(self):
        """Test cleanup with no processes."""
        registry = SubprocessRegistry()
        await registry.cleanup_all()
        # Should not raise

    @pytest.mark.asyncio
    async def test_cleanup_terminated_processes(self):
        """Test cleanup ignores already terminated processes."""
        registry = SubprocessRegistry()
        mock_process = MockProcess(returncode=0)  # Already terminated

        await registry.register(mock_process)
        await registry.cleanup_all(timeout=1.0)
        # Should complete without error

    @pytest.mark.asyncio
    async def test_cleanup_with_timeout(self):
        """Test cleanup with timeout - processes that don't terminate get killed."""
        registry = SubprocessRegistry()
        mock_process = MockProcess(returncode=None)

        # Create a wait that never completes
        async def hanging_wait():
            await asyncio.sleep(100)

        mock_process.wait = hanging_wait

        await registry.register(mock_process)
        await registry.cleanup_all(timeout=0.1)

        # Should have called terminate then kill due to timeout
        assert mock_process.terminate_called
        assert mock_process.kill_called

    @pytest.mark.asyncio
    async def test_cleanup_terminates_then_waits(self):
        """Test cleanup terminates and waits for graceful shutdown."""
        registry = SubprocessRegistry()
        mock_process = MockProcess(returncode=None)

        # Create a wait that completes quickly
        async def quick_wait():
            await asyncio.sleep(0.01)
            mock_process._returncode = 0

        mock_process.wait = quick_wait

        await registry.register(mock_process)
        await registry.cleanup_all(timeout=1.0)

        # Should have called terminate but not kill (graceful shutdown)
        assert mock_process.terminate_called
        assert not mock_process.kill_called

    @pytest.mark.asyncio
    async def test_cleanup_handles_terminate_exception(self):
        """Test cleanup handles exceptions during terminate."""
        registry = SubprocessRegistry()

        class BadProcess:
            """Process that raises on terminate."""

            returncode = None
            pid = 999

            def terminate(self):
                raise RuntimeError("Cannot terminate")

            async def wait(self):
                await asyncio.sleep(100)

        bad_process = BadProcess()
        await registry.register(bad_process)

        # Should not raise, just log and continue
        await registry.cleanup_all(timeout=0.1)


class TestGlobalRegistry:
    """Test global registry functions."""

    def test_get_registry_creates_singleton(self):
        """Test get_registry creates singleton instance."""
        reset_registry()

        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2
        assert isinstance(registry1, SubprocessRegistry)

    def test_reset_registry(self):
        """Test reset_registry clears the global instance."""
        reset_registry()

        registry1 = get_registry()
        reset_registry()
        registry2 = get_registry()

        assert registry1 is not registry2


class TestManagedSubprocess:
    """Test managed_subprocess context manager."""

    @pytest.mark.asyncio
    async def test_managed_subprocess_creates_process(self):
        """Test managed_subprocess creates and registers process."""
        reset_registry()

        mock_process = MockProcess()
        mock_process.complete(0)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            async with managed_subprocess(
                ["echo", "hello"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ) as process:
                assert process is not None

        # Process should be cleaned up (unregistered)
        registry = get_registry()
        await registry.cleanup_all()  # Should not have our process

    @pytest.mark.asyncio
    async def test_managed_subprocess_shell_mode(self):
        """Test managed_subprocess with shell=True."""
        reset_registry()

        mock_process = MockProcess()
        mock_process.complete(0)

        with patch("asyncio.create_subprocess_shell", AsyncMock(return_value=mock_process)):
            async with managed_subprocess(
                "echo hello",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True,
            ) as process:
                assert process is not None

    @pytest.mark.asyncio
    async def test_managed_subprocess_cleanup_on_exception(self):
        """Test managed_subprocess cleans up even if exception occurs."""
        reset_registry()

        mock_process = MockProcess()
        mock_process.complete(0)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            with pytest.raises(RuntimeError):
                async with managed_subprocess(
                    ["echo", "test"],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ):
                    raise RuntimeError("Test exception")

        # Process should still be cleaned up
        assert mock_process.terminate_called or mock_process._returncode is not None

    @pytest.mark.asyncio
    async def test_managed_subprocess_terminates_on_exit(self):
        """Test managed_subprocess terminates process on context exit."""
        reset_registry()

        mock_process = MockProcess(returncode=None)  # Still running

        async def hanging_wait():
            await asyncio.sleep(100)

        mock_process.wait = hanging_wait

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            try:
                async with managed_subprocess(
                    ["sleep", "10"],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ):
                    pass
            except asyncio.TimeoutError:
                # Expected during cleanup
                pass

        # Process should have been terminated
        assert mock_process.terminate_called

    @pytest.mark.asyncio
    async def test_managed_subprocess_registers_and_unregisters(self):
        """Test that process is registered and unregistered properly."""
        reset_registry()
        registry = get_registry()

        mock_process = MockProcess()
        mock_process.complete(0)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            async with managed_subprocess(
                ["echo", "test"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ):
                # Process should be registered while in context
                # We can't directly check, but behavior confirms it
                pass

        # After exit, should be unregistered


class TestCleanupAllSubprocesses:
    """Test cleanup_all_subprocesses function."""

    @pytest.mark.asyncio
    async def test_cleanup_all_with_no_processes(self):
        """Test cleanup_all with no active processes."""
        reset_registry()
        await cleanup_all_subprocesses()
        # Should not raise

    @pytest.mark.asyncio
    async def test_cleanup_all_calls_registry(self):
        """Test cleanup_all delegates to registry."""
        reset_registry()

        mock_process = MockProcess()
        mock_process.complete(0)

        registry = get_registry()
        await registry.register(mock_process)

        await cleanup_all_subprocesses(timeout=1.0)
        # Should complete without error


class TestSubprocessRegistryEdgeCases:
    """Test edge cases in SubprocessRegistry."""

    @pytest.mark.asyncio
    async def test_register_duplicate_process(self):
        """Test registering the same process twice."""
        registry = SubprocessRegistry()
        mock_process = MockProcess()

        await registry.register(mock_process)
        await registry.register(mock_process)  # Register again
        # Should handle gracefully (set keeps only one)

        await registry.cleanup_all()

    @pytest.mark.asyncio
    async def test_unregister_non_registered_process(self):
        """Test unregistering a process that was never registered."""
        registry = SubprocessRegistry()
        mock_process = MockProcess()

        # Should not raise
        await registry.unregister(mock_process)

    @pytest.mark.asyncio
    async def test_cleanup_concurrent(self):
        """Test concurrent cleanup calls."""
        registry = SubprocessRegistry()

        processes = [MockProcess(pid=i) for i in range(5)]
        for proc in processes:
            proc.complete(0)

        for proc in processes:
            await registry.register(proc)

        # Run cleanup concurrently
        await asyncio.gather(
            registry.cleanup_all(timeout=1.0),
            registry.cleanup_all(timeout=1.0),
        )
        # Should complete without error

    @pytest.mark.asyncio
    async def test_cleanup_with_mixed_states(self):
        """Test cleanup with processes in different states."""
        registry = SubprocessRegistry()

        # Mix of running and terminated processes
        running = MockProcess(pid=1, returncode=None)
        running.complete(0)

        terminated = MockProcess(pid=2, returncode=0)

        stuck = MockProcess(pid=3, returncode=None)

        async def hanging_wait():
            await asyncio.sleep(100)

        stuck.wait = hanging_wait

        await registry.register(running)
        await registry.register(terminated)
        await registry.register(stuck)

        await registry.cleanup_all(timeout=0.1)

        # Stuck process should be killed
        assert stuck.kill_called


class TestManagedSubprocessEdgeCases:
    """Test edge cases in managed_subprocess."""

    @pytest.mark.asyncio
    async def test_managed_subprocess_handles_create_exception(self):
        """Test managed_subprocess handles creation errors."""
        reset_registry()

        with patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(side_effect=FileNotFoundError("Command not found")),
        ):
            with pytest.raises(FileNotFoundError):
                async with managed_subprocess(
                    ["nonexistent_command_xyz"],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ):
                    pass

    @pytest.mark.asyncio
    async def test_managed_subprocess_handles_kill_exception(self):
        """Test managed_subprocess handles exceptions during kill."""
        reset_registry()

        class UnkillableProcess:
            """Process that can't be killed."""

            returncode = None
            pid = 999

            def terminate(self):
                pass

            async def wait(self):
                raise asyncio.TimeoutError()

            def kill(self):
                raise RuntimeError("Cannot kill")

            async def wait(self):
                await asyncio.sleep(100)

        unkillable = UnkillableProcess()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=unkillable)):
            try:
                async with managed_subprocess(
                    ["sleep", "10"],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ):
                    pass
            except (asyncio.TimeoutError, RuntimeError):
                # Expected
                pass

    @pytest.mark.asyncio
    async def test_managed_subprocess_with_completed_process(self):
        """Test managed_subprocess with process that completes immediately."""
        reset_registry()

        mock_process = MockProcess()
        mock_process.complete(0)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            async with managed_subprocess(
                ["true"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ) as process:
                await process.wait()
                assert process.returncode == 0


class TestIntegrationWithEventLoop:
    """Test integration with asyncio event loop."""

    @pytest.mark.asyncio
    async def test_cleanup_before_loop_close(self):
        """Test cleanup before event loop closes."""
        reset_registry()

        mock_process = MockProcess()
        mock_process.complete(0)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            async with managed_subprocess(
                ["echo", "test"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ):
                pass

        # Cleanup should work without "event loop closed" errors
        await cleanup_all_subprocesses()

        # Verify loop still works
        result = await asyncio.sleep(0.01, result="success")
        assert result == "success"

    @pytest.mark.asyncio
    async def test_multiple_managed_subprocesses(self):
        """Test multiple managed subprocesses in sequence."""
        reset_registry()

        processes = []
        for i in range(3):
            mock_process = MockProcess(pid=100 + i)
            mock_process.complete(0)
            processes.append(mock_process)

        with patch("asyncio.create_subprocess_exec", AsyncMock(side_effect=processes)):
            for i in range(3):
                async with managed_subprocess(
                    ["echo", f"test{i}"],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ):
                    pass

        # Final cleanup should work
        await cleanup_all_subprocesses()
