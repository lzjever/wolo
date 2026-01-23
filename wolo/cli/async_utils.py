"""
Utilities for async execution with proper error handling.
"""

import asyncio
import logging
from collections.abc import Awaitable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _suppress_mcp_shutdown_errors(loop, context):
    """
    Custom exception handler to suppress expected MCP shutdown errors.

    These errors occur during cleanup when async generators are closed
    in different task contexts, which is expected during shutdown.
    """
    msg = context.get("message", "")
    exc = context.get("exception")
    asyncgen = context.get("asyncgen")

    # Suppress known MCP/anyio shutdown errors
    if exc:
        exc_str = str(exc)
        # Check for cancel scope errors
        if "cancel scope" in exc_str:
            logger.debug(f"Suppressing expected shutdown error: {exc_str}")
            return

        # Check for dictionary iteration errors during cleanup
        if isinstance(exc, RuntimeError) and "dictionary changed size during iteration" in exc_str:
            logger.debug(f"Suppressing expected cleanup error: {exc_str}")
            return

        # Check for BaseExceptionGroup (Python 3.11+)
        if isinstance(exc, BaseExceptionGroup):
            # Check if all exceptions in the group are expected shutdown errors
            all_expected = True
            for sub_exc in exc.exceptions:
                sub_exc_str = str(sub_exc)
                if not (
                    "cancel scope" in sub_exc_str
                    or "dictionary changed" in sub_exc_str
                    or "stdio_client" in sub_exc_str
                    or "streamable_http_client" in sub_exc_str
                    or "streamablehttp_client" in sub_exc_str
                    or "async_generator" in sub_exc_str
                    or "already running" in sub_exc_str
                ):
                    all_expected = False
                    break
            if all_expected:
                logger.debug(f"Suppressing expected exception group: {exc_str}")
                return

    # Check async generator context
    if asyncgen:
        asyncgen_str = str(asyncgen)
        if (
            "stdio_client" in asyncgen_str
            or "streamable_http_client" in asyncgen_str
            or "streamablehttp_client" in asyncgen_str
        ):
            logger.debug(f"Suppressing expected async generator shutdown error: {asyncgen_str}")
            return

    # Check message for shutdown-related errors
    if (
        "shutdown" in msg.lower()
        or "closing" in msg.lower()
        or "unhandled exception" in msg.lower()
    ):
        if exc:
            exc_str = str(exc)
            if (
                "cancel scope" in exc_str
                or "dictionary changed" in exc_str
                or "stdio_client" in exc_str
                or "streamable_http_client" in exc_str
                or "streamablehttp_client" in exc_str
                or "async_generator" in exc_str
            ):
                logger.debug(f"Suppressing expected shutdown error: {msg}")
                return

    # For other errors, use default handler
    loop.default_exception_handler(context)


def safe_async_run(coro: Awaitable[T]) -> T:
    """
    Run an async coroutine with proper error handling for MCP shutdown errors.

    This wrapper around asyncio.run() sets up a custom exception handler
    that suppresses expected shutdown errors from MCP clients.

    Args:
        coro: The coroutine to run

    Returns:
        The result of the coroutine
    """
    # Create a new event loop with our exception handler
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Set custom exception handler
        loop.set_exception_handler(_suppress_mcp_shutdown_errors)

        # Run the coroutine
        return loop.run_until_complete(coro)
    finally:
        try:
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # Wait for tasks to complete cancellation
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except (Exception, KeyboardInterrupt) as e:
            # Suppress errors during cleanup, including keyboard interrupt
            logger.debug(f"Error during cleanup (suppressed): {e}")
        finally:
            try:
                loop.close()
            except Exception:
                pass  # Ignore errors during loop close
