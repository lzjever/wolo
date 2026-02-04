"""
Subprocess lifecycle management for Wolo.

This module provides centralized tracking and cleanup of all subprocesses
created during execution, ensuring proper cleanup before event loop shutdown.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)


class SubprocessRegistry:
    """
    Registry for tracking all active subprocesses.

    This ensures all subprocesses are properly cleaned up before event loop shutdown,
    preventing "Event loop is closed" errors.
    """

    def __init__(self):
        self._processes: set[asyncio.subprocess.Process] = set()
        self._lock = asyncio.Lock()

    async def register(self, process: asyncio.subprocess.Process) -> None:
        """Register a subprocess for tracking."""
        async with self._lock:
            self._processes.add(process)

    async def unregister(self, process: asyncio.subprocess.Process) -> None:
        """Unregister a subprocess (when it completes)."""
        async with self._lock:
            self._processes.discard(process)

    async def cleanup_all(self, timeout: float = 2.0) -> None:
        """
        Cleanup all registered subprocesses.

        Args:
            timeout: Maximum time to wait for processes to terminate gracefully
        """
        async with self._lock:
            if not self._processes:
                return

            processes_to_cleanup = list(self._processes)
            self._processes.clear()

        # Terminate all processes
        for process in processes_to_cleanup:
            if process.returncode is None:  # Still running
                try:
                    process.terminate()
                except Exception as e:
                    logger.debug(f"Error terminating process {process.pid}: {e}")

        # Wait for all processes to finish (with timeout)
        if processes_to_cleanup:
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        *[p.wait() for p in processes_to_cleanup if p.returncode is None],
                        return_exceptions=True,
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                # Force kill any remaining processes
                for process in processes_to_cleanup:
                    if process.returncode is None:
                        try:
                            process.kill()
                            await asyncio.wait_for(process.wait(), timeout=1.0)
                        except Exception as e:
                            logger.debug(f"Error killing process {process.pid}: {e}")


# Global registry instance
_registry: SubprocessRegistry | None = None


def get_registry() -> SubprocessRegistry:
    """Get or create the global subprocess registry."""
    global _registry
    if _registry is None:
        _registry = SubprocessRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (for testing)."""
    global _registry
    _registry = None


@asynccontextmanager
async def managed_subprocess(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
    """
    Context manager for creating and managing subprocesses.

    Automatically registers the subprocess and ensures cleanup on exit.

    Usage:
        async with managed_subprocess(...) as process:
            # Use process
            await process.wait()
    """
    registry = get_registry()

    # Create subprocess
    if "shell" in kwargs and kwargs["shell"]:
        process = await asyncio.create_subprocess_shell(*args, **kwargs)
    else:
        process = await asyncio.create_subprocess_exec(*args, **kwargs)

    try:
        await registry.register(process)
        yield process
    finally:
        await registry.unregister(process)
        # Ensure process is cleaned up if still running
        if process.returncode is None:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=1.0)
            except (asyncio.TimeoutError, Exception):
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                except Exception as e:
                    logger.debug(f"Error cleaning up subprocess {process.pid}: {e}")


async def cleanup_all_subprocesses(timeout: float = 2.0) -> None:
    """
    Cleanup all registered subprocesses.

    This should be called before closing the event loop.

    Args:
        timeout: Maximum time to wait for processes to terminate
    """
    registry = get_registry()
    await registry.cleanup_all(timeout=timeout)
